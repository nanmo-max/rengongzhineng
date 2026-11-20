"""Official task metrics used only for bounded candidate safety checks."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import numpy as np

from .model import FormalModel


@dataclass(frozen=True)
class MetricContract:
    """Canonical primary metric semantics supplied by the task contract."""

    task: str
    name: str
    direction: str
    auxiliary_metrics: tuple[str, ...] = ()

    @property
    def metric_directions(self) -> dict[str, str]:
        return {name: _ALL_DIRECTIONS[name] for name in (self.name, *self.auxiliary_metrics)}

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "metric": self.name,
            "direction": self.direction,
            "metric_directions": self.metric_directions,
        }


_METRICS: dict[str, dict[str, str]] = {
    "classification": {"accuracy": "higher", "macro_f1": "higher"},
    "regression": {"mae": "lower", "rmse": "lower"},
}
_ALL_DIRECTIONS = {
    "accuracy": "higher",
    "macro_f1": "higher",
    "mae": "lower",
    "rmse": "lower",
    "nasa_score": "lower",
    "nasa_score_mean": "lower",
}
_DEFAULTS = {"classification": "macro_f1", "regression": "rmse"}


def resolve_metric_contract(task_contract: Mapping[str, Any] | None, model_task: str) -> MetricContract:
    """Resolve one fail-closed metric contract without silently changing direction."""

    if model_task not in _METRICS:
        raise ValueError("unsupported model task")
    contract = task_contract if isinstance(task_contract, Mapping) else {}
    declared_task = contract.get("task")
    if declared_task is not None and declared_task != model_task:
        raise ValueError("task contract differs from parent model task")
    metric = contract.get("metric")
    if metric is None:
        metric = _DEFAULTS[model_task]
    explicit_nasa = metric == "rmse_nasa"
    if explicit_nasa:
        metric = "rmse"
    if not isinstance(metric, str) or metric not in _METRICS[model_task]:
        raise ValueError("unsupported primary metric for task")
    expected_direction = _METRICS[model_task][metric]
    direction = contract.get("metric_direction")
    if direction is None:
        direction = expected_direction
    if direction != expected_direction:
        raise ValueError("metric direction is incompatible with the primary metric")
    auxiliary = [name for name in _METRICS[model_task] if name != metric]
    declared_auxiliary = contract.get("auxiliary_metrics", ())
    if declared_auxiliary is not None:
        if not isinstance(declared_auxiliary, (list, tuple)) or any(not isinstance(name, str) for name in declared_auxiliary):
            raise ValueError("auxiliary metrics must be a list of metric names")
        auxiliary.extend(declared_auxiliary)
    if explicit_nasa:
        auxiliary.extend(["nasa_score", "nasa_score_mean"])
    unique_auxiliary: list[str] = []
    for name in auxiliary:
        if name == metric:
            continue
        if name not in _ALL_DIRECTIONS:
            raise ValueError("unsupported auxiliary metric")
        if name not in unique_auxiliary:
            unique_auxiliary.append(name)
    return MetricContract(model_task, metric, expected_direction, tuple(unique_auxiliary))


def primary_evidence(
    contract: MetricContract,
    parent_metrics: Mapping[str, float],
    candidate_metrics: Mapping[str, float],
    *,
    parent_validation_sha256: str,
    candidate_validation_sha256: str,
) -> dict[str, Any]:
    """Return machine-computed, same-scope parent/candidate evidence."""

    if not isinstance(parent_validation_sha256, str) or not parent_validation_sha256:
        raise ValueError("validation scope fingerprint is required")
    if parent_validation_sha256 != candidate_validation_sha256:
        raise ValueError("parent and candidate validation scopes differ")
    try:
        parent_value = float(parent_metrics[contract.name])
        candidate_value = float(candidate_metrics[contract.name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("primary metric is missing from measured evidence") from exc
    if not math.isfinite(parent_value) or not math.isfinite(candidate_value):
        raise ValueError("primary metric evidence must be finite")
    signed_gain = candidate_value - parent_value if contract.direction == "higher" else parent_value - candidate_value
    tolerance = 1e-12 * max(1.0, abs(parent_value), abs(candidate_value))
    relation = "improved" if signed_gain > tolerance else "regressed" if signed_gain < -tolerance else "unchanged"
    return {
        "metric": contract.name,
        "direction": contract.direction,
        "parent_value": parent_value,
        "candidate_value": candidate_value,
        "signed_gain": signed_gain,
        "relation": relation,
        "validation_sha256": parent_validation_sha256,
    }


def metric_evidence_bundle(
    contract: MetricContract,
    parent_metrics: Mapping[str, float],
    candidate_metrics: Mapping[str, float],
    *,
    parent_validation_sha256: str,
    candidate_validation_sha256: str,
) -> dict[str, Any]:
    """Compute directional evidence for every declared metric on one shared scope."""

    if parent_validation_sha256 != candidate_validation_sha256:
        raise ValueError("parent and candidate validation scopes differ")
    evidence: dict[str, Any] = {}
    for name, direction in contract.metric_directions.items():
        parent_value = parent_metrics.get(name)
        candidate_value = candidate_metrics.get(name)
        if parent_value is None or candidate_value is None:
            evidence[name] = {"direction": direction, "relation": "unavailable", "signed_gain": None}
            continue
        parent_number = float(parent_value)
        candidate_number = float(candidate_value)
        if not math.isfinite(parent_number) or not math.isfinite(candidate_number):
            evidence[name] = {"direction": direction, "relation": "unavailable", "signed_gain": None}
            continue
        signed_gain = candidate_number - parent_number if direction == "higher" else parent_number - candidate_number
        tolerance = 1e-12 * max(1.0, abs(parent_number), abs(candidate_number))
        relation = "improved" if signed_gain > tolerance else "regressed" if signed_gain < -tolerance else "unchanged"
        evidence[name] = {
            "direction": direction,
            "parent_value": parent_number,
            "candidate_value": candidate_number,
            "signed_gain": signed_gain,
            "relation": relation,
        }
    return {"validation_sha256": parent_validation_sha256, "metrics": evidence}


def evaluate(
    model: FormalModel,
    values: np.ndarray,
    targets: np.ndarray,
    metric_contract: MetricContract | None = None,
) -> dict[str, float]:
    raw = model.predict_raw(values)
    if model.meta["task"] == "classification":
        labels = raw.argmax(axis=1)
        observed = sorted(set(targets.tolist()) | set(labels.tolist()))
        scores: list[float] = []
        for label in observed:
            denominator = int(np.sum(labels == label) + np.sum(targets == label))
            numerator = 2 * int(np.sum((labels == label) & (targets == label)))
            scores.append(numerator / denominator if denominator else 0.0)
        return {"accuracy": float(np.mean(labels == targets)), "macro_f1": float(np.mean(scores))}
    error = raw - targets
    result = {"mae": float(np.mean(np.abs(error))), "rmse": float(np.sqrt(np.mean(error**2)))}
    if metric_contract is not None and "nasa_score" in metric_contract.metric_directions:
        clipped = np.clip(error, -700.0, 700.0)
        penalties = np.where(
            clipped < 0.0,
            np.exp(-clipped / 13.0) - 1.0,
            np.exp(clipped / 10.0) - 1.0,
        )
        score = float(np.sum(penalties))
        result["nasa_score"] = score
        result["nasa_score_mean"] = score / max(1, len(targets))
    return result
