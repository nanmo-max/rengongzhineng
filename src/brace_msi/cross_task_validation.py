"""Task-level leave-one-out validation and robust shared-config ranking."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import fmean
from typing import Callable, Iterable


@dataclass(frozen=True)
class TaskOutcome:
    task_key: str
    relative_gain_vs_static: float
    relative_gain_vs_simple: float
    cpu_seconds: float
    simple_cpu_seconds: float
    training_samples: int
    hard_constraints_passed: bool
    resource_within_budget: bool

    def __post_init__(self) -> None:
        if not self.task_key:
            raise ValueError("task_key is required")
        values = (
            self.relative_gain_vs_static,
            self.relative_gain_vs_simple,
            self.cpu_seconds,
            self.simple_cpu_seconds,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("task outcome values must be finite")
        if self.cpu_seconds < 0.0 or self.simple_cpu_seconds < 0.0:
            raise ValueError("CPU usage cannot be negative")
        if self.training_samples < 0:
            raise ValueError("training_samples cannot be negative")


@dataclass(frozen=True)
class FoldResult:
    held_out_task: str
    development_tasks: tuple[str, ...]
    selected_config_id: str
    outcome: TaskOutcome


@dataclass(frozen=True)
class CandidateEvaluation:
    config_id: str
    outcomes: tuple[TaskOutcome, ...]

    def __post_init__(self) -> None:
        if not self.config_id or not self.outcomes:
            raise ValueError("candidate evaluation requires an ID and outcomes")
        keys = [outcome.task_key for outcome in self.outcomes]
        if len(keys) != len(set(keys)):
            raise ValueError("candidate outcomes must contain unique tasks")


@dataclass(frozen=True)
class CandidateRanking:
    winner: str | None
    ordered_candidate_ids: tuple[str, ...]
    eliminated: dict[str, str]


def leave_one_task_out(
    task_keys: Iterable[str],
    select_config: Callable[[tuple[str, ...]], str],
    evaluate_held_out: Callable[[str, str], TaskOutcome],
) -> tuple[FoldResult, ...]:
    """Select on N-1 tasks, then evaluate the frozen selection on the omitted task."""

    tasks = tuple(sorted(task_keys))
    if len(tasks) < 3 or len(tasks) != len(set(tasks)):
        raise ValueError("leave-one-task-out requires at least three unique tasks")
    folds: list[FoldResult] = []
    for held_out in tasks:
        development = tuple(task for task in tasks if task != held_out)
        selected = select_config(development)
        if not selected:
            raise ValueError("selector returned an empty config ID")
        outcome = evaluate_held_out(selected, held_out)
        if outcome.task_key != held_out:
            raise ValueError("held-out evaluator returned the wrong task")
        folds.append(FoldResult(held_out, development, selected, outcome))
    return tuple(folds)


def rank_shared_candidates(
    candidates: Iterable[CandidateEvaluation],
    *,
    static_tolerance: float,
    domination_fold_limit: int = 2,
) -> CandidateRanking:
    """Apply eligibility gates, then rank worst-task, mean, baseline gain and cost."""

    if static_tolerance < 0.0 or not math.isfinite(static_tolerance):
        raise ValueError("static_tolerance must be finite and nonnegative")
    if domination_fold_limit < 1:
        raise ValueError("domination_fold_limit must be positive")
    candidate_list = tuple(candidates)
    ids = [candidate.config_id for candidate in candidate_list]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate config IDs must be unique")

    eligible: list[CandidateEvaluation] = []
    eliminated: dict[str, str] = {}
    for candidate in candidate_list:
        if any(
            not outcome.hard_constraints_passed
            or not outcome.resource_within_budget
            for outcome in candidate.outcomes
        ):
            eliminated[candidate.config_id] = "hard_constraint_or_resource_failure"
            continue
        if min(
            outcome.relative_gain_vs_static for outcome in candidate.outcomes
        ) < -static_tolerance:
            eliminated[candidate.config_id] = "worst_task_below_static_tolerance"
            continue
        dominated_folds = sum(
            outcome.relative_gain_vs_simple < 0.0
            and outcome.cpu_seconds >= outcome.simple_cpu_seconds
            for outcome in candidate.outcomes
        )
        if dominated_folds >= domination_fold_limit:
            eliminated[candidate.config_id] = (
                f"dominated_by_simple_in_{dominated_folds}_folds"
            )
            continue
        eligible.append(candidate)

    def ranking_key(candidate: CandidateEvaluation) -> tuple[object, ...]:
        gains = [outcome.relative_gain_vs_static for outcome in candidate.outcomes]
        gains_vs_simple = [
            outcome.relative_gain_vs_simple for outcome in candidate.outcomes
        ]
        return (
            -min(gains),
            -fmean(gains),
            -fmean(gains_vs_simple),
            sum(outcome.cpu_seconds for outcome in candidate.outcomes),
            sum(outcome.training_samples for outcome in candidate.outcomes),
            candidate.config_id,
        )

    ordered = tuple(sorted(eligible, key=ranking_key))
    ordered_ids = tuple(candidate.config_id for candidate in ordered)
    return CandidateRanking(
        winner=ordered_ids[0] if ordered_ids else None,
        ordered_candidate_ids=ordered_ids,
        eliminated=eliminated,
    )
