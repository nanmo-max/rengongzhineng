"""Training-time budget decisions made before candidate construction."""

from __future__ import annotations

from dataclasses import dataclass

from .resources import ResourceUsage


@dataclass(frozen=True)
class BudgetLimits:
    max_candidates: int
    max_training_samples: int
    max_wall_seconds: float
    max_cpu_seconds: float


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str


class BudgetLedger:
    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits
        self.candidates_started = 0
        self.training_samples = 0
        self.wall_seconds = 0.0
        self.cpu_seconds = 0.0

    def check_before_training(self, *, estimated_samples: int) -> BudgetDecision:
        if self.candidates_started >= self.limits.max_candidates:
            return BudgetDecision(False, "candidate limit exhausted")
        if self.training_samples + estimated_samples > self.limits.max_training_samples:
            return BudgetDecision(False, "training samples would exceed budget")
        if self.wall_seconds >= self.limits.max_wall_seconds:
            return BudgetDecision(False, "wall-time budget exhausted")
        if self.cpu_seconds >= self.limits.max_cpu_seconds:
            return BudgetDecision(False, "CPU-time budget exhausted")
        return BudgetDecision(True, "within budget")

    def record_candidate(
        self, usage: ResourceUsage, *, training_samples: int
    ) -> None:
        self.candidates_started += 1
        self.training_samples += training_samples
        self.wall_seconds += usage.wall_seconds
        self.cpu_seconds += usage.cpu_seconds
