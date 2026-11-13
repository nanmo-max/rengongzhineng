from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brace_msi.dual_loop import (
    CandidateOutcome,
    CandidateSpec,
    DecisionContext,
    DualLoopController,
    paired_shadow_reward,
)


def _context(round_index: int, batch_id: str, stable_model_id: str = "stable-v1") -> DecisionContext:
    return DecisionContext(
        round_index=round_index,
        batch_id=batch_id,
        stable_model_id=stable_model_id,
        submitted_prediction_digest=f"prediction-{round_index}",
        labels_open=True,
        remaining_cpu_seconds=100.0,
        evidence={"performance_drop": 0.1},
    )


def _candidate(candidate_id: str, mechanism: str, action: str = "REPLAY_REFIT") -> CandidateSpec:
    return CandidateSpec(
        candidate_id=candidate_id,
        action=action,
        mechanism=mechanism,
        estimated_cpu_seconds=5.0,
        parameters={"epochs": 1},
    )


def test_each_batch_has_exactly_one_decision_and_noop_is_valid(tmp_path: Path) -> None:
    controller = DualLoopController(tmp_path, minimum_gate_gain=0.01)
    controller.begin_round(_context(1, "batch-1"))
    plan = controller.plan_first_candidate(None, reason="stable evidence")

    assert plan.candidates == ()
    with pytest.raises(RuntimeError, match="already planned"):
        controller.plan_first_candidate(None, reason="duplicate")

    commit = controller.commit_round(decision="noop", deployed_model_id="stable-v1")
    assert commit.round_index == 1
    assert commit.candidates == ()
    assert controller.state.next_round == 2
    assert controller.state.real_experiment_count == 0

    with pytest.raises(ValueError, match="already committed"):
        controller.begin_round(_context(2, "batch-1"))


def test_second_candidate_requires_failed_or_weak_first_result_new_evidence_and_new_mechanism(
    tmp_path: Path,
) -> None:
    controller = DualLoopController(tmp_path, minimum_gate_gain=0.02)
    controller.begin_round(_context(1, "batch-1"))
    controller.plan_first_candidate(_candidate("c1", "incremental"), reason="performance drop")

    with pytest.raises(RuntimeError, match="first outcome"):
        controller.escalate_second_candidate(
            _candidate("c2", "replay"),
            new_evidence="candidate underfit",
            budget_remaining=True,
        )

    controller.record_candidate_outcome(
        CandidateOutcome(
            candidate_id="c1",
            completed=True,
            accepted=False,
            gate_gain=0.005,
            cpu_seconds=4.0,
        )
    )
    with pytest.raises(ValueError, match="different mechanism"):
        controller.escalate_second_candidate(
            _candidate("c2", "incremental"),
            new_evidence="candidate underfit",
            budget_remaining=True,
        )
    with pytest.raises(ValueError, match="new evidence"):
        controller.escalate_second_candidate(
            _candidate("c2", "replay"),
            new_evidence="",
            budget_remaining=True,
        )

    plan = controller.escalate_second_candidate(
        _candidate("c2", "replay"),
        new_evidence="first candidate underfit on Gate",
        budget_remaining=True,
    )
    assert [candidate.candidate_id for candidate in plan.candidates] == ["c1", "c2"]
    with pytest.raises(RuntimeError, match="two candidates"):
        controller.escalate_second_candidate(
            _candidate("c3", "family-switch"),
            new_evidence="another observation",
            budget_remaining=True,
        )


def test_successful_first_candidate_blocks_unnecessary_escalation(tmp_path: Path) -> None:
    controller = DualLoopController(tmp_path, minimum_gate_gain=0.01)
    controller.begin_round(_context(1, "batch-1"))
    controller.plan_first_candidate(_candidate("c1", "incremental"), reason="performance drop")
    controller.record_candidate_outcome(
        CandidateOutcome(
            candidate_id="c1",
            completed=True,
            accepted=True,
            gate_gain=0.03,
            cpu_seconds=3.0,
        )
    )

    with pytest.raises(RuntimeError, match="sufficient benefit"):
        controller.escalate_second_candidate(
            _candidate("c2", "replay"),
            new_evidence="not enough to justify",
            budget_remaining=True,
        )


def test_shadow_reward_is_paired_on_the_same_samples_and_has_low_confidence_fallback() -> None:
    classification = paired_shadow_reward(
        task_kind="classification",
        y_true=np.asarray([0, 0, 1, 1]),
        deployed_predictions=np.asarray([0, 0, 1, 1]),
        predecessor_predictions=np.asarray([0, 1, 1, 0]),
        cpu_seconds=0.2,
    )
    assert classification.confidence == "paired"
    assert classification.primary_delta > 0
    assert classification.details["accuracy_delta"] == pytest.approx(0.5)
    assert classification.cpu_seconds == pytest.approx(0.2)

    regression = paired_shadow_reward(
        task_kind="regression",
        y_true=np.asarray([0.0, 1.0, 2.0]),
        deployed_predictions=np.asarray([0.0, 1.0, 2.0]),
        predecessor_predictions=np.asarray([1.0, 2.0, 3.0]),
        cpu_seconds=0.1,
    )
    assert regression.primary_delta > 0
    assert regression.details["mae_improvement"] == pytest.approx(1.0)

    fallback = paired_shadow_reward(
        task_kind="regression",
        y_true=np.asarray([0.0, 1.0]),
        deployed_predictions=np.asarray([0.1, 1.1]),
        predecessor_predictions=None,
        historical_baseline=0.5,
        deployed_metric=0.1,
        cpu_seconds=0.0,
    )
    assert fallback.confidence == "historical_low"
    assert fallback.primary_delta == pytest.approx(0.4)


def test_pending_transaction_recovers_and_commit_is_atomic(tmp_path: Path) -> None:
    controller = DualLoopController(tmp_path, minimum_gate_gain=0.01)
    controller.begin_round(_context(1, "batch-1"))
    controller.plan_first_candidate(_candidate("c1", "incremental"), reason="drop")
    controller.record_candidate_outcome(
        CandidateOutcome(
            candidate_id="c1",
            completed=True,
            accepted=True,
            gate_gain=0.02,
            cpu_seconds=2.0,
        )
    )

    recovered = DualLoopController(tmp_path, minimum_gate_gain=0.01)
    assert recovered.pending_plan is not None
    assert recovered.pending_plan.candidates[0].candidate_id == "c1"
    commit = recovered.commit_round(decision="deploy", deployed_model_id="candidate-v1")

    assert (tmp_path / "commits" / "round-001.json").is_file()
    assert not (tmp_path / "pending.json").exists()
    reloaded = DualLoopController(tmp_path, minimum_gate_gain=0.01)
    assert reloaded.state.next_round == 2
    assert reloaded.state.stable_model_id == "candidate-v1"
    assert reloaded.state.real_experiment_count == 1
    assert commit.predecessor_model_id == "stable-v1"
