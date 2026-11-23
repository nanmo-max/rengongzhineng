from __future__ import annotations

import json
from pathlib import Path

import pytest

from brace_msi.formal_observation import build_formal_observation


def _write_fixture(root: Path, *, rounds: int = 2) -> Path:
    profiles: dict[str, object] = {}
    for task_id, metrics in {
        "A": ({"macro_f1": 0.7, "accuracy": 0.8}, {"macro_f1": 0.72, "accuracy": 0.82}),
        "B": ({"rmse": 10.0, "mae": 8.0}, {"rmse": 9.0, "mae": 7.0}),
        "C": ({"rmse": 12.0, "mae": 9.0}, {"rmse": 11.0, "mae": 8.0}),
    }.items():
        rows = []
        for index in range(1, rounds + 1):
            rows.append(
                {
                    "round_index": index,
                    "parent_metrics": metrics[0],
                    "candidate_metrics": metrics[1],
                    "applied_role": "candidate" if index == 1 else "parent",
                    "executed_recipe_id": "native_current",
                    "selection_reason": "fixture selection",
                    "model_call_ids": [f"call-{task_id}-{index}-1"],
                }
            )
            state = root / task_id / f"round-{index:02d}-state"
            state.mkdir(parents=True)
            ledger = {
                "rounds": [
                    {
                        "round_index": index,
                        "artifact_evaluations": [
                            {
                                "role": "candidate",
                                "resource_evidence": {
                                    "cpu_seconds": 0.5,
                                    "wall_seconds": 0.75,
                                    "peak_rss_bytes": 1024,
                                },
                            }
                        ],
                        "candidate_execution": {"training_samples": 20},
                    }
                ]
            }
            (state / "round-ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
        profiles[task_id] = {"round_count": rounds, "rounds": rows}
    acceptance = root / "acceptance.json"
    acceptance.write_text(
        json.dumps(
            {
                "format": "brace-msi.workspace-v2-acceptance.v1",
                "image": "brace-msi:test",
                "profiles": profiles,
                "valid": True,
            }
        ),
        encoding="utf-8",
    )
    return acceptance


def test_build_formal_observation_binds_rounds_to_source_and_resources(tmp_path: Path) -> None:
    acceptance = _write_fixture(tmp_path / "source")
    result = build_formal_observation(acceptance, tmp_path / "out", expected_rounds=2)

    assert result.record_count == 6
    assert result.task_counts == {"A": 2, "B": 2, "C": 2}
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["image"] == "brace-msi:test"
    assert manifest["source_acceptance_sha256"] == result.source_sha256
    records = [json.loads(line) for line in result.spool_path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["primary_metric"] == pytest.approx(0.72)
    assert records[1]["primary_metric"] == pytest.approx(0.7)
    assert records[0]["cpu_seconds"] == pytest.approx(0.5)
    assert records[0]["record_id"] == "formal-observation:A:1"
    assert "model_call_ids" not in records[0]


def test_build_formal_observation_fails_closed_on_incomplete_rounds(tmp_path: Path) -> None:
    acceptance = _write_fixture(tmp_path / "source", rounds=1)
    with pytest.raises(ValueError, match="round count"):
        build_formal_observation(acceptance, tmp_path / "out", expected_rounds=2)
