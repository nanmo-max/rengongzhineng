from __future__ import annotations

import json
from pathlib import Path

import pytest

from brace_msi.final_record import build_swanlab_spool


def _write_runtime(root: Path) -> None:
    rounds = [
        {
            "round": 1,
            "kind": "candidate",
            "action": "incremental_update",
            "deployed": True,
            "metric_before": 0.5,
            "metric_after": 0.6,
            "metrics_after": {"macro_f1": 0.6, "accuracy": 0.75},
            "gate_reason": "strict_public_validation_improvement",
            "cpu_seconds": 1.25,
            "wall_seconds": 1.5,
            "peak_rss_bytes": 123_456,
            "checkpoint_sha256": "must-not-leak",
            "output_dir": "must-not-leak",
        },
        {
            "round": 2,
            "kind": "candidate",
            "action": "replay_refit",
            "deployed": False,
            "metric_before": 0.6,
            "metric_after": 0.55,
            "metrics_after": {"macro_f1": 0.55, "accuracy": 0.7},
            "gate_reason": "no_strict_public_validation_improvement",
            "cpu_seconds": 2.0,
            "wall_seconds": 2.5,
            "peak_rss_bytes": 200_000,
        },
        {
            "round": 3,
            "kind": "noop",
            "action": "noop",
            "reason": "proposal_noop",
        },
    ]
    state = {
        "profile": "A",
        "initial_metric": 0.5,
        "initial_metrics": {"macro_f1": 0.5, "accuracy": 0.7},
        "rounds": rounds,
    }
    root.mkdir(parents=True)
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "audit.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rounds), encoding="utf-8"
    )


def test_build_swanlab_spool_tracks_only_deployed_metric_chain(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_runtime(runtime)
    output = tmp_path / "public-spool.jsonl"

    result = build_swanlab_spool(
        runtime,
        output,
        task_id="A",
        task_kind="classification",
        primary_metric_name="macro_f1",
        secondary_metric_name="accuracy",
        higher_is_better=True,
    )

    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert result.record_count == 3
    assert [row["primary_metric"] for row in records] == [0.6, 0.6, 0.6]
    assert [row["secondary_metric"] for row in records] == [0.75, 0.75, 0.75]
    assert [row["accepted"] for row in records] == [True, False, False]
    assert [row["candidate_count"] for row in records] == [1, 2, 2]
    assert [row["training_started"] for row in records] == [True, True, False]
    assert records[0]["validation_improvement"] == pytest.approx(0.1)
    assert records[1]["validation_improvement"] == pytest.approx(-0.05)
    assert records[2]["validation_improvement"] == 0.0
    serialized = output.read_text(encoding="utf-8")
    assert "checkpoint_sha256" not in serialized
    assert "output_dir" not in serialized
    assert "must-not-leak" not in serialized


def test_build_swanlab_spool_rejects_audit_state_mismatch(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_runtime(runtime)
    (runtime / "audit.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="audit log does not match state"):
        build_swanlab_spool(
            runtime,
            tmp_path / "public-spool.jsonl",
            task_id="A",
            task_kind="classification",
            primary_metric_name="macro_f1",
            secondary_metric_name="accuracy",
            higher_is_better=True,
        )

