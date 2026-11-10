"""Prequential local stream runner shared by all deterministic policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

from .audit import JsonlAuditLog
from .budget import BudgetLedger, BudgetLimits
from .data.types import BatchData, TaskStream
from .evidence import Evidence, build_evidence
from .modeling import SklearnModelAdapter
from .policies import Action, PolicyContext
from .protocol import ProtocolMode, SimulatedSdkAdapter
from .resources import ResourceTracker, ResourceUsage
from .safety import GateConfig, evaluate_candidate, select_deployment


class Policy(Protocol):
    def choose(self, context: PolicyContext) -> Action: ...

    def observe(self, action: Action, *, accepted: bool, improvement: float) -> None: ...


@dataclass(frozen=True)
class RunConfig:
    seed: int
    budget: BudgetLimits
    gate: GateConfig
    validation_fraction: float = 0.25
    replay_max_samples: int = 20_000


@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    phase: str
    sample_count: int
    primary_metric: float
    secondary_metric: float


@dataclass(frozen=True)
class CandidateEvent:
    batch_id: str
    action: str
    budget_allowed: bool
    accepted: bool
    reason: str
    validation_improvement: float
    anchor_degradation: float
    training_samples: int
    usage: ResourceUsage | None


@dataclass(frozen=True)
class RunSummary:
    task_id: str
    policy: str
    proxy_only: bool
    batch_results: tuple[BatchResult, ...]
    candidate_events: tuple[CandidateEvent, ...]
    development_metrics: dict[str, float]
    sealed_metrics: dict[str, float]
    protocol_history: tuple[str, ...]

    @property
    def candidate_count(self) -> int:
        return sum(event.budget_allowed for event in self.candidate_events)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidate_count"] = self.candidate_count
        return payload


def _metrics(task_kind: str, targets: NDArray, predictions: NDArray) -> dict[str, float]:
    if task_kind == "classification":
        return {
            "accuracy": float(accuracy_score(targets, predictions)),
            "macro_f1": float(f1_score(targets, predictions, average="macro", zero_division=0)),
        }
    return {
        "rmse": float(mean_squared_error(targets, predictions) ** 0.5),
        "mae": float(mean_absolute_error(targets, predictions)),
    }


def _primary(metrics: dict[str, float], task_kind: str) -> float:
    return metrics["accuracy"] if task_kind == "classification" else metrics["rmse"]


def _secondary(metrics: dict[str, float], task_kind: str) -> float:
    return metrics["macro_f1"] if task_kind == "classification" else metrics["mae"]


def _split_initial(batch: BatchData, task_kind: str, config: RunConfig):
    indices = np.arange(len(batch.y))
    if task_kind == "classification":
        train_indices, anchor_indices = train_test_split(
            indices,
            test_size=config.validation_fraction,
            random_state=config.seed,
            stratify=batch.y,
        )
    elif batch.group_ids and len(set(batch.group_ids)) > 1:
        groups = sorted(set(batch.group_ids), key=int)
        anchor_count = max(1, int(round(len(groups) * config.validation_fraction)))
        anchor_groups = set(groups[-anchor_count:])
        anchor_mask = np.asarray([group in anchor_groups for group in batch.group_ids])
        train_indices, anchor_indices = indices[~anchor_mask], indices[anchor_mask]
    else:
        cut = max(1, int(len(indices) * (1 - config.validation_fraction)))
        train_indices, anchor_indices = indices[:cut], indices[cut:]
    return train_indices, anchor_indices


def _split_feedback(batch: BatchData, task_kind: str, config: RunConfig):
    indices = np.arange(len(batch.y))
    if task_kind == "classification" and len(np.unique(batch.y)) > 1:
        counts = np.unique(batch.y, return_counts=True)[1]
        stratify = batch.y if counts.min() >= 2 else None
        return train_test_split(
            indices,
            test_size=config.validation_fraction,
            random_state=config.seed,
            stratify=stratify,
        )
    if batch.group_ids and len(set(batch.group_ids)) > 1:
        groups = sorted(set(batch.group_ids), key=int)
        validation_count = max(1, int(round(len(groups) * config.validation_fraction)))
        validation_groups = set(groups[-validation_count:])
        validation_mask = np.asarray(
            [group in validation_groups for group in batch.group_ids]
        )
        return indices[~validation_mask], indices[validation_mask]
    cut = max(1, int(len(indices) * (1 - config.validation_fraction)))
    return indices[:cut], indices[cut:]


def _aggregate(task_kind: str, targets: list[NDArray], predictions: list[NDArray]):
    if not targets:
        return {}
    return _metrics(task_kind, np.concatenate(targets), np.concatenate(predictions))


def _bounded_replay(
    feature_parts: list[NDArray], target_parts: list[NDArray], max_samples: int
) -> tuple[NDArray, NDArray]:
    X = np.concatenate(feature_parts)
    y = np.concatenate(target_parts)
    if len(y) > max_samples:
        X = X[-max_samples:]
        y = y[-max_samples:]
    return X, y


def run_stream(
    stream: TaskStream,
    *,
    policy: Policy,
    config: RunConfig,
    audit_path: Path,
    include_sealed: bool,
) -> RunSummary:
    logger = JsonlAuditLog(audit_path)
    protocol = SimulatedSdkAdapter(ProtocolMode.PREDICT_THEN_FEEDBACK)
    protocol.open_task(stream.task_id)
    train_indices, anchor_indices = _split_initial(stream.initial, stream.task_kind, config)
    initial_X = stream.initial.X[train_indices]
    initial_y = stream.initial.y[train_indices]
    anchor_X = stream.initial.X[anchor_indices]
    anchor_y = stream.initial.y[anchor_indices]
    stable = SklearnModelAdapter(task_kind=stream.task_kind, seed=config.seed).fit(
        initial_X, initial_y
    )
    reference_predictions = stable.predict(anchor_X)
    reference_metrics = _metrics(stream.task_kind, anchor_y, reference_predictions)
    reference_primary = _primary(reference_metrics, stream.task_kind)
    ledger = BudgetLedger(config.budget)
    replay_X: list[NDArray] = [initial_X]
    replay_y: list[NDArray] = [initial_y]
    batch_results: list[BatchResult] = []
    candidate_events: list[CandidateEvent] = []
    development_targets: list[NDArray] = []
    development_predictions: list[NDArray] = []
    sealed_targets: list[NDArray] = []
    sealed_predictions: list[NDArray] = []

    phases: list[tuple[str, tuple[BatchData, ...], bool]] = [
        ("development", stream.development, True)
    ]
    if include_sealed:
        phases.append(("sealed", stream.sealed, False))

    batch_index = 0
    for phase, batches, allow_training in phases:
        for batch in batches:
            batch_index += 1
            protocol.request_predictions(batch.batch_id, batch.sample_ids)
            predictions = stable.predict(batch.X)
            protocol.submit_predictions(batch.batch_id, batch.sample_ids)
            logger.write(
                "prediction_submitted",
                {
                    "task_id": stream.task_id,
                    "phase": phase,
                    "batch_id": batch.batch_id,
                    "sample_count": len(batch.y),
                },
            )
            protocol.provide_feedback(batch.batch_id, batch.sample_ids)
            logger.write(
                "feedback_received",
                {
                    "task_id": stream.task_id,
                    "phase": phase,
                    "batch_id": batch.batch_id,
                    "sample_count": len(batch.y),
                },
            )
            metrics = _metrics(stream.task_kind, batch.y, predictions)
            result = BatchResult(
                batch_id=batch.batch_id,
                phase=phase,
                sample_count=len(batch.y),
                primary_metric=_primary(metrics, stream.task_kind),
                secondary_metric=_secondary(metrics, stream.task_kind),
            )
            batch_results.append(result)
            if phase == "development":
                development_targets.append(batch.y)
                development_predictions.append(predictions)
            else:
                sealed_targets.append(batch.y)
                sealed_predictions.append(predictions)
            logger.write("batch_scored", {**asdict(result), "task_id": stream.task_id})

            if allow_training:
                evidence = build_evidence(
                    initial_X,
                    batch.X,
                    current_metric=result.primary_metric,
                    reference_metric=reference_primary,
                    higher_is_better=stream.task_kind == "classification",
                )
                action = policy.choose(PolicyContext(batch_index, evidence))
                logger.write(
                    "action_selected",
                    {
                        "task_id": stream.task_id,
                        "batch_id": batch.batch_id,
                        "batch_index": batch_index,
                        "performance_drop": evidence.performance_drop,
                        "drift_score": evidence.drift_score,
                        "action": action.value,
                    },
                )
                if action is not Action.NOOP:
                    candidate_train_indices, validation_indices = _split_feedback(
                        batch, stream.task_kind, config
                    )
                    candidate_train_X = batch.X[candidate_train_indices]
                    candidate_train_y = batch.y[candidate_train_indices]
                    if action is Action.REPLAY_REFIT:
                        candidate_X, candidate_y = _bounded_replay(
                            [*replay_X, candidate_train_X],
                            [*replay_y, candidate_train_y],
                            config.replay_max_samples,
                        )
                    else:
                        candidate_X, candidate_y = candidate_train_X, candidate_train_y
                    budget_decision = ledger.check_before_training(
                        estimated_samples=len(candidate_y)
                    )
                    if not budget_decision.allowed:
                        event = CandidateEvent(
                            batch.batch_id,
                            action.value,
                            False,
                            False,
                            budget_decision.reason,
                            0.0,
                            0.0,
                            len(candidate_y),
                            None,
                        )
                        candidate_events.append(event)
                        policy.observe(action, accepted=False, improvement=0.0)
                    else:
                        candidate_recorded = False
                        tracker: ResourceTracker | None = None
                        try:
                            with ResourceTracker() as tracker:
                                candidate = (
                                    stable.clone().partial_fit(candidate_X, candidate_y)
                                    if action is Action.INCREMENTAL_UPDATE
                                    else stable.refit(candidate_X, candidate_y)
                                )
                            usage = tracker.usage
                            if usage is None:
                                raise RuntimeError("resource usage was not recorded")
                            ledger.record_candidate(
                                usage, training_samples=len(candidate_y)
                            )
                            candidate_recorded = True
                            validation_X = batch.X[validation_indices]
                            validation_y = batch.y[validation_indices]
                            decision = evaluate_candidate(
                                task_kind=stream.task_kind,
                                stable_validation=stable.predict(validation_X),
                                candidate_validation=candidate.predict(validation_X),
                                validation_targets=validation_y,
                                stable_anchor=stable.predict(anchor_X),
                                candidate_anchor=candidate.predict(anchor_X),
                                anchor_targets=anchor_y,
                                hard_constraints_passed=True,
                                config=config.gate,
                            )
                            stable = select_deployment(stable, candidate, decision)
                            event = CandidateEvent(
                                batch.batch_id,
                                action.value,
                                True,
                                decision.accepted,
                                decision.reason,
                                decision.validation_improvement,
                                decision.anchor_degradation,
                                len(candidate_y),
                                usage,
                            )
                            candidate_events.append(event)
                            policy.observe(
                                action,
                                accepted=decision.accepted,
                                improvement=decision.validation_improvement,
                            )
                        except Exception as exc:
                            failure_usage = tracker.usage if tracker is not None else None
                            if failure_usage is None:
                                failure_usage = ResourceUsage(0.0, 0.0, 0, 0, 0)
                            if not candidate_recorded:
                                ledger.record_candidate(
                                    failure_usage, training_samples=len(candidate_y)
                                )
                            event = CandidateEvent(
                                batch.batch_id,
                                action.value,
                                True,
                                False,
                                f"candidate failure: {type(exc).__name__}",
                                0.0,
                                0.0,
                                len(candidate_y),
                                failure_usage,
                            )
                            candidate_events.append(event)
                            policy.observe(action, accepted=False, improvement=0.0)
                    logger.write(
                        "candidate_evaluated",
                        {
                            **asdict(candidate_events[-1]),
                            "task_id": stream.task_id,
                            "wall_seconds": (
                                candidate_events[-1].usage.wall_seconds
                                if candidate_events[-1].usage
                                else 0.0
                            ),
                            "cpu_seconds": (
                                candidate_events[-1].usage.cpu_seconds
                                if candidate_events[-1].usage
                                else 0.0
                            ),
                            "peak_rss_bytes": (
                                candidate_events[-1].usage.peak_rss_bytes
                                if candidate_events[-1].usage
                                else 0
                            ),
                        },
                    )
                replay_X.append(batch.X)
                replay_y.append(batch.y)
            protocol.request_batch_commit(batch.batch_id)
    protocol.finish_task()
    return RunSummary(
        task_id=stream.task_id,
        policy=type(policy).__name__,
        proxy_only=True,
        batch_results=tuple(batch_results),
        candidate_events=tuple(candidate_events),
        development_metrics=_aggregate(
            stream.task_kind, development_targets, development_predictions
        ),
        sealed_metrics=_aggregate(stream.task_kind, sealed_targets, sealed_predictions),
        protocol_history=protocol.history,
    )
