from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from brace_formal.data import DataBatch
from brace_formal.model import FormalModel
from brace_formal.profile import TaskProfile, build_task_profile
from tests.competition_core.support import write_parent


def _model(tmp_path: Path, task: str) -> FormalModel:
    path = tmp_path / f"{task}.npz"
    write_parent(path, task=task)
    return FormalModel.load(path)


def _batch(x, y, *, prefix: str = "sample") -> DataBatch:
    values = np.asarray(x, dtype=np.float64)
    targets = np.asarray(y)
    return DataBatch(
        ids=tuple(f"{prefix}-{index}" for index in range(len(values))),
        x=values,
        y=targets,
        sha256=(prefix[0] * 64),
    )


def test_classification_profile_ignores_opaque_dataset_identity_and_reports_imbalance(tmp_path: Path) -> None:
    """Catches dataset-name routing and loss of observable class-distribution evidence."""

    model = _model(tmp_path, "classification")
    training = _batch([[0, 0], [1, 0], [2, 1], [3, 1]], [0, 0, 0, 1], prefix="t")
    validation = _batch([[4, 0], [5, 1]], [0, 1], prefix="v")
    common = {
        "task": "classification",
        "metric": "macro_f1",
        "metric_direction": "higher",
        "group_hints": ["machine_id"],
        "time_hints": ["timestamp"],
    }

    first = build_task_profile({**common, "dataset_key": "Gas"}, model, training, validation)
    renamed = build_task_profile({**common, "dataset_key": "never-seen-task"}, model, training, validation)

    assert isinstance(first, TaskProfile)
    assert first == renamed
    assert first.task == "classification"
    assert first.primary_metric == "macro_f1"
    assert first.metric_direction == "higher"
    assert first.feature_count == 2
    assert first.class_count == 2
    assert first.sample_count == 4
    assert first.validation_count == 2
    assert first.label_summary == {
        "classes": ["cold", "hot"],
        "counts": {"cold": 3, "hot": 1},
        "minority_to_majority_ratio": pytest.approx(1 / 3),
    }
    assert first.group_hints == ("machine_id",)
    assert first.time_hints == ("timestamp",)
    assert len(first.contract_fingerprint) == 64
    with pytest.raises(FrozenInstanceError):
        first.task = "regression"  # type: ignore[misc]


def test_regression_profile_reports_target_range_and_missing_quality(tmp_path: Path) -> None:
    """Catches classification-only profiling and silent non-finite feature evidence."""

    model = _model(tmp_path, "regression")
    training = _batch([[0, 0], [1, np.nan], [2, 1]], [2.0, 4.0, 9.0], prefix="t")
    validation = _batch([[3, 0], [np.inf, 1]], [10.0, 12.0], prefix="v")

    profile = build_task_profile(
        {
            "task": "regression",
            "metric": "rmse_nasa",
            "metric_direction": "lower",
            "group_hints": "unit_id",
            "time_hints": ["cycle", "timestamp"],
        },
        model,
        training,
        validation,
    )

    assert profile.task == "regression"
    assert profile.primary_metric == "rmse"
    assert profile.metric_direction == "lower"
    assert profile.class_count == 0
    assert profile.label_summary == {
        "minimum": 2.0,
        "maximum": 9.0,
        "mean": 5.0,
        "standard_deviation": pytest.approx(2.943920288775949),
    }
    assert profile.data_quality == {
        "training_missing_values": 1,
        "validation_missing_values": 1,
        "training_finite_fraction": pytest.approx(5 / 6),
        "validation_finite_fraction": pytest.approx(3 / 4),
    }
    assert profile.group_hints == ("unit_id",)
    assert profile.time_hints == ("cycle", "timestamp")
    payload = profile.as_dict()
    assert payload["label_summary"] == profile.label_summary
    assert payload["data_quality"] == profile.data_quality


def test_profile_rejects_contract_checkpoint_task_conflict(tmp_path: Path) -> None:
    model = _model(tmp_path, "classification")
    batch = _batch([[0, 0], [1, 1]], [0, 1])

    with pytest.raises(ValueError, match="task contract differs"):
        build_task_profile({"task": "regression", "metric": "rmse"}, model, batch, batch)


@pytest.mark.parametrize(
    "training,validation",
    [
        (_batch([[0, 0, 0]], [0], prefix="t"), _batch([[0, 0]], [0], prefix="v")),
        (_batch([[0, 0]], [0], prefix="t"), _batch([[0, 0, 0]], [0], prefix="v")),
    ],
)
def test_profile_rejects_feature_count_mismatch(tmp_path: Path, training: DataBatch, validation: DataBatch) -> None:
    model = _model(tmp_path, "classification")

    with pytest.raises(ValueError, match="feature count differs"):
        build_task_profile({"task": "classification"}, model, training, validation)


def test_profile_rejects_invalid_group_or_time_hints(tmp_path: Path) -> None:
    model = _model(tmp_path, "regression")
    batch = _batch([[0, 0]], [1.0])

    with pytest.raises(ValueError, match="group_hints"):
        build_task_profile({"task": "regression", "group_hints": [""]}, model, batch, batch)
    with pytest.raises(ValueError, match="time_hints"):
        build_task_profile({"task": "regression", "time_hints": [1]}, model, batch, batch)
