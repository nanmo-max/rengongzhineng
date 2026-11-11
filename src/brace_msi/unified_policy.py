"""Identity-blind evidence and action selection shared by every task."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from .evidence import Evidence
from .modeling import ModelCapabilities
from .policies import Action


@dataclass(frozen=True)
class MetricDescriptor:
    """Describe only metric direction and numerical scaling, never task identity."""

    higher_is_better: bool
    scale_floor: float = 1e-12

    def __post_init__(self) -> None:
        if not math.isfinite(self.scale_floor) or self.scale_floor <= 0.0:
            raise ValueError("scale_floor must be finite and positive")


def normalized_metric_delta(
    *, reference: float, current: float, descriptor: MetricDescriptor
) -> float:
    """Return positive relative degradation independent of metric direction/scale."""

    if not math.isfinite(reference) or not math.isfinite(current):
        raise ValueError("metric values must be finite")
    scale = max(abs(reference), descriptor.scale_floor)
    signed_drop = (
        reference - current
        if descriptor.higher_is_better
        else current - reference
    )
    return float(signed_drop / scale)


@dataclass(frozen=True)
class NormalizedEvidence:
    training_allowed: bool
    relative_performance_drop: float
    drift_score: float
    drift_percentile: float
    uncertainty_ratio: float
    sample_support: float
    failed_actions: int
    remaining_budget_fraction: float
    recent_relative_improvement: float

    def __post_init__(self) -> None:
        finite_fields = (
            self.relative_performance_drop,
            self.drift_score,
            self.drift_percentile,
            self.uncertainty_ratio,
            self.sample_support,
            self.remaining_budget_fraction,
            self.recent_relative_improvement,
        )
        if not all(math.isfinite(value) for value in finite_fields):
            raise ValueError("normalized evidence values must be finite")
        if not 0.0 <= self.drift_percentile <= 1.0:
            raise ValueError("drift_percentile must be in [0, 1]")
        if not 0.0 <= self.remaining_budget_fraction <= 1.0:
            raise ValueError("remaining_budget_fraction must be in [0, 1]")
        if self.drift_score < 0.0 or self.uncertainty_ratio < 0.0:
            raise ValueError("drift and uncertainty cannot be negative")
        if not 0.0 <= self.sample_support <= 1.0:
            raise ValueError("sample_support must be in [0, 1]")
        if self.failed_actions < 0:
            raise ValueError("failed_actions cannot be negative")


@dataclass(frozen=True)
class SharedPolicyConfig:
    update_drop_threshold: float = 0.02
    refit_drop_threshold: float = 0.10
    drift_percentile_threshold: float = 0.70
    high_drift_percentile_threshold: float = 0.90
    minimum_sample_support: float = 0.10
    hpo_failure_threshold: int = 2
    hpo_min_budget_fraction: float = 0.25
    replay_fraction: float = 0.50
    search_budget_fraction: float = 0.20
    minimum_relative_improvement: float = 0.0
    maximum_relative_anchor_degradation: float = 0.02

    def __post_init__(self) -> None:
        bounded = (
            self.drift_percentile_threshold,
            self.high_drift_percentile_threshold,
            self.minimum_sample_support,
            self.hpo_min_budget_fraction,
            self.replay_fraction,
            self.search_budget_fraction,
        )
        if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in bounded):
            raise ValueError("shared fractions and percentiles must be in [0, 1]")
        if self.update_drop_threshold < 0.0 or self.refit_drop_threshold < 0.0:
            raise ValueError("performance thresholds cannot be negative")
        if self.refit_drop_threshold < self.update_drop_threshold:
            raise ValueError("refit threshold cannot be below update threshold")
        if self.high_drift_percentile_threshold < self.drift_percentile_threshold:
            raise ValueError("high drift threshold cannot be below drift threshold")
        if self.hpo_failure_threshold < 1:
            raise ValueError("hpo_failure_threshold must be positive")
        if self.maximum_relative_anchor_degradation < 0.0:
            raise ValueError("anchor degradation threshold cannot be negative")


class UnifiedActionPolicy:
    """Select one bounded action without receiving a task or dataset identity."""

    def __init__(self, config: SharedPolicyConfig) -> None:
        self.config = config

    def select(
        self, evidence: NormalizedEvidence, capabilities: ModelCapabilities
    ) -> Action:
        if (
            not evidence.training_allowed
            or evidence.remaining_budget_fraction <= 0.0
            or evidence.sample_support < self.config.minimum_sample_support
        ):
            return Action.NOOP
        moderate = (
            evidence.relative_performance_drop >= self.config.update_drop_threshold
            or evidence.drift_percentile >= self.config.drift_percentile_threshold
        )
        if not moderate:
            return Action.NOOP
        severe = (
            evidence.relative_performance_drop >= self.config.refit_drop_threshold
            or evidence.drift_percentile
            >= self.config.high_drift_percentile_threshold
        )
        if (
            severe
            and evidence.failed_actions >= self.config.hpo_failure_threshold
            and evidence.remaining_budget_fraction
            >= self.config.hpo_min_budget_fraction
        ):
            return Action.BOUNDED_HPO
        if evidence.failed_actions > 0 or not capabilities.supports_partial_fit:
            return Action.REPLAY_REFIT
        return Action.INCREMENTAL_UPDATE


class FixedLowCostPolicy:
    """Strong control that performs exactly one low-cost update."""

    def __init__(self) -> None:
        self._used = False

    def choose_raw(self, evidence: Evidence) -> Action:
        del evidence
        if self._used:
            return Action.NOOP
        self._used = True
        return Action.INCREMENTAL_UPDATE

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None:
        del action, accepted, improvement


class NormalizedPerformanceTriggeredPolicy:
    """Single-action comparator using a dimensionless degradation threshold."""

    def __init__(self, *, threshold: float, descriptor: MetricDescriptor) -> None:
        if not math.isfinite(threshold) or threshold < 0.0:
            raise ValueError("threshold must be finite and nonnegative")
        self.threshold = threshold
        self.descriptor = descriptor

    def choose_raw(self, evidence: Evidence) -> Action:
        degradation = normalized_metric_delta(
            reference=evidence.reference_metric,
            current=evidence.current_metric,
            descriptor=self.descriptor,
        )
        return (
            Action.INCREMENTAL_UPDATE
            if degradation >= self.threshold
            else Action.NOOP
        )

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None:
        del action, accepted, improvement


class UnifiedRuntimePolicy:
    """Adapt raw per-batch evidence to the identity-blind shared policy contract."""

    def __init__(
        self,
        *,
        config: SharedPolicyConfig,
        descriptor: MetricDescriptor,
        capabilities: ModelCapabilities,
        remaining_budget_fraction: Callable[[], float],
        minimum_samples: int,
    ) -> None:
        if minimum_samples < 1:
            raise ValueError("minimum_samples must be positive")
        self.config = config
        self.descriptor = descriptor
        self.capabilities = capabilities
        self.remaining_budget_fraction = remaining_budget_fraction
        self.minimum_samples = minimum_samples
        self._core = UnifiedActionPolicy(config)
        self._drift_history: list[float] = []
        self._failed_actions = 0
        self._recent_improvement = 0.0

    def choose_raw(self, evidence: Evidence) -> Action:
        if self._drift_history:
            drift_percentile = sum(
                previous < evidence.drift_score for previous in self._drift_history
            ) / len(self._drift_history)
        else:
            drift_percentile = 0.0
        self._drift_history.append(evidence.drift_score)
        sample_support = min(1.0, evidence.sample_count / self.minimum_samples)
        remaining = self.remaining_budget_fraction()
        try:
            degradation = normalized_metric_delta(
                reference=evidence.reference_metric,
                current=evidence.current_metric,
                descriptor=self.descriptor,
            )
            normalized = NormalizedEvidence(
                training_allowed=True,
                relative_performance_drop=max(0.0, degradation),
                drift_score=evidence.drift_score,
                drift_percentile=drift_percentile,
                uncertainty_ratio=1.0 / math.sqrt(max(1, evidence.sample_count)),
                sample_support=sample_support,
                failed_actions=self._failed_actions,
                remaining_budget_fraction=remaining,
                recent_relative_improvement=self._recent_improvement,
            )
        except ValueError:
            return Action.NOOP
        return self._core.select(normalized, self.capabilities)

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None:
        if action is Action.NOOP:
            return
        self._recent_improvement = improvement
        if accepted and improvement >= self.config.minimum_relative_improvement:
            self._failed_actions = 0
        else:
            self._failed_actions += 1
