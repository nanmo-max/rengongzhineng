"""Integrated, platform-neutral implementation of the controlled dual loop."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import pickle
import tempfile
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error

from .audit import JsonlAuditLog
from .data.types import TaskStream
from .dual_loop import (
    CandidateOutcome,
    CandidateSpec,
    DecisionContext,
    DualLoopController,
    paired_shadow_reward,
)
from .evidence import build_evidence
from .modeling import CpuModelAdapter
from .online_data import (
    BufferSlice,
    candidate_training_data,
    materialize_round_data,
    partition_feedback,
    partition_initial_data,
    promote_gate_to_replay,
)
from .policy_learning import ActionObservation, ActionValueTable, EvidenceState, rank_actions
from .protocol import ProtocolMode, SimulatedSdkAdapter
from .resources import ResourceTracker, ResourceUsage
from .safety import GateConfig, evaluate_candidate


@dataclass(frozen=True)
class ControlledHarnessConfig:
    seed: int = 20261113
    max_rounds: int = 10
    max_total_candidates: int = 8
    total_cpu_budget_seconds: float = 120.0
    performance_drop_threshold: float = 0.05
    drift_threshold: float = 0.3
    min_gate_gain: float = 0.0
    max_anchor_degradation: float = 0.02
    min_gate_samples: int = 8
    gate_fraction: float = 0.2
    enable_shadow: bool = True

    def __post_init__(self) -> None:
        if self.max_rounds != 10:
            raise ValueError("formal controlled loop requires ten decision rounds")
        if not 1 <= self.max_total_candidates <= 8:
            raise ValueError("max_total_candidates must be in [1, 8]")
        if self.total_cpu_budget_seconds <= 0:
            raise ValueError("CPU budget must be positive")


@dataclass(frozen=True)
class ControlledRoundResult:
    round_index: int
    batch_id: str
    primary_metric: float
    secondary_metric: float
    performance_drop: float
    drift_score: float
    actions: tuple[str, ...]
    decision: str
    decision_count: int
    candidate_count: int
    deployed_model_id: str
    shadow_delta: float | None
    shadow_confidence: str | None
    cpu_seconds: float
    peak_rss_bytes: int


@dataclass(frozen=True)
class ControlledRunSummary:
    task_kind: str
    complete: bool
    rounds: tuple[ControlledRoundResult, ...]
    total_candidates: int
    real_experiment_count: int
    stable_model_id: str


@dataclass
class _HarnessState:
    task_kind: str
    feature_count: int
    stable: CpuModelAdapter
    stable_model_id: str
    reference_X: np.ndarray
    anchor: BufferSlice
    reference_primary: float
    quarantine: list[BufferSlice] = field(default_factory=list)
    replay: list[BufferSlice] = field(default_factory=list)
    shadow_model: CpuModelAdapter | None = None
    shadow_action: str | None = None
    shadow_evidence: EvidenceState | None = None
    cpu_used: float = 0.0
    rounds: list[ControlledRoundResult] = field(default_factory=list)


def _atomic_pickle(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _metrics(task_kind: str, y: np.ndarray, predictions: np.ndarray) -> tuple[float, float]:
    if task_kind == "classification":
        return (
            float(f1_score(y, predictions, average="macro", zero_division=0)),
            float(accuracy_score(y, predictions)),
        )
    return (
        float(mean_squared_error(y, predictions) ** 0.5),
        float(mean_absolute_error(y, predictions)),
    )


def _prediction_digest(predictions: np.ndarray) -> str:
    array = np.ascontiguousarray(predictions)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(str(array.shape).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


class ControlledDualLoopHarness:
    def __init__(self, root: Path, config: ControlledHarnessConfig) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.controller = DualLoopController(
            self.root / "controller",
            minimum_gate_gain=config.min_gate_gain,
            max_rounds=config.max_rounds,
            max_total_candidates=config.max_total_candidates,
        )
        self.values = ActionValueTable(
            self.root / "action-values.json",
            weak_priors={
                "INCREMENTAL_UPDATE": {"mean_reward": 0.0, "pseudo_count": 0.25},
                "REPLAY_REFIT": {"mean_reward": 0.0, "pseudo_count": 0.25},
            },
        )
        self.state_path = self.root / "harness-state.pkl"

    def run(
        self,
        stream: TaskStream,
        *,
        max_rounds_this_call: int | None = None,
    ) -> ControlledRunSummary:
        if len(stream.development) < self.config.max_rounds:
            raise ValueError("stream must provide at least ten development batches")
        if not stream.all_sample_ids_are_disjoint():
            raise ValueError("stream sample IDs must be globally disjoint")
        state = self._load_or_initialize(stream)
        if state.task_kind != stream.task_kind or state.feature_count != stream.initial.X.shape[1]:
            raise ValueError("resumed stream is incompatible with persisted task signature")
        logger = JsonlAuditLog(self.root / "audit.jsonl", truncate=not bool(state.rounds))
        protocol = self._restore_protocol(stream, len(state.rounds))
        start = len(state.rounds)
        stop = self.config.max_rounds
        if max_rounds_this_call is not None:
            stop = min(stop, start + max(0, max_rounds_this_call))

        for offset in range(start, stop):
            batch = stream.development[offset]
            round_index = offset + 1
            protocol.request_predictions(batch.batch_id, batch.sample_ids)
            with ResourceTracker() as prediction_tracker:
                predictions = np.asarray(state.stable.predict(batch.X))
            prediction_usage = prediction_tracker.usage
            assert prediction_usage is not None
            protocol.submit_predictions(batch.batch_id, batch.sample_ids)

            shadow_delta: float | None = None
            shadow_confidence: str | None = None
            shadow_usage = ResourceUsage(0.0, 0.0, 0, 0, 0)
            if self.config.enable_shadow and state.shadow_model is not None:
                with ResourceTracker() as tracker:
                    shadow_predictions = np.asarray(state.shadow_model.predict(batch.X))
                shadow_usage = tracker.usage or shadow_usage
            else:
                shadow_predictions = None

            protocol.provide_feedback(batch.batch_id, batch.sample_ids)
            primary, secondary = _metrics(stream.task_kind, batch.y, predictions)
            higher_is_better = stream.task_kind == "classification"
            evidence = build_evidence(
                state.reference_X,
                batch.X,
                current_metric=primary,
                reference_metric=state.reference_primary,
                higher_is_better=higher_is_better,
            )
            evidence_state = EvidenceState(
                task_kind=stream.task_kind,
                performance_drop=max(-1.0, min(1.0, evidence.performance_drop)),
                drift_score=max(0.0, min(1.0, evidence.drift_score)),
                failure_streak=0,
                remaining_budget_fraction=self._remaining_fraction(state),
                action_uncertainty=0.5,
            )

            if (
                shadow_predictions is not None
                and state.shadow_action is not None
                and state.shadow_evidence is not None
            ):
                reward = paired_shadow_reward(
                    task_kind=stream.task_kind,
                    y_true=batch.y,
                    deployed_predictions=predictions,
                    predecessor_predictions=shadow_predictions,
                    cpu_seconds=shadow_usage.cpu_seconds,
                )
                shadow_delta = reward.primary_delta
                shadow_confidence = reward.confidence
                self.values.record(
                    "active-task",
                    state.shadow_evidence,
                    ActionObservation(
                        action=state.shadow_action,
                        primary_delta=reward.primary_delta,
                        cpu_seconds=shadow_usage.cpu_seconds,
                        peak_memory_mb=shadow_usage.peak_rss_bytes / (1024 * 1024),
                        token_count=0,
                        model_bytes=0,
                        accepted=True,
                        succeeded=True,
                        reward_source="delayed_shadow",
                        attribution_confidence="paired",
                        round_index=round_index,
                    ),
                )
                state.shadow_model = None
                state.shadow_action = None
                state.shadow_evidence = None

            update, gate = partition_feedback(
                batch.X,
                batch.y,
                batch.sample_ids,
                task_kind=stream.task_kind,
                batch_id=batch.batch_id,
                round_index=round_index,
                gate_fraction=self.config.gate_fraction,
                groups=batch.group_ids or None,
                seed=self.config.seed,
            )
            still_quarantined: list[BufferSlice] = []
            for previous_gate in state.quarantine:
                if previous_gate.eligible_replay_round is not None and round_index >= previous_gate.eligible_replay_round:
                    state.replay.append(
                        promote_gate_to_replay(previous_gate, current_round=round_index)
                    )
                else:
                    still_quarantined.append(previous_gate)
            state.quarantine = still_quarantined
            materialize_round_data(
                self.root / "round-data" / f"round-{round_index:03d}",
                round_index=round_index,
                update=update,
                replay_buffers=state.replay,
                gate=gate,
                anchor=state.anchor,
            )

            remaining_cpu = max(0.0, self.config.total_cpu_budget_seconds - state.cpu_used)
            self.controller.begin_round(
                DecisionContext(
                    round_index=round_index,
                    batch_id=batch.batch_id,
                    stable_model_id=state.stable_model_id,
                    submitted_prediction_digest=_prediction_digest(predictions),
                    labels_open=True,
                    remaining_cpu_seconds=min(remaining_cpu, self.config.total_cpu_budget_seconds * 0.2),
                    evidence={
                        "performance_drop": evidence.performance_drop,
                        "drift_score": evidence.drift_score,
                    },
                )
            )

            actions: list[str] = []
            candidate_count = 0
            decision = "noop"
            candidate_model: CpuModelAdapter | None = None
            predecessor_for_shadow: CpuModelAdapter | None = None
            first_action = self._select_action(state, evidence_state)
            if first_action is None:
                self.controller.plan_first_candidate(None, reason="stable evidence or reserved budget")
                commit = self.controller.commit_round(
                    decision="noop", deployed_model_id=state.stable_model_id
                )
            else:
                spec = self._candidate_spec(first_action, round_index, 1, remaining_cpu)
                self.controller.plan_first_candidate(spec, reason="identity-free evidence trigger")
                outcome, candidate_model, usage = self._execute_candidate(
                    state, update, gate, first_action, round_index, spec.candidate_id
                )
                actions.append(first_action)
                candidate_count += 1
                state.cpu_used += usage.cpu_seconds
                self.controller.record_candidate_outcome(outcome)
                self._record_gate_observation(evidence_state, first_action, outcome, usage, round_index)

                if (
                    not outcome.accepted
                    and first_action != "REPLAY_REFIT"
                    and state.replay
                    and self._can_train(state, round_index)
                    and self.controller.state.total_candidates + 1 < self.config.max_total_candidates
                ):
                    second_action = "REPLAY_REFIT"
                    second_spec = self._candidate_spec(second_action, round_index, 2, remaining_cpu)
                    self.controller.escalate_second_candidate(
                        second_spec,
                        new_evidence="first candidate failed SafetyGate",
                        budget_remaining=True,
                    )
                    second_outcome, second_model, second_usage = self._execute_candidate(
                        state,
                        update,
                        gate,
                        second_action,
                        round_index,
                        second_spec.candidate_id,
                    )
                    actions.append(second_action)
                    candidate_count += 1
                    state.cpu_used += second_usage.cpu_seconds
                    self.controller.record_candidate_outcome(second_outcome)
                    self._record_gate_observation(
                        evidence_state, second_action, second_outcome, second_usage, round_index
                    )
                    if second_outcome.accepted:
                        outcome, candidate_model = second_outcome, second_model

                if outcome.accepted and candidate_model is not None:
                    predecessor_for_shadow = state.stable
                    deployed_id = f"model-r{round_index:02d}-{candidate_count}"
                    commit = self.controller.commit_round(
                        decision="deploy", deployed_model_id=deployed_id
                    )
                    state.stable = candidate_model
                    state.stable_model_id = deployed_id
                    state.shadow_model = predecessor_for_shadow
                    state.shadow_action = actions[-1]
                    state.shadow_evidence = evidence_state
                    decision = "deploy"
                else:
                    commit = self.controller.commit_round(
                        decision="reject", deployed_model_id=state.stable_model_id
                    )
                    decision = "reject"

            state.quarantine.append(gate)
            protocol.request_batch_commit(batch.batch_id)
            total_cpu = prediction_usage.cpu_seconds + shadow_usage.cpu_seconds
            result = ControlledRoundResult(
                round_index=round_index,
                batch_id=batch.batch_id,
                primary_metric=primary,
                secondary_metric=secondary,
                performance_drop=evidence.performance_drop,
                drift_score=evidence.drift_score,
                actions=tuple(actions),
                decision=decision,
                decision_count=1,
                candidate_count=candidate_count,
                deployed_model_id=commit.deployed_model_id,
                shadow_delta=shadow_delta,
                shadow_confidence=shadow_confidence,
                cpu_seconds=total_cpu,
                peak_rss_bytes=max(prediction_usage.peak_rss_bytes, shadow_usage.peak_rss_bytes),
            )
            state.rounds.append(result)
            logger.write_once(
                f"round-{round_index:03d}",
                "controlled_round_committed",
                {
                    "task_id": stream.task_id,
                    "batch_id": batch.batch_id,
                    "batch_index": round_index,
                    "primary_metric": primary,
                    "secondary_metric": secondary,
                    "performance_drop": evidence.performance_drop,
                    "drift_score": evidence.drift_score,
                    "action": "+".join(actions) if actions else "noop",
                    "accepted": decision == "deploy",
                    "cpu_seconds": total_cpu,
                    "peak_rss_bytes": result.peak_rss_bytes,
                },
            )
            _atomic_pickle(self.state_path, state)

        complete = len(state.rounds) == self.config.max_rounds
        if complete:
            protocol.finish_task()
        return ControlledRunSummary(
            task_kind=state.task_kind,
            complete=complete,
            rounds=tuple(state.rounds),
            total_candidates=self.controller.state.total_candidates,
            real_experiment_count=self.controller.state.real_experiment_count,
            stable_model_id=state.stable_model_id,
        )

    def _load_or_initialize(self, stream: TaskStream) -> _HarnessState:
        if self.state_path.is_file():
            with self.state_path.open("rb") as stream_file:
                return pickle.load(stream_file)
        update, anchor = partition_initial_data(
            stream.initial.X,
            stream.initial.y,
            stream.initial.sample_ids,
            task_kind=stream.task_kind,
            batch_id=stream.initial.batch_id,
            groups=stream.initial.group_ids or None,
            seed=self.config.seed,
        )
        stable = CpuModelAdapter(
            task_kind=stream.task_kind, family="sgd", seed=self.config.seed
        ).fit(update.X, update.y)
        reference_primary, _ = _metrics(
            stream.task_kind, anchor.y, np.asarray(stable.predict(anchor.X))
        )
        state = _HarnessState(
            task_kind=stream.task_kind,
            feature_count=stream.initial.X.shape[1],
            stable=stable,
            stable_model_id="model-v0",
            reference_X=np.asarray(update.X),
            anchor=anchor,
            reference_primary=reference_primary,
        )
        _atomic_pickle(self.state_path, state)
        return state

    @staticmethod
    def _restore_protocol(stream: TaskStream, completed_rounds: int) -> SimulatedSdkAdapter:
        protocol = SimulatedSdkAdapter(ProtocolMode.PREDICT_THEN_FEEDBACK)
        protocol.open_task(stream.task_id)
        for batch in stream.development[:completed_rounds]:
            protocol.request_predictions(batch.batch_id, batch.sample_ids)
            protocol.submit_predictions(batch.batch_id, batch.sample_ids)
            protocol.provide_feedback(batch.batch_id, batch.sample_ids)
            protocol.request_batch_commit(batch.batch_id)
        return protocol

    def _remaining_fraction(self, state: _HarnessState) -> float:
        return max(0.0, 1.0 - state.cpu_used / self.config.total_cpu_budget_seconds)

    def _can_train(self, state: _HarnessState, round_index: int) -> bool:
        if self.controller.state.total_candidates >= self.config.max_total_candidates:
            return False
        remaining = self.config.total_cpu_budget_seconds - state.cpu_used
        reserve = self.config.total_cpu_budget_seconds * 0.25 if round_index <= 7 else 0.0
        return remaining > reserve

    def _select_action(self, state: _HarnessState, evidence: EvidenceState) -> str | None:
        round_index = self.controller.state.next_round
        if not self._can_train(state, round_index):
            return None
        if (
            evidence.performance_drop < self.config.performance_drop_threshold
            and evidence.drift_score < self.config.drift_threshold
        ):
            return None
        actions = ["INCREMENTAL_UPDATE"]
        if state.replay:
            actions.append("REPLAY_REFIT")
        costs = {
            "INCREMENTAL_UPDATE": {"cpu_seconds": 1.0, "peak_memory_mb": 64.0},
            "REPLAY_REFIT": {"cpu_seconds": 3.0, "peak_memory_mb": 128.0},
        }
        ranked = rank_actions(self.values, "active-task", evidence, actions, costs)
        return ranked[0].action if ranked else None

    def _candidate_spec(
        self, action: str, round_index: int, number: int, remaining_cpu: float
    ) -> CandidateSpec:
        estimate = min(remaining_cpu, self.config.total_cpu_budget_seconds * 0.2)
        return CandidateSpec(
            candidate_id=f"r{round_index:02d}-c{number}",
            action=action,
            mechanism="incremental" if action == "INCREMENTAL_UPDATE" else "replay-refit",
            estimated_cpu_seconds=max(0.001, min(estimate, 1.0)),
            parameters={"seed": self.config.seed},
        )

    def _execute_candidate(
        self,
        state: _HarnessState,
        update: BufferSlice,
        gate: BufferSlice,
        action: str,
        round_index: int,
        candidate_id: str,
    ) -> tuple[CandidateOutcome, CpuModelAdapter, ResourceUsage]:
        include_replay = action == "REPLAY_REFIT"
        X, y, _ = candidate_training_data(
            update,
            replay_buffers=state.replay,
            current_round=round_index,
            include_replay=include_replay,
        )
        with ResourceTracker() as tracker:
            if action == "INCREMENTAL_UPDATE":
                candidate = state.stable.clone().partial_fit(X, y)
            else:
                candidate = state.stable.refit(X, y)
        usage = tracker.usage
        assert usage is not None
        stable_gate = np.asarray(state.stable.predict(gate.X))
        candidate_gate = np.asarray(candidate.predict(gate.X))
        stable_anchor = np.asarray(state.stable.predict(state.anchor.X))
        candidate_anchor = np.asarray(candidate.predict(state.anchor.X))
        gate_decision = evaluate_candidate(
            task_kind=state.task_kind,
            stable_validation=stable_gate,
            candidate_validation=candidate_gate,
            validation_targets=gate.y,
            stable_anchor=stable_anchor,
            candidate_anchor=candidate_anchor,
            anchor_targets=state.anchor.y,
            hard_constraints_passed=True,
            config=GateConfig(
                min_validation_samples=self.config.min_gate_samples,
                min_primary_improvement=self.config.min_gate_gain,
                max_anchor_degradation=self.config.max_anchor_degradation,
            ),
        )
        return (
            CandidateOutcome(
                candidate_id=candidate_id,
                completed=True,
                accepted=gate_decision.accepted,
                gate_gain=gate_decision.validation_improvement,
                cpu_seconds=usage.cpu_seconds,
                error=None if gate_decision.accepted else gate_decision.reason,
            ),
            candidate,
            usage,
        )

    def _record_gate_observation(
        self,
        evidence: EvidenceState,
        action: str,
        outcome: CandidateOutcome,
        usage: ResourceUsage,
        round_index: int,
    ) -> None:
        self.values.record(
            "active-task",
            evidence,
            ActionObservation(
                action=action,
                primary_delta=float(outcome.gate_gain or 0.0),
                cpu_seconds=usage.cpu_seconds,
                peak_memory_mb=usage.peak_rss_bytes / (1024 * 1024),
                token_count=0,
                model_bytes=0,
                accepted=outcome.accepted,
                succeeded=outcome.completed,
                reward_source="immediate_gate",
                attribution_confidence="gate_low",
                round_index=round_index,
            ),
        )
