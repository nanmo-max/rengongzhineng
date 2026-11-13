from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from brace_msi.controlled_harness import (
    ControlledDualLoopHarness,
    ControlledHarnessConfig,
)
from brace_msi.data.types import BatchData, TaskStream
from brace_msi.cli import main


def _classification_stream(task_id: str = "unknown-industrial-task") -> TaskStream:
    rng = np.random.default_rng(20261113)

    def batch(batch_id: str, offset: float, count: int = 60) -> BatchData:
        y = np.asarray([index % 2 for index in range(count)], dtype=np.int64)
        signal = (y * 2.0 - 1.0) + offset + rng.normal(0.0, 0.25, count)
        X = np.column_stack([signal, signal**2, np.sin(signal)])
        return BatchData(
            batch_id=batch_id,
            X=X,
            y=y,
            sample_ids=tuple(f"{batch_id}-{index}" for index in range(count)),
        )

    return TaskStream(
        task_id=task_id,
        task_kind="classification",
        initial=batch("initial", 0.0, 100),
        development=tuple(batch(f"batch-{index}", index * 0.3) for index in range(1, 11)),
        sealed=(),
    )


def _regression_stream(task_id: str = "unknown-regression-task") -> TaskStream:
    rng = np.random.default_rng(7)

    def batch(batch_id: str, offset: float, count: int = 50) -> BatchData:
        X = rng.normal(offset, 1.0, (count, 3))
        y = 2.0 * X[:, 0] - X[:, 1] + 0.5 * X[:, 2] + rng.normal(0.0, 0.1, count)
        return BatchData(
            batch_id=batch_id,
            X=X,
            y=y,
            sample_ids=tuple(f"{batch_id}-{index}" for index in range(count)),
        )

    return TaskStream(
        task_id=task_id,
        task_kind="regression",
        initial=batch("initial", 0.0, 100),
        development=tuple(batch(f"batch-{index}", index * 0.4) for index in range(1, 11)),
        sealed=(),
    )


def _config() -> ControlledHarnessConfig:
    return ControlledHarnessConfig(
        seed=20261113,
        max_rounds=10,
        max_total_candidates=8,
        total_cpu_budget_seconds=60.0,
        performance_drop_threshold=0.0,
        drift_threshold=0.1,
        min_gate_gain=-1.0,
        max_anchor_degradation=1.0,
        min_gate_samples=4,
    )


def test_ten_round_controlled_loop_integrates_data_decision_gate_shadow_and_audit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    summary = ControlledDualLoopHarness(root, _config()).run(_classification_stream())

    assert summary.complete
    assert len(summary.rounds) == 10
    assert [round_result.round_index for round_result in summary.rounds] == list(range(1, 11))
    assert 3 <= summary.real_experiment_count <= 8
    assert summary.total_candidates <= 8
    assert all(round_result.decision_count == 1 for round_result in summary.rounds)
    assert any(round_result.shadow_confidence == "paired" for round_result in summary.rounds[1:])
    assert (root / "controller" / "commits" / "round-010.json").is_file()
    assert (root / "audit.jsonl").is_file()
    assert all((root / "round-data" / f"round-{index:03d}" / "training").is_dir() for index in range(1, 11))


def test_task_rename_does_not_change_actions_or_metrics(tmp_path: Path) -> None:
    original = _classification_stream("original-name")
    renamed = replace(original, task_id="renamed-hidden-task")

    first = ControlledDualLoopHarness(tmp_path / "first", _config()).run(original)
    second = ControlledDualLoopHarness(tmp_path / "second", _config()).run(renamed)

    assert [item.actions for item in first.rounds] == [item.actions for item in second.rounds]
    assert [item.decision for item in first.rounds] == [item.decision for item in second.rounds]
    assert [item.primary_metric for item in first.rounds] == [item.primary_metric for item in second.rounds]


def test_regression_and_interrupted_resume_complete_without_duplicate_rounds(tmp_path: Path) -> None:
    root = tmp_path / "resume"
    harness = ControlledDualLoopHarness(root, _config())
    paused = harness.run(_regression_stream(), max_rounds_this_call=4)
    assert not paused.complete
    assert len(paused.rounds) == 4

    resumed = ControlledDualLoopHarness(root, _config()).run(_regression_stream())
    assert resumed.complete
    assert len(resumed.rounds) == 10
    assert [item.round_index for item in resumed.rounds] == list(range(1, 11))
    assert len({item.batch_id for item in resumed.rounds}) == 10


def test_controlled_loop_has_a_resumable_cli_entry(tmp_path: Path) -> None:
    output = tmp_path / "cli"
    assert main(
        [
            "controlled-loop-smoke",
            "--output",
            str(output),
            "--max-rounds-this-call",
            "1",
        ]
    ) == 0
    summary = (output / "summary.json").read_text(encoding="utf-8")
    assert '"formal_eligible": false' in summary
    assert '"round_count"' not in summary
