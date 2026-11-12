from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from brace_msi.regression_sprint import (
    candidate_grid,
    evaluate_checkpoint,
    partition_name,
    select_candidate,
)


def test_candidate_grid_is_the_bounded_nine_run_matrix() -> None:
    grid = candidate_grid(0.003, [1, 3, 5], [0.3, 1.0, 3.0])

    assert len(grid) == 9
    assert {(item.epochs, item.learning_rate_multiplier) for item in grid} == {
        (epoch, multiplier)
        for epoch in (1, 3, 5)
        for multiplier in (0.3, 1.0, 3.0)
    }
    assert grid[0].learning_rate == pytest.approx(0.0009)
    assert grid[-1].learning_rate == pytest.approx(0.009)


def test_partitions_are_group_based_and_keep_confirmation_last() -> None:
    assert partition_name("B", {"bearing": "Bearing2_1"}) == "train"
    assert partition_name("B", {"bearing": "Bearing2_2"}) == "development"
    assert partition_name("B", {"bearing": "Bearing2_3"}) == "confirmation"
    assert partition_name("C", {"source_subset": "FD001", "unit": 1}) == "train"
    assert partition_name("C", {"source_subset": "FD002", "unit": 1}) == "train"
    assert partition_name("C", {"source_subset": "FD003", "unit": 1}) == "development"
    assert partition_name("C", {"source_subset": "FD004", "unit": 1}) == "confirmation"


def test_select_candidate_uses_development_only_and_has_a_fixed_fallback() -> None:
    candidates = [
        {"id": "e1-lr1", "epochs": 1, "learning_rate_multiplier": 1.0, "development": {"rmse": 9.9}},
        {"id": "e3-lr03", "epochs": 3, "learning_rate_multiplier": 0.3, "development": {"rmse": 9.0}},
    ]

    selected = select_candidate(candidates, baseline_rmse=10.0, minimum_improvement_fraction=0.01)
    fallback = select_candidate(candidates, baseline_rmse=8.0, minimum_improvement_fraction=0.01)

    assert selected["id"] == "e3-lr03"
    assert selected["selection_reason"] == "development_gate_passed"
    assert fallback["id"] == "e1-lr1"
    assert fallback["selection_reason"] == "fixed_low_cost_fallback"


def test_checkpoint_evaluation_reports_regression_metrics_and_groups(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.npz"
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "task": "regression",
        "paths": ['[["key","value"]]'],
        "classes": [],
        "hidden": 1,
        "target_mean": 0.0,
        "target_scale": 1.0,
    }
    np.savez(
        checkpoint,
        metadata=np.array(json.dumps(metadata)),
        mean=np.array([0.0]),
        scale=np.array([1.0]),
        w1=np.array([[1.0]]),
        b1=np.array([0.0]),
        w2=np.array([[1.0]]),
        b2=np.array([0.0]),
    )
    dataset = tmp_path / "data.jsonl"
    rows = [
        {"id": "a", "inputs": {"value": 0.0}, "answer": 0.0, "meta": {"bearing": "g1"}},
        {"id": "b", "inputs": {"value": 1.0}, "answer": 1.0, "meta": {"bearing": "g2"}},
    ]
    dataset.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    result = evaluate_checkpoint(checkpoint, dataset, "B")

    expected = np.tanh(1.0)
    assert result["rows"] == 2
    assert result["rmse"] == np.sqrt(((expected - 1.0) ** 2) / 2)
    assert result["groups"]["g1"]["rmse"] == 0.0
    assert result["groups"]["g2"]["mae"] == 1.0 - expected
