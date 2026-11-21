from __future__ import annotations

import json
from pathlib import Path

import pytest


def _config() -> dict[str, object]:
    return {
        "format": "brace-msi.competition-simulation-config.v1",
        "model_name": "Qwen/Qwen3.5-4B",
        "tasks": [
            {
                "dataset_key": "A",
                "opaque_name": "opaque-process-alpha",
                "task": "classification",
                "rounds": 10,
                "samples_per_round": 24,
                "validation_samples": 20,
                "confirmation_samples": 32,
                "seed": 701,
            },
            {
                "dataset_key": "B",
                "opaque_name": "opaque-process-beta",
                "task": "regression",
                "rounds": 10,
                "samples_per_round": 24,
                "validation_samples": 20,
                "confirmation_samples": 32,
                "seed": 907,
            },
        ],
    }


@pytest.fixture()
def simulation(tmp_path: Path) -> tuple[dict[str, object], Path]:
    from brace_msi.competition_simulator import run_simulation

    output = tmp_path / "simulation"
    result = run_simulation(_config(), output)
    return result, output


def test_simulator_runs_official_round_frames_for_classification_and_regression(
    simulation: tuple[dict[str, object], Path],
) -> None:
    result, output = simulation

    assert result["valid"] is True
    assert result["official_hidden_score"] is None
    assert result["label"] == "LOCAL OFFICIAL-PROTOCOL SIMULATION — NOT AN OFFICIAL SCORE"
    assert len(result["tasks"]) == 2
    for task in result["tasks"]:
        assert task["opaque_name"].startswith("opaque-process-")
        assert len(task["rounds"]) == 10
        assert task["model_calls"] == 20
        assert task["real_candidates"] == 10
        assert len(task["parent_chain"]) == 11
        assert task["final_prediction_count"] == 32
        assert task["final_confirmation_read_count"] == 1
        assert task["final_confirmation_metrics"]
        assert task["history_records"] == 10
        assert task["resource_contract"] == {
            "cpu_count": 4,
            "memory_bytes": 8 * 1024**3,
        }
        for index, round_record in enumerate(task["rounds"], 1):
            assert round_record["round_index"] == index
            assert len(round_record["model_call_ids"]) == 2
            assert round_record["candidate_trained"] is True
            assert round_record["candidate_artifact_id"]
            assert round_record["parent_checkpoint_sha256"].startswith("sha256:")
            assert round_record["selected_checkpoint_sha256"].startswith("sha256:")
            assert round_record["host_resource_fields"]["cpu_count"] == 4
            assert round_record["history_count_before_round"] == index - 1

    assert (output / "report.json").is_file()
    assert (output / "report.html").is_file()


def test_report_contains_official_style_evidence_without_hidden_score_claim(
    simulation: tuple[dict[str, object], Path],
) -> None:
    result, output = simulation
    persisted = json.loads((output / "report.json").read_text(encoding="utf-8"))
    html = (output / "report.html").read_text(encoding="utf-8")

    assert persisted == result
    assert "LOCAL OFFICIAL-PROTOCOL SIMULATION" in html
    assert "NOT AN OFFICIAL SCORE" in html
    assert "official hidden score" not in html.lower()
    assert "PyTRiO" in html
    assert "SwanLab" in html
    for task in persisted["tasks"]:
        for round_record in task["rounds"]:
            assert round_record["hypothesis"]
            assert round_record["executed_recipe_id"]
            assert round_record["parent_metrics"]
            assert round_record["candidate_metrics"]
            assert round_record["requested_artifact_id"]
            assert round_record["applied_artifact_id"]
            assert round_record["cpu_seconds"] >= 0.0
            assert round_record["wall_seconds"] >= 0.0
            assert round_record["peak_rss_bytes"] is None or round_record["peak_rss_bytes"] > 0
            assert round_record["token_usage"]["total_tokens"] > 0


def test_task_identity_does_not_enter_agent_prompts(
    simulation: tuple[dict[str, object], Path],
) -> None:
    result, _ = simulation

    for task in result["tasks"]:
        opaque_name = task["opaque_name"]
        for call in task["model_receipts"]:
            assert opaque_name not in call["request_json"]


def test_confirmation_metrics_are_computed_after_all_rounds(
    simulation: tuple[dict[str, object], Path],
) -> None:
    result, _ = simulation

    for task in result["tasks"]:
        confirmation_hash = task["final_confirmation_sha256"]
        assert confirmation_hash
        assert all(
            confirmation_hash not in json.dumps(round_record, sort_keys=True)
            for round_record in task["rounds"]
        )

