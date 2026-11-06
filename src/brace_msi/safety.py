"""Three-layer candidate evaluation for local proxy experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeVar

import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import accuracy_score, mean_squared_error

TaskKind = Literal["classification", "regression"]
T = TypeVar("T")


@dataclass(frozen=True)
class GateConfig:
    min_validation_samples: int = 16
    min_primary_improvement: float = 0.0
    max_anchor_degradation: float = 0.02


@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    layer: str
    reason: str
    validation_improvement: float
    anchor_degradation: float


def _score(task_kind: TaskKind, targets: ArrayLike, predictions: ArrayLike) -> float:
    if task_kind == "classification":
        return float(accuracy_score(targets, predictions))
    if task_kind == "regression":
        return float(mean_squared_error(targets, predictions) ** 0.5)
    raise ValueError(f"unsupported task kind: {task_kind}")


def evaluate_candidate(
    *,
    task_kind: TaskKind,
    stable_validation: ArrayLike,
    candidate_validation: ArrayLike,
    validation_targets: ArrayLike,
    stable_anchor: ArrayLike,
    candidate_anchor: ArrayLike,
    anchor_targets: ArrayLike,
    hard_constraints_passed: bool,
    config: GateConfig,
) -> GateDecision:
    validation_targets_array = np.asarray(validation_targets)
    if not hard_constraints_passed:
        return GateDecision(False, "hard_constraint", "hard constraint failed", 0.0, 0.0)
    if len(validation_targets_array) < config.min_validation_samples:
        return GateDecision(
            False, "statistical", "insufficient validation samples", 0.0, 0.0
        )

    stable_validation_score = _score(
        task_kind, validation_targets_array, stable_validation
    )
    candidate_validation_score = _score(
        task_kind, validation_targets_array, candidate_validation
    )
    stable_anchor_score = _score(task_kind, anchor_targets, stable_anchor)
    candidate_anchor_score = _score(task_kind, anchor_targets, candidate_anchor)
    if task_kind == "classification":
        validation_improvement = candidate_validation_score - stable_validation_score
        anchor_degradation = stable_anchor_score - candidate_anchor_score
    else:
        validation_improvement = stable_validation_score - candidate_validation_score
        anchor_degradation = candidate_anchor_score - stable_anchor_score

    values = np.asarray([validation_improvement, anchor_degradation], dtype=float)
    if not np.all(np.isfinite(values)):
        return GateDecision(False, "hard_constraint", "non-finite metric", 0.0, 0.0)
    if anchor_degradation > config.max_anchor_degradation:
        return GateDecision(
            False,
            "statistical",
            "anchor degradation exceeds limit",
            float(validation_improvement),
            float(anchor_degradation),
        )
    if validation_improvement < config.min_primary_improvement:
        return GateDecision(
            False,
            "deployment",
            "validation gain is below threshold",
            float(validation_improvement),
            float(anchor_degradation),
        )
    return GateDecision(
        True,
        "deployment",
        "candidate passed all layers",
        float(validation_improvement),
        float(anchor_degradation),
    )


def select_deployment(stable: T, candidate: T, decision: GateDecision) -> T:
    return candidate if decision.accepted else stable
