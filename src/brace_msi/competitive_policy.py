"""Evidence-only routing for the bounded native adaptation portfolio."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PortfolioEvidence:
    task_kind: str
    target_batch_means: tuple[float, ...]
    target_scale: float
    previous_delayed_gain: float | None
    failure_streak: int
    consecutive_aggressive: int = 0


@dataclass(frozen=True)
class CandidatePlan:
    primary_recipe: str
    secondary_recipe: str | None
    monotonic_trend_score: float
    normalized_trend_slope: float
    rationale: str


def _trend(values: tuple[float, ...], scale: float) -> tuple[float, float]:
    if len(values) < 3:
        return 0.0, 0.0
    target = np.asarray(values, dtype=np.float64)
    index = np.arange(len(target), dtype=np.float64)
    slope, intercept = np.polyfit(index, target, 1)
    fitted = slope * index + intercept
    residual = float(np.sum((target - fitted) ** 2))
    total = float(np.sum((target - target.mean()) ** 2))
    score = 1.0 if total <= 1e-12 else max(0.0, 1.0 - residual / total)
    return score, abs(float(slope)) / max(abs(float(scale)), 1e-12)


def build_candidate_plan(evidence: PortfolioEvidence) -> CandidatePlan:
    if evidence.task_kind not in {"classification", "regression"}:
        raise ValueError("unsupported task kind")
    if (
        not math.isfinite(evidence.target_scale)
        or evidence.target_scale <= 0.0
        or evidence.failure_streak < 0
        or evidence.consecutive_aggressive < 0
        or any(not math.isfinite(value) for value in evidence.target_batch_means)
    ):
        raise ValueError("portfolio evidence is invalid")
    score, normalized_slope = _trend(
        evidence.target_batch_means, evidence.target_scale
    )
    primary = "soup_current_e3_alpha0.25"
    if (
        evidence.previous_delayed_gain is not None
        and evidence.previous_delayed_gain < 0.0
    ) or evidence.failure_streak >= 2:
        secondary = None
        rationale = "negative delayed evidence keeps the bounded conservative update"
    elif evidence.task_kind == "classification":
        secondary = "recent_e3" if len(evidence.target_batch_means) >= 3 else None
        rationale = "classification uses recent replay after enough observed batches"
    else:
        mature_trend = bool(
            len(evidence.target_batch_means) >= 4
            and score >= 0.95
            and normalized_slope >= 0.10
        )
        strong_monotonic = mature_trend
        if strong_monotonic:
            secondary = "current_e3_lr3"
            rationale = "consistent monotonic target drift favors bounded local continuation"
        elif len(evidence.target_batch_means) >= 3:
            secondary = "cumulative_e3_lr0.3"
            rationale = "nonmonotonic regression favors conservative cumulative replay"
        else:
            secondary = None
            rationale = "insufficient history keeps only the conservative candidate"
    return CandidatePlan(
        primary_recipe=primary,
        secondary_recipe=secondary,
        monotonic_trend_score=score,
        normalized_trend_slope=normalized_slope,
        rationale=rationale,
    )
