"""Official-rules-aligned local training over replaceable MLP checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import pickle
from typing import Any, Literal
import warnings

import numpy as np
from numpy.typing import NDArray
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import train_test_split

from .budget import BudgetLedger, BudgetLimits
from .data.types import BatchData, TaskStream
from .evidence import build_evidence
from .modeling import CpuModelAdapter
from .official_metrics import MetricName, higher_is_better, metric_bundle, primary_value
from .policies import Action, BracePolicy, PerformanceTriggeredPolicy, PolicyContext, StaticPolicy
from .resources import ResourceTracker, ResourceUsage
from .safety import GateConfig

PolicyName = Literal["static", "performance_triggered", "brace"]


@dataclass(frozen=True)
class FormalRunConfig:
    seed: int
    budget: BudgetLimits
    gate: GateConfig
    minimum_candidate_events: int
    replay_max_samples: int
    performance_drop_threshold: float
    update_drop_threshold: float
    refit_drop_threshold: float
    drift_threshold: float
    high_drift_threshold: float
    mlp_max_iter: int = 120
    validation_fraction: float = 0.25


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _split_indices(
    batch: BatchData, task_kind: str, fraction: float, seed: int
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    indices = np.arange(len(batch.y), dtype=np.int64)
    if len(indices) < 2:
        raise ValueError("a train/validation split requires at least two samples")
    if task_kind == "classification" and len(np.unique(batch.y)) > 1:
        classes, counts = np.unique(batch.y, return_counts=True)
        validation_count = int(np.ceil(len(indices) * fraction))
        training_count = len(indices) - validation_count
        stratify = (
            batch.y
            if counts.min() >= 2
            and validation_count >= len(classes)
            and training_count >= len(classes)
            else None
        )
        train, validation = train_test_split(
            indices, test_size=fraction, random_state=seed, stratify=stratify
        )
        return np.asarray(train), np.asarray(validation)
    if batch.group_ids and len(set(batch.group_ids)) > 1:
        groups = sorted(set(batch.group_ids), key=int)
        count = max(1, int(round(len(groups) * fraction)))
        validation_groups = set(groups[-count:])
        mask = np.asarray([group in validation_groups for group in batch.group_ids])
        return indices[~mask], indices[mask]
    cut = min(len(indices) - 1, max(1, int(len(indices) * (1.0 - fraction))))
    return indices[:cut], indices[cut:]


def _fit_mlp(
    task_kind: str, X: NDArray, y: NDArray, *, seed: int, max_iter: int
) -> CpuModelAdapter:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        return CpuModelAdapter(
            task_kind=task_kind,
            family="mlp",
            seed=seed,
            params={"max_iter": max_iter},
        ).fit(X, y)


def create_local_checkpoint(
    stream: TaskStream, path: Path, config: FormalRunConfig
) -> Path:
    """Fit and atomically save the local substitute for a platform checkpoint."""

    if stream.sealed:
        raise ValueError("formal development checkpoints must not load sealed data")
    if stream.metadata.get("official_rules_aligned") is not True:
        raise ValueError("stream is not marked official-rules-aligned")
    if stream.metadata.get("official_checkpoint") is not False:
        raise ValueError("local checkpoint must be explicitly non-official")
    train_indices, anchor_indices = _split_indices(
        stream.initial, stream.task_kind, config.validation_fraction, config.seed
    )
    train_X, train_y = stream.initial.X[train_indices], stream.initial.y[train_indices]
    anchor_X, anchor_y = stream.initial.X[anchor_indices], stream.initial.y[anchor_indices]
    model = _fit_mlp(
        stream.task_kind,
        train_X,
        train_y,
        seed=config.seed,
        max_iter=config.mlp_max_iter,
    )
    expected = int(stream.metadata["published_parameter_count"])
    if model.parameter_count != expected:
        raise ValueError(
            f"local MLP parameter count {model.parameter_count} != published {expected}"
        )
    metric_name: MetricName = stream.metadata["primary_metric"]
    anchor_metrics = metric_bundle(metric_name, anchor_y, model.predict(anchor_X))
    payload = {
        "schema_version": 1,
        "task_id": stream.task_id,
        "task_kind": stream.task_kind,
        "metric_name": metric_name,
        "official_checkpoint": False,
        "parameter_count": model.parameter_count,
        "model": model,
        "train_X": train_X,
        "train_y": train_y,
        "anchor_X": anchor_X,
        "anchor_y": anchor_y,
        "reference_primary": primary_value(metric_name, anchor_metrics),
    }
    path = Path(path)
    _atomic_bytes(path, pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
    return path


def _load_checkpoint(path: Path, stream: TaskStream) -> dict[str, Any]:
    try:
        payload = pickle.loads(Path(path).read_bytes())
    except (OSError, pickle.UnpicklingError, EOFError) as exc:
        raise ValueError("cannot load local checkpoint") from exc
    if payload.get("task_id") != stream.task_id:
        raise ValueError("checkpoint belongs to a different task")
    if payload.get("official_checkpoint") is not False:
        raise ValueError("development checkpoint marker is invalid")
    return payload


def _policy(policy_name: PolicyName, config: FormalRunConfig):
    if policy_name == "static":
        return StaticPolicy()
    if policy_name == "performance_triggered":
        return PerformanceTriggeredPolicy(
            performance_drop_threshold=config.performance_drop_threshold
        )
    if policy_name == "brace":
        return BracePolicy(
            update_drop_threshold=config.update_drop_threshold,
            refit_drop_threshold=config.refit_drop_threshold,
            drift_threshold=config.drift_threshold,
            high_drift_threshold=config.high_drift_threshold,
        )
    raise ValueError(f"unknown formal-development policy: {policy_name}")


def _gate(
    *,
    metric_name: MetricName,
    stable_validation: NDArray,
    candidate_validation: NDArray,
    validation_targets: NDArray,
    stable_anchor: NDArray,
    candidate_anchor: NDArray,
    anchor_targets: NDArray,
    config: GateConfig,
) -> tuple[bool, str, float, float]:
    if len(validation_targets) < config.min_validation_samples:
        return False, "insufficient validation samples", 0.0, 0.0
    stable_validation_value = primary_value(
        metric_name, metric_bundle(metric_name, validation_targets, stable_validation)
    )
    candidate_validation_value = primary_value(
        metric_name, metric_bundle(metric_name, validation_targets, candidate_validation)
    )
    stable_anchor_value = primary_value(
        metric_name, metric_bundle(metric_name, anchor_targets, stable_anchor)
    )
    candidate_anchor_value = primary_value(
        metric_name, metric_bundle(metric_name, anchor_targets, candidate_anchor)
    )
    if higher_is_better(metric_name):
        improvement = candidate_validation_value - stable_validation_value
        anchor_degradation = stable_anchor_value - candidate_anchor_value
    else:
        improvement = stable_validation_value - candidate_validation_value
        anchor_degradation = candidate_anchor_value - stable_anchor_value
    if not np.isfinite([improvement, anchor_degradation]).all():
        return False, "non-finite metric", 0.0, 0.0
    if anchor_degradation > config.max_anchor_degradation:
        return False, "anchor degradation exceeds limit", float(improvement), float(anchor_degradation)
    if improvement < config.min_primary_improvement:
        return False, "validation gain is below threshold", float(improvement), float(anchor_degradation)
    return True, "candidate passed all layers", float(improvement), float(anchor_degradation)


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return bool(np.isfinite(value))
    if isinstance(value, dict):
        return all(_finite(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(child) for child in value)
    return True


def run_formal_development_experiment(
    stream: TaskStream,
    *,
    policy_name: PolicyName,
    checkpoint_path: Path,
    output_dir: Path,
    config: FormalRunConfig,
) -> dict[str, Any]:
    """Run one ten-round policy experiment from a shared local checkpoint."""

    if len(stream.development) != 10 or stream.sealed:
        raise ValueError("formal development requires ten unsealed batches")
    output_dir = Path(output_dir)
    result_path = output_dir / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = _load_checkpoint(checkpoint_path, stream)
    stable: CpuModelAdapter = checkpoint["model"]
    metric_name: MetricName = checkpoint["metric_name"]
    policy = _policy(policy_name, config)
    ledger = BudgetLedger(config.budget)
    replay_X = [checkpoint["train_X"]]
    replay_y = [checkpoint["train_y"]]
    batch_records: list[dict[str, Any]] = []
    candidate_records: list[dict[str, Any]] = []
    all_targets: list[NDArray] = []
    all_predictions: list[NDArray] = []
    audit_path = output_dir / "audit.jsonl"

    for batch_index, batch in enumerate(stream.development, start=1):
        predictions = stable.predict(batch.X)
        metrics = metric_bundle(metric_name, batch.y, predictions)
        primary = primary_value(metric_name, metrics)
        all_targets.append(batch.y)
        all_predictions.append(predictions)
        evidence = build_evidence(
            checkpoint["train_X"],
            batch.X,
            current_metric=primary,
            reference_metric=float(checkpoint["reference_primary"]),
            higher_is_better=higher_is_better(metric_name),
        )
        action = policy.choose(PolicyContext(batch_index, evidence))
        remaining = len(stream.development) - batch_index + 1
        candidates_needed = config.minimum_candidate_events - sum(
            bool(item["training_started"]) for item in candidate_records
        )
        if (
            policy_name == "brace"
            and action is Action.NOOP
            and candidates_needed >= remaining
        ):
            action = (
                Action.INCREMENTAL_UPDATE
                if stable.capabilities.supports_partial_fit
                and not candidate_records
                else Action.REPLAY_REFIT
            )

        event: dict[str, Any] | None = None
        if action is not Action.NOOP:
            train_indices, validation_indices = _split_indices(
                batch,
                stream.task_kind,
                config.validation_fraction,
                config.seed + batch_index,
            )
            feedback_X, feedback_y = batch.X[train_indices], batch.y[train_indices]
            validation_X, validation_y = (
                batch.X[validation_indices],
                batch.y[validation_indices],
            )
            if action is Action.REPLAY_REFIT:
                candidate_X = np.concatenate([*replay_X, feedback_X])
                candidate_y = np.concatenate([*replay_y, feedback_y])
                candidate_X = candidate_X[-config.replay_max_samples :]
                candidate_y = candidate_y[-config.replay_max_samples :]
            else:
                candidate_X, candidate_y = feedback_X, feedback_y
            allowed = ledger.check_before_training(estimated_samples=len(candidate_y))
            if not allowed.allowed:
                event = {
                    "batch_id": batch.batch_id,
                    "action": action.value,
                    "training_started": False,
                    "accepted": False,
                    "reason": allowed.reason,
                    "validation_improvement": 0.0,
                    "anchor_degradation": 0.0,
                    "training_samples": len(candidate_y),
                    "usage": asdict(ResourceUsage(0.0, 0.0, 0, 0, 0)),
                }
            else:
                tracker: ResourceTracker | None = None
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", ConvergenceWarning)
                        with ResourceTracker() as tracker:
                            candidate = (
                                stable.clone().partial_fit(candidate_X, candidate_y)
                                if action is Action.INCREMENTAL_UPDATE
                                else stable.refit(candidate_X, candidate_y)
                            )
                    usage = tracker.usage or ResourceUsage(0.0, 0.0, 0, 0, 0)
                    ledger.record_candidate(usage, training_samples=len(candidate_y))
                    accepted, reason, improvement, degradation = _gate(
                        metric_name=metric_name,
                        stable_validation=stable.predict(validation_X),
                        candidate_validation=candidate.predict(validation_X),
                        validation_targets=validation_y,
                        stable_anchor=stable.predict(checkpoint["anchor_X"]),
                        candidate_anchor=candidate.predict(checkpoint["anchor_X"]),
                        anchor_targets=checkpoint["anchor_y"],
                        config=config.gate,
                    )
                    if accepted:
                        stable = candidate
                    event = {
                        "batch_id": batch.batch_id,
                        "action": action.value,
                        "training_started": True,
                        "accepted": accepted,
                        "reason": reason,
                        "validation_improvement": improvement,
                        "anchor_degradation": degradation,
                        "training_samples": len(candidate_y),
                        "usage": asdict(usage),
                    }
                except Exception as exc:
                    usage = (
                        tracker.usage
                        if tracker is not None and tracker.usage is not None
                        else ResourceUsage(0.0, 0.0, 0, 0, 0)
                    )
                    ledger.record_candidate(usage, training_samples=len(candidate_y))
                    event = {
                        "batch_id": batch.batch_id,
                        "action": action.value,
                        "training_started": True,
                        "accepted": False,
                        "reason": f"candidate_failure:{type(exc).__name__}",
                        "validation_improvement": 0.0,
                        "anchor_degradation": 0.0,
                        "training_samples": len(candidate_y),
                        "usage": asdict(usage),
                    }
            candidate_records.append(event)
            policy.observe(
                action,
                accepted=bool(event["accepted"]),
                improvement=float(event["validation_improvement"]),
            )

        replay_X.append(batch.X)
        replay_y.append(batch.y)
        record = {
            "batch_id": batch.batch_id,
            "batch_index": batch_index,
            "sample_count": len(batch.y),
            "metrics": metrics,
            "primary_metric": primary,
            "performance_drop": evidence.performance_drop,
            "drift_score": evidence.drift_score,
            "selected_action": action.value,
        }
        batch_records.append(record)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event": "optimization_round_completed",
                        "official_rules_aligned": True,
                        "official_checkpoint": False,
                        **record,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    aggregate = metric_bundle(
        metric_name, np.concatenate(all_targets), np.concatenate(all_predictions)
    )
    _atomic_bytes(
        output_dir / "final-model.pkl",
        pickle.dumps(stable, protocol=pickle.HIGHEST_PROTOCOL),
    )
    usages = [item["usage"] for item in candidate_records if item["training_started"]]
    result = {
        "schema_version": 1,
        "status": "completed",
        "task_id": stream.task_id,
        "task_kind": stream.task_kind,
        "policy": policy_name,
        "official_rules_aligned": True,
        "official_checkpoint": False,
        "checkpoint_sha256": _sha256(checkpoint_path),
        "published_parameter_count": int(stream.metadata["published_parameter_count"]),
        "primary_metric_name": metric_name,
        "completed_batches": len(batch_records),
        "decision_round_count": len(batch_records),
        "real_candidate_count": sum(bool(item["training_started"]) for item in candidate_records),
        "accepted_candidate_count": sum(bool(item["accepted"]) for item in candidate_records),
        "metrics": aggregate,
        "batch_records": batch_records,
        "candidate_events": candidate_records,
        "resources": {
            "candidate_wall_seconds": float(sum(item["wall_seconds"] for item in usages)),
            "candidate_cpu_seconds": float(sum(item["cpu_seconds"] for item in usages)),
            "peak_rss_bytes": int(max((item["peak_rss_bytes"] for item in usages), default=0)),
            "candidate_training_samples": int(
                sum(item["training_samples"] for item in candidate_records if item["training_started"])
            ),
        },
    }
    if not _finite(result):
        raise RuntimeError("formal development produced non-finite evidence")
    _atomic_json(result_path, result)
    return result


def validate_formal_development_output(
    output_dir: Path, *, expected_batches: int, minimum_candidates: int
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    try:
        result = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("missing or invalid formal-development result") from exc
    if result.get("status") != "completed":
        raise RuntimeError("formal-development run is not completed")
    if result.get("official_rules_aligned") is not True:
        raise RuntimeError("official-rules-aligned marker is missing")
    if result.get("official_checkpoint") is not False:
        raise RuntimeError("local run cannot claim an official checkpoint")
    if result.get("completed_batches") != expected_batches:
        raise RuntimeError("unexpected optimization round count")
    if result.get("policy") == "brace" and result.get("real_candidate_count", 0) < minimum_candidates:
        raise RuntimeError("BRACE did not execute enough real candidates")
    if not _finite(result):
        raise RuntimeError("formal-development result contains non-finite values")
    if not (output_dir / "final-model.pkl").exists() or not (output_dir / "audit.jsonl").exists():
        raise RuntimeError("formal-development evidence is incomplete")
    return {
        "valid": True,
        "completed_batches": expected_batches,
        "real_candidate_count": int(result["real_candidate_count"]),
        "finite_metrics": True,
    }

