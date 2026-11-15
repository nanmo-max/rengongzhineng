from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "simulate_platform_report.py"
SPEC = importlib.util.spec_from_file_location("simulate_platform_report", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _receipt(index: int, *, deployed: bool) -> dict:
    before = {"accuracy": 0.50 + index / 100, "macro_f1": 0.40 + index / 100}
    candidate = {"accuracy": 0.51 + index / 100, "macro_f1": 0.41 + index / 100}
    return {
        "round_index": index,
        "candidate_trained": True,
        "deployed": deployed,
        "gate_reason": "safe_gain" if deployed else "candidate_rejected",
        "metrics_before": before,
        "metrics_candidate": candidate,
        "decision": {"executed_action": "replay_refit"},
        "cpu_seconds": 1.0,
        "wall_seconds": 2.0,
        "peak_rss_bytes": 1024,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    run_root = tmp_path / "run"
    package_root = tmp_path / "packages"
    for profile, package_name in MODULE.PACKAGES.items():
        task_root = run_root / profile
        task_root.mkdir(parents=True)
        rounds = [_receipt(index, deployed=index in {3, 8}) for index in range(1, 11)]
        (task_root / "summary.json").write_text(
            json.dumps({"rounds": rounds, "input_tokens": 0, "output_tokens": 0}),
            encoding="utf-8",
        )
        for index in range(1, 11):
            checkpoint = task_root / f"round-{index:02d}" / "checkpoint.npz"
            checkpoint.parent.mkdir()
            checkpoint.write_bytes(b"checkpoint")
        validation = package_root / package_name / "public" / "validation.jsonl"
        validation.parent.mkdir(parents=True)
        validation.write_text('{"id":"one"}\n{"id":"two"}\n', encoding="utf-8")
    return run_root, package_root


def test_public_validation_is_evaluated_once_per_frozen_task_and_never_selects_round(
    tmp_path: Path, monkeypatch
) -> None:
    run_root, package_root = _roots(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_evaluate(
        checkpoint: Path, validation: Path, profile: str
    ) -> tuple[dict[str, float], int]:
        calls.append((checkpoint.parent.name, profile))
        if profile == "A":
            return {"accuracy": 0.80, "macro_f1": 0.70}, 7
        return {"mae": 10.0, "rmse": 20.0}, 7

    monkeypatch.setattr(MODULE, "_evaluate", fake_evaluate)
    report = MODULE.build_report(run_root, package_root)

    assert report["format"] == "brace-msi.local-platform-report-simulation.v2"
    assert report["selection_use"] == "harness_gate_only_public_validation_not_used_for_selection"
    assert calls == [("round-10", "A"), ("round-10", "B"), ("round-10", "C")]
    for task in report["tasks"].values():
        assert task["final_checkpoint_round"] == 10
        assert task["last_deployed_round"] == 8
        assert task["public_validation_evaluations"] == 1
        assert task["evaluation_samples"] == 7
        assert "selected_round" not in task
        assert "selected_metrics" not in task
        assert all("public_validation_metrics" not in row for row in task["rounds"])
        assert task["rounds"][0]["gate_metrics_before"]
        assert task["rounds"][0]["gate_metrics_candidate"]
        assert task["rounds"][7]["model_selection"] == "adopt"


def test_rounds_without_deployment_keep_initial_parent_as_final_origin(
    tmp_path: Path, monkeypatch
) -> None:
    run_root, package_root = _roots(tmp_path)
    summary_path = run_root / "A" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for row in summary["rounds"]:
        row["deployed"] = False
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(
        MODULE,
        "_evaluate",
        lambda checkpoint, validation, profile: (
            ({"accuracy": 0.8, "macro_f1": 0.7}, 2)
            if profile == "A"
            else ({"mae": 10.0, "rmse": 20.0}, 2)
        ),
    )

    report = MODULE.build_report(run_root, package_root)

    assert report["tasks"]["A"]["last_deployed_round"] is None
    assert report["tasks"]["A"]["final_model_origin"] == "initial_parent"
