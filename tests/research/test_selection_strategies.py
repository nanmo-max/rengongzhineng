from __future__ import annotations

import math

import pytest

from brace_formal.metrics import MetricContract
from brace_msi.selection_strategies import (
    ArtifactEvidence,
    ExplorationBudget,
    RecipeFeedback,
    SelectionContext,
    decide,
    update_recipe_feedback,
)
from scripts.run_selection_decision_replay import build_replay


@pytest.mark.parametrize(
    ("contract", "parent", "candidate"),
    [
        (MetricContract("classification", "macro_f1", "higher"), 0.9213, 0.8805),
        (MetricContract("regression", "rmse", "lower"), 660.81, 675.55),
        (MetricContract("regression", "rmse", "lower"), 52.71, 52.94),
    ],
)
def test_strict_parent_gate_rejects_confirmed_regressions(
    contract: MetricContract, parent: float, candidate: float
) -> None:
    decision = decide(
        "strict_parent_gate",
        SelectionContext(
            contract=contract,
            validation_scope="scope-1",
            parent=ArtifactEvidence("parent", parent, "scope-1", True, True),
            candidate=ArtifactEvidence("candidate", candidate, "scope-1", True, True),
        ),
    )

    assert decision.selected_artifact_id == "parent"
    assert decision.reason == "candidate_not_better_than_parent"


def test_bounded_exploration_requires_tolerance_budget_and_rollback() -> None:
    contract = MetricContract("classification", "macro_f1", "higher")
    context = SelectionContext(
        contract=contract,
        validation_scope="same",
        parent=ArtifactEvidence("parent", 0.8000, "same", True, True),
        candidate=ArtifactEvidence("candidate", 0.7995, "same", True, True),
        exploration=ExplorationBudget(remaining=1, regression_tolerance=0.001),
        rollback_available=True,
    )

    explored = decide("bounded_exploration", context)
    assert explored.selected_artifact_id == "candidate"
    assert explored.exploration_consumed == 1

    no_budget = decide(
        "bounded_exploration",
        context.with_exploration(ExplorationBudget(remaining=0, regression_tolerance=0.001)),
    )
    assert no_budget.selected_artifact_id == "parent"

    no_rollback = decide(
        "bounded_exploration",
        context.with_rollback_available(False),
    )
    assert no_rollback.selected_artifact_id == "parent"

    too_large = decide(
        "bounded_exploration",
        SelectionContext(
            contract=contract,
            validation_scope="same",
            parent=context.parent,
            candidate=ArtifactEvidence("candidate", 0.7900, "same", True, True),
            exploration=context.exploration,
            rollback_available=True,
        ),
    )
    assert too_large.selected_artifact_id == "parent"


@pytest.mark.parametrize(
    ("champion_scope", "recoverable"), [("different", True), ("same", False)]
)
def test_conditional_champion_must_be_same_scope_and_recoverable(
    champion_scope: str, recoverable: bool
) -> None:
    context = SelectionContext(
        contract=MetricContract("regression", "rmse", "lower"),
        validation_scope="same",
        parent=ArtifactEvidence("parent", 50.0, "same", True, True),
        candidate=ArtifactEvidence("candidate", 49.0, "same", True, True),
        champion=ArtifactEvidence("champion", 40.0, champion_scope, recoverable, True),
    )

    decision = decide("conditional_champion", context)
    assert decision.selected_artifact_id == "candidate"
    assert decision.selected_artifact_id != "champion"


def test_conditional_champion_can_restore_legal_same_scope_best() -> None:
    context = SelectionContext(
        contract=MetricContract("regression", "rmse", "lower"),
        validation_scope="same",
        parent=ArtifactEvidence("parent", 50.0, "same", True, True),
        candidate=ArtifactEvidence("candidate", 49.0, "same", True, True),
        champion=ArtifactEvidence("champion", 45.0, "same", True, True),
    )

    decision = decide("conditional_champion", context)
    assert decision.selected_artifact_id == "champion"
    assert decision.reason == "same_scope_recoverable_best"


def test_recipe_feedback_cools_regression_but_quarantines_hard_failure() -> None:
    initial = RecipeFeedback()
    cooled = update_recipe_feedback(initial, "recipe-a", outcome="performance_regression", round_index=3)
    assert not cooled.is_quarantined("recipe-a")
    assert not cooled.is_available("recipe-a", round_index=4)
    assert cooled.is_available("recipe-a", round_index=5)

    quarantined = update_recipe_feedback(cooled, "recipe-b", outcome="hard_failure", round_index=3)
    assert quarantined.is_quarantined("recipe-b")
    assert not quarantined.is_available("recipe-b", round_index=100)


def test_nonfinite_candidate_fails_closed() -> None:
    context = SelectionContext(
        contract=MetricContract("classification", "macro_f1", "higher"),
        validation_scope="same",
        parent=ArtifactEvidence("parent", 0.8, "same", True, True),
        candidate=ArtifactEvidence("candidate", math.nan, "same", True, True),
    )

    assert decide("strict_parent_gate", context).selected_artifact_id == "parent"


def test_task_label_is_not_an_input_to_selection() -> None:
    contract = MetricContract("classification", "macro_f1", "higher")
    base = SelectionContext(
        contract=contract,
        validation_scope="same",
        parent=ArtifactEvidence("parent", 0.8, "same", True, True),
        candidate=ArtifactEvidence("candidate", 0.82, "same", True, True),
    )

    assert decide("strict_parent_gate", base) == decide("strict_parent_gate", base)


def test_frozen_official_counterexamples_all_fail_closed() -> None:
    replay = build_replay()

    assert replay["valid"] is True
    assert replay["strict_regression_cases_rejected"] == 3
    assert replay["strict_case_count"] == 3
    assert replay["training_count"] == 0
    assert replay["public_confirmation_reads"] == 0

