from __future__ import annotations

from dataclasses import replace

import pytest

from brace_msi.policies import Action
from brace_msi.pytrio_agent import (
    AdvisorReceipt,
    AgentCallReceipt,
    AgentContext,
    AgentTrigger,
    ExperimentProposal,
    ProposalOutcome,
    RetryingProposalAdvisor,
)


def _context() -> AgentContext:
    return AgentContext(
        task_kind="classification",
        metric_name="macro_f1",
        higher_is_better=True,
        round_index=4,
        evidence={"performance_drop": 0.2, "drift_score": 0.5},
        history=(),
        budget={"cpu_seconds_remaining": 50.0, "candidate_slots_remaining": 2},
        capabilities={"supports_partial_fit": True},
    )


def _proposal(action: Action = Action.INCREMENTAL_UPDATE) -> ExperimentProposal:
    tools = {
        Action.INCREMENTAL_UPDATE: "train_incremental",
        Action.REPLAY_REFIT: "train_replay_refit",
    }
    return ExperimentProposal(
        schema_version="brace-msi.experiment-proposal.v1",
        action=action,
        tool=tools[action],
        rationale="bounded evidence-driven proposal",
        parameters={"epochs": 1},
        max_cpu_seconds=10.0,
        max_candidates=1,
        stop_conditions=("budget_exhausted",),
    )


def _receipt(status: str = "accepted") -> AgentCallReceipt:
    return AgentCallReceipt(
        status=status,
        model="Qwen/Qwen3.5-4B",
        model_path_configured=False,
        prompt_sha256="a" * 64,
        response_sha256="b" * 64,
        input_tokens=100,
        output_tokens=30,
        latency_seconds=0.5,
    )


class SequenceProposer:
    def __init__(self, results: list[ProposalOutcome | Exception]) -> None:
        self.results = list(results)
        self.calls = 0

    def propose(self, context: AgentContext) -> ProposalOutcome:
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _fallback(_: AgentContext) -> ExperimentProposal:
    return _proposal(Action.INCREMENTAL_UPDATE)


def test_stable_round_does_not_call_qwen() -> None:
    trigger = AgentTrigger.evaluate(
        performance_drop=0.01,
        drift_complexity=0.1,
        failure_streak=0,
        action_uncertainty=0.1,
        pareto_indistinguishable=False,
    )
    proposer = SequenceProposer([])
    outcome = RetryingProposalAdvisor(proposer, fallback=_fallback).advise(_context(), trigger)

    assert not trigger.should_call
    assert proposer.calls == 0
    assert outcome.proposal is None
    assert outcome.receipt.status == "not_triggered"
    assert outcome.receipt.attempts == 0


@pytest.mark.parametrize(
    "kwargs, expected_reason",
    [
        ({"performance_drop": 0.2}, "severe_degradation"),
        ({"drift_complexity": 0.8}, "complex_drift"),
        ({"failure_streak": 2}, "consecutive_failures"),
        ({"action_uncertainty": 0.8}, "action_value_uncertainty"),
        ({"pareto_indistinguishable": True}, "pareto_indistinguishable"),
    ],
)
def test_each_documented_condition_triggers_qwen(kwargs: dict[str, object], expected_reason: str) -> None:
    values: dict[str, object] = {
        "performance_drop": 0.0,
        "drift_complexity": 0.0,
        "failure_streak": 0,
        "action_uncertainty": 0.0,
        "pareto_indistinguishable": False,
    }
    values.update(kwargs)
    trigger = AgentTrigger.evaluate(**values)
    assert trigger.should_call
    assert expected_reason in trigger.reasons


def test_triggered_advisor_accepts_first_valid_qwen_proposal() -> None:
    proposer = SequenceProposer(
        [ProposalOutcome(proposal=_proposal(Action.REPLAY_REFIT), source="pytrio", receipt=_receipt())]
    )
    trigger = AgentTrigger(True, ("severe_degradation",))
    outcome = RetryingProposalAdvisor(proposer, fallback=_fallback).advise(_context(), trigger)

    assert outcome.source == "pytrio"
    assert outcome.proposal is not None and outcome.proposal.action is Action.REPLAY_REFIT
    assert outcome.receipt.attempts == 1
    assert outcome.receipt.total_input_tokens == 100


def test_advisor_retries_once_then_accepts() -> None:
    proposer = SequenceProposer(
        [
            RuntimeError("temporary failure"),
            ProposalOutcome(proposal=_proposal(Action.REPLAY_REFIT), source="pytrio", receipt=_receipt()),
        ]
    )
    outcome = RetryingProposalAdvisor(proposer, fallback=_fallback).advise(
        _context(), AgentTrigger(True, ("complex_drift",))
    )

    assert proposer.calls == 2
    assert outcome.source == "pytrio"
    assert outcome.receipt.status == "accepted_after_retry"
    assert outcome.receipt.attempts == 2
    assert outcome.receipt.error_categories == ("RuntimeError",)


def test_two_failures_produce_auditable_deterministic_recovery() -> None:
    invalid_fallback = ProposalOutcome(
        proposal=_proposal(),
        source="deterministic_fallback",
        receipt=replace(_receipt("fallback"), error_category="invalid_response"),
    )
    proposer = SequenceProposer([invalid_fallback, TimeoutError("service timeout")])
    outcome = RetryingProposalAdvisor(proposer, fallback=_fallback).advise(
        _context(), AgentTrigger(True, ("consecutive_failures",))
    )

    assert proposer.calls == 2
    assert outcome.source == "deterministic_recovery"
    assert outcome.proposal is not None and outcome.proposal.action is Action.INCREMENTAL_UPDATE
    assert outcome.receipt.status == "fallback_after_retry"
    assert outcome.receipt.attempts == 2
    assert outcome.receipt.error_categories == ("invalid_response", "TimeoutError")
    assert isinstance(outcome.receipt, AdvisorReceipt)
