from __future__ import annotations

import io
import json
from pathlib import Path
import tarfile

import pytest

from scripts.audit_competition_release import audit_competition_release, render_release_html
from scripts.verify_workspace_v2_image import (
    _materialize_round_data,
    _merge_round_record,
    _proposal,
    _resolve_profiles,
)


def _archive(path: Path, *, docker_save: bool = True) -> None:
    with tarfile.open(path, "w") as archive:
        payload = (
            b'[{"Config":"config.json","RepoTags":["test:latest"],"Layers":[]}]'
            if docker_save else b"not-docker"
        )
        info = tarfile.TarInfo("manifest.json" if docker_save else "source.zip")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))


def _evidence(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    release = tmp_path / "release.json"
    release.write_text(json.dumps({
        "source_commit": "abc123",
        "content_manifest": {"files": [
            "src/contest_harness/round.py", "src/contest_harness/protocol.py",
            "src/brace_formal/submission.py", "submission/harness.py",
        ]},
    }), encoding="utf-8")
    rounds = [
        {
            "model_call_ids": ["proposal", "deployment"],
            "candidate_submitted": True,
            "proposal_parse_error": None,
            "proposal_evidence_valid": True,
        }
        for _ in range(10)
    ]
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(json.dumps({"valid": True, "profiles": {
        "A": {"rounds": rounds, "prediction_smoke_rows": 5},
        "B": {"rounds": rounds, "prediction_smoke_rows": 5},
        "C": {"rounds": rounds, "prediction_smoke_rows": 5},
    }}), encoding="utf-8")
    blackbox = tmp_path / "blackbox.json"
    blackbox.write_text(json.dumps({
        "wrong_deploy_accepted": False,
        "history_rollback_valid": True,
        "model_reload_predictions_equal": True,
    }), encoding="utf-8")
    archive = tmp_path / "harness.tar"
    _archive(archive)
    return release, acceptance, blackbox, archive


def test_release_audit_passes_complete_evidence(tmp_path: Path) -> None:
    release, acceptance, blackbox, archive = _evidence(tmp_path)
    result = audit_competition_release(
        release, acceptance, blackbox, archive, expected_source_commit="abc123"
    )
    assert result["valid"]
    assert all(gate["status"] == "PASS" for gate in result["gates"].values())
    html = render_release_html(
        result,
        json.loads(release.read_text(encoding="utf-8")),
        [json.loads(acceptance.read_text(encoding="utf-8"))],
        json.loads(blackbox.read_text(encoding="utf-8")),
    )
    assert "LOCAL RELEASE ACCEPTANCE" in html
    assert "NOT AN OFFICIAL SCORE" in html
    assert "A" in html


def test_release_audit_fails_each_critical_boundary(tmp_path: Path) -> None:
    release, acceptance, blackbox, archive = _evidence(tmp_path)
    payload = json.loads(release.read_text())
    payload["source_commit"] = "wrong"
    payload["content_manifest"]["files"].append("tests/private_data.jsonl")
    payload["content_manifest"]["files"].remove("src/contest_harness/protocol.py")
    release.write_text(json.dumps(payload), encoding="utf-8")
    report = json.loads(acceptance.read_text())
    report["profiles"].pop("C")
    report["profiles"]["A"]["rounds"][0]["model_call_ids"] = ["one"]
    report["profiles"]["B"]["rounds"][0]["candidate_submitted"] = False
    report["profiles"]["A"]["rounds"][1]["proposal_parse_error"] = "unsupported parameter"
    report["profiles"]["A"]["rounds"][1]["proposal_evidence_valid"] = False
    acceptance.write_text(json.dumps(report), encoding="utf-8")
    blackbox.write_text(json.dumps({
        "wrong_deploy_accepted": True,
        "history_rollback_valid": False,
        "model_reload_predictions_equal": False,
    }), encoding="utf-8")
    _archive(archive, docker_save=False)

    result = audit_competition_release(
        release, acceptance, blackbox, archive, expected_source_commit="abc123"
    )
    assert not result["valid"]
    expected_failed = {
        "source_binding", "formal_forbidden_content", "official_sdk_files",
        "acceptance_reports",
        "dual_model_calls", "every_round_candidate", "training_proposals_executed",
        "wrong_deploy_rejected", "history_rollback", "model_reload", "docker_save_archive",
    }
    assert expected_failed.issubset(
        {name for name, gate in result["gates"].items() if gate["status"] == "FAIL"}
    )


def _message(instruction: str, context: dict[str, object]) -> list[dict[str, str]]:
    return [{"role": "user", "content": instruction + " Context: " + json.dumps(context)}]


def _assistant_payload(response: dict[str, object]) -> dict[str, object]:
    content = response["choices"][0]["message"]["content"]  # type: ignore[index]
    return json.loads(content)


def test_protocol_host_answers_current_experiment_and_deployment_schemas() -> None:
    experiment = _assistant_payload(_proposal(_message(
        "Required fields: recipe_id, parameters, history_policy, hypothesis and rationale.",
        {
            "available_recipes": [
                {"recipe_id": "native_current", "history_policy": "current"},
                {"recipe_id": "native_replay", "history_policy": "current_plus_history"},
            ],
            "history_summary": {"completed_rounds": 1},
        },
    )))
    assert experiment["recipe_id"] == "native_replay"
    assert experiment["history_policy"] == "current_plus_history"
    assert experiment["parameters"] == {}
    assert experiment["hypothesis"]

    deployment = _assistant_payload(_proposal(_message(
        "Required fields: artifact_id and rationale.",
        {
            "metric_contract": {"metric": "rmse", "direction": "lower"},
            "artifact_metrics": {
                "parent": {"rmse": 10.0},
                "candidate-1": {"rmse": 8.0},
            },
            "legal_artifact_ids": ["parent", "candidate-1"],
        },
    )))
    assert deployment["artifact_id"] == "candidate-1"


def test_protocol_host_can_request_worst_artifact_for_selector_blackbox() -> None:
    deployment = _assistant_payload(_proposal(_message(
        "Required fields: artifact_id and rationale.",
        {
            "metric_contract": {"name": "macro_f1", "direction": "higher"},
            "artifact_metrics": {
                "parent": {"macro_f1": 0.9},
                "candidate-1": {"macro_f1": 0.2},
            },
            "legal_artifact_ids": ["parent", "candidate-1"],
        },
    ), mode="worst"))
    assert deployment["artifact_id"] == "candidate-1"


def test_protocol_acceptance_materializes_unique_round_training_ids(tmp_path: Path) -> None:
    package = tmp_path / "package"
    public = package / "public"
    public.mkdir(parents=True)
    train = [{"id": "row-1", "inputs": {"x": 1.0}, "answer": 1}]
    validation = [{"id": "validation-1", "inputs": {"x": 2.0}, "answer": 1}]
    for name, rows in (("train.jsonl", train), ("validation.jsonl", validation)):
        (public / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    first = _materialize_round_data(package, tmp_path / "round-1", "opaque", 1)
    second = _materialize_round_data(package, tmp_path / "round-2", "opaque", 2)
    first_train = json.loads((first / "train.jsonl").read_text(encoding="utf-8"))
    second_train = json.loads((second / "train.jsonl").read_text(encoding="utf-8"))
    assert first_train["id"] != second_train["id"]
    assert json.loads((first / "validation.jsonl").read_text(encoding="utf-8"))["id"] == "validation-1"


def test_protocol_acceptance_resolves_only_registered_profile_names() -> None:
    assert _resolve_profiles("A,opaque-regression") == ("A", "opaque-regression")
    with pytest.raises(ValueError, match="unknown acceptance profile"):
        _resolve_profiles("not-a-profile")


def test_protocol_acceptance_merges_detailed_state_receipt_with_finish_record(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "round-receipt.json").write_text(json.dumps({
        "selection": {"applied_role": "candidate"},
        "parent_metrics": {"rmse": 10.0},
    }), encoding="utf-8")
    merged = _merge_round_record({
        "selected_artifact_id": "artifact-1",
        "model_call_ids": ["call-1", "call-2"],
    }, state)
    assert merged["selection"]["applied_role"] == "candidate"
    assert merged["selected_artifact_id"] == "artifact-1"
    assert merged["model_call_ids"] == ["call-1", "call-2"]
