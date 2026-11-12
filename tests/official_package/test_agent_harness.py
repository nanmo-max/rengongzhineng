from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from brace_msi.official_agent_harness import (
    DeterministicOfficialProposalProvider,
    FrozenScheduleOfficialProposalProvider,
    OfficialAgentHarnessConfig,
    official_agent_config_from_mapping,
    run_official_agent_harness,
    validate_official_agent_harness,
)
from brace_msi.official_package import audit_package_root
from brace_msi.official_trainer import CandidateReceipt
from brace_msi.policies import Action
from brace_msi.pytrio_agent import (
    AgentCallReceipt,
    AgentContext,
    ExperimentProposal,
    ProposalOutcome,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


@pytest.fixture(scope="module")
def audit_a():
    config = json.loads(
        (REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8")
    )
    return audit_package_root(PACKAGE_ROOT, config)["A"]


class StaticProvider:
    def __init__(self, proposals: list[ExperimentProposal]) -> None:
        self.proposals = iter(proposals)
        self.contexts: list[AgentContext] = []

    def propose(self, context: AgentContext) -> ProposalOutcome:
        self.contexts.append(context)
        proposal = next(self.proposals)
        return ProposalOutcome(
            proposal=proposal,
            source="pytrio",
            receipt=AgentCallReceipt(
                status="accepted",
                model="Qwen/Qwen3.5-4B",
                model_path_configured=False,
                prompt_sha256="a" * 64,
                response_sha256="b" * 64,
                input_tokens=100,
                output_tokens=40,
                latency_seconds=0.2,
            ),
        )


class FakeTrainer:
    def __init__(self, metrics: list[float | dict[str, float]]) -> None:
        self.metrics = iter(metrics)
        self.calls: list[dict] = []

    def run_candidate(self, package, parent, output_dir, config, stage_id):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True)
        checkpoint = output_dir / "checkpoint.npz"
        checkpoint.write_bytes(f"{stage_id}:{len(self.calls)}".encode())
        parent_sha = hashlib.sha256(Path(parent).read_bytes()).hexdigest()
        child_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        metric_value = next(self.metrics)
        metrics_after = (
            metric_value
            if isinstance(metric_value, dict)
            else {package.primary_metric: metric_value}
        )
        receipt = CandidateReceipt(
            stage_id=stage_id,
            profile=package.profile,
            parent_sha256=parent_sha,
            checkpoint_sha256=child_sha,
            metrics_before={package.primary_metric: package.baseline_metric},
            metrics_after=metrics_after,
            initial_epochs=20,
            final_epochs=20 + config.epochs,
            initial_steps=80,
            final_steps=81,
            model_state_changed=True,
            optimizer_state_changed=True,
            wall_seconds=0.2,
            cpu_seconds=0.1,
            peak_rss_bytes=1024,
            output_dir=str(output_dir),
            validation_file_reads=1,
            validation_metric_evaluations=2,
        )
        self.calls.append(
            {
                "parent_sha256": parent_sha,
                "config": asdict(config),
                "stage_id": stage_id,
            }
        )
        (output_dir / "candidate-receipt.json").write_text(
            json.dumps(asdict(receipt)), encoding="utf-8"
        )
        return receipt


def proposal(action: Action, **parameters) -> ExperimentProposal:
    tools = {
        Action.NOOP: "noop",
        Action.INCREMENTAL_UPDATE: "train_incremental",
        Action.REPLAY_REFIT: "train_replay_refit",
        Action.FAMILY_SWITCH: "train_family_switch",
    }
    return ExperimentProposal(
        schema_version="brace-msi.experiment-proposal.v1",
        action=action,
        tool=tools[action],
        rationale="test proposal",
        parameters=parameters,
        max_cpu_seconds=5.0,
        max_candidates=1,
        stop_conditions=("no_validation_gain",),
    )


def config(**updates) -> OfficialAgentHarnessConfig:
    values = {
        "rounds": 3,
        "max_candidates": 3,
        "minimum_candidate_events": 0,
        "max_cpu_seconds": 30.0,
        "max_wall_seconds": 30.0,
        "max_peak_rss_bytes": 1024 * 1024,
        "max_agent_calls": 3,
        "max_total_input_tokens": 1000,
        "max_total_output_tokens": 1000,
        "allowed_epochs": (1, 2),
        "allowed_learning_rate_multipliers": (0.5, 1.0),
    }
    values.update(updates)
    if "rounds" in updates and "max_candidates" not in updates:
        values["max_candidates"] = min(values["max_candidates"], values["rounds"])
    return OfficialAgentHarnessConfig(**values)


def test_minimum_candidate_guard_overrides_agent_noop_and_keeps_receipt(
    tmp_path: Path, audit_a
) -> None:
    provider = StaticProvider([proposal(Action.NOOP)])
    trainer = FakeTrainer([0.72])

    result = run_official_agent_harness(
        audit_a,
        tmp_path / "minimum-guard",
        config(rounds=1, max_candidates=1, minimum_candidate_events=1),
        trainer,
        provider,
        fallback_provider=DeterministicOfficialProposalProvider(candidate_rounds=1),
    )

    assert result.candidate_count == 1
    assert result.agent_call_count == 1
    assert result.total_input_tokens == 100
    assert result.rounds[0]["action"] == "incremental_update"
    assert result.rounds[0]["suggested_action"] == "noop"
    assert result.rounds[0]["guard_override_reason"] == "minimum_candidate_events"
    assert provider.contexts[0].evidence["minimum_candidate_events_remaining"] == 1


def test_agent_rounds_train_gate_and_never_chain_rejected_candidate(tmp_path: Path, audit_a) -> None:
    provider = StaticProvider(
        [
            proposal(Action.INCREMENTAL_UPDATE, epochs=1),
            proposal(Action.REPLAY_REFIT, epochs=2, replay_fraction=1.0),
            proposal(Action.INCREMENTAL_UPDATE, epochs=1),
        ]
    )
    trainer = FakeTrainer([0.72, 0.70, 0.73])

    result = run_official_agent_harness(
        audit_a, tmp_path / "run", config(), trainer, provider
    )

    assert result.complete is True
    assert result.candidate_count == 3
    assert result.accepted_count == 2
    assert [row["deployed"] for row in result.rounds] == [True, False, True]
    assert trainer.calls[1]["parent_sha256"] == result.rounds[0]["checkpoint_sha256"]
    assert trainer.calls[2]["parent_sha256"] == result.rounds[0]["checkpoint_sha256"]
    assert trainer.calls[2]["parent_sha256"] != result.rounds[1]["checkpoint_sha256"]
    assert provider.contexts[2].history[1]["accepted"] is False
    assert result.total_input_tokens == 300
    assert result.total_output_tokens == 120
    assert result.agent_call_count == 3


def test_unsupported_agent_action_is_rejected_without_training(tmp_path: Path, audit_a) -> None:
    provider = StaticProvider(
        [proposal(Action.FAMILY_SWITCH, model_family="extra_trees")]
    )
    trainer = FakeTrainer([])

    result = run_official_agent_harness(
        audit_a, tmp_path / "unsupported", config(rounds=1), trainer, provider
    )

    assert trainer.calls == []
    assert result.rounds[0]["kind"] == "proposal_rejected"
    assert result.rounds[0]["reason"] == "action_not_executable"


def test_budget_is_checked_before_candidate_directory_exists(tmp_path: Path, audit_a) -> None:
    provider = StaticProvider([proposal(Action.INCREMENTAL_UPDATE, epochs=1)])
    trainer = FakeTrainer([])
    runtime = tmp_path / "budget"

    result = run_official_agent_harness(
        audit_a,
        runtime,
        config(rounds=1, max_cpu_seconds=1.0),
        trainer,
        provider,
    )

    assert result.rounds[0]["kind"] == "proposal_rejected"
    assert result.rounds[0]["reason"] == "proposal_cpu_budget_exceeds_remaining"
    assert not (runtime / "candidates").exists()


def test_agent_token_overrun_is_recorded_and_never_trains(tmp_path: Path, audit_a) -> None:
    provider = StaticProvider([proposal(Action.INCREMENTAL_UPDATE, epochs=1)])
    trainer = FakeTrainer([])

    result = run_official_agent_harness(
        audit_a,
        tmp_path / "tokens",
        config(rounds=1, max_total_input_tokens=10),
        trainer,
        provider,
    )

    assert trainer.calls == []
    assert result.rounds[0]["reason"] == "agent_token_budget_exceeded"
    assert result.total_input_tokens == 100


def test_deterministic_provider_uses_same_harness_and_resume_is_idempotent(tmp_path: Path, audit_a) -> None:
    trainer = FakeTrainer([0.72, 0.73])
    runtime = tmp_path / "deterministic"
    provider = DeterministicOfficialProposalProvider(candidate_rounds=2)

    first = run_official_agent_harness(
        audit_a,
        runtime,
        config(rounds=2),
        trainer,
        provider,
        max_rounds_this_call=1,
    )
    finished = run_official_agent_harness(
        audit_a, runtime, config(rounds=2), trainer, provider
    )
    repeated = run_official_agent_harness(
        audit_a, runtime, config(rounds=2), trainer, provider
    )

    assert first.complete is False
    assert finished.complete is True
    assert repeated == finished
    assert len(trainer.calls) == 2
    assert all(row["proposal_source"] == "deterministic" for row in finished.rounds)


def test_frozen_schedule_provider_emits_selected_actions_then_noops(audit_a) -> None:
    provider = FrozenScheduleOfficialProposalProvider(
        audit_a,
        (
            {"epochs": 5, "learning_rate_multiplier": 3.0},
            {"epochs": 1, "learning_rate_multiplier": 0.3},
        ),
    )
    harness_config = config(
        rounds=3,
        allowed_epochs=(1, 3, 5),
        allowed_learning_rate_multipliers=(0.3, 1.0, 3.0),
    )
    state = {
        "initial_metric": audit_a.baseline_metric,
        "stable_metric": audit_a.baseline_metric,
        "rounds": [],
        "candidate_count": 0,
        "cpu_seconds": 0.0,
        "wall_seconds": 0.0,
    }
    reader = __import__(
        "brace_msi.official_agent_harness", fromlist=["HistoryReader"]
    ).HistoryReader()

    first = provider.propose(reader.build_context(audit_a, state, harness_config))
    state["rounds"].append({"round": 1, "kind": "candidate", "deployed": True})
    state["candidate_count"] = 1
    second = provider.propose(reader.build_context(audit_a, state, harness_config))
    state["rounds"].append({"round": 2, "kind": "candidate", "deployed": False})
    state["candidate_count"] = 2
    third = provider.propose(reader.build_context(audit_a, state, harness_config))

    assert first.proposal.action is Action.REPLAY_REFIT
    assert first.proposal.parameters["epochs"] == 5
    assert first.proposal.parameters["learning_rate"] == pytest.approx(
        audit_a.base_learning_rate * 3.0
    )
    assert second.proposal.action is Action.INCREMENTAL_UPDATE
    assert second.proposal.parameters["learning_rate"] == pytest.approx(
        audit_a.base_learning_rate * 0.3
    )
    assert third.proposal.action is Action.NOOP


def test_regression_gate_rejects_primary_gain_when_mae_worsens(tmp_path: Path, audit_a) -> None:
    package = replace(
        audit_a,
        task="regression",
        primary_metric="rmse",
        higher_is_better=False,
        baseline_metric=10.0,
        baseline_metrics={"rmse": 10.0, "mae": 8.0},
    )
    result = run_official_agent_harness(
        package,
        tmp_path / "regression-risk",
        config(rounds=1),
        FakeTrainer([{"rmse": 9.0, "mae": 9.0}]),
        DeterministicOfficialProposalProvider(candidate_rounds=1),
    )

    assert result.rounds[0]["deployed"] is False
    assert result.rounds[0]["gate_reason"] == "secondary_metric_regression"


def test_runtime_config_mapping_keeps_agent_and_trainer_budgets_explicit() -> None:
    parsed = official_agent_config_from_mapping(
        {
            "rounds": 10,
            "max_candidates_per_policy": 3,
            "minimum_candidate_events": 3,
            "max_cpu_seconds_per_policy": 40,
            "max_wall_seconds_per_policy": 50,
            "max_peak_rss_bytes_per_policy": 1234,
            "max_agent_calls": 7,
            "max_total_input_tokens": 8000,
            "max_total_output_tokens": 2000,
            "allowed_epochs": [1, 2],
            "allowed_learning_rate_multipliers": [0.5, 1.0],
        }
    )

    assert parsed.max_candidates == 3
    assert parsed.minimum_candidate_events == 3
    assert parsed.max_cpu_seconds == 40
    assert parsed.max_agent_calls == 7
    assert parsed.max_total_output_tokens == 2000


def test_machine_validator_recomputes_parent_chain_gate_and_usage(tmp_path: Path, audit_a) -> None:
    runtime = tmp_path / "validate"
    harness_config = config(rounds=2, max_candidates=2)
    run_official_agent_harness(
        audit_a,
        runtime,
        harness_config,
        FakeTrainer([0.72, 0.70]),
        DeterministicOfficialProposalProvider(candidate_rounds=2),
    )

    result = validate_official_agent_harness(runtime, audit_a, harness_config)

    assert result["valid"] is True
    assert result["candidate_count"] == 2
    state_path = runtime / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["rounds"][1]["deployed"] = True
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (runtime / "audit.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in state["rounds"]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="deployment gate"):
        validate_official_agent_harness(runtime, audit_a, harness_config)
