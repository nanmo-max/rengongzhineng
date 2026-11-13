"""Deterministic, evidence-driven action policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .evidence import Evidence


class Action(str, Enum):
    NOOP = "noop"
    RECALIBRATE = "recalibrate"
    INCREMENTAL_UPDATE = "incremental_update"
    REPLAY_REFIT = "replay_refit"
    FAMILY_SWITCH = "family_switch"
    BOUNDED_HPO = "bounded_hpo"
    REGISTERED_PLUGIN = "registered_plugin"
    ROLLBACK = "rollback"


@dataclass(frozen=True)
class PolicyContext:
    batch_index: int
    evidence: Evidence


class StaticPolicy:
    def choose(self, context: PolicyContext) -> Action:
        return Action.NOOP

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None:
        return None


class PerformanceTriggeredPolicy:
    """Strong simple control: one trigger and one low-cost action."""

    def __init__(self, *, performance_drop_threshold: float) -> None:
        self.performance_drop_threshold = performance_drop_threshold

    def choose(self, context: PolicyContext) -> Action:
        if context.evidence.performance_drop >= self.performance_drop_threshold:
            return Action.INCREMENTAL_UPDATE
        return Action.NOOP

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None:
        return None


class BracePolicy:
    """Escalate actions from current evidence and realized candidate outcomes."""

    def __init__(
        self,
        *,
        update_drop_threshold: float,
        refit_drop_threshold: float,
        drift_threshold: float,
        high_drift_threshold: float,
    ) -> None:
        self.update_drop_threshold = update_drop_threshold
        self.refit_drop_threshold = refit_drop_threshold
        self.drift_threshold = drift_threshold
        self.high_drift_threshold = high_drift_threshold
        self._incremental_failed = False

    def choose(self, context: PolicyContext) -> Action:
        evidence = context.evidence
        severe = (
            evidence.performance_drop >= self.refit_drop_threshold
            or evidence.drift_score >= self.high_drift_threshold
        )
        moderate = (
            evidence.performance_drop >= self.update_drop_threshold
            or evidence.drift_score >= self.drift_threshold
        )
        if severe or (moderate and self._incremental_failed):
            return Action.REPLAY_REFIT
        if moderate:
            return Action.INCREMENTAL_UPDATE
        return Action.NOOP

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None:
        if action is Action.INCREMENTAL_UPDATE:
            self._incremental_failed = not accepted
        elif action is Action.REPLAY_REFIT and accepted:
            self._incremental_failed = False
