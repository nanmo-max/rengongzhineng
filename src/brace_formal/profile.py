"""Task-contract and checkpoint-driven aggregate profiling."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

import numpy as np

from .data import DataBatch
from .metrics import resolve_metric_contract
from .model import FormalModel


def _hints(contract: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = contract.get(name, ())
    if isinstance(value, str):
        value = (value,)
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{name} must contain nonempty strings")
    result: list[str] = []
    for item in value:
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def _validate_batch(batch: DataBatch, feature_count: int, name: str) -> None:
    if batch.x.ndim != 2 or batch.x.shape[1] != feature_count:
        raise ValueError(f"{name} feature count differs from parent checkpoint")
    if batch.y.shape != (len(batch.x),) or len(batch.ids) != len(batch.x):
        raise ValueError(f"{name} batch shapes are inconsistent")


def _data_quality(training: DataBatch, validation: DataBatch) -> dict[str, int | float]:
    def summary(values: np.ndarray) -> tuple[int, float]:
        finite = np.isfinite(values)
        return int(values.size - int(finite.sum())), float(finite.mean())

    training_missing, training_fraction = summary(training.x)
    validation_missing, validation_fraction = summary(validation.x)
    return {
        "training_missing_values": training_missing,
        "validation_missing_values": validation_missing,
        "training_finite_fraction": training_fraction,
        "validation_finite_fraction": validation_fraction,
    }


@dataclass(frozen=True)
class TaskProfile:
    task: str
    primary_metric: str
    metric_direction: str
    auxiliary_metrics: tuple[str, ...]
    feature_count: int
    class_count: int
    sample_count: int
    validation_count: int
    label_summary: dict[str, Any]
    data_quality: dict[str, Any]
    group_hints: tuple[str, ...]
    time_hints: tuple[str, ...]
    contract_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "primary_metric": self.primary_metric,
            "metric_direction": self.metric_direction,
            "auxiliary_metrics": list(self.auxiliary_metrics),
            "feature_count": self.feature_count,
            "class_count": self.class_count,
            "sample_count": self.sample_count,
            "validation_count": self.validation_count,
            "label_summary": deepcopy(self.label_summary),
            "data_quality": deepcopy(self.data_quality),
            "group_hints": list(self.group_hints),
            "time_hints": list(self.time_hints),
            "contract_fingerprint": self.contract_fingerprint,
        }


def build_task_profile(
    task_contract: Mapping[str, Any],
    model: FormalModel,
    training: DataBatch,
    validation: DataBatch,
) -> TaskProfile:
    """Describe an unknown task using only its contract, parent and aggregate data."""

    if not isinstance(task_contract, Mapping):
        raise ValueError("task contract must be a mapping")
    task = str(model.meta["task"])
    metric = resolve_metric_contract(task_contract, task)
    feature_count = len(model.meta["paths"])
    _validate_batch(training, feature_count, "training")
    _validate_batch(validation, feature_count, "validation")
    group_hints = _hints(task_contract, "group_hints")
    time_hints = _hints(task_contract, "time_hints")

    if task == "classification":
        class_count = len(model.meta["classes"])
        targets = training.y.astype(np.int64, copy=False)
        if np.any(targets < 0) or np.any(targets >= class_count):
            raise ValueError("classification targets differ from parent classes")
        counts = np.bincount(targets, minlength=class_count)
        positive = counts[counts > 0]
        ratio = float(positive.min() / positive.max()) if len(positive) else 0.0
        label_summary: dict[str, Any] = {
            "classes": list(model.meta["classes"]),
            "counts": {
                str(label): int(count)
                for label, count in zip(model.meta["classes"], counts, strict=True)
            },
            "minority_to_majority_ratio": ratio,
        }
    else:
        class_count = 0
        targets = training.y.astype(np.float64, copy=False)
        if not np.all(np.isfinite(targets)):
            raise ValueError("regression targets must be finite")
        label_summary = {
            "minimum": float(np.min(targets)),
            "maximum": float(np.max(targets)),
            "mean": float(np.mean(targets)),
            "standard_deviation": float(np.std(targets)),
        }

    fingerprint_payload = {
        "metric_contract": metric.as_dict(),
        "feature_paths": list(model.meta["paths"]),
        "classes": list(model.meta["classes"]),
        "group_hints": list(group_hints),
        "time_hints": list(time_hints),
    }
    encoded = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return TaskProfile(
        task=task,
        primary_metric=metric.name,
        metric_direction=metric.direction,
        auxiliary_metrics=metric.auxiliary_metrics,
        feature_count=feature_count,
        class_count=class_count,
        sample_count=len(training.ids),
        validation_count=len(validation.ids),
        label_summary=label_summary,
        data_quality=_data_quality(training, validation),
        group_hints=group_hints,
        time_hints=time_hints,
        contract_fingerprint=hashlib.sha256(encoded).hexdigest(),
    )
