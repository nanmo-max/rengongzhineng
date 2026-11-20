"""Research-only, identity-blind selection strategies for local replay.

This module deliberately consumes only metric semantics, artifact lineage and
explicit resource state.  Dataset/profile names are not part of the contract.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from brace_formal.metrics import MetricContract, primary_evidence


@dataclass(frozen=True)
class ArtifactEvidence:
    artifact_id: str
    metric_value: float
    validation_scope: str
    recoverable: bool
    hard_valid: bool


@dataclass(frozen=True)
class ExplorationBudget:
    remaining: int
    regression_tolerance: float

    def __post_init__(self) -> None:
        if self.remaining < 0:
            raise ValueError("exploration budget cannot be negative")
        if not math.isfinite(self.regression_tolerance) or self.regression_tolerance < 0.0:
            raise ValueError("exploration tolerance must be finite and non-negative")


@dataclass(frozen=True)
class SelectionContext:
    contract: MetricContract
    validation_scope: str
    parent: ArtifactEvidence
    candidate: ArtifactEvidence
    champion: ArtifactEvidence | None = None
    exploration: ExplorationBudget | None = None
    rollback_available: bool = False

    def with_exploration(self, value: ExplorationBudget) -> "SelectionContext":
        return replace(self, exploration=value)

    def with_rollback_available(self, value: bool) -> "SelectionContext":
        return replace(self, rollback_available=value)


@dataclass(frozen=True)
class SelectionDecision:
    strategy: str
    selected_artifact_id: str
    relation: str
    signed_gain: float | None
    reason: str
    exploration_consumed: int = 0


@dataclass(frozen=True)
class RecipeFeedback:
    """Finite cooldowns for performance misses and permanent hard quarantines."""

    cooldown_until: tuple[tuple[str, int], ...] = ()
    quarantined: tuple[str, ...] = ()

    def _cooldowns(self) -> dict[str, int]:
        return dict(self.cooldown_until)

    def is_quarantined(self, recipe: str) -> bool:
        return recipe in self.quarantined

    def is_available(self, recipe: str, *, round_index: int) -> bool:
        if self.is_quarantined(recipe):
            return False
        return round_index >= self._cooldowns().get(recipe, 0)


def update_recipe_feedback(
    feedback: RecipeFeedback,
    recipe: str,
    *,
    outcome: str,
    round_index: int,
    cooldown_rounds: int = 2,
) -> RecipeFeedback:
    if not recipe or round_index < 0 or cooldown_rounds < 1:
        raise ValueError("recipe feedback input is invalid")
    cooldowns = feedback._cooldowns()
    quarantined = set(feedback.quarantined)
    if outcome == "hard_failure":
        quarantined.add(recipe)
        cooldowns.pop(recipe, None)
    elif outcome == "performance_regression":
        if recipe not in quarantined:
            cooldowns[recipe] = max(cooldowns.get(recipe, 0), round_index + cooldown_rounds)
    elif outcome == "success":
        cooldowns.pop(recipe, None)
    else:
        raise ValueError("unsupported recipe outcome")
    return RecipeFeedback(
        cooldown_until=tuple(sorted(cooldowns.items())),
        quarantined=tuple(sorted(quarantined)),
    )


def _primary(context: SelectionContext) -> dict[str, object] | None:
    if not context.validation_scope:
        raise ValueError("validation scope is required")
    if context.parent.validation_scope != context.validation_scope:
        raise ValueError("parent evidence scope differs from the active scope")
    candidate = context.candidate
    if (
        candidate.validation_scope != context.validation_scope
        or not candidate.hard_valid
        or not math.isfinite(candidate.metric_value)
    ):
        return None
    if not context.parent.hard_valid or not math.isfinite(context.parent.metric_value):
        raise ValueError("parent evidence is not valid")
    return primary_evidence(
        context.contract,
        {context.contract.name: context.parent.metric_value},
        {context.contract.name: candidate.metric_value},
        parent_validation_sha256=context.validation_scope,
        candidate_validation_sha256=candidate.validation_scope,
    )


def _retain(strategy: str, evidence: dict[str, object] | None, reason: str) -> SelectionDecision:
    return SelectionDecision(
        strategy=strategy,
        selected_artifact_id="parent",
        relation="unavailable" if evidence is None else str(evidence["relation"]),
        signed_gain=None if evidence is None else float(evidence["signed_gain"]),
        reason=reason,
    )


def _better(contract: MetricContract, left: float, right: float) -> bool:
    return left > right if contract.direction == "higher" else left < right


def decide(strategy: str, context: SelectionContext) -> SelectionDecision:
    """Choose an artifact using one preregistered, task-name-free strategy."""

    supported = {
        "strict_parent_gate",
        "bounded_exploration",
        "conditional_champion",
        "recipe_feedback",
    }
    if strategy not in supported:
        raise ValueError("unsupported selection strategy")
    evidence = _primary(context)
    if evidence is None:
        return _retain(strategy, evidence, "candidate_evidence_unavailable")

    relation = str(evidence["relation"])
    signed_gain = float(evidence["signed_gain"])
    if strategy in {"strict_parent_gate", "recipe_feedback"}:
        if relation != "improved":
            return _retain(strategy, evidence, "candidate_not_better_than_parent")
        return SelectionDecision(
            strategy, context.candidate.artifact_id, relation, signed_gain, "same_scope_improvement"
        )

    if strategy == "bounded_exploration":
        if relation == "improved":
            return SelectionDecision(
                strategy, context.candidate.artifact_id, relation, signed_gain, "same_scope_improvement"
            )
        budget = context.exploration
        can_explore = bool(
            budget is not None
            and budget.remaining > 0
            and context.rollback_available
            and context.parent.recoverable
            and abs(signed_gain) <= budget.regression_tolerance
        )
        if can_explore:
            return SelectionDecision(
                strategy,
                context.candidate.artifact_id,
                relation,
                signed_gain,
                "bounded_recoverable_exploration",
                exploration_consumed=1,
            )
        return _retain(strategy, evidence, "exploration_not_permitted")

    eligible = [context.parent]
    if relation == "improved":
        eligible.append(context.candidate)
    champion = context.champion
    if (
        champion is not None
        and champion.validation_scope == context.validation_scope
        and champion.recoverable
        and champion.hard_valid
        and math.isfinite(champion.metric_value)
    ):
        eligible.append(champion)
    selected = eligible[0]
    for artifact in eligible[1:]:
        if _better(context.contract, artifact.metric_value, selected.metric_value):
            selected = artifact
    reason = (
        "same_scope_recoverable_best"
        if selected.artifact_id == getattr(champion, "artifact_id", None)
        else "same_scope_candidate_best"
        if selected.artifact_id == context.candidate.artifact_id
        else "parent_remains_best"
    )
    return SelectionDecision(
        strategy, selected.artifact_id, relation, signed_gain, reason
    )

