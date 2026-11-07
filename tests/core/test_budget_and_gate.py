from __future__ import annotations

import numpy as np


def test_budget_precheck_rejects_candidate_before_training() -> None:
    from brace_msi.budget import BudgetLedger, BudgetLimits

    ledger = BudgetLedger(
        BudgetLimits(
            max_candidates=2,
            max_training_samples=100,
            max_wall_seconds=5.0,
            max_cpu_seconds=5.0,
        )
    )

    allowed = ledger.check_before_training(estimated_samples=80)
    rejected = ledger.check_before_training(estimated_samples=120)

    assert allowed.allowed is True
    assert rejected.allowed is False
    assert "samples" in rejected.reason
    assert ledger.candidates_started == 0


def test_budget_recording_reduces_remaining_capacity() -> None:
    from brace_msi.budget import BudgetLedger, BudgetLimits
    from brace_msi.resources import ResourceUsage

    ledger = BudgetLedger(
        BudgetLimits(
            max_candidates=1,
            max_training_samples=100,
            max_wall_seconds=1.0,
            max_cpu_seconds=1.0,
        )
    )
    ledger.record_candidate(
        ResourceUsage(
            wall_seconds=0.4,
            cpu_seconds=0.3,
            rss_before_bytes=100,
            rss_after_bytes=120,
            peak_rss_bytes=120,
        ),
        training_samples=50,
    )

    decision = ledger.check_before_training(estimated_samples=1)

    assert decision.allowed is False
    assert "candidate" in decision.reason
    assert ledger.candidates_started == 1


def test_budget_remaining_fraction_uses_most_constrained_resource() -> None:
    from brace_msi.budget import BudgetLedger, BudgetLimits
    from brace_msi.resources import ResourceUsage

    ledger = BudgetLedger(
        BudgetLimits(
            max_candidates=4,
            max_training_samples=100,
            max_wall_seconds=10.0,
            max_cpu_seconds=10.0,
        )
    )
    ledger.record_candidate(
        ResourceUsage(1.0, 2.0, 0, 0, 0), training_samples=75
    )

    assert ledger.remaining_fraction == 0.25


def test_safety_gate_accepts_gain_with_anchor_retention() -> None:
    from brace_msi.safety import GateConfig, evaluate_candidate

    decision = evaluate_candidate(
        task_kind="classification",
        stable_validation=np.asarray([0, 0, 1, 0, 1, 0]),
        candidate_validation=np.asarray([0, 1, 1, 0, 1, 0]),
        validation_targets=np.asarray([0, 1, 1, 0, 1, 0]),
        stable_anchor=np.asarray([0, 1, 1, 0, 1, 0]),
        candidate_anchor=np.asarray([0, 1, 1, 0, 1, 0]),
        anchor_targets=np.asarray([0, 1, 1, 0, 1, 0]),
        hard_constraints_passed=True,
        config=GateConfig(min_validation_samples=6, min_primary_improvement=0.05),
    )

    assert decision.accepted is True
    assert decision.layer == "deployment"
    assert decision.validation_improvement > 0


def test_safety_gate_rejects_anchor_regression_without_replacing_stable() -> None:
    from brace_msi.safety import GateConfig, evaluate_candidate, select_deployment

    stable_model = object()
    candidate_model = object()
    decision = evaluate_candidate(
        task_kind="regression",
        stable_validation=np.asarray([4.0, 4.0, 4.0, 4.0]),
        candidate_validation=np.asarray([0.0, 0.0, 0.0, 0.0]),
        validation_targets=np.asarray([0.0, 0.0, 0.0, 0.0]),
        stable_anchor=np.asarray([0.0, 0.0, 0.0, 0.0]),
        candidate_anchor=np.asarray([10.0, 10.0, 10.0, 10.0]),
        anchor_targets=np.asarray([0.0, 0.0, 0.0, 0.0]),
        hard_constraints_passed=True,
        config=GateConfig(
            min_validation_samples=4,
            min_primary_improvement=0.0,
            max_anchor_degradation=1.0,
        ),
    )

    deployed = select_deployment(stable_model, candidate_model, decision)

    assert decision.accepted is False
    assert decision.layer == "statistical"
    assert deployed is stable_model


def test_safety_gate_rejects_failed_hard_constraint() -> None:
    from brace_msi.safety import GateConfig, evaluate_candidate

    target = np.asarray([0, 1, 0, 1])
    decision = evaluate_candidate(
        task_kind="classification",
        stable_validation=target,
        candidate_validation=target,
        validation_targets=target,
        stable_anchor=target,
        candidate_anchor=target,
        anchor_targets=target,
        hard_constraints_passed=False,
        config=GateConfig(min_validation_samples=4),
    )

    assert decision.accepted is False
    assert decision.layer == "hard_constraint"
