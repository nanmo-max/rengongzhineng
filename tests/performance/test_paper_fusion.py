from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from brace_msi.paper_fusion import (
    TeacherSpec,
    aligned_predict_proba,
    build_causal_features,
    fit_weighted_ensemble,
    grouped_folds,
    load_official_rows,
    successive_halving,
)


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_loader_and_features_use_only_causal_metadata(tmp_path: Path) -> None:
    path = tmp_path / "bearing.jsonl"
    _write(
        path,
        [
            {
                "id": "b-1",
                "inputs": {"features": [1.0, 2.0]},
                "answer": 9,
                "meta": {
                    "bearing": "Bearing1_1",
                    "snapshot": 3,
                    "source": "train",
                    "total_life": 12,
                },
            }
        ],
    )

    rows = load_official_rows(path, "B")
    features, names = build_causal_features(rows, "B")

    assert rows[0].group == "Bearing1_1"
    assert features.tolist() == [[1.0, 2.0, 3.0]]
    assert names == ("input:features[0]", "input:features[1]", "meta:snapshot")
    assert all("total_life" not in name for name in names)


def test_engine_features_use_past_rows_but_not_future_rows(tmp_path: Path) -> None:
    path = tmp_path / "engine.jsonl"
    _write(
        path,
        [
            {
                "id": "u1-c2",
                "inputs": {"settings": [2.0], "sensors": [6.0]},
                "answer": 8,
                "meta": {"source_subset": "FD001", "unit": 1, "cycle": 2},
            },
            {
                "id": "u1-c1",
                "inputs": {"settings": [1.0], "sensors": [4.0]},
                "answer": 9,
                "meta": {"source_subset": "FD001", "unit": 1, "cycle": 1},
            },
        ],
    )

    rows = load_official_rows(path, "C")
    features, names = build_causal_features(rows, "C")

    delta_offset = names.index("history:delta:input:sensors[0]")
    mean_offset = names.index("history:mean:input:sensors[0]")
    by_id = {row.sample_id: features[index] for index, row in enumerate(rows)}
    assert by_id["u1-c1"][delta_offset] == 0.0
    assert by_id["u1-c1"][mean_offset] == 4.0
    assert by_id["u1-c2"][delta_offset] == 2.0
    assert by_id["u1-c2"][mean_offset] == 5.0


def test_grouped_folds_never_cross_device_identity(tmp_path: Path) -> None:
    path = tmp_path / "bearing.jsonl"
    rows = []
    for bearing in ("Bearing1_1", "Bearing1_2", "Bearing1_3"):
        for snapshot in (1, 2):
            rows.append(
                {
                    "id": f"{bearing}-{snapshot}",
                    "inputs": {"features": [float(snapshot)]},
                    "answer": snapshot,
                    "meta": {"bearing": bearing, "snapshot": snapshot, "source": "x"},
                }
            )
    _write(path, rows)
    loaded = load_official_rows(path, "B")

    folds = grouped_folds(loaded, "B", seed=7, n_splits=3)

    assert len(folds) == 3
    for train, holdout in folds:
        train_groups = {loaded[index].group for index in train}
        holdout_groups = {loaded[index].group for index in holdout}
        assert train_groups.isdisjoint(holdout_groups)


class _ProbabilityEstimator:
    classes_ = np.asarray(["b", "a"])

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.asarray([[0.8, 0.2] for _ in range(len(X))])


def test_probability_alignment_follows_global_class_order() -> None:
    result = aligned_predict_proba(
        _ProbabilityEstimator(), np.zeros((2, 1)), np.asarray(["a", "b", "c"])
    )

    assert result.tolist() == [[0.2, 0.8, 0.0], [0.2, 0.8, 0.0]]


def test_ensemble_weights_are_normalized_from_oof_quality() -> None:
    predictions = {
        "good": np.asarray([0.0, 1.0, 2.0]),
        "bad": np.asarray([3.0, 3.0, 3.0]),
    }

    weights = fit_weighted_ensemble(
        predictions, np.asarray([0.0, 1.0, 2.0]), task_kind="regression"
    )

    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["good"] > weights["bad"]


def test_successive_halving_keeps_only_requested_finalists() -> None:
    X = np.asarray([[float(index)] for index in range(18)])
    y = np.asarray([index % 2 for index in range(18)])
    rows = [
        type("Row", (), {"group": f"g{index // 2}", "target": y[index]})()
        for index in range(18)
    ]
    folds = grouped_folds(rows, "A", seed=4, n_splits=3)
    specs = [
        TeacherSpec("linear", {"C": 0.1}),
        TeacherSpec("linear", {"C": 1.0}),
        TeacherSpec("extra_trees", {"n_estimators": 20, "min_samples_leaf": 1}),
    ]

    result = successive_halving(
        X,
        y,
        folds,
        specs,
        task_kind="classification",
        finalist_count=2,
        seed=3,
    )

    assert len(result.finalists) == 2
    assert len(result.all_results) == 3
    assert all(np.isfinite(item.primary_metric) for item in result.all_results)


def test_loader_fails_closed_on_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.jsonl"
    row = {
        "id": "same",
        "inputs": {"features": [1.0]},
        "answer": "x",
        "meta": {"source_batch": 1, "source_index": 1},
    }
    _write(path, [row, row])

    with pytest.raises(ValueError, match="duplicate"):
        load_official_rows(path, "A")
