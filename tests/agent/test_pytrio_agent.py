from __future__ import annotations

import json

import pytest

from brace_msi.policies import Action
from brace_msi.pytrio_agent import (
    AgentContext,
    build_agent_prompt,
    ExperimentProposal,
    parse_experiment_proposal,
    PyTrioAgentClient,
    PyTrioAgentConfig,
    SamplingResult,
)


class FakeTransport:
    def __init__(self, result: SamplingResult | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def sample(self, prompt: str, **kwargs: object) -> SamplingResult:
        self.calls.append({"prompt": prompt, **kwargs})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def context() -> AgentContext:
    return AgentContext(
        task_kind="classification",
        metric_name="macro_f1",
        higher_is_better=True,
        round_index=2,
        evidence={"performance_drop": 0.08, "drift_score": 0.31},
        history=({"action": "noop", "accepted": False},),
        budget={"cpu_seconds_remaining": 120.0, "candidate_slots_remaining": 2},
        capabilities={"supports_partial_fit": True},
    )


def fallback(_: AgentContext) -> ExperimentProposal:
    return ExperimentProposal(
        schema_version="brace-msi.experiment-proposal.v1",
        action=Action.INCREMENTAL_UPDATE,
        tool="train_incremental",
        rationale="deterministic performance trigger",
        parameters={"epochs": 1},
        max_cpu_seconds=30.0,
        max_candidates=1,
        stop_conditions=("budget_exhausted",),
    )


def valid_response() -> str:
    return json.dumps(
        {
            "schema_version": "brace-msi.experiment-proposal.v1",
            "action": "replay_refit",
            "tool": "train_replay_refit",
            "rationale": "recent degradation and one failed low-cost update",
            "parameters": {"epochs": 2, "replay_fraction": 0.5},
            "max_cpu_seconds": 45.0,
            "max_candidates": 1,
            "stop_conditions": ["no_validation_gain", "budget_exhausted"],
        }
    )


def test_parser_accepts_qwen_im_end_suffix_but_rejects_other_trailing_text() -> None:
    proposal = parse_experiment_proposal(valid_response() + "<|im_end|>\n")

    assert proposal.action is Action.REPLAY_REFIT
    with pytest.raises(json.JSONDecodeError):
        parse_experiment_proposal(valid_response() + " trailing text")


def test_valid_structured_proposal_records_only_hashes_and_usage() -> None:
    transport = FakeTransport(
        SamplingResult(valid_response(), input_tokens=211, output_tokens=83)
    )
    client = PyTrioAgentClient(
        PyTrioAgentConfig(model="Qwen/Qwen3.5-4B", model_path="trio://persisted"),
        transport=transport,
        fallback=fallback,
    )

    outcome = client.propose(context())

    assert outcome.source == "pytrio"
    assert outcome.proposal.action is Action.REPLAY_REFIT
    assert outcome.proposal.parameters == {"epochs": 2, "replay_fraction": 0.5}
    assert outcome.receipt.status == "accepted"
    assert outcome.receipt.input_tokens == 211
    assert outcome.receipt.output_tokens == 83
    assert len(outcome.receipt.prompt_sha256) == 64
    assert len(outcome.receipt.response_sha256 or "") == 64
    assert not hasattr(outcome.receipt, "raw_prompt")
    assert not hasattr(outcome.receipt, "raw_response")
    assert transport.calls[0]["model"] == "Qwen/Qwen3.5-4B"
    assert transport.calls[0]["model_path"] == "trio://persisted"


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        json.dumps({"schema_version": "wrong", "action": "noop"}),
        json.dumps(
            {
                "schema_version": "brace-msi.experiment-proposal.v1",
                "action": "incremental_update",
                "tool": "shell",
                "rationale": "run a command",
                "parameters": {"command": "echo unsafe"},
                "max_cpu_seconds": 1,
                "max_candidates": 1,
                "stop_conditions": [],
            }
        ),
    ],
)
def test_invalid_output_falls_back_without_lowering_safety(raw: str) -> None:
    client = PyTrioAgentClient(
        PyTrioAgentConfig(),
        transport=FakeTransport(SamplingResult(raw, 10, 10)),
        fallback=fallback,
    )

    outcome = client.propose(context())

    assert outcome.source == "deterministic_fallback"
    assert outcome.proposal.action is Action.INCREMENTAL_UPDATE
    assert outcome.receipt.status == "fallback"
    assert outcome.receipt.error_category == "invalid_response"


def test_transport_failure_falls_back_and_is_auditable() -> None:
    client = PyTrioAgentClient(
        PyTrioAgentConfig(),
        transport=FakeTransport(TimeoutError("secret service detail")),
        fallback=fallback,
    )

    outcome = client.propose(context())

    assert outcome.source == "deterministic_fallback"
    assert outcome.receipt.error_category == "transport_error"
    assert outcome.receipt.error_detail == "TimeoutError"


def test_secret_bearing_context_is_rejected_before_transport() -> None:
    transport = FakeTransport(SamplingResult(valid_response(), 1, 1))
    client = PyTrioAgentClient(
        PyTrioAgentConfig(), transport=transport, fallback=fallback
    )
    unsafe = context()
    unsafe = AgentContext(
        **{
            **unsafe.__dict__,
            "evidence": {"performance_drop": 0.1, "api_key": "must-not-leak"},
        }
    )

    with pytest.raises(ValueError, match="secret-bearing key"):
        client.propose(unsafe)

    assert transport.calls == []


def test_config_contains_no_credentials_and_defaults_to_confirmed_model() -> None:
    config = PyTrioAgentConfig()

    assert config.model == "Qwen/Qwen3.5-4B"
    assert "key" not in repr(config).lower()
    assert "credential" not in repr(config).lower()


def test_prompt_only_advertises_runtime_executable_actions() -> None:
    payload = context().to_payload()
    payload["capabilities"]["allowed_actions"] = [
        "noop",
        "incremental_update",
        "replay_refit",
    ]

    prompt = build_agent_prompt(payload)

    schema_line = next(
        line for line in prompt.splitlines() if line.startswith("PROPOSAL_SCHEMA=")
    )
    schema = json.loads(schema_line.split("=", 1)[1])
    assert schema["action"] == [
        "incremental_update",
        "noop",
        "replay_refit",
    ]
    assert set(schema["tool_mapping"]) == set(schema["action"])


def test_prompt_exposes_minimum_candidate_policy_without_task_identity_rules() -> None:
    payload = context().to_payload()
    payload["evidence"]["minimum_candidate_events_remaining"] = 2

    prompt = build_agent_prompt(payload)

    policy_line = next(
        line for line in prompt.splitlines() if line.startswith("CONTROL_POLICY=")
    )
    policy = json.loads(policy_line.split("=", 1)[1])
    assert policy["minimum_candidate_events_remaining"] == 2
    assert "dataset" not in policy_line.lower()
    assert policy["minimum_candidate_rule"]["first_action"] == "incremental_update"
