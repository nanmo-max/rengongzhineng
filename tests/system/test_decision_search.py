import numpy as np

from brace_msi.budget import BudgetLedger, BudgetLimits
from brace_msi.decision import AdaptiveActionPlanner, DecisionContext, EvidenceRouter
from brace_msi.modeling import CpuModelAdapter
from brace_msi.policies import Action
from brace_msi.search import BoundedSearch, CandidateConfig, ReplayBuffer, SearchConfig


def _limits(*, candidates: int = 4, samples: int = 1000) -> BudgetLimits:
    return BudgetLimits(candidates, samples, 30.0, 30.0)


def test_evidence_router_blocks_training_on_nonfinite_data() -> None:
    reference = np.asarray([[0.0, 0.0], [1.0, 1.0]])
    current = np.asarray([[np.nan, 0.0], [2.0, 2.0]])

    routed = EvidenceRouter().route(
        reference_X=reference,
        current_X=current,
        current_metric=0.4,
        reference_metric=0.8,
        higher_is_better=True,
        failed_actions=0,
        budget_fraction=1.0,
    )

    assert routed.training_allowed is False
    assert routed.diagnosis == "data_quality"
    assert routed.invalid_value_count == 1


def test_adaptive_planner_escalates_from_incremental_to_refit_then_hpo() -> None:
    reference = np.zeros((20, 2))
    current = np.ones((20, 2))
    router = EvidenceRouter()
    model = CpuModelAdapter(task_kind="classification", family="sgd", seed=1)
    planner = AdaptiveActionPlanner(
        update_drop_threshold=0.05,
        refit_drop_threshold=0.20,
        drift_threshold=0.20,
        high_drift_threshold=0.80,
    )

    moderate = router.route(
        reference_X=reference,
        current_X=current * 0.2,
        current_metric=0.72,
        reference_metric=0.80,
        higher_is_better=True,
        failed_actions=0,
        budget_fraction=1.0,
    )
    assert planner.select(DecisionContext(moderate, model.capabilities)) is Action.INCREMENTAL_UPDATE
    planner.observe(Action.INCREMENTAL_UPDATE, accepted=False, improvement=-0.1)
    assert planner.select(DecisionContext(moderate, model.capabilities)) is Action.REPLAY_REFIT
    planner.observe(Action.REPLAY_REFIT, accepted=False, improvement=-0.1)

    severe = router.route(
        reference_X=reference,
        current_X=current * 10.0,
        current_metric=0.40,
        reference_metric=0.80,
        higher_is_better=True,
        failed_actions=2,
        budget_fraction=0.8,
    )
    assert planner.select(DecisionContext(severe, model.capabilities)) is Action.BOUNDED_HPO


def test_adaptive_planner_stops_when_budget_or_evidence_disallows_training() -> None:
    router = EvidenceRouter()
    clean = np.zeros((10, 2))
    evidence = router.route(
        reference_X=clean,
        current_X=clean + 1.0,
        current_metric=0.0,
        reference_metric=1.0,
        higher_is_better=True,
        failed_actions=3,
        budget_fraction=0.0,
    )
    capabilities = CpuModelAdapter(
        task_kind="classification", family="sgd", seed=1
    ).capabilities

    assert AdaptiveActionPlanner().select(
        DecisionContext(evidence, capabilities)
    ) is Action.NOOP


def test_replay_buffer_is_bounded_and_keeps_most_recent_samples() -> None:
    replay = ReplayBuffer(max_samples=4)
    replay.append(np.arange(6).reshape(3, 2), np.asarray([0, 1, 2]))
    replay.append(np.arange(6, 12).reshape(3, 2), np.asarray([3, 4, 5]))

    X, y = replay.arrays()
    assert X.shape == (4, 2)
    np.testing.assert_array_equal(y, np.asarray([2, 3, 4, 5]))


def test_bounded_search_respects_budget_and_patience_without_mutating_stable() -> None:
    X = np.asarray(
        [[-3.0], [-2.0], [-1.0], [-0.5], [0.5], [1.0], [2.0], [3.0]]
    )
    y = np.asarray([0, 0, 0, 0, 1, 1, 1, 1])
    stable = CpuModelAdapter(
        task_kind="classification", family="sgd", seed=7
    ).fit(X[:6], y[:6])
    before = stable.predict(X).copy()
    ledger = BudgetLedger(_limits(candidates=2, samples=20))
    search = BoundedSearch(
        task_kind="classification",
        seed=7,
        config=SearchConfig(max_trials=4, patience=1, min_improvement=0.0),
    )

    result = search.run(
        candidates=(
            CandidateConfig("linear", {"C": 0.1}),
            CandidateConfig("extra_trees", {"n_estimators": 8, "max_depth": 2}),
            CandidateConfig("hist_gradient_boosting", {"max_iter": 8}),
        ),
        train_X=X[:6],
        train_y=y[:6],
        validation_X=X[6:],
        validation_y=y[6:],
        ledger=ledger,
    )

    assert 1 <= len(result.trials) <= 2
    assert ledger.candidates_started == len(result.trials)
    assert result.best_model is not None
    np.testing.assert_array_equal(stable.predict(X), before)
