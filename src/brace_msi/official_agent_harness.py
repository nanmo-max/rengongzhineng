"""Resumable Agent-to-official-trainer workflow with deterministic control.

This module deliberately owns every side effect after an Agent proposal. The
provider can suggest an allow-listed experiment, but only this harness can
allocate budget, invoke the immutable official trainer, evaluate a receipt, and
advance the stable checkpoint chain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Protocol

from .official_package import PackageAudit
from .official_trainer import CandidateConfig, CandidateReceipt
from .policies import Action
from .action_sandbox import (
    ActionSandboxError,
    BudgetSnapshot,
    assert_isolated_output_path,
    default_official_tool_registry,
)
from .pytrio_agent import (
    AgentCallReceipt,
    AgentContext,
    ExperimentProposal,
    ProposalOutcome,
    validate_experiment_proposal,
)


@dataclass(frozen=True)
class OfficialAgentHarnessConfig:
    rounds: int = 10
    max_candidates: int = 3
    max_cpu_seconds: float = 600.0
    max_wall_seconds: float = 600.0
    max_peak_rss_bytes: int = 8 * 1024**3
    max_agent_calls: int = 10
    max_total_input_tokens: int = 100_000
    max_total_output_tokens: int = 20_000
    allowed_epochs: tuple[int, ...] = (1, 2, 3, 5)
    allowed_learning_rate_multipliers: tuple[float, ...] = (0.25, 0.5, 1.0)

    def __post_init__(self) -> None:
        if not 1 <= self.rounds <= 100:
            raise ValueError("rounds must be in [1, 100]")
        if not 1 <= self.max_candidates <= self.rounds:
            raise ValueError("max_candidates must be in [1, rounds]")
        if self.max_cpu_seconds <= 0 or self.max_wall_seconds <= 0:
            raise ValueError("time budgets must be positive")
        if self.max_peak_rss_bytes <= 0:
            raise ValueError("memory budget must be positive")
        if self.max_agent_calls < 0:
            raise ValueError("max_agent_calls must be nonnegative")
        if self.max_total_input_tokens < 0 or self.max_total_output_tokens < 0:
            raise ValueError("token budgets must be nonnegative")
        if not self.allowed_epochs or any(value <= 0 for value in self.allowed_epochs):
            raise ValueError("allowed_epochs must be positive")
        if not self.allowed_learning_rate_multipliers or any(
            value <= 0 for value in self.allowed_learning_rate_multipliers
        ):
            raise ValueError("learning-rate multipliers must be positive")


@dataclass(frozen=True)
class OfficialAgentHarnessResult:
    profile: str
    complete: bool
    round_count: int
    candidate_count: int
    accepted_count: int
    stable_checkpoint: str
    stable_sha256: str
    stable_metric: float
    rounds: list[dict[str, Any]]
    cpu_seconds: float
    wall_seconds: float
    peak_rss_bytes: int
    total_input_tokens: int
    total_output_tokens: int
    agent_call_count: int


class ProposalProvider(Protocol):
    def propose(self, context: AgentContext) -> ProposalOutcome: ...


def official_agent_config_from_mapping(
    value: Mapping[str, Any],
) -> OfficialAgentHarnessConfig:
    """Build the formal harness limits from a versioned runtime config."""

    return OfficialAgentHarnessConfig(
        rounds=int(value.get("rounds", 10)),
        max_candidates=int(value.get("max_candidates_per_policy", 3)),
        max_cpu_seconds=float(value.get("max_cpu_seconds_per_policy", 600.0)),
        max_wall_seconds=float(value.get("max_wall_seconds_per_policy", 600.0)),
        max_peak_rss_bytes=int(
            value.get("max_peak_rss_bytes_per_policy", 8 * 1024**3)
        ),
        max_agent_calls=int(value.get("max_agent_calls", 10)),
        max_total_input_tokens=int(value.get("max_total_input_tokens", 100_000)),
        max_total_output_tokens=int(value.get("max_total_output_tokens", 20_000)),
        allowed_epochs=tuple(int(item) for item in value.get("allowed_epochs", (1, 2, 3, 5))),
        allowed_learning_rate_multipliers=tuple(
            float(item)
            for item in value.get("allowed_learning_rate_multipliers", (0.25, 0.5, 1.0))
        ),
    )


class HistoryReader:
    """Expose only aggregate, secret-free state to a proposal provider."""

    def build_context(
        self,
        package: PackageAudit,
        state: Mapping[str, Any],
        config: OfficialAgentHarnessConfig,
    ) -> AgentContext:
        history = tuple(
            {
                "round": row["round"],
                "action": row.get("action", "noop"),
                "kind": row["kind"],
                "accepted": bool(row.get("deployed", False)),
                "metric_after": row.get("metric_after"),
                "reason": row.get("reason") or row.get("gate_reason"),
                "cpu_seconds": row.get("cpu_seconds", 0.0),
            }
            for row in state["rounds"]
        )
        baseline = float(state["initial_metric"])
        stable = float(state["stable_metric"])
        scale = max(abs(baseline), 1e-12)
        improvement = (
            (stable - baseline) / scale
            if package.higher_is_better
            else (baseline - stable) / scale
        )
        return AgentContext(
            task_kind=package.task,
            metric_name=package.primary_metric,
            higher_is_better=package.higher_is_better,
            round_index=len(state["rounds"]) + 1,
            evidence={
                "baseline_metric": baseline,
                "stable_metric": stable,
                "relative_improvement": improvement,
                "failed_candidates": sum(
                    1
                    for row in state["rounds"]
                    if row.get("kind") == "candidate" and not row.get("deployed")
                ),
            },
            history=history,
            budget={
                "candidate_slots_remaining": config.max_candidates
                - int(state["candidate_count"]),
                "cpu_seconds_remaining": max(
                    0.0, config.max_cpu_seconds - float(state["cpu_seconds"])
                ),
                "wall_seconds_remaining": max(
                    0.0, config.max_wall_seconds - float(state["wall_seconds"])
                ),
            },
            capabilities={
                "official_numpy_trainer": True,
                "supports_resume": True,
                "supports_partial_fit": False,
                "allowed_epochs": list(config.allowed_epochs),
                "allowed_learning_rate_multipliers": list(
                    config.allowed_learning_rate_multipliers
                ),
            },
        )


class DeterministicOfficialProposalProvider:
    """Safe no-service comparator using the exact same execution path."""

    def __init__(self, *, candidate_rounds: int = 3) -> None:
        if candidate_rounds < 1:
            raise ValueError("candidate_rounds must be positive")
        self.candidate_rounds = candidate_rounds

    def propose(self, context: AgentContext) -> ProposalOutcome:
        if context.round_index <= self.candidate_rounds:
            action = (
                Action.INCREMENTAL_UPDATE
                if context.round_index == 1
                else Action.REPLAY_REFIT
            )
            tool = (
                "train_incremental"
                if action is Action.INCREMENTAL_UPDATE
                else "train_replay_refit"
            )
            parameters: dict[str, Any] = {"epochs": 1}
            if action is Action.REPLAY_REFIT:
                parameters["replay_fraction"] = 1.0
        else:
            action = Action.NOOP
            tool = "noop"
            parameters = {}
        proposal = ExperimentProposal(
            schema_version="brace-msi.experiment-proposal.v1",
            action=action,
            tool=tool,
            rationale="deterministic official-package baseline",
            parameters=parameters,
            max_cpu_seconds=max(
                0.001, float(context.budget["cpu_seconds_remaining"])
            ),
            max_candidates=1,
            stop_conditions=("budget_exhausted", "no_validation_gain"),
        )
        context_hash = hashlib.sha256(
            json.dumps(
                context.to_payload(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return ProposalOutcome(
            proposal=proposal,
            source="deterministic",
            receipt=AgentCallReceipt(
                status="accepted",
                model="deterministic",
                model_path_configured=False,
                prompt_sha256=context_hash,
                response_sha256=None,
                input_tokens=0,
                output_tokens=0,
                latency_seconds=0.0,
            ),
        )


class FrozenScheduleOfficialProposalProvider:
    """Replay a preregistered per-profile candidate schedule, then emit no-ops."""

    def __init__(
        self,
        package: PackageAudit,
        schedule: tuple[Mapping[str, Any], ...],
    ) -> None:
        if not schedule:
            raise ValueError("frozen candidate schedule must not be empty")
        self.package = package
        self.schedule = schedule

    def propose(self, context: AgentContext) -> ProposalOutcome:
        index = context.round_index - 1
        if index < len(self.schedule):
            item = self.schedule[index]
            epochs = int(item["epochs"])
            multiplier = float(item["learning_rate_multiplier"])
            action = Action.INCREMENTAL_UPDATE if epochs == 1 else Action.REPLAY_REFIT
            parameters: dict[str, Any] = {
                "epochs": epochs,
                "learning_rate": self.package.base_learning_rate * multiplier,
            }
            tool = "train_incremental"
            if action is Action.REPLAY_REFIT:
                tool = "train_replay_refit"
                parameters["replay_fraction"] = 1.0
        else:
            action = Action.NOOP
            parameters = {}
            tool = "noop"
        proposal = ExperimentProposal(
            schema_version="brace-msi.experiment-proposal.v1",
            action=action,
            tool=tool,
            rationale="preregistered sprint candidate schedule",
            parameters=parameters,
            max_cpu_seconds=max(0.001, float(context.budget["cpu_seconds_remaining"])),
            max_candidates=1,
            stop_conditions=("budget_exhausted", "schedule_complete"),
        )
        context_hash = hashlib.sha256(
            json.dumps(
                context.to_payload(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return ProposalOutcome(
            proposal=proposal,
            source="deterministic",
            receipt=AgentCallReceipt(
                status="accepted",
                model="deterministic-frozen-schedule",
                model_path_configured=False,
                prompt_sha256=context_hash,
                response_sha256=None,
                input_tokens=0,
                output_tokens=0,
                latency_seconds=0.0,
            ),
        )


def run_official_agent_harness(
    package: PackageAudit,
    runtime_dir: Path,
    config: OfficialAgentHarnessConfig,
    trainer: Any,
    provider: ProposalProvider,
    *,
    fallback_provider: ProposalProvider | None = None,
    max_rounds_this_call: int | None = None,
) -> OfficialAgentHarnessResult:
    runtime_dir = Path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state = _load_or_initialize(runtime_dir, package, config)
    call_limit = config.rounds if max_rounds_this_call is None else max_rounds_this_call
    if call_limit < 1:
        raise ValueError("max_rounds_this_call must be positive")
    stop_at = min(config.rounds, len(state["rounds"]) + call_limit)
    reader = HistoryReader()
    tool_registry = default_official_tool_registry()

    while len(state["rounds"]) < stop_at:
        round_number = len(state["rounds"]) + 1
        context = reader.build_context(package, state, config)
        safe_fallback = fallback_provider or DeterministicOfficialProposalProvider(
            candidate_rounds=config.max_candidates
        )
        if int(state["agent_call_count"]) >= config.max_agent_calls:
            outcome = safe_fallback.propose(context)
        else:
            try:
                outcome = provider.propose(context)
            except Exception:
                outcome = safe_fallback.propose(context)
        validate_experiment_proposal(outcome.proposal)
        if outcome.receipt.input_tokens < 0 or outcome.receipt.output_tokens < 0:
            raise ValueError("agent token counts must be nonnegative")
        if outcome.source == "pytrio":
            state["agent_call_count"] += 1
        state["total_input_tokens"] += outcome.receipt.input_tokens
        state["total_output_tokens"] += outcome.receipt.output_tokens
        base_record: dict[str, Any] = {
            "round": round_number,
            "action": outcome.proposal.action.value,
            "proposal_source": outcome.source,
            "agent_receipt": asdict(outcome.receipt),
        }

        token_budget_exceeded = (
            int(state["total_input_tokens"]) > config.max_total_input_tokens
            or int(state["total_output_tokens"]) > config.max_total_output_tokens
        )
        plan = None
        if token_budget_exceeded:
            rejection = "agent_token_budget_exceeded"
        else:
            try:
                plan = tool_registry.build_plan(
                    outcome.proposal,
                    package,
                    BudgetSnapshot(
                        candidate_slots_remaining=config.max_candidates
                        - int(state["candidate_count"]),
                        cpu_seconds_remaining=max(
                            0.0,
                            config.max_cpu_seconds - float(state["cpu_seconds"]),
                        ),
                        wall_seconds_remaining=max(
                            0.0,
                            config.max_wall_seconds - float(state["wall_seconds"]),
                        ),
                    ),
                    allowed_epochs=config.allowed_epochs,
                    allowed_learning_rate_multipliers=config.allowed_learning_rate_multipliers,
                )
                rejection = None
            except ActionSandboxError as exc:
                rejection = exc.code
        if rejection is not None:
            state["rounds"].append(
                {**base_record, "kind": "proposal_rejected", "reason": rejection}
            )
            _persist(runtime_dir, state)
            continue
        if outcome.proposal.action is Action.NOOP:
            state["rounds"].append(
                {
                    **base_record,
                    "kind": "noop",
                    "reason": "proposal_noop",
                    "tool_registry_sha256": plan.tool_registry_sha256,
                }
            )
            _persist(runtime_dir, state)
            continue

        if plan is None or plan.candidate_config is None:
            raise RuntimeError("candidate proposal produced no execution plan")
        candidate_config = plan.candidate_config
        output = runtime_dir / "candidates" / f"round-{round_number:02d}"
        assert_isolated_output_path(package.package_dir, runtime_dir, output)
        if output.exists() or output.with_name(output.name + ".failure.json").exists():
            raise FileExistsError(f"candidate output conflict: {output}")
        parent = Path(state["stable_checkpoint"])
        parent_sha = _sha256(parent)
        if parent_sha != state["stable_sha256"]:
            raise ValueError("stable checkpoint hash mismatch")
        stage_id = f"{package.profile}-agent-round-{round_number:02d}"
        receipt: CandidateReceipt = trainer.run_candidate(
            package, parent, output, candidate_config, stage_id
        )
        candidate_metrics = _validate_receipt_metrics(
            package, receipt, parent_sha, output
        )
        metric = candidate_metrics[package.primary_metric]
        prospective_cpu = float(state["cpu_seconds"]) + receipt.cpu_seconds
        prospective_wall = float(state["wall_seconds"]) + receipt.wall_seconds
        prospective_rss = max(int(state["peak_rss_bytes"]), receipt.peak_rss_bytes)
        resources_ok = (
            prospective_cpu <= config.max_cpu_seconds
            and prospective_wall <= config.max_wall_seconds
            and prospective_rss <= config.max_peak_rss_bytes
        )
        improved = (
            metric > float(state["stable_metric"])
            if package.higher_is_better
            else metric < float(state["stable_metric"])
        )
        secondary_ok = True
        if package.task == "regression" and "mae" in state["stable_metrics"]:
            secondary_ok = (
                "mae" in candidate_metrics
                and candidate_metrics["mae"] <= float(state["stable_metrics"]["mae"])
            )
        deployed = resources_ok and improved and secondary_ok
        record = {
            **base_record,
            "kind": "candidate",
            "stage_id": stage_id,
            "config": asdict(candidate_config),
            "tool_id": plan.tool_id,
            "tool_version": plan.tool_version,
            "tool_registry_sha256": plan.tool_registry_sha256,
            "estimated_training_sample_visits": plan.estimated_training_sample_visits,
            "estimated_cpu_seconds": plan.estimated_cpu_seconds,
            "parent_sha256": parent_sha,
            "checkpoint_sha256": receipt.checkpoint_sha256,
            "metric_before": state["stable_metric"],
            "metric_after": metric,
            "metrics_before": dict(state["stable_metrics"]),
            "metrics_after": candidate_metrics,
            "primary_metric": package.primary_metric,
            "deployed": deployed,
            "gate_reason": (
                "strict_public_validation_improvement"
                if deployed
                else "actual_resource_budget_exceeded"
                if not resources_ok
                else "no_strict_public_validation_improvement"
                if not improved
                else "secondary_metric_regression"
            ),
            "cpu_seconds": receipt.cpu_seconds,
            "wall_seconds": receipt.wall_seconds,
            "peak_rss_bytes": receipt.peak_rss_bytes,
            "output_dir": str(output),
        }
        state["rounds"].append(record)
        state["candidate_count"] += 1
        state["cpu_seconds"] = prospective_cpu
        state["wall_seconds"] = prospective_wall
        state["peak_rss_bytes"] = prospective_rss
        if deployed:
            state["accepted_count"] += 1
            state["stable_checkpoint"] = str(output / "checkpoint.npz")
            state["stable_sha256"] = receipt.checkpoint_sha256
            state["stable_metric"] = metric
            state["stable_metrics"] = candidate_metrics
        _persist(runtime_dir, state)

    return _result(state)


def validate_official_agent_harness(
    runtime_dir: Path,
    package: PackageAudit,
    config: OfficialAgentHarnessConfig,
) -> dict[str, Any]:
    """Reopen persisted evidence and recompute the accepted-only model chain."""

    runtime_dir = Path(runtime_dir)
    state = _load_or_initialize(runtime_dir, package, config)
    rounds = state["rounds"]
    if [row.get("round") for row in rounds] != list(range(1, len(rounds) + 1)):
        raise ValueError("round sequence is not contiguous")
    audit_rows = [
        json.loads(line)
        for line in (runtime_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    if audit_rows != rounds:
        raise ValueError("audit log does not match state")

    stable_sha = state["initial_sha256"]
    stable_checkpoint = Path(state["initial_checkpoint"])
    stable_metric = float(state["initial_metric"])
    stable_metrics = dict(state["initial_metrics"])
    candidate_count = 0
    accepted_count = 0
    cpu_seconds = 0.0
    wall_seconds = 0.0
    peak_rss_bytes = 0
    input_tokens = 0
    output_tokens = 0
    agent_call_count = 0
    for row in rounds:
        receipt_summary = row.get("agent_receipt")
        if not isinstance(receipt_summary, dict):
            raise ValueError("agent receipt is missing")
        input_tokens += int(receipt_summary["input_tokens"])
        output_tokens += int(receipt_summary["output_tokens"])
        if row.get("proposal_source") == "pytrio":
            agent_call_count += 1
        if row["kind"] != "candidate":
            if row["kind"] not in {"noop", "proposal_rejected"}:
                raise ValueError("unknown round kind")
            continue

        candidate_count += 1
        if row["parent_sha256"] != stable_sha:
            raise ValueError("candidate parent chain is invalid")
        output = Path(row["output_dir"])
        receipt_path = output / "candidate-receipt.json"
        try:
            candidate_receipt = CandidateReceipt(
                **json.loads(receipt_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise ValueError("candidate receipt is invalid") from exc
        candidate_metrics = _validate_receipt_metrics(
            package, candidate_receipt, stable_sha, output
        )
        metric = candidate_metrics[package.primary_metric]
        if (
            row["checkpoint_sha256"] != candidate_receipt.checkpoint_sha256
            or not math.isclose(float(row["metric_after"]), metric, rel_tol=0.0, abs_tol=0.0)
        ):
            raise ValueError("candidate row does not match receipt")
        cpu_seconds += candidate_receipt.cpu_seconds
        wall_seconds += candidate_receipt.wall_seconds
        peak_rss_bytes = max(peak_rss_bytes, candidate_receipt.peak_rss_bytes)
        resources_ok = (
            cpu_seconds <= config.max_cpu_seconds
            and wall_seconds <= config.max_wall_seconds
            and peak_rss_bytes <= config.max_peak_rss_bytes
        )
        improved = (
            metric > stable_metric if package.higher_is_better else metric < stable_metric
        )
        secondary_ok = True
        if package.task == "regression" and "mae" in stable_metrics:
            secondary_ok = (
                "mae" in candidate_metrics
                and candidate_metrics["mae"] <= float(stable_metrics["mae"])
            )
        expected_deployment = resources_ok and improved and secondary_ok
        if bool(row["deployed"]) != expected_deployment:
            raise ValueError("candidate deployment gate cannot be recomputed")
        if expected_deployment:
            accepted_count += 1
            stable_sha = candidate_receipt.checkpoint_sha256
            stable_checkpoint = output / "checkpoint.npz"
            stable_metric = metric
            stable_metrics = candidate_metrics

    expected_values = {
        "candidate_count": candidate_count,
        "accepted_count": accepted_count,
        "stable_sha256": stable_sha,
        "stable_checkpoint": str(stable_checkpoint),
        "stable_metric": stable_metric,
        "stable_metrics": stable_metrics,
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "agent_call_count": agent_call_count,
    }
    for key, value in expected_values.items():
        if state.get(key) != value:
            raise ValueError(f"state aggregate mismatch: {key}")
    if not math.isclose(float(state["cpu_seconds"]), cpu_seconds):
        raise ValueError("state aggregate mismatch: cpu_seconds")
    if not math.isclose(float(state["wall_seconds"]), wall_seconds):
        raise ValueError("state aggregate mismatch: wall_seconds")
    if int(state["peak_rss_bytes"]) != peak_rss_bytes:
        raise ValueError("state aggregate mismatch: peak_rss_bytes")
    return {
        "valid": True,
        "profile": package.profile,
        "round_count": len(rounds),
        "complete": len(rounds) == config.rounds,
        "candidate_count": candidate_count,
        "accepted_count": accepted_count,
        "stable_metric": stable_metric,
        "cpu_seconds": cpu_seconds,
        "wall_seconds": wall_seconds,
        "peak_rss_bytes": peak_rss_bytes,
        "agent_call_count": agent_call_count,
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
    }


def _validate_receipt_metrics(
    package: PackageAudit,
    receipt: CandidateReceipt,
    parent_sha: str,
    output: Path,
) -> dict[str, float]:
    if receipt.parent_sha256 != parent_sha:
        raise ValueError("candidate parent mismatch")
    if Path(receipt.output_dir).resolve() != output.resolve():
        raise ValueError("candidate output mismatch")
    checkpoint = output / "checkpoint.npz"
    if not checkpoint.is_file() or _sha256(checkpoint) != receipt.checkpoint_sha256:
        raise ValueError("candidate checkpoint mismatch")
    if not receipt.model_state_changed or not receipt.optimizer_state_changed:
        raise ValueError("candidate state did not change")
    metrics: dict[str, float] = {}
    for name, raw in receipt.metrics_after.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(float(raw)):
            raise ValueError("candidate metric is invalid")
        metrics[str(name)] = float(raw)
    if package.primary_metric not in metrics:
        raise ValueError("candidate primary metric is missing")
    return metrics


def _validate_receipt(
    package: PackageAudit,
    receipt: CandidateReceipt,
    parent_sha: str,
    output: Path,
) -> float:
    """Backward-compatible primary-metric validator used by existing callers."""

    return _validate_receipt_metrics(package, receipt, parent_sha, output)[
        package.primary_metric
    ]


def _initial_state(
    package: PackageAudit, config: OfficialAgentHarnessConfig
) -> dict[str, Any]:
    return {
        "format": "brace-msi.official-agent-harness.v1",
        "profile": package.profile,
        "task": package.task,
        "primary_metric": package.primary_metric,
        "higher_is_better": package.higher_is_better,
        "package_tree_sha256": package.package_tree_sha256,
        "initial_checkpoint": str(package.checkpoint_path),
        "initial_sha256": package.checkpoint_sha256,
        "initial_metric": package.baseline_metric,
        "initial_metrics": dict(package.baseline_metrics),
        "stable_checkpoint": str(package.checkpoint_path),
        "stable_sha256": package.checkpoint_sha256,
        "stable_metric": package.baseline_metric,
        "stable_metrics": dict(package.baseline_metrics),
        "config_sha256": _config_sha256(config),
        "expected_rounds": config.rounds,
        "rounds": [],
        "candidate_count": 0,
        "accepted_count": 0,
        "cpu_seconds": 0.0,
        "wall_seconds": 0.0,
        "peak_rss_bytes": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "agent_call_count": 0,
        "official_package": True,
        "official_scoring_ready": False,
    }


def _load_or_initialize(
    runtime_dir: Path, package: PackageAudit, config: OfficialAgentHarnessConfig
) -> dict[str, Any]:
    path = runtime_dir / "state.json"
    if not path.exists():
        if _sha256(package.checkpoint_path) != package.checkpoint_sha256:
            raise ValueError("official initial checkpoint hash mismatch")
        return _initial_state(package, config)
    state = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "format": "brace-msi.official-agent-harness.v1",
        "profile": package.profile,
        "task": package.task,
        "package_tree_sha256": package.package_tree_sha256,
        "initial_sha256": package.checkpoint_sha256,
        "config_sha256": _config_sha256(config),
        "expected_rounds": config.rounds,
    }
    for key, value in expected.items():
        if state.get(key) != value:
            raise ValueError(f"agent harness state mismatch: {key}")
    if len(state.get("rounds", [])) > config.rounds:
        raise ValueError("agent harness has too many rounds")
    return state


def _persist(runtime_dir: Path, state: Mapping[str, Any]) -> None:
    _atomic_json(runtime_dir / "state.json", state)
    audit = runtime_dir / "audit.jsonl"
    temporary = audit.with_name(audit.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in state["rounds"]:
            handle.write(
                json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                + "\n"
            )
    os.replace(temporary, audit)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _config_sha256(config: OfficialAgentHarnessConfig) -> str:
    return hashlib.sha256(
        json.dumps(asdict(config), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _result(state: Mapping[str, Any]) -> OfficialAgentHarnessResult:
    return OfficialAgentHarnessResult(
        profile=state["profile"],
        complete=len(state["rounds"]) == int(state["expected_rounds"]),
        round_count=len(state["rounds"]),
        candidate_count=int(state["candidate_count"]),
        accepted_count=int(state["accepted_count"]),
        stable_checkpoint=state["stable_checkpoint"],
        stable_sha256=state["stable_sha256"],
        stable_metric=float(state["stable_metric"]),
        rounds=list(state["rounds"]),
        cpu_seconds=float(state["cpu_seconds"]),
        wall_seconds=float(state["wall_seconds"]),
        peak_rss_bytes=int(state["peak_rss_bytes"]),
        total_input_tokens=int(state["total_input_tokens"]),
        total_output_tokens=int(state["total_output_tokens"]),
        agent_call_count=int(state["agent_call_count"]),
    )
