"""Evidence routing and deterministic, budget-aware action escalation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from .evidence import build_evidence
from .modeling import ModelCapabilities
from .policies import Action


@dataclass(frozen=True)
class RoutedEvidence:
    training_allowed: bool
    diagnosis: str
    invalid_value_count: int
    performance_drop: float
    drift_score: float
    failed_actions: int
    budget_fraction: float


class EvidenceRouter:
    def route(
        self,
        *,
        reference_X: ArrayLike,
        current_X: ArrayLike,
        current_metric: float,
        reference_metric: float,
        higher_is_better: bool,
        failed_actions: int,
        budget_fraction: float,
    ) -> RoutedEvidence:
        reference = np.asarray(reference_X, dtype=np.float64)
        current = np.asarray(current_X, dtype=np.float64)
        invalid_count = int(np.size(current) - np.count_nonzero(np.isfinite(current)))
        finite_metrics = np.isfinite([current_metric, reference_metric]).all()
        if invalid_count or not finite_metrics or current.ndim != 2:
            return RoutedEvidence(
                False,
                "data_quality",
                invalid_count + int(not finite_metrics),
                0.0,
                0.0,
                failed_actions,
                max(0.0, min(1.0, budget_fraction)),
            )
        evidence = build_evidence(
            reference,
            current,
            current_metric=current_metric,
            reference_metric=reference_metric,
            higher_is_better=higher_is_better,
        )
        if budget_fraction <= 0.0:
            diagnosis = "budget_exhausted"
        elif evidence.performance_drop > 0.0 and evidence.drift_score > 0.0:
            diagnosis = "performance_and_covariate_drift"
        elif evidence.performance_drop > 0.0:
            diagnosis = "performance_degradation"
        elif evidence.drift_score > 0.0:
            diagnosis = "covariate_drift"
        else:
            diagnosis = "stable"
        return RoutedEvidence(
            budget_fraction > 0.0,
            diagnosis,
            0,
            evidence.performance_drop,
            evidence.drift_score,
            failed_actions,
            max(0.0, min(1.0, budget_fraction)),
        )


@dataclass(frozen=True)
class DecisionContext:
    evidence: RoutedEvidence
    capabilities: ModelCapabilities


class AdaptiveActionPlanner:
    """Escalation ladder driven by evidence and realized candidate failures."""

    def __init__(
        self,
        *,
        update_drop_threshold: float = 0.02,
        refit_drop_threshold: float = 0.20,
        drift_threshold: float = 0.20,
        high_drift_threshold: float = 0.80,
    ) -> None:
        self.update_drop_threshold = update_drop_threshold
        self.refit_drop_threshold = refit_drop_threshold
        self.drift_threshold = drift_threshold
        self.high_drift_threshold = high_drift_threshold
        self.consecutive_failures = 0

    def select(self, context: DecisionContext) -> Action:
        evidence = context.evidence
        if not evidence.training_allowed or evidence.budget_fraction <= 0.0:
            return Action.NOOP
        moderate = (
            evidence.performance_drop >= self.update_drop_threshold
            or evidence.drift_score >= self.drift_threshold
        )
        severe = (
            evidence.performance_drop >= self.refit_drop_threshold
            or evidence.drift_score >= self.high_drift_threshold
        )
        if not moderate:
            return Action.NOOP
        failure_count = max(evidence.failed_actions, self.consecutive_failures)
        if severe and failure_count >= 2 and evidence.budget_fraction >= 0.25:
            return Action.BOUNDED_HPO
        if failure_count >= 1 or not context.capabilities.supports_partial_fit:
            return Action.REPLAY_REFIT
        return Action.INCREMENTAL_UPDATE

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None:
        if action is Action.NOOP:
            return
        if accepted and improvement >= 0.0:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
