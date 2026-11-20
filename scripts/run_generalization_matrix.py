"""Run the preregistered four-strategy matrix on legal ten-round proxy streams."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_formal.metrics import MetricContract  # noqa: E402
from brace_msi.competitive_policy import PortfolioEvidence, build_candidate_plan  # noqa: E402
from brace_msi.method_pilot import (  # noqa: E402
    _metrics,
    _native_prediction,
    _signed_gain,
    fit_native_recipe,
    fit_performance_method,
)
from brace_msi.platform_runtime import _NativeModel, _read_rows  # noqa: E402
from brace_msi.selection_strategies import (  # noqa: E402
    ArtifactEvidence,
    ExplorationBudget,
    RecipeFeedback,
    SelectionContext,
    decide,
    update_recipe_feedback,
)


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}
STRATEGIES = (
    "strict_parent_gate",
    "bounded_exploration",
    "conditional_champion",
    "recipe_feedback",
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _experiment_id(output_root: Path) -> str:
    value = output_root.name.strip()
    if not value:
        raise ValueError("output root must have an experiment ID directory name")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _native_state_digest(model: Any) -> str:
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            model.meta,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    groups = (
        ("params", model.params),
        ("first", model.first),
        ("second", model.second),
        ("preprocessing", {"mean": model.mean, "scale": model.scale}),
    )
    for group_name, arrays in groups:
        for name, value in sorted(arrays.items()):
            array = np.asarray(value)
            digest.update(group_name.encode("utf-8"))
            digest.update(name.encode("utf-8"))
            digest.update(array.dtype.str.encode("ascii"))
            digest.update(json.dumps(array.shape).encode("ascii"))
            digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _round_root(runtime_inputs: Path, round_index: int) -> Path:
    if not 1 <= round_index <= 10:
        raise ValueError("round index must be within the frozen ten-round stream")
    if runtime_inputs.is_symlink() or runtime_inputs.is_junction():
        raise ValueError("runtime input root cannot be a symlink or junction")
    base = runtime_inputs.resolve(strict=True)
    raw_candidate = base / f"round-{round_index:02d}"
    if raw_candidate.is_symlink() or raw_candidate.is_junction():
        raise ValueError("round directory cannot be a symlink or junction")
    candidate = raw_candidate.resolve(strict=True)
    if candidate.parent != base:
        raise ValueError("round directory escapes the frozen runtime input root")
    return candidate


def _round_file(round_root: Path, name: str) -> Path:
    if name not in {"feedback.jsonl", "update.jsonl", "gate.jsonl"}:
        raise ValueError("unsupported round input file")
    path = round_root / name
    if path.is_symlink():
        raise ValueError("round input symlinks are not allowed")
    resolved = path.resolve(strict=True)
    if resolved.parent != round_root:
        raise ValueError("round input escapes its materialized directory")
    return resolved


def _candidate_recipes(
    *,
    task_kind: str,
    target_batch_means: tuple[float, ...],
    target_scale: float,
    previous_delayed_gain: float | None,
    failure_streak: int,
    method_portfolio: bool = False,
    classification_balance_only: bool = False,
) -> tuple[str, ...]:
    plan = build_candidate_plan(
        PortfolioEvidence(
            task_kind=task_kind,
            target_batch_means=target_batch_means,
            target_scale=target_scale,
            previous_delayed_gain=previous_delayed_gain,
            failure_streak=failure_streak,
        )
    )
    normalized_range = (
        (max(target_batch_means) - min(target_batch_means)) / max(1.0, abs(target_scale))
        if len(target_batch_means) >= 2
        else 0.0
    )
    if method_portfolio or classification_balance_only:
        if task_kind == "classification":
            return ("balanced_current_e3", "native_recent_e3")
        if method_portfolio:
            if normalized_range >= 1.0:
                return (
                    "native_current_e3_lr3",
                    "asymmetric_current_e3_lr3",
                )
            return ("soup_current_e3_alpha0.25", "huber_recent_e3")
    secondary = plan.secondary_recipe
    if (
        task_kind == "regression"
        and normalized_range >= 1.0
        and not (previous_delayed_gain is not None and previous_delayed_gain < 0.0)
        and failure_streak < 2
    ):
        secondary = "current_e3_lr3"
    return tuple(dict.fromkeys(filter(None, (plan.primary_recipe, secondary))))


def _recovery_lags(gains: tuple[float, ...]) -> tuple[int, ...]:
    lags: list[int] = []
    start: int | None = None
    for index, gain in enumerate(gains):
        if gain < 0.0 and start is None:
            start = index
        elif gain >= 0.0 and start is not None:
            lags.append(index - start)
            start = None
    return tuple(lags)


def _relative_signed_gain(signed_gain: float, reference: float) -> float:
    return signed_gain / max(1.0, abs(reference))


def _rollback_available(*, round_index: int, parent_recoverable: bool) -> bool:
    return bool(parent_recoverable and round_index < 10)


def _promotion_pass(
    rows: list[dict[str, Any]],
    *,
    baseline_rows: list[dict[str, Any]],
    strategy: str,
) -> bool:
    if len(rows) != len(PACKAGES):
        return False
    if strategy == "conditional_champion":
        return False
    baseline = {str(row["profile"]): row for row in baseline_rows}
    if set(baseline) != {str(row["profile"]) for row in rows}:
        return False
    gains = [float(row["mean_arrival_gain_vs_static"]) for row in rows]
    aggregate_relative = float(
        np.mean([float(row["mean_relative_gain_vs_static"]) for row in rows])
    )
    baseline_aggregate = float(
        np.mean([float(row["mean_relative_gain_vs_static"]) for row in baseline_rows])
    )
    worst_relative = min(float(row["worst_relative_gain_vs_static"]) for row in rows)
    baseline_worst = min(
        float(row["worst_relative_gain_vs_static"]) for row in baseline_rows
    )
    return bool(
        all(not bool(row["catastrophic_regression"]) for row in rows)
        and all(gain >= 0.0 for gain in gains)
        and sum(gain > 0.0 for gain in gains) >= 2
        and all(int(row["training_round_count"]) == 10 for row in rows)
        and all(int(row["candidate_count"]) >= 10 for row in rows)
        and all(int(row["confirmation_files_read"]) == 0 for row in rows)
        and all(bool(row["final_selection_safe"]) for row in rows)
        and all(bool(row["final_checkpoint_verified"]) for row in rows)
        and aggregate_relative >= baseline_aggregate
        and worst_relative >= baseline_worst
    )


def _contract(task: str) -> MetricContract:
    if task == "classification":
        return MetricContract(task, "macro_f1", "higher", ("accuracy",))
    if task == "regression":
        return MetricContract(task, "rmse", "lower", ("mae",))
    raise ValueError("unsupported task")


def _primary(metrics: dict[str, float], contract: MetricContract) -> float:
    value = float(metrics[contract.name])
    if not math.isfinite(value):
        raise ValueError("non-finite primary metric")
    return value


def _best_candidate(
    rows: list[dict[str, Any]], contract: MetricContract
) -> dict[str, Any]:
    if not rows:
        raise RuntimeError("every round must produce at least one real candidate")
    reverse = contract.direction == "higher"
    return sorted(rows, key=lambda row: _primary(row["gate_metrics"], contract), reverse=reverse)[0]


def _best_historical(
    history: list[tuple[str, _NativeModel]],
    *,
    gate_x: np.ndarray,
    gate_y: np.ndarray,
    task: str,
    contract: MetricContract,
) -> tuple[str, _NativeModel, dict[str, float]] | None:
    if not history:
        return None
    evaluated = [
        (
            artifact_id,
            model,
            _metrics(task, gate_y, _native_prediction(model, gate_x)),
        )
        for artifact_id, model in history
    ]
    reverse = contract.direction == "higher"
    return sorted(
        evaluated, key=lambda row: _primary(row[2], contract), reverse=reverse
    )[0]


def _empty_history(parent: _NativeModel) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.empty((0, len(parent.meta["paths"])), dtype=np.float64),
        np.empty(
            (0,),
            dtype=np.int64 if parent.meta["task"] == "classification" else np.float64,
        ),
    )


def _run_profile(
    *,
    strategy: str,
    profile: str,
    stream_root: Path,
    package_root: Path,
    output_root: Path,
    method_portfolio: bool = False,
    classification_balance_only: bool = False,
) -> dict[str, Any]:
    initial_path = package_root / PACKAGES[profile] / "checkpoint.npz"
    initial = _NativeModel.load(initial_path)
    parent = initial.clone()
    task = str(parent.meta["task"])
    contract = _contract(task)
    runtime_inputs = stream_root / profile / "runtime-inputs"
    history_x: list[np.ndarray] = []
    history_y: list[np.ndarray] = []
    recoverable: list[tuple[str, _NativeModel]] = [("initial", initial.clone())]
    target_batch_means: list[float] = []
    rounds: list[dict[str, Any]] = []
    direct_predecessor: _NativeModel | None = None
    deployed_recipe: str | None = None
    previous_delayed_gain: float | None = None
    failure_streak = 0
    feedback_state = RecipeFeedback()
    exploration_remaining = 2
    candidate_attempts = candidate_count = deployed_count = rollback_count = 0
    cpu_total = 0.0
    wall_started = time.perf_counter()
    process = psutil.Process(os.getpid())
    peak_rss = int(process.memory_info().rss)

    for round_index in range(1, 11):
        round_root = _round_root(runtime_inputs, round_index)
        feedback = _read_rows(_round_file(round_root, "feedback.jsonl"), initial, require_answers=True)
        update = _read_rows(_round_file(round_root, "update.jsonl"), initial, require_answers=True)
        gate = _read_rows(_round_file(round_root, "gate.jsonl"), initial, require_answers=True)
        deployed_arrival_metrics = _metrics(
            task, feedback["y"], _native_prediction(parent, feedback["x"])
        )
        static_metrics = _metrics(
            task, feedback["y"], _native_prediction(initial, feedback["x"])
        )
        arrival_gain = _signed_gain(task, static_metrics, deployed_arrival_metrics)
        delayed_gain: float | None = None
        delayed_predecessor_metrics: dict[str, float] | None = None
        rolled_back = False
        if direct_predecessor is not None:
            delayed_predecessor_metrics = _metrics(
                task,
                feedback["y"],
                _native_prediction(direct_predecessor, feedback["x"]),
            )
            delayed_gain = _signed_gain(
                task, delayed_predecessor_metrics, deployed_arrival_metrics
            )
            previous_delayed_gain = delayed_gain
            if delayed_gain < 0.0:
                if strategy == "recipe_feedback" and deployed_recipe is not None:
                    feedback_state = update_recipe_feedback(
                        feedback_state,
                        deployed_recipe,
                        outcome="performance_regression",
                        round_index=round_index,
                    )
                parent = direct_predecessor
                rollback_count += 1
                failure_streak += 1
                rolled_back = True
            else:
                failure_streak = 0
            direct_predecessor = None
            deployed_recipe = None

        target_batch_means.append(float(np.mean(update["y"])))
        recipes = list(
            _candidate_recipes(
                task_kind=task,
                target_batch_means=tuple(target_batch_means),
                target_scale=float(parent.meta["target_scale"]),
                previous_delayed_gain=previous_delayed_gain,
                failure_streak=failure_streak,
                method_portfolio=method_portfolio,
                classification_balance_only=classification_balance_only,
            )
        )
        if strategy == "recipe_feedback":
            recipes = [
                recipe
                for recipe in recipes
                if feedback_state.is_available(recipe, round_index=round_index)
            ]
            if not recipes:
                if method_portfolio or (
                    classification_balance_only and task == "classification"
                ):
                    recipes = [
                        _candidate_recipes(
                            task_kind=task,
                            target_batch_means=tuple(target_batch_means),
                            target_scale=float(parent.meta["target_scale"]),
                            previous_delayed_gain=previous_delayed_gain,
                            failure_streak=failure_streak,
                            method_portfolio=method_portfolio,
                            classification_balance_only=classification_balance_only,
                        )[0]
                    ]
                else:
                    recipes = ["current_e1"]

        prior_x, prior_y = _empty_history(parent)
        if history_x:
            prior_x = np.concatenate(history_x, axis=0)
            prior_y = np.concatenate(history_y, axis=0)
        parent_gate = _metrics(task, gate["y"], _native_prediction(parent, gate["x"]))
        candidate_rows: list[dict[str, Any]] = []
        candidate_models: dict[str, _NativeModel] = {}
        for recipe in recipes[:2]:
            candidate_attempts += 1
            started_cpu = time.process_time()
            try:
                if method_portfolio or (
                    classification_balance_only and task == "classification"
                ):
                    candidate = fit_performance_method(
                        parent,
                        method=recipe,
                        history_x=prior_x,
                        history_y=prior_y,
                        current_x=update["x"],
                        current_y=update["y"],
                    )
                else:
                    candidate = fit_native_recipe(
                        parent,
                        recipe=recipe,
                        history_x=prior_x,
                        history_y=prior_y,
                        current_x=update["x"],
                        current_y=update["y"],
                    )
                gate_metrics = _metrics(
                    task, gate["y"], _native_prediction(candidate, gate["x"])
                )
                if not all(math.isfinite(float(value)) for value in gate_metrics.values()):
                    raise ValueError("candidate metrics are non-finite")
                candidate_count += 1
                artifact_id = f"candidate-{round_index:02d}-{len(candidate_rows) + 1}"
                candidate_models[artifact_id] = candidate
                candidate_rows.append(
                    {
                        "artifact_id": artifact_id,
                        "recipe": recipe,
                        "gate_metrics": gate_metrics,
                        "gate_gain": _signed_gain(task, parent_gate, gate_metrics),
                        "cpu_seconds": time.process_time() - started_cpu,
                        "status": "trained",
                    }
                )
            except Exception as exc:
                if strategy == "recipe_feedback":
                    feedback_state = update_recipe_feedback(
                        feedback_state,
                        recipe,
                        outcome="hard_failure",
                        round_index=round_index,
                    )
                candidate_rows.append(
                    {
                        "artifact_id": None,
                        "recipe": recipe,
                        "cpu_seconds": time.process_time() - started_cpu,
                        "status": "hard_failure",
                        "error_type": type(exc).__name__,
                    }
                )
            cpu_total += time.process_time() - started_cpu
        trained_rows = [row for row in candidate_rows if row["status"] == "trained"]
        chosen_candidate = _best_candidate(trained_rows, contract)
        candidate_artifact_id = str(chosen_candidate["artifact_id"])
        candidate_model = candidate_models[candidate_artifact_id]

        champion = None
        champion_model = None
        if strategy == "conditional_champion":
            historical = _best_historical(
                recoverable,
                gate_x=gate["x"],
                gate_y=gate["y"],
                task=task,
                contract=contract,
            )
            if historical is not None:
                _, champion_model, champion_metrics = historical
                champion = ArtifactEvidence(
                    "champion",
                    _primary(champion_metrics, contract),
                    gate["sha256"],
                    True,
                    True,
                )

        tolerance = (
            0.002
            if contract.direction == "higher"
            else 0.01 * max(1.0, abs(_primary(parent_gate, contract)))
        )
        selection_strategy = strategy
        context = SelectionContext(
            contract=contract,
            validation_scope=gate["sha256"],
            parent=ArtifactEvidence(
                "parent", _primary(parent_gate, contract), gate["sha256"], True, True
            ),
            candidate=ArtifactEvidence(
                "candidate",
                _primary(chosen_candidate["gate_metrics"], contract),
                gate["sha256"],
                True,
                True,
            ),
            champion=champion,
            exploration=ExplorationBudget(
                remaining=exploration_remaining,
                regression_tolerance=tolerance,
            ),
            rollback_available=True,
        )
        context = context.with_rollback_available(
            _rollback_available(round_index=round_index, parent_recoverable=True)
        )
        decision = decide(selection_strategy, context)
        previous_parent = parent.clone()
        previous_parent_id = f"stable-{round_index - 1:02d}"
        selected_recipe: str | None = None
        if decision.selected_artifact_id == "candidate":
            parent = candidate_model
            selected_recipe = str(chosen_candidate["recipe"])
        elif decision.selected_artifact_id == "champion":
            if champion_model is None:
                raise RuntimeError("champion decision lacks a recoverable model")
            parent = champion_model.clone()
            selected_recipe = "restored_historical_model"

        changed = decision.selected_artifact_id != "parent"
        if changed:
            recoverable.append((previous_parent_id, previous_parent))
            direct_predecessor = previous_parent
            deployed_recipe = selected_recipe
            deployed_count += 1
        if decision.exploration_consumed:
            exploration_remaining -= decision.exploration_consumed
        if strategy == "recipe_feedback":
            if decision.selected_artifact_id == "candidate":
                feedback_state = update_recipe_feedback(
                    feedback_state,
                    str(chosen_candidate["recipe"]),
                    outcome="success",
                    round_index=round_index,
                )
            elif float(chosen_candidate["gate_gain"]) < 0.0:
                feedback_state = update_recipe_feedback(
                    feedback_state,
                    str(chosen_candidate["recipe"]),
                    outcome="performance_regression",
                    round_index=round_index,
                )

        history_x.append(feedback["x"])
        history_y.append(feedback["y"])
        peak_rss = max(peak_rss, int(process.memory_info().rss))
        rounds.append(
            {
                "round_index": round_index,
                "feedback_sha256": feedback["sha256"],
                "update_sha256": update["sha256"],
                "gate_sha256": gate["sha256"],
                "update_sample_count": len(update["ids"]),
                "gate_sample_count": len(gate["ids"]),
                "arrival_metrics": deployed_arrival_metrics,
                "static_metrics": static_metrics,
                "arrival_gain_vs_static": arrival_gain,
                "delayed_predecessor_metrics": delayed_predecessor_metrics,
                "delayed_gain": delayed_gain,
                "rolled_back_before_training": rolled_back,
                "parent_gate_metrics": parent_gate,
                "candidates": candidate_rows,
                "selection": {
                    "strategy": decision.strategy,
                    "selected_artifact_id": decision.selected_artifact_id,
                    "relation": decision.relation,
                    "signed_gain": decision.signed_gain,
                    "reason": decision.reason,
                    "exploration_consumed": decision.exploration_consumed,
                    "selected_recipe": selected_recipe,
                },
                "recipe_feedback": {
                    "cooldown_until": list(feedback_state.cooldown_until),
                    "quarantined": list(feedback_state.quarantined),
                },
            }
        )

    task_output = output_root / strategy / profile
    task_output.mkdir(parents=True, exist_ok=True)
    checkpoint = task_output / "checkpoint.npz"
    selected_state_sha256 = _native_state_digest(parent)
    selected_prediction = _native_prediction(parent, gate["x"])
    parent.save(checkpoint)
    loaded = _NativeModel.load(checkpoint)
    loaded_state_sha256 = _native_state_digest(loaded)
    loaded_prediction = _native_prediction(loaded, gate["x"])
    final_checkpoint_verified = bool(
        selected_state_sha256 == loaded_state_sha256
        and np.array_equal(selected_prediction, loaded_prediction)
    )
    final_checkpoint_gate_metrics = _metrics(task, gate["y"], loaded_prediction)
    gains = tuple(float(row["arrival_gain_vs_static"]) for row in rounds)
    references = tuple(
        _primary(row["static_metrics"], contract) for row in rounds
    )
    relative = tuple(
        _relative_signed_gain(gain, reference)
        for gain, reference in zip(gains, references, strict=True)
    )
    lags = _recovery_lags(gains)
    drifts = tuple(
        abs(right - left) / max(1.0, abs(float(parent.meta["target_scale"])))
        for left, right in zip(target_batch_means, target_batch_means[1:])
    )
    result = {
        "strategy": strategy,
        "profile": profile,
        "task": task,
        "round_count": len(rounds),
        "training_round_count": sum(
            any(candidate["status"] == "trained" for candidate in row["candidates"])
            for row in rounds
        ),
        "candidate_attempts": candidate_attempts,
        "candidate_count": candidate_count,
        "deployed_count": deployed_count,
        "rollback_count": rollback_count,
        "mean_arrival_gain_vs_static": float(np.mean(gains)),
        "mean_relative_gain_vs_static": float(np.mean(relative)),
        "worst_arrival_gain_vs_static": float(np.min(gains)),
        "worst_relative_gain_vs_static": float(np.min(relative)),
        "win_rate_vs_static": float(np.mean(np.asarray(gains) > 0.0)),
        "negative_stage_count": int(np.sum(np.asarray(gains) < 0.0)),
        "recovery_lags": list(lags),
        "mean_recovery_rounds": float(np.mean(lags)) if lags else 0.0,
        "observed_drift_strength_mean": float(np.mean(drifts)) if drifts else 0.0,
        "observed_drift_strength_max": float(np.max(drifts)) if drifts else 0.0,
        "cpu_seconds": cpu_total,
        "wall_seconds": time.perf_counter() - wall_started,
        "peak_rss_bytes": peak_rss,
        "token_count": 0,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "catastrophic_regression": bool(np.min(relative) < -0.05),
        "final_selection_safe": not bool(
            rounds[-1]["selection"]["selected_artifact_id"] == "candidate"
            and rounds[-1]["selection"]["relation"] == "regressed"
        ),
        "final_checkpoint_verified": final_checkpoint_verified,
        "final_checkpoint_verification": {
            "final_selected_artifact_id": rounds[-1]["selection"]["selected_artifact_id"],
            "selected_state_sha256": selected_state_sha256,
            "loaded_state_sha256": loaded_state_sha256,
            "prediction_equal": bool(np.array_equal(selected_prediction, loaded_prediction)),
            "gate_metrics": final_checkpoint_gate_metrics,
        },
        "history_artifact_restore_verified": False,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "rounds": rounds,
    }
    _write_json(task_output / "result.json", result)
    return result


def run_matrix(
    *,
    stream_root: Path,
    package_root: Path,
    output_root: Path,
    method_portfolio: bool = False,
    classification_balance_only: bool = False,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError("output root must be new")
    output_root.mkdir(parents=True)
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for strategy in STRATEGIES:
        for profile in PACKAGES:
            try:
                results.append(
                    _run_profile(
                        strategy=strategy,
                        profile=profile,
                        stream_root=stream_root,
                        package_root=package_root,
                        output_root=output_root,
                        method_portfolio=method_portfolio,
                        classification_balance_only=classification_balance_only,
                    )
                )
            except Exception as exc:
                failures.append(
                    {
                        "strategy": strategy,
                        "profile": profile,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
    compact = [{key: value for key, value in row.items() if key != "rounds"} for row in results]
    strategy_summary: dict[str, Any] = {}
    strict_rows = [row for row in compact if row["strategy"] == "strict_parent_gate"]
    for strategy in STRATEGIES:
        rows = [row for row in compact if row["strategy"] == strategy]
        strategy_summary[strategy] = {
            "completed_tasks": len(rows),
            "mean_task_gain": float(
                np.mean([row["mean_arrival_gain_vs_static"] for row in rows])
            )
            if rows
            else None,
            "minimum_task_gain": float(
                np.min([row["mean_arrival_gain_vs_static"] for row in rows])
            )
            if rows
            else None,
            "worst_relative_gain": float(
                np.min([row["worst_relative_gain_vs_static"] for row in rows])
            )
            if rows
            else None,
            "positive_task_count": sum(
                row["mean_arrival_gain_vs_static"] > 0.0 for row in rows
            ),
            "catastrophic_task_count": sum(row["catastrophic_regression"] for row in rows),
            "cpu_seconds": float(np.sum([row["cpu_seconds"] for row in rows])),
            "wall_seconds": float(np.sum([row["wall_seconds"] for row in rows])),
            "token_count": 0,
            "promotion_pass": _promotion_pass(
                rows, baseline_rows=strict_rows, strategy=strategy
            ),
        }
    valid = not failures and all(row["round_count"] == 10 for row in compact)
    summary = {
        "format": "brace-msi-generalization-matrix.v1",
        "experiment_id": _experiment_id(output_root),
        "scope": "legal-ten-round-proxy-stream-no-confirmation",
        "method_portfolio": method_portfolio,
        "classification_balance_only": classification_balance_only,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "pytrio_remote_calls": 0,
        "swanlab_sync_count": 0,
        "wall_seconds": time.perf_counter() - started,
        "valid": valid,
        "failures": failures,
        "strategy_summary": strategy_summary,
        "results": compact,
    }
    _write_json(output_root / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stream-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--method-portfolio", action="store_true")
    parser.add_argument("--classification-balance-only", action="store_true")
    args = parser.parse_args()
    summary = run_matrix(
        stream_root=args.stream_root,
        package_root=args.package_root,
        output_root=args.output_root,
        method_portfolio=args.method_portfolio,
        classification_balance_only=args.classification_balance_only,
    )
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

