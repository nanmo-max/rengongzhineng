from brace_msi.cross_task_validation import (
    CandidateEvaluation,
    FoldResult,
    TaskOutcome,
    leave_one_task_out,
    rank_shared_candidates,
)


def _outcome(
    task: str,
    *,
    gain: float,
    versus_simple: float = 0.0,
    cpu: float = 1.0,
    simple_cpu: float = 0.5,
    samples: int = 100,
    hard: bool = True,
    budget: bool = True,
) -> TaskOutcome:
    return TaskOutcome(
        task_key=task,
        relative_gain_vs_static=gain,
        relative_gain_vs_simple=versus_simple,
        cpu_seconds=cpu,
        simple_cpu_seconds=simple_cpu,
        training_samples=samples,
        hard_constraints_passed=hard,
        resource_within_budget=budget,
    )


def test_leave_one_task_out_never_passes_held_out_task_to_selector() -> None:
    calls: list[tuple[str, ...]] = []

    def select(development_tasks: tuple[str, ...]) -> str:
        calls.append(development_tasks)
        return "shared-config"

    def evaluate(config_id: str, held_out_task: str) -> TaskOutcome:
        assert config_id == "shared-config"
        return _outcome(held_out_task, gain=0.01)

    folds = leave_one_task_out(("opaque-1", "opaque-2", "opaque-3"), select, evaluate)

    assert len(folds) == 3
    assert all(isinstance(fold, FoldResult) for fold in folds)
    assert {fold.held_out_task for fold in folds} == {"opaque-1", "opaque-2", "opaque-3"}
    assert all(fold.held_out_task not in fold.development_tasks for fold in folds)
    assert all(len(call) == 2 for call in calls)


def test_ranking_maximizes_worst_task_before_mean_or_cost() -> None:
    candidate_a = CandidateEvaluation(
        "a",
        (
            _outcome("1", gain=0.01, cpu=1.0),
            _outcome("2", gain=0.08, cpu=1.0),
            _outcome("3", gain=0.08, cpu=1.0),
        ),
    )
    candidate_b = CandidateEvaluation(
        "b",
        (
            _outcome("1", gain=0.02, cpu=3.0),
            _outcome("2", gain=0.02, cpu=3.0),
            _outcome("3", gain=0.02, cpu=3.0),
        ),
    )

    ranking = rank_shared_candidates((candidate_a, candidate_b), static_tolerance=0.005)

    assert ranking.winner == "b"
    assert ranking.ordered_candidate_ids == ("b", "a")


def test_ranking_eliminates_candidate_dominated_by_simple_in_two_folds() -> None:
    dominated = CandidateEvaluation(
        "complex",
        (
            _outcome("1", gain=0.03, versus_simple=-0.01, cpu=2.0, simple_cpu=1.0),
            _outcome("2", gain=0.03, versus_simple=-0.02, cpu=2.0, simple_cpu=1.0),
            _outcome("3", gain=0.03, versus_simple=0.01, cpu=2.0, simple_cpu=1.0),
        ),
    )
    simple_winner = CandidateEvaluation(
        "simple-compatible",
        (
            _outcome("1", gain=0.01, versus_simple=0.0, cpu=0.8, simple_cpu=1.0),
            _outcome("2", gain=0.01, versus_simple=0.0, cpu=0.8, simple_cpu=1.0),
            _outcome("3", gain=0.01, versus_simple=0.0, cpu=0.8, simple_cpu=1.0),
        ),
    )

    ranking = rank_shared_candidates(
        (dominated, simple_winner),
        static_tolerance=0.005,
        domination_fold_limit=2,
    )

    assert ranking.winner == "simple-compatible"
    assert ranking.eliminated["complex"] == "dominated_by_simple_in_2_folds"


def test_ranking_rejects_static_floor_or_hard_constraint_failure() -> None:
    below_static = CandidateEvaluation(
        "below",
        (
            _outcome("1", gain=-0.006),
            _outcome("2", gain=0.1),
            _outcome("3", gain=0.1),
        ),
    )
    invalid = CandidateEvaluation(
        "invalid",
        (
            _outcome("1", gain=0.1, hard=False),
            _outcome("2", gain=0.1),
            _outcome("3", gain=0.1),
        ),
    )

    ranking = rank_shared_candidates((below_static, invalid), static_tolerance=0.005)

    assert ranking.winner is None
    assert ranking.eliminated == {
        "below": "worst_task_below_static_tolerance",
        "invalid": "hard_constraint_or_resource_failure",
    }


def test_ranking_uses_resource_then_config_id_for_deterministic_ties() -> None:
    expensive = CandidateEvaluation(
        "z-config",
        tuple(_outcome(str(index), gain=0.02, cpu=2.0) for index in range(3)),
    )
    cheap_b = CandidateEvaluation(
        "b-config",
        tuple(_outcome(str(index), gain=0.02, cpu=1.0) for index in range(3)),
    )
    cheap_a = CandidateEvaluation(
        "a-config",
        tuple(_outcome(str(index), gain=0.02, cpu=1.0) for index in range(3)),
    )

    ranking = rank_shared_candidates(
        (expensive, cheap_b, cheap_a), static_tolerance=0.005
    )

    assert ranking.ordered_candidate_ids == ("a-config", "b-config", "z-config")
