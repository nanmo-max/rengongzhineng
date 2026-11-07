"""Platform-neutral unattended BRACE-MSI Harness over internal task streams."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

from .audit import JsonlAuditLog
from .bootstrap import TaskBootstrap, TaskDefinition, TaskSignature
from .budget import BudgetLedger, BudgetLimits
from .checkpoint import CheckpointStore
from .data.types import BatchData, TaskStream
from .decision import AdaptiveActionPlanner, DecisionContext, EvidenceRouter
from .modeling import CpuModelAdapter
from .policies import Action
from .protocol import EventProtocolAdapter, ProtocolMode, SimulatedSdkAdapter
from .recording import LocalPublicSpool
from .registry import ModelRegistry
from .resources import ResourceTracker, ResourceUsage
from .safety import GateConfig, evaluate_candidate
from .search import BoundedSearch, CandidateConfig, ReplayBuffer, SearchConfig


@dataclass(frozen=True)
class HarnessConfig:
    seed: int
    protocol_mode: ProtocolMode
    budget: BudgetLimits
    gate: GateConfig
    minimum_candidate_events: int = 3
    replay_max_samples: int = 20_000
    hpo_max_trials: int = 3
    validation_fraction: float = 0.25
    fail_candidate_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class HarnessCandidate:
    batch_id: str
    action: str
    accepted: bool
    reason: str
    validation_improvement: float
    training_samples: int
    usage: ResourceUsage


@dataclass(frozen=True)
class HarnessResult:
    task_id: str
    status: str
    completed_batches: int
    candidates: tuple[HarnessCandidate, ...]
    rollback_count: int
    deployed_version: str | None
    protocol_history: tuple[str, ...]
    batch_metrics: tuple[dict[str, Any], ...]

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


def _metrics(task_kind: str, y: NDArray, predictions: NDArray) -> dict[str, float]:
    if task_kind == "classification":
        return {
            "accuracy": float(accuracy_score(y, predictions)),
            "macro_f1": float(f1_score(y, predictions, average="macro", zero_division=0)),
        }
    return {
        "rmse": float(mean_squared_error(y, predictions) ** 0.5),
        "mae": float(mean_absolute_error(y, predictions)),
    }


def _primary(task_kind: str, metrics: dict[str, float]) -> float:
    return metrics["accuracy"] if task_kind == "classification" else metrics["rmse"]


def _split_indices(
    batch: BatchData, task_kind: str, fraction: float, seed: int
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    indices = np.arange(len(batch.y))
    if task_kind == "classification" and len(np.unique(batch.y)) > 1:
        counts = np.unique(batch.y, return_counts=True)[1]
        stratify = batch.y if counts.min() >= 2 else None
        return train_test_split(
            indices, test_size=fraction, random_state=seed, stratify=stratify
        )
    if batch.group_ids and len(set(batch.group_ids)) > 1:
        groups = sorted(set(batch.group_ids), key=int)
        count = max(1, int(round(len(groups) * fraction)))
        validation_groups = set(groups[-count:])
        mask = np.asarray([group in validation_groups for group in batch.group_ids])
        return indices[~mask], indices[mask]
    cut = max(1, int(len(indices) * (1.0 - fraction)))
    return indices[:cut], indices[cut:]


class UnifiedHarness:
    def __init__(
        self,
        root: Path,
        config: HarnessConfig,
        *,
        adapter_factory: Callable[[ProtocolMode], EventProtocolAdapter] = SimulatedSdkAdapter,
    ) -> None:
        self.root = Path(root)
        self.config = config
        self.adapter_factory = adapter_factory
        self.registry = ModelRegistry(self.root / "registry")
        self.checkpoint = CheckpointStore(self.root / "checkpoint.pkl")

    def _new_state(self, stream: TaskStream) -> dict[str, Any]:
        train_indices, anchor_indices = _split_indices(
            stream.initial,
            stream.task_kind,
            self.config.validation_fraction,
            self.config.seed,
        )
        train_X, train_y = stream.initial.X[train_indices], stream.initial.y[train_indices]
        anchor_X, anchor_y = stream.initial.X[anchor_indices], stream.initial.y[anchor_indices]
        definition = TaskDefinition(
            stream.task_id, stream.task_kind, stream.initial.X.shape[1]
        )
        bootstrapped = TaskBootstrap(seed=self.config.seed).initialize(
            definition, train_X, train_y
        )
        anchor_metrics = _metrics(
            stream.task_kind, anchor_y, bootstrapped.model.predict(anchor_X)
        )
        replay = ReplayBuffer(max_samples=self.config.replay_max_samples)
        replay.append(train_X, train_y)
        state: dict[str, Any] = {
            "task_id": stream.task_id,
            "next_batch": 0,
            "stable": bootstrapped.model,
            "signature": bootstrapped.signature,
            "stable_version": "initial",
            "anchor_X": anchor_X,
            "anchor_y": anchor_y,
            "reference_X": train_X,
            "reference_primary": _primary(stream.task_kind, anchor_metrics),
            "last_primary": _primary(stream.task_kind, anchor_metrics),
            "replay": replay,
            "ledger": BudgetLedger(self.config.budget),
            "planner": AdaptiveActionPlanner(),
            "candidates": [],
            "rollback_count": 0,
            "batch_metrics": [],
            "finished": False,
        }
        self.registry.ensure_deployed(
            task_id=stream.task_id,
            version="initial",
            model=bootstrapped.model,
            signature=bootstrapped.signature,
        )
        self.checkpoint.save(state)
        return state

    def _sync_registry(self, state: dict[str, Any]) -> None:
        self.registry.ensure_deployed(
            task_id=state["task_id"],
            version=state["stable_version"],
            model=state["stable"],
            signature=state["signature"],
        )

    def _protocol_for_resume(
        self, stream: TaskStream, completed: int
    ) -> EventProtocolAdapter:
        protocol = self.adapter_factory(self.config.protocol_mode)
        protocol.open_task(stream.task_id)
        for index, batch in enumerate(stream.development[:completed]):
            if self.config.protocol_mode is ProtocolMode.PREDICT_THEN_FEEDBACK:
                protocol.request_predictions(batch.batch_id, batch.sample_ids)
                protocol.submit_predictions(batch.batch_id, batch.sample_ids)
                protocol.provide_feedback(batch.batch_id, batch.sample_ids)
            else:
                train_indices, score_indices = _split_indices(
                    batch,
                    stream.task_kind,
                    self.config.validation_fraction,
                    self.config.seed + index,
                )
                train_ids = tuple(batch.sample_ids[i] for i in train_indices)
                score_ids = tuple(batch.sample_ids[i] for i in score_indices)
                protocol.provide_training_batch(batch.batch_id, train_ids)
                protocol.request_predictions(batch.batch_id, score_ids)
                protocol.submit_predictions(batch.batch_id, score_ids)
            protocol.request_batch_commit(batch.batch_id)
        return protocol

    def _result(
        self, state: dict[str, Any], status: str, protocol_history: tuple[str, ...]
    ) -> HarnessResult:
        return HarnessResult(
            task_id=state["task_id"],
            status=status,
            completed_batches=state["next_batch"],
            candidates=tuple(state["candidates"]),
            rollback_count=state["rollback_count"],
            deployed_version=state["stable_version"],
            protocol_history=protocol_history,
            batch_metrics=tuple(state["batch_metrics"]),
        )

    def _qualification_action(
        self, action: Action, state: dict[str, Any], remaining_batches: int
    ) -> Action:
        needed = self.config.minimum_candidate_events - len(state["candidates"])
        if action is not Action.NOOP or needed < remaining_batches:
            return action
        if state["stable"].capabilities.supports_partial_fit and not state["candidates"]:
            return Action.INCREMENTAL_UPDATE
        return Action.REPLAY_REFIT

    def _single_candidate(
        self,
        *,
        state: dict[str, Any],
        batch_id: str,
        action: Action,
        train_X: NDArray,
        train_y: NDArray,
        validation_X: NDArray,
        validation_y: NDArray,
    ) -> tuple[CpuModelAdapter, list[HarnessCandidate], bool]:
        ledger: BudgetLedger = state["ledger"]
        if action is Action.REPLAY_REFIT:
            replay_X, replay_y = state["replay"].arrays()
            candidate_X = np.concatenate([replay_X, train_X])
            candidate_y = np.concatenate([replay_y, train_y])
            candidate_X = candidate_X[-self.config.replay_max_samples :]
            candidate_y = candidate_y[-self.config.replay_max_samples :]
        else:
            candidate_X, candidate_y = train_X, train_y
        budget = ledger.check_before_training(estimated_samples=len(candidate_y))
        zero = ResourceUsage(0.0, 0.0, 0, 0, 0)
        if not budget.allowed:
            return state["stable"], [HarnessCandidate(batch_id, action.value, False, budget.reason, 0.0, len(candidate_y), zero)], False
        candidate_number = len(state["candidates"]) + 1
        if candidate_number in self.config.fail_candidate_numbers:
            ledger.record_candidate(zero, training_samples=len(candidate_y))
            return state["stable"], [HarnessCandidate(batch_id, action.value, False, "injected_candidate_failure", 0.0, len(candidate_y), zero)], True
        tracker: ResourceTracker | None = None
        try:
            with ResourceTracker() as tracker:
                candidate = (
                    state["stable"].clone().partial_fit(candidate_X, candidate_y)
                    if action is Action.INCREMENTAL_UPDATE
                    else state["stable"].refit(candidate_X, candidate_y)
                )
            usage = tracker.usage or zero
            ledger.record_candidate(usage, training_samples=len(candidate_y))
            decision = evaluate_candidate(
                task_kind=state["signature"].task_kind,
                stable_validation=state["stable"].predict(validation_X),
                candidate_validation=candidate.predict(validation_X),
                validation_targets=validation_y,
                stable_anchor=state["stable"].predict(state["anchor_X"]),
                candidate_anchor=candidate.predict(state["anchor_X"]),
                anchor_targets=state["anchor_y"],
                hard_constraints_passed=True,
                config=self.config.gate,
            )
            event = HarnessCandidate(
                batch_id,
                action.value,
                decision.accepted,
                decision.reason,
                decision.validation_improvement,
                len(candidate_y),
                usage,
            )
            return (candidate if decision.accepted else state["stable"]), [event], not decision.accepted
        except Exception as exc:
            usage = tracker.usage if tracker and tracker.usage else zero
            ledger.record_candidate(usage, training_samples=len(candidate_y))
            event = HarnessCandidate(
                batch_id,
                action.value,
                False,
                f"candidate_failure:{type(exc).__name__}",
                0.0,
                len(candidate_y),
                usage,
            )
            return state["stable"], [event], True

    def _hpo_candidates(
        self,
        *,
        state: dict[str, Any],
        batch_id: str,
        train_X: NDArray,
        train_y: NDArray,
        validation_X: NDArray,
        validation_y: NDArray,
    ) -> tuple[CpuModelAdapter, list[HarnessCandidate], bool]:
        search = BoundedSearch(
            task_kind=state["signature"].task_kind,
            seed=self.config.seed,
            config=SearchConfig(
                max_trials=self.config.hpo_max_trials, patience=1, min_improvement=0.0
            ),
        )
        configs = (
            CandidateConfig("linear", {}),
            CandidateConfig("extra_trees", {"n_estimators": 64, "max_depth": 12}),
            CandidateConfig("hist_gradient_boosting", {"max_iter": 64}),
        )
        result = search.run(
            candidates=configs,
            train_X=train_X,
            train_y=train_y,
            validation_X=validation_X,
            validation_y=validation_y,
            ledger=state["ledger"],
        )
        events = [
            HarnessCandidate(
                batch_id,
                Action.BOUNDED_HPO.value,
                False,
                f"search_trial:{trial.status}:{trial.family}",
                0.0,
                len(train_y),
                trial.usage,
            )
            for trial in result.trials
        ]
        if result.best_model is None:
            return state["stable"], events, True
        decision = evaluate_candidate(
            task_kind=state["signature"].task_kind,
            stable_validation=state["stable"].predict(validation_X),
            candidate_validation=result.best_model.predict(validation_X),
            validation_targets=validation_y,
            stable_anchor=state["stable"].predict(state["anchor_X"]),
            candidate_anchor=result.best_model.predict(state["anchor_X"]),
            anchor_targets=state["anchor_y"],
            hard_constraints_passed=True,
            config=self.config.gate,
        )
        if events:
            events[-1] = HarnessCandidate(
                batch_id,
                Action.BOUNDED_HPO.value,
                decision.accepted,
                decision.reason,
                decision.validation_improvement,
                len(train_y),
                events[-1].usage,
            )
        return (
            result.best_model if decision.accepted else state["stable"],
            events,
            not decision.accepted,
        )

    def run(self, stream: TaskStream, *, max_batches: int | None = None) -> HarnessResult:
        self.root.mkdir(parents=True, exist_ok=True)
        resumed = self.checkpoint.exists()
        state = self.checkpoint.load() if resumed else self._new_state(stream)
        if state["task_id"] != stream.task_id:
            raise ValueError("checkpoint belongs to a different task")
        self._sync_registry(state)
        if state["finished"]:
            return self._result(state, "completed", tuple(state["protocol_history"]))
        protocol = self._protocol_for_resume(stream, state["next_batch"])
        private = JsonlAuditLog(self.root / "private-audit.jsonl", truncate=not resumed)
        public = LocalPublicSpool(self.root / "public-spool.jsonl", truncate=not resumed)
        processed = 0

        for batch_index in range(state["next_batch"], len(stream.development)):
            if max_batches is not None and processed >= max_batches:
                return self._result(state, "paused", protocol.history)
            batch = stream.development[batch_index]
            if self.config.protocol_mode is ProtocolMode.LABELED_TRAIN_THEN_PREDICT:
                train_indices, score_indices = _split_indices(
                    batch,
                    stream.task_kind,
                    self.config.validation_fraction,
                    self.config.seed + batch_index,
                )
                train_ids = tuple(batch.sample_ids[i] for i in train_indices)
                score_ids = tuple(batch.sample_ids[i] for i in score_indices)
                protocol.provide_training_batch(batch.batch_id, train_ids)
                visible_X, visible_y = batch.X[train_indices], batch.y[train_indices]
                score_X, score_y = batch.X[score_indices], batch.y[score_indices]
                current_primary = state["last_primary"]
            else:
                protocol.request_predictions(batch.batch_id, batch.sample_ids)
                predictions = state["stable"].predict(batch.X)
                protocol.submit_predictions(batch.batch_id, batch.sample_ids)
                protocol.provide_feedback(batch.batch_id, batch.sample_ids)
                score_X, score_y = batch.X, batch.y
                metrics = _metrics(stream.task_kind, score_y, predictions)
                current_primary = _primary(stream.task_kind, metrics)
                visible_X, visible_y = batch.X, batch.y

            train_indices, validation_indices = _split_indices(
                BatchData(
                    f"{batch.batch_id}-visible",
                    visible_X,
                    visible_y,
                    tuple(f"visible-{i}" for i in range(len(visible_y))),
                ),
                stream.task_kind,
                self.config.validation_fraction,
                self.config.seed + batch_index,
            )
            evidence = EvidenceRouter().route(
                reference_X=state["reference_X"],
                current_X=visible_X,
                current_metric=current_primary,
                reference_metric=state["reference_primary"],
                higher_is_better=stream.task_kind == "classification",
                failed_actions=state["planner"].consecutive_failures,
                budget_fraction=state["ledger"].remaining_fraction,
            )
            action = state["planner"].select(
                DecisionContext(evidence, state["stable"].capabilities)
            )
            action = self._qualification_action(
                action, state, len(stream.development) - batch_index
            )
            events: list[HarnessCandidate] = []
            failed = False
            if action is not Action.NOOP:
                if action is Action.BOUNDED_HPO:
                    stable, events, failed = self._hpo_candidates(
                        state=state,
                        batch_id=batch.batch_id,
                        train_X=visible_X[train_indices],
                        train_y=visible_y[train_indices],
                        validation_X=visible_X[validation_indices],
                        validation_y=visible_y[validation_indices],
                    )
                else:
                    stable, events, failed = self._single_candidate(
                        state=state,
                        batch_id=batch.batch_id,
                        action=action,
                        train_X=visible_X[train_indices],
                        train_y=visible_y[train_indices],
                        validation_X=visible_X[validation_indices],
                        validation_y=visible_y[validation_indices],
                    )
                state["stable"] = stable
                state["candidates"].extend(events)
                accepted = any(event.accepted for event in events)
                improvement = max(
                    (event.validation_improvement for event in events), default=0.0
                )
                state["planner"].observe(
                    action, accepted=accepted, improvement=improvement
                )
                if accepted:
                    state["stable_version"] = (
                        f"batch-{batch_index + 1}-candidate-{len(state['candidates'])}"
                    )
                if failed:
                    state["rollback_count"] += 1
                for event in events:
                    payload = {
                        "task_id": stream.task_id,
                        "batch_id": batch.batch_id,
                        "action": event.action,
                        "accepted": event.accepted,
                        "reason": event.reason,
                        "validation_improvement": event.validation_improvement,
                        "training_samples": event.training_samples,
                        "wall_seconds": event.usage.wall_seconds,
                        "cpu_seconds": event.usage.cpu_seconds,
                        "peak_rss_bytes": event.usage.peak_rss_bytes,
                    }
                    private.write("candidate_evaluated", payload)
                    public.record("candidate_evaluated", payload)

            state["replay"].append(visible_X[train_indices], visible_y[train_indices])
            if self.config.protocol_mode is ProtocolMode.LABELED_TRAIN_THEN_PREDICT:
                protocol.request_predictions(batch.batch_id, score_ids)
                predictions = state["stable"].predict(score_X)
                protocol.submit_predictions(batch.batch_id, score_ids)
                metrics = _metrics(stream.task_kind, score_y, predictions)
                current_primary = _primary(stream.task_kind, metrics)
            protocol.request_batch_commit(batch.batch_id)
            state["last_primary"] = current_primary
            metric_record = {
                "batch_id": batch.batch_id,
                "batch_index": batch_index + 1,
                "sample_count": len(score_y),
                **metrics,
            }
            state["batch_metrics"].append(metric_record)
            state["next_batch"] = batch_index + 1
            self.checkpoint.save(state)
            self._sync_registry(state)
            log_payload = {
                "task_id": stream.task_id,
                "batch_id": batch.batch_id,
                "batch_index": batch_index + 1,
                "sample_count": len(score_y),
                "primary_metric": current_primary,
            }
            private.write("batch_committed", log_payload)
            public.record("batch_committed", log_payload)
            processed += 1

        protocol.finish_task()
        state["finished"] = True
        state["protocol_history"] = protocol.history
        self.checkpoint.save(state)
        public.record(
            "run_finished",
            {
                "task_id": stream.task_id,
                "status": "completed",
                "candidate_count": len(state["candidates"]),
                "rollback_count": state["rollback_count"],
                "deployed_version": state["stable_version"],
            },
        )
        return self._result(state, "completed", protocol.history)
