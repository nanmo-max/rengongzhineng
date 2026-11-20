"""One-time, leakage-bounded final generalization validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any

import numpy as np
import psutil

from brace_formal.metrics import MetricContract

from .competitive_policy import PortfolioEvidence, build_candidate_plan
from .method_pilot import _metrics, _native_prediction, _signed_gain, fit_native_recipe
from .platform_runtime import _NativeModel
from .selection_strategies import (
    ArtifactEvidence,
    ExplorationBudget,
    SelectionContext,
    decide,
)


class FinalValidationError(RuntimeError):
    """Raised when the one-time validation contract cannot be preserved."""


@dataclass(frozen=True)
class ProgressRound:
    update_x: np.ndarray
    update_y: np.ndarray
    update_ids: tuple[str, ...]
    gate_x: np.ndarray
    gate_y: np.ndarray
    gate_ids: tuple[str, ...]


def load_cache_batch(
    path: Path, *, expected_bearing: str
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    """Load the minimum immutable feature-cache contract used by final validation."""

    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise FinalValidationError(f"bearing cache is missing or unsafe: {path.name}")
    try:
        with np.load(path, allow_pickle=False) as archive:
            x = np.asarray(archive["X"], dtype=np.float64)
            y = np.asarray(archive["y"], dtype=np.float64)
            ids = tuple(str(value) for value in archive["sample_ids"].tolist())
            bearing = str(archive["bearing_id"].item())
    except (OSError, KeyError, ValueError) as exc:
        raise FinalValidationError(f"bearing cache is invalid: {path.name}") from exc
    if (
        bearing != expected_bearing
        or x.ndim != 2
        or y.shape != (len(x),)
        or len(ids) != len(x)
        or len(set(ids)) != len(ids)
        or not np.all(np.isfinite(x))
        or not np.all(np.isfinite(y))
    ):
        raise FinalValidationError(f"bearing cache contract mismatch: {path.name}")
    return x, y, ids


def assert_sealed_not_cached(cache_root: Path, bearings: tuple[str, ...]) -> None:
    """Refuse to call a holdout virgin if any persistent derived cache exists."""

    cache_root = Path(cache_root)
    existing = [bearing for bearing in bearings if (cache_root / f"{bearing}.npz").exists()]
    if existing:
        raise FinalValidationError(
            "sealed holdout was already cached: " + ", ".join(sorted(existing))
        )


def build_progress_rounds(
    batches: tuple[tuple[np.ndarray, np.ndarray, tuple[str, ...]], ...],
    *,
    round_count: int,
    update_fraction: float,
) -> tuple[ProgressRound, ...]:
    """Split every trajectory into ordered progress blocks, then Update/Gate."""

    if round_count < 2 or not 0.0 < update_fraction < 1.0 or not batches:
        raise ValueError("invalid progress-round configuration")
    per_bearing: list[list[tuple[np.ndarray, np.ndarray, tuple[str, ...]]]] = []
    all_ids: set[str] = set()
    feature_count: int | None = None
    for x_raw, y_raw, ids_raw in batches:
        x = np.asarray(x_raw, dtype=np.float64)
        y = np.asarray(y_raw, dtype=np.float64)
        ids = tuple(str(value) for value in ids_raw)
        if (
            x.ndim != 2
            or y.shape != (len(x),)
            or len(ids) != len(x)
            or len(x) < 2 * round_count
            or not np.all(np.isfinite(x))
            or not np.all(np.isfinite(y))
        ):
            raise ValueError("trajectory is too small or malformed")
        if feature_count is None:
            feature_count = x.shape[1]
        elif feature_count != x.shape[1]:
            raise ValueError("trajectory feature widths differ")
        if len(set(ids)) != len(ids) or all_ids.intersection(ids):
            raise ValueError("trajectory sample IDs overlap")
        all_ids.update(ids)
        indices = np.array_split(np.arange(len(x)), round_count)
        chunks: list[tuple[np.ndarray, np.ndarray, tuple[str, ...]]] = []
        for index in indices:
            cut = max(1, min(len(index) - 1, int(math.floor(len(index) * update_fraction))))
            chunks.append((x[index], y[index], tuple(ids[position] for position in index)))
            if cut <= 0 or cut >= len(index):
                raise ValueError("trajectory block cannot form disjoint Update/Gate")
        per_bearing.append(chunks)

    rounds: list[ProgressRound] = []
    for round_index in range(round_count):
        update_x: list[np.ndarray] = []
        update_y: list[np.ndarray] = []
        update_ids: list[str] = []
        gate_x: list[np.ndarray] = []
        gate_y: list[np.ndarray] = []
        gate_ids: list[str] = []
        for chunks in per_bearing:
            x, y, ids = chunks[round_index]
            cut = max(1, min(len(x) - 1, int(math.floor(len(x) * update_fraction))))
            update_x.append(x[:cut])
            update_y.append(y[:cut])
            update_ids.extend(ids[:cut])
            gate_x.append(x[cut:])
            gate_y.append(y[cut:])
            gate_ids.extend(ids[cut:])
        rounds.append(
            ProgressRound(
                update_x=np.concatenate(update_x),
                update_y=np.concatenate(update_y),
                update_ids=tuple(update_ids),
                gate_x=np.concatenate(gate_x),
                gate_y=np.concatenate(gate_y),
                gate_ids=tuple(gate_ids),
            )
        )
    return tuple(rounds)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def claim_one_time_holdout(path: Path, *, experiment_id: str) -> None:
    """Atomically claim the holdout before any sealed feature is materialized."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "experiment_id": experiment_id,
            "claimed_at_utc": datetime.now(timezone.utc).isoformat(),
            "post_open_tuning_allowed": False,
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise FinalValidationError("one-time holdout was already claimed") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def promotion_decision(
    observed: dict[str, Any], gate: dict[str, Any]
) -> dict[str, Any]:
    """Apply the preregistered final gate without task- or result-specific tuning."""

    comparisons = (
        ("development_mean_gain", ">=", "development_mean_gain_min"),
        (
            "development_worst_relative_gain",
            ">=",
            "development_worst_relative_gain_min",
        ),
        ("sealed_global_rmse_gain", ">=", "sealed_global_rmse_gain_min"),
        ("sealed_global_mae_gain", ">=", "sealed_global_mae_gain_min"),
        (
            "sealed_worst_bearing_relative_gain",
            ">=",
            "sealed_worst_bearing_relative_gain_min",
        ),
        (
            "sealed_improved_bearings",
            ">=",
            "sealed_minimum_improved_bearings",
        ),
        ("cpu_seconds", "<=", "max_cpu_seconds"),
        ("wall_seconds", "<=", "max_wall_seconds"),
        ("peak_rss_bytes", "<=", "max_rss_bytes"),
        ("checkpoint_bytes", "<=", "max_checkpoint_bytes"),
    )
    failed: list[str] = []
    for observed_name, direction, gate_name in comparisons:
        value = observed.get(observed_name)
        threshold = gate.get(gate_name)
        if (
            isinstance(value, bool)
            or isinstance(threshold, bool)
            or not isinstance(value, (int, float))
            or not isinstance(threshold, (int, float))
            or not math.isfinite(float(value))
            or not math.isfinite(float(threshold))
        ):
            failed.append(gate_name)
            continue
        passed = value >= threshold if direction == ">=" else value <= threshold
        if not passed:
            failed.append(gate_name)
    if observed.get("leakage_free") is not True:
        failed.append("leakage_free")
    if observed.get("checkpoint_verified") is not True:
        failed.append("checkpoint_verified")
    return {"passed": not failed, "failed_gates": failed}


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_parent(
    batches: tuple[tuple[np.ndarray, np.ndarray, tuple[str, ...]], ...],
    config: dict[str, Any],
) -> _NativeModel:
    x = np.concatenate([np.asarray(batch[0], dtype=np.float64) for batch in batches])
    y = np.concatenate([np.asarray(batch[1], dtype=np.float64) for batch in batches])
    if x.ndim != 2 or y.shape != (len(x),) or not len(x):
        raise ValueError("initial batches are malformed")
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    target_scale = max(float(y.std()), 1e-8)
    hidden = int(config["hidden"])
    rng = np.random.default_rng(int(config["seed"]))
    params = {
        "w1": rng.normal(0.0, 1.0 / np.sqrt(x.shape[1]), size=(x.shape[1], hidden)),
        "b1": np.zeros(hidden, dtype=np.float64),
        "w2": rng.normal(0.0, 1.0 / np.sqrt(hidden), size=(hidden, 1)),
        "b2": np.zeros(1, dtype=np.float64),
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": "FINAL-GENERALIZATION-VALIDATION",
        "task": "regression",
        "paths": [f"feature:{index}" for index in range(x.shape[1])],
        "classes": [],
        "hidden": hidden,
        "seed": int(config["seed"]),
        "epochs": 0,
        "steps": 0,
        "learning_rate": float(config["learning_rate"]),
        "batch_size": int(config["batch_size"]),
        "parameter_count": int(sum(value.size for value in params.values())),
        "target_mean": float(y.mean()),
        "target_scale": target_scale,
        "independent_holdout_parent": True,
    }
    arrays = {
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        "mean": mean.astype(np.float64),
        "scale": scale.astype(np.float64),
    }
    model = _NativeModel(arrays, metadata)
    model.fit(x, y, int(config["epochs"]))
    return model


def _regression_recipes(
    *,
    target_batch_means: tuple[float, ...],
    target_scale: float,
    previous_delayed_gain: float | None,
    failure_streak: int,
) -> tuple[str, ...]:
    plan = build_candidate_plan(
        PortfolioEvidence(
            task_kind="regression",
            target_batch_means=target_batch_means,
            target_scale=target_scale,
            previous_delayed_gain=previous_delayed_gain,
            failure_streak=failure_streak,
        )
    )
    normalized_range = (
        (max(target_batch_means) - min(target_batch_means))
        / max(1.0, abs(target_scale))
        if len(target_batch_means) >= 2
        else 0.0
    )
    secondary = plan.secondary_recipe
    if (
        normalized_range >= 1.0
        and not (previous_delayed_gain is not None and previous_delayed_gain < 0.0)
        and failure_streak < 2
    ):
        secondary = "current_e3_lr3"
    return tuple(dict.fromkeys(filter(None, (plan.primary_recipe, secondary))))


def _adapt(
    initial: _NativeModel,
    rounds: tuple[ProgressRound, ...],
    config: dict[str, Any],
) -> tuple[_NativeModel, dict[str, Any]]:
    parent = initial.clone()
    history_x: list[np.ndarray] = []
    history_y: list[np.ndarray] = []
    target_means: list[float] = []
    rows: list[dict[str, Any]] = []
    direct_predecessor: _NativeModel | None = None
    previous_delayed_gain: float | None = None
    failure_streak = 0
    exploration_remaining = int(config["exploration_budget"])
    candidate_count = deployed_count = rollback_count = 0
    contract = MetricContract("regression", "rmse", "lower", ("mae",))

    for round_index, current in enumerate(rounds, 1):
        arrival_x = np.concatenate((current.update_x, current.gate_x))
        arrival_y = np.concatenate((current.update_y, current.gate_y))
        arrival_metrics = _metrics("regression", arrival_y, _native_prediction(parent, arrival_x))
        static_metrics = _metrics("regression", arrival_y, _native_prediction(initial, arrival_x))
        arrival_gain = _signed_gain("regression", static_metrics, arrival_metrics)
        delayed_gain: float | None = None
        rolled_back = False
        if direct_predecessor is not None:
            predecessor_metrics = _metrics(
                "regression", arrival_y, _native_prediction(direct_predecessor, arrival_x)
            )
            delayed_gain = _signed_gain("regression", predecessor_metrics, arrival_metrics)
            previous_delayed_gain = delayed_gain
            if delayed_gain < 0.0:
                parent = direct_predecessor
                rollback_count += 1
                failure_streak += 1
                rolled_back = True
            else:
                failure_streak = 0
            direct_predecessor = None

        target_means.append(float(np.mean(current.update_y)))
        recipes = _regression_recipes(
            target_batch_means=tuple(target_means),
            target_scale=float(parent.meta["target_scale"]),
            previous_delayed_gain=previous_delayed_gain,
            failure_streak=failure_streak,
        )
        history_values = (
            np.concatenate(history_x)
            if history_x
            else np.empty((0, current.update_x.shape[1]), dtype=np.float64)
        )
        history_targets = (
            np.concatenate(history_y)
            if history_y
            else np.empty((0,), dtype=np.float64)
        )
        parent_gate = _metrics(
            "regression", current.gate_y, _native_prediction(parent, current.gate_x)
        )
        candidates: list[tuple[str, _NativeModel, dict[str, float]]] = []
        for recipe in recipes[:2]:
            candidate = fit_native_recipe(
                parent,
                recipe=recipe,
                history_x=history_values,
                history_y=history_targets,
                current_x=current.update_x,
                current_y=current.update_y,
            )
            metrics = _metrics(
                "regression", current.gate_y, _native_prediction(candidate, current.gate_x)
            )
            candidates.append((recipe, candidate, metrics))
            candidate_count += 1
        recipe, candidate, candidate_gate = min(
            candidates, key=lambda value: float(value[2]["rmse"])
        )
        validation_scope = f"round-{round_index:02d}-gate"
        decision = decide(
            str(config["strategy"]),
            SelectionContext(
                contract=contract,
                validation_scope=validation_scope,
                parent=ArtifactEvidence(
                    "parent", float(parent_gate["rmse"]), validation_scope, True, True
                ),
                candidate=ArtifactEvidence(
                    "candidate", float(candidate_gate["rmse"]), validation_scope, True, True
                ),
                exploration=ExplorationBudget(
                    remaining=exploration_remaining,
                    regression_tolerance=float(config["relative_regression_tolerance"])
                    * max(1.0, abs(float(parent_gate["rmse"]))),
                ),
                rollback_available=round_index < len(rounds),
            ),
        )
        if decision.selected_artifact_id == "candidate":
            direct_predecessor = parent.clone()
            parent = candidate
            deployed_count += 1
        if decision.exploration_consumed:
            exploration_remaining -= decision.exploration_consumed
        history_x.append(arrival_x)
        history_y.append(arrival_y)
        rows.append(
            {
                "round_index": round_index,
                "arrival_metrics": arrival_metrics,
                "static_metrics": static_metrics,
                "arrival_gain_vs_static": arrival_gain,
                "delayed_gain": delayed_gain,
                "rolled_back_before_training": rolled_back,
                "update_sample_count": len(current.update_y),
                "gate_sample_count": len(current.gate_y),
                "candidate_recipes": list(recipes[:2]),
                "selected_recipe": recipe if decision.selected_artifact_id == "candidate" else None,
                "parent_gate_metrics": parent_gate,
                "candidate_gate_metrics": candidate_gate,
                "selection": {
                    "selected_artifact_id": decision.selected_artifact_id,
                    "relation": decision.relation,
                    "signed_gain": decision.signed_gain,
                    "reason": decision.reason,
                    "exploration_consumed": decision.exploration_consumed,
                },
            }
        )
    gains = np.asarray([row["arrival_gain_vs_static"] for row in rows], dtype=np.float64)
    references = np.asarray([row["static_metrics"]["rmse"] for row in rows], dtype=np.float64)
    relative = gains / np.maximum(1.0, np.abs(references))
    return parent, {
        "round_count": len(rows),
        "candidate_count": candidate_count,
        "deployed_count": deployed_count,
        "rollback_count": rollback_count,
        "mean_gain_vs_static": float(np.mean(gains)),
        "worst_gain_vs_static": float(np.min(gains)),
        "worst_relative_gain_vs_static": float(np.min(relative)),
        "rounds": rows,
    }


def _evaluate_batches(
    static: _NativeModel,
    candidate: _NativeModel,
    batches: tuple[tuple[np.ndarray, np.ndarray, tuple[str, ...]], ...],
) -> dict[str, Any]:
    static_predictions: list[np.ndarray] = []
    candidate_predictions: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    per_bearing: list[dict[str, Any]] = []
    for bearing_index, (x, y, ids) in enumerate(batches, 1):
        static_prediction = _native_prediction(static, np.asarray(x, dtype=np.float64))
        candidate_prediction = _native_prediction(candidate, np.asarray(x, dtype=np.float64))
        static_metrics = _metrics("regression", np.asarray(y), static_prediction)
        candidate_metrics = _metrics("regression", np.asarray(y), candidate_prediction)
        gain = _signed_gain("regression", static_metrics, candidate_metrics)
        per_bearing.append(
            {
                "bearing_index": bearing_index,
                "sample_count": len(ids),
                "static_metrics": static_metrics,
                "candidate_metrics": candidate_metrics,
                "rmse_gain": gain,
                "relative_rmse_gain": gain / max(1.0, abs(float(static_metrics["rmse"]))),
            }
        )
        static_predictions.append(static_prediction)
        candidate_predictions.append(candidate_prediction)
        targets.append(np.asarray(y, dtype=np.float64))
    y = np.concatenate(targets)
    static_metrics = _metrics("regression", y, np.concatenate(static_predictions))
    candidate_metrics = _metrics("regression", y, np.concatenate(candidate_predictions))
    return {
        "bearing_count": len(batches),
        "sample_count": len(y),
        "static_metrics": static_metrics,
        "candidate_metrics": candidate_metrics,
        "global_rmse_gain": float(static_metrics["rmse"] - candidate_metrics["rmse"]),
        "global_mae_gain": float(static_metrics["mae"] - candidate_metrics["mae"]),
        "improved_bearings": sum(row["rmse_gain"] > 0.0 for row in per_bearing),
        "worst_bearing_relative_gain": min(
            float(row["relative_rmse_gain"]) for row in per_bearing
        ),
        "per_bearing": per_bearing,
    }


def run_one_time_validation(
    *,
    initial_batches: tuple[tuple[np.ndarray, np.ndarray, tuple[str, ...]], ...],
    development_batches: tuple[tuple[np.ndarray, np.ndarray, tuple[str, ...]], ...],
    open_sealed: Any,
    output_root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Run all development decisions before atomically opening a virgin holdout."""

    output_root = Path(output_root)
    if output_root.exists():
        raise FinalValidationError("output root must be new")
    output_root.mkdir(parents=True)
    wall_started = time.monotonic()
    cpu_started = time.process_time()
    process = psutil.Process(os.getpid())
    parent_config = {**config["parent"], "seed": int(config["seed"])}
    static = _build_parent(initial_batches, parent_config)
    static_path = output_root / "static-parent.npz"
    static.save(static_path)
    rounds = build_progress_rounds(
        development_batches,
        round_count=int(config["adaptation"]["rounds"]),
        update_fraction=float(config["adaptation"]["update_fraction"]),
    )
    candidate, development = _adapt(static, rounds, config["adaptation"])
    candidate_path = output_root / "candidate.npz"
    candidate.save(candidate_path)
    _atomic_json(
        output_root / "development-complete.json",
        {
            "experiment_id": config["experiment_id"],
            "round_count": development["round_count"],
            "candidate_checkpoint_sha256": _sha256(candidate_path),
            "sealed_opened": False,
        },
    )

    claim_one_time_holdout(
        output_root / "sealed-opened.json", experiment_id=str(config["experiment_id"])
    )
    sealed_batches = tuple(open_sealed())
    if not sealed_batches:
        raise FinalValidationError("sealed holdout is empty")
    sealed = _evaluate_batches(static, candidate, sealed_batches)

    initial_ids = {value for batch in initial_batches for value in batch[2]}
    development_ids = {value for batch in development_batches for value in batch[2]}
    sealed_ids = {value for batch in sealed_batches for value in batch[2]}
    overlap = len(initial_ids & development_ids) + len(initial_ids & sealed_ids) + len(
        development_ids & sealed_ids
    )
    loaded = _NativeModel.load(candidate_path)
    probe_x = np.asarray(sealed_batches[0][0], dtype=np.float64)
    checkpoint_verified = bool(
        np.array_equal(_native_prediction(candidate, probe_x), _native_prediction(loaded, probe_x))
    )
    observed = {
        "development_mean_gain": development["mean_gain_vs_static"],
        "development_worst_relative_gain": development["worst_relative_gain_vs_static"],
        "sealed_global_rmse_gain": sealed["global_rmse_gain"],
        "sealed_global_mae_gain": sealed["global_mae_gain"],
        "sealed_worst_bearing_relative_gain": sealed["worst_bearing_relative_gain"],
        "sealed_improved_bearings": sealed["improved_bearings"],
        "cpu_seconds": time.process_time() - cpu_started,
        "wall_seconds": time.monotonic() - wall_started,
        "peak_rss_bytes": int(process.memory_info().rss),
        "checkpoint_bytes": candidate_path.stat().st_size,
        "leakage_free": overlap == 0,
        "checkpoint_verified": checkpoint_verified,
    }
    promotion = promotion_decision(observed, config["promotion_gate"])
    summary = {
        "format": "brace-msi-final-generalization-validation.v1",
        "experiment_id": config["experiment_id"],
        "evidence_scope": config.get("evidence_scope", "one-time-independent-holdout"),
        "official_trial_count": 0,
        "public_validation_reads": 0,
        "pytrio_remote_calls": 0,
        "swanlab_sync_count": 0,
        "development": development,
        "sealed": sealed,
        "data_integrity": {
            "initial_sample_count": len(initial_ids),
            "development_sample_count": len(development_ids),
            "sealed_sample_count": len(sealed_ids),
            "sample_id_overlap_count": overlap,
        },
        "static_checkpoint": str(static_path),
        "static_checkpoint_sha256": _sha256(static_path),
        "candidate_checkpoint": str(candidate_path),
        "candidate_checkpoint_sha256": _sha256(candidate_path),
        "checkpoint_verified": checkpoint_verified,
        "resources": {
            "cpu_seconds": observed["cpu_seconds"],
            "wall_seconds": observed["wall_seconds"],
            "peak_rss_bytes": observed["peak_rss_bytes"],
            "checkpoint_bytes": observed["checkpoint_bytes"],
        },
        "promotion": promotion,
    }
    _atomic_json(output_root / "summary.json", summary)
    return summary
