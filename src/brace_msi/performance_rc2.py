"""Research-only RC2 candidates for train-internal performance experiments.

This module is deliberately outside the formal upload runtime.  It preserves
the official checkpoint schema while testing task-contract-driven recipes.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Sequence

import numpy as np

from brace_formal.data import DataBatch
from brace_formal.metrics import MetricContract
from brace_formal.model import FormalModel
from brace_formal.recipes import CandidateResult


@dataclass(frozen=True)
class RC2Recipe:
    recipe_id: str
    task: str
    history_policy: str
    epochs: int
    learning_rate_multiplier: float = 1.0
    loss: str = "native"
    loss_parameters: tuple[tuple[str, float], ...] = ()
    class_weighting: bool = False
    adaptive_blend: float | None = None


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    model: object
    fold_gains: tuple[float, ...]
    cpu_seconds: float
    wall_seconds: float
    peak_rss_bytes: float
    metrics: dict[str, float]


_RECIPES = (
    RC2Recipe("native_current_e3", "classification", "current", 3, loss="cross_entropy"),
    RC2Recipe("balanced_current_e3", "classification", "current", 3, loss="cross_entropy", class_weighting=True),
    RC2Recipe("adaptive_balanced_e3", "classification", "current", 3, loss="cross_entropy", class_weighting=True, adaptive_blend=0.5),
    RC2Recipe("adaptive_recent_e3", "classification", "recent", 3, loss="cross_entropy", class_weighting=True, adaptive_blend=0.5),
    RC2Recipe("mse_current_e3_lr3", "regression", "current", 3, 3.0, loss="mse"),
    RC2Recipe("huber_recent_e3", "regression", "recent", 3, loss="huber", loss_parameters=(("delta", 1.0),)),
    RC2Recipe(
        "asymmetric_recent_e3",
        "regression",
        "recent",
        3,
        loss="asymmetric",
        loss_parameters=(("overprediction_weight", 1.0), ("underprediction_weight", 1.5)),
    ),
    RC2Recipe("adaptive_recent_mse_e3_lr3", "regression", "recent", 3, 3.0, loss="mse", adaptive_blend=0.5),
)


def recipes_for_task(task: str) -> tuple[RC2Recipe, ...]:
    if task not in {"classification", "regression"}:
        raise ValueError("unsupported task contract")
    return tuple(recipe for recipe in _RECIPES if recipe.task == task)


def reparameterize_normalizer(model: FormalModel, values: np.ndarray, *, blend: float) -> dict[str, Any]:
    """Change input normalization without changing the represented function.

    Only coordinates that remain outside the model's clipping boundary for all
    supplied calibration rows are changed. Adam state for the transformed first
    layer is reset because it belongs to the old coordinate system.
    """

    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != len(model.mean) or not len(matrix):
        raise ValueError("normalizer calibration values are invalid")
    if not np.all(np.isfinite(matrix)) or not 0.0 < blend <= 1.0:
        raise ValueError("normalizer blend or values are invalid")
    old_mean = model.mean.copy()
    old_scale = model.scale.copy()
    observed_mean = np.mean(matrix, axis=0)
    observed_scale = np.std(matrix, axis=0)
    observed_scale = np.maximum(observed_scale, 1e-8)
    proposed_mean = (1.0 - blend) * old_mean + blend * observed_mean
    proposed_scale = np.exp((1.0 - blend) * np.log(old_scale) + blend * np.log(observed_scale))
    old_normalized = (matrix - old_mean) / old_scale
    new_normalized = (matrix - proposed_mean) / proposed_scale
    eligible = (np.max(np.abs(old_normalized), axis=0) < 9.999) & (np.max(np.abs(new_normalized), axis=0) < 9.999)
    before = model.predict_raw(matrix)
    original_w1 = model.params["w1"].copy()
    for feature in np.flatnonzero(eligible):
        ratio = proposed_scale[feature] / old_scale[feature]
        model.params["w1"][feature] = original_w1[feature] * ratio
    shift = np.zeros_like(old_mean)
    shift[eligible] = (proposed_mean[eligible] - old_mean[eligible]) / old_scale[eligible]
    model.params["b1"] = model.params["b1"] + shift @ original_w1
    model.mean[eligible] = proposed_mean[eligible]
    model.scale[eligible] = proposed_scale[eligible]
    for name in ("w1", "b1"):
        model.first[name].fill(0.0)
        model.second[name].fill(0.0)
    after = model.predict_raw(matrix)
    delta = float(np.max(np.abs(after - before)))
    tolerance = 1e-10
    if delta > tolerance:
        raise ValueError("normalizer reparameterization changed predictions")
    model.validate()
    return {
        "blend": float(blend),
        "updated_features": int(np.sum(eligible)),
        "max_prediction_delta": delta,
    }


def recent_weighted_training(
    history: Sequence[DataBatch],
    current: DataBatch,
    *,
    limit: int = 2,
    decay: float = 0.5,
) -> tuple[DataBatch, np.ndarray]:
    if limit < 0 or not 0.0 < decay <= 1.0:
        raise ValueError("recent-history policy is invalid")
    selected = list(history[-limit:]) if limit else []
    batches = [*selected, current]
    combined = DataBatch.concat(batches) if len(batches) > 1 else current
    count = len(selected)
    weights = np.concatenate(
        [
            np.full(len(batch.ids), decay ** (count - index), dtype=np.float64)
            for index, batch in enumerate(selected)
        ]
        + [np.ones(len(current.ids), dtype=np.float64)]
    )
    return combined, weights


def _balanced_weights(targets: np.ndarray, class_count: int) -> np.ndarray:
    labels = targets.astype(np.int64)
    counts = np.bincount(labels, minlength=class_count)
    if np.any(counts == 0):
        # A partial industrial round need not contain every known class.
        present = counts > 0
        inverse = np.ones(class_count, dtype=np.float64)
        inverse[present] = len(labels) / (int(np.sum(present)) * counts[present])
    else:
        inverse = len(labels) / (class_count * counts.astype(np.float64))
    return inverse[labels]


def fit_research_candidate(
    parent: FormalModel,
    recipe: RC2Recipe,
    current: DataBatch,
    history: Sequence[DataBatch],
) -> CandidateResult:
    task = str(parent.meta["task"])
    if task != recipe.task:
        raise ValueError("recipe and parent task differ")
    if recipe.history_policy == "recent":
        training, weights = recent_weighted_training(history, current)
    elif recipe.history_policy == "current":
        training = current
        weights = np.ones(len(current.ids), dtype=np.float64)
    else:
        raise ValueError("unknown history policy")
    if recipe.class_weighting:
        weights *= _balanced_weights(training.y, len(parent.meta["classes"]))
    candidate = parent.clone()
    normalizer = {"updated_features": 0, "max_prediction_delta": 0.0}
    if recipe.adaptive_blend is not None:
        normalizer = reparameterize_normalizer(candidate, training.x, blend=recipe.adaptive_blend)
    original_rate = float(parent.meta["learning_rate"])
    effective_rate = original_rate * recipe.learning_rate_multiplier
    if not math.isfinite(effective_rate) or not 0.0 < effective_rate <= 1.0:
        raise ValueError("effective learning rate is invalid")
    candidate.meta["learning_rate"] = effective_rate
    started = time.process_time()
    losses = candidate.fit(
        training.x,
        training.y,
        recipe.epochs,
        sample_weights=weights,
        loss=recipe.loss,
        loss_parameters=dict(recipe.loss_parameters),
    )
    cpu_seconds = time.process_time() - started
    candidate.meta["learning_rate"] = original_rate
    candidate.validate()
    return CandidateResult(
        candidate,
        tuple(float(value) for value in losses),
        {
            "recipe_id": recipe.recipe_id,
            "task": task,
            "history_policy": recipe.history_policy,
            "epochs": recipe.epochs,
            "learning_rate_multiplier": recipe.learning_rate_multiplier,
            "effective_learning_rate": effective_rate,
            "loss": recipe.loss,
            "loss_parameters": dict(recipe.loss_parameters),
            "class_weighting": recipe.class_weighting,
            "training_samples": len(training.ids),
            "training_sha256": training.sha256,
            "normalizer": normalizer,
            "cpu_seconds": cpu_seconds,
        },
    )


def select_robust_candidate(
    contract: MetricContract,
    candidates: Sequence[CandidateEvidence],
) -> CandidateEvidence | None:
    """Choose only candidates with positive central evidence on legal gates."""

    eligible: list[tuple[tuple[float, float, float, float], CandidateEvidence]] = []
    for candidate in candidates:
        gains = np.asarray(candidate.fold_gains, dtype=np.float64)
        if not len(gains) or not np.all(np.isfinite(gains)):
            continue
        median = float(np.median(gains))
        mean = float(np.mean(gains))
        worst = float(np.min(gains))
        if median <= 0.0 or mean <= 0.0:
            continue
        eligible.append(((median, mean, worst, -float(candidate.cpu_seconds)), candidate))
    return max(eligible, key=lambda item: item[0])[1] if eligible else None
