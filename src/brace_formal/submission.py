"""Minimal official workspace-v2 submission built from verified primitives only."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import numpy as np

from .agent import request_deployment_decision, request_training_proposal
from .data import _flatten, load_rows
from .metrics import evaluate
from .model import FormalModel
from .portfolio import fit_recipe, recipe_settings
from .workspace import create_round_paths


TASKS = ("classification", "regression")
PREDICT_ARGV = ["python3", "/app/harness.py", "predict"]
_SEED = 20261117


def _parent_checkpoint(rnd: Any) -> Path:
    descriptor = getattr(rnd.parent, "descriptor", None)
    paths = descriptor.get("checkpoint_paths") if isinstance(descriptor, Mapping) else None
    matches = [item for item in paths or () if isinstance(item, str) and item.endswith(".npz")]
    if len(matches) != 1:
        raise ValueError("parent artifact must declare exactly one NPZ checkpoint")
    return Path(rnd.parent.path(matches[0]))


def _primary_contract(rnd: Any, model: FormalModel) -> tuple[str, str]:
    contract = getattr(rnd, "task", None)
    metric = contract.get("metric") if isinstance(contract, Mapping) else None
    direction = contract.get("metric_direction") if isinstance(contract, Mapping) else None
    defaults = ("macro_f1", "higher") if model.meta["task"] == "classification" else ("rmse", "lower")
    if metric not in ({"accuracy", "macro_f1"} if model.meta["task"] == "classification" else {"mae", "rmse"}):
        metric = defaults[0]
    if direction not in {"higher", "lower"}:
        direction = defaults[1]
    return str(metric), str(direction)


def _platform_metrics(receipt: Mapping[str, Any] | None) -> dict[str, float]:
    summary = receipt.get("summary") if isinstance(receipt, Mapping) else None
    metrics = summary.get("metrics") if isinstance(summary, Mapping) else None
    if not isinstance(metrics, Mapping):
        return {}
    result: dict[str, float] = {}
    for key, value in metrics.items():
        if isinstance(key, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            result[key] = float(value)
    return result


def _state_payload(state_root: Path) -> dict[str, Any]:
    path = state_root / "formal-state.json"
    if not path.exists():
        return {"format": "brace-formal-state.v1", "rounds": []}
    if path.is_symlink() or not path.is_file():
        raise ValueError("formal state must be a regular file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != "brace-formal-state.v1" or not isinstance(payload.get("rounds"), list):
        raise ValueError("formal state is invalid")
    return payload


def _write_state(state_root: Path, record: Mapping[str, Any]) -> None:
    payload = _state_payload(state_root)
    rounds = payload["rounds"]
    if rounds and rounds[-1].get("round_index", 0) >= record["round_index"]:
        raise ValueError("state already contains this or a future round")
    rounds.append(dict(record))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n"
    temporary = state_root / "formal-state.json.tmp"
    temporary.write_text(encoded, encoding="utf-8")
    os.replace(temporary, state_root / "formal-state.json")


def _context(rnd: Any, model: FormalModel, train_count: int, validation_count: int, parent_metrics: Mapping[str, float], history: list[Any]) -> dict[str, Any]:
    return {
        "task": model.meta["task"],
        "round_index": int(rnd.round_index),
        "train_samples": train_count,
        "validation_samples": validation_count,
        "current_batch_is_new_training_data": True,
        "candidate_training_required": True,
        "deployment_is_separately_gated": True,
        "parent_metrics": dict(parent_metrics),
        "parent_epochs": int(model.meta["epochs"]),
        "parent_learning_rate": float(model.meta["learning_rate"]),
        "history_records": len(history),
    }


def _hard_gate(parent: FormalModel, checkpoint: Path, metrics: Mapping[str, float]) -> list[str]:
    failures: list[str] = []
    if checkpoint.stat().st_size > 64 * 1024 * 1024:
        failures.append("checkpoint_exceeds_64_mib")
    if not metrics or any(not math.isfinite(float(value)) for value in metrics.values()):
        failures.append("candidate_metrics_nonfinite")
    try:
        loaded = FormalModel.load(checkpoint)
    except (OSError, ValueError, KeyError) as exc:
        failures.append(f"checkpoint_unloadable:{type(exc).__name__}")
    else:
        if loaded.meta["task"] != parent.meta["task"] or loaded.meta["paths"] != parent.meta["paths"]:
            failures.append("checkpoint_contract_changed")
    return failures


def _training_data_summary(model: FormalModel, values: np.ndarray, targets: np.ndarray) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "sample_count": int(values.shape[0]),
        "feature_count": int(values.shape[1]),
        "finite_fraction": float(np.mean(np.isfinite(values))),
        "mean_absolute_feature_value": float(np.mean(np.abs(values))),
        "max_absolute_feature_value": float(np.max(np.abs(values))),
    }
    if model.meta["task"] == "classification":
        counts = np.bincount(targets.astype(np.int64), minlength=len(model.meta["classes"]))
        summary["class_counts"] = {
            str(label): int(count) for label, count in zip(model.meta["classes"], counts, strict=True)
        }
    else:
        summary["target"] = {
            "minimum": float(np.min(targets)),
            "maximum": float(np.max(targets)),
            "mean": float(np.mean(targets)),
            "standard_deviation": float(np.std(targets)),
        }
    return summary


def _peak_rss_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def train(rnd: Any) -> None:
    """Execute one bounded decision transaction using the official Round object."""

    history = rnd.history()
    if not isinstance(history, list):
        raise ValueError("history must be a list")
    parent_path = _parent_checkpoint(rnd)
    parent = FormalModel.load(parent_path)
    training = load_rows(rnd.data.train_path, parent, require_answers=True)
    validation = load_rows(rnd.data.validation_path, parent, require_answers=True)
    parent_metrics = evaluate(parent, validation.x, validation.y)

    workspace = Path(os.environ.get("CONTEST_WORK", "/workspace"))
    dataset_key = str(getattr(rnd, "dataset_key", "default"))
    paths = create_round_paths(
        workspace,
        int(rnd.round_index),
        str(getattr(rnd, "stage_id", "default")),
        dataset_key,
    )
    state = Path(rnd.state_workspace(paths.state))
    prior_state = _state_payload(state)
    recent_history = [
        {
            key: row.get(key)
            for key in (
                "round_index", "recipe", "parent_metrics", "candidate_metrics",
                "deployment_decision", "outcome", "cpu_seconds",
            )
        }
        for row in prior_state["rounds"][-5:]
        if isinstance(row, Mapping)
    ]
    training_context = _context(
        rnd, parent, len(training.ids), len(validation.ids), parent_metrics, history
    )
    training_context.update(
        {
            "available_recipes": ["e1_lr1", "e3_lr3", "soup_e3_alpha0.25"],
            "training_data_summary": _training_data_summary(parent, training.x, training.y),
            "recent_experiment_history": recent_history,
        }
    )
    training_decision = request_training_proposal(rnd, training_context)

    selected_artifact = rnd.parent.artifact_id
    recipe = training_decision.recipe
    executed = recipe_settings(parent, recipe)
    started = time.process_time()
    candidate = fit_recipe(parent, recipe, training.x, training.y)
    cpu_seconds = time.process_time() - started
    candidate_metrics = evaluate(candidate, validation.x, validation.y)
    paths.candidate.mkdir(parents=True, exist_ok=False)
    checkpoint = paths.candidate / "checkpoint.npz"
    candidate.save(checkpoint)
    safety_failures = _hard_gate(parent, checkpoint, candidate_metrics)

    metric, direction = _primary_contract(rnd, parent)
    deployment_decision = request_deployment_decision(
        rnd,
        {
            "task": parent.meta["task"],
            "round_index": int(rnd.round_index),
            "metric": metric,
            "metric_direction": direction,
            "recipe": recipe,
            "parent_metrics": parent_metrics,
            "candidate_metrics": candidate_metrics,
            "resource_evidence": {
                "cpu_seconds": cpu_seconds,
                "checkpoint_bytes": checkpoint.stat().st_size,
                "parameter_count": int(candidate.meta["parameter_count"]),
                "peak_rss_bytes": _peak_rss_bytes(),
            },
            "history": recent_history,
            "hard_safety_failures": safety_failures,
        },
    )

    outcome = "candidate_retained_parent_by_agent"
    candidate_receipt: Mapping[str, Any] | None = None
    platform_metrics: dict[str, float] = {}
    candidate_receipt = rnd.submit_candidate(
        paths.candidate,
        hypothesis=training_decision.rationale,
        change_summary="Qwen selected a controlled parent-compatible recipe; the candidate was trained and evaluated before a separate Qwen deployment decision.",
        configuration={
            "action": "train",
            "training_call_id": training_decision.call_id,
            "deployment_call_id": deployment_decision.call_id,
            "deployment_decision": deployment_decision.decision,
            "executed_recipe": recipe,
            "executed_epochs": executed["epochs"],
            "executed_learning_rate_multiplier": executed["learning_rate_multiplier"],
            "effective_learning_rate": executed["effective_learning_rate"],
            "optimizer_seed": executed["optimizer_seed"],
            "fold_assignment_seed": _SEED,
            "metric": metric,
            "direction": direction,
        },
        seed=int(executed["optimizer_seed"]),
        checkpoint_paths=["checkpoint.npz"],
        code_paths=[],
        predict_argv=PREDICT_ARGV,
    )
    platform_metrics = _platform_metrics(candidate_receipt)
    if safety_failures:
        outcome = "candidate_rejected_by_safety_gate"
    elif deployment_decision.decision == "deploy":
        selected_artifact = candidate_receipt["artifact_id"]
        outcome = "candidate_selected_by_agent"
    elif deployment_decision.decision == "rollback":
        outcome = "candidate_rolled_back_by_agent"

    record = {
        "round_index": int(rnd.round_index),
        "stage_id": str(getattr(rnd, "stage_id", "")),
        "dataset_key": dataset_key,
        "action": "train",
        "training_call_id": training_decision.call_id,
        "training_rationale": training_decision.rationale,
        "training_parse_error": training_decision.parse_error,
        "deployment_call_id": deployment_decision.call_id,
        "deployment_decision": deployment_decision.decision,
        "deployment_rationale": deployment_decision.rationale,
        "deployment_parse_error": deployment_decision.parse_error,
        "outcome": outcome,
        "executed_epochs": executed["epochs"],
        "executed_learning_rate_multiplier": executed["learning_rate_multiplier"],
        "effective_learning_rate": executed["effective_learning_rate"],
        "optimizer_seed": executed["optimizer_seed"],
        "fold_assignment_seed": _SEED,
        "cpu_seconds": cpu_seconds,
        "checkpoint_bytes": checkpoint.stat().st_size,
        "safety_failures": safety_failures,
        "parent_checkpoint_sha256": str(rnd.parent.checkpoint_sha256),
        "train_sha256": training.sha256,
        "validation_sha256": validation.sha256,
        "parent_metrics": parent_metrics,
        "candidate_metrics": candidate_metrics,
        "platform_metrics": platform_metrics,
        "recipe": recipe,
        "selected_artifact_id": selected_artifact,
    }
    _write_state(state, record)
    rnd.save_state(state)

    configuration = {
        "action": "train",
        "training_call_id": training_decision.call_id,
        "training_rationale": training_decision.rationale,
        "training_parse_error": training_decision.parse_error,
        "deployment_call_id": deployment_decision.call_id,
        "deployment_decision": deployment_decision.decision,
        "deployment_rationale": deployment_decision.rationale,
        "deployment_parse_error": deployment_decision.parse_error,
        "outcome": outcome,
        "executed_epochs": executed["epochs"],
        "executed_learning_rate_multiplier": executed["learning_rate_multiplier"],
        "effective_learning_rate": executed["effective_learning_rate"],
        "optimizer_seed": executed["optimizer_seed"],
        "fold_assignment_seed": _SEED,
        "parent_metrics": parent_metrics,
        "candidate_metrics": candidate_metrics,
        "platform_metrics": platform_metrics,
        "metric": metric,
        "recipe": recipe,
        "cpu_seconds": cpu_seconds,
        "checkpoint_bytes": checkpoint.stat().st_size,
        "safety_failures": safety_failures,
    }
    rnd.finish(
        selected_artifact_id=selected_artifact,
        hypothesis=training_decision.rationale,
        change_summary="Trained one Qwen-selected candidate, evaluated it locally, and applied the independent Qwen deployment decision subject only to hard safety checks.",
        reason=f"{deployment_decision.rationale}; outcome={outcome}",
        configuration=configuration,
        seed=int(executed["optimizer_seed"]),
        history_ids=[item["id"] for item in history],
        model_call_ids=[training_decision.call_id, deployment_decision.call_id],
    )


def _checkpoint_path(model_dir: Path) -> Path:
    root = model_dir.resolve()
    configured = os.environ.get("CONTEST_ARTIFACT_PATH")
    path = (Path(configured) if configured else root / "checkpoint.npz").resolve()
    if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
        raise ValueError("selected checkpoint must be a regular file inside the model mount")
    return path


def predict(sample: Any, model_dir: Path) -> Any:
    model = FormalModel.load(_checkpoint_path(Path(model_dir)))
    if sample.task != model.meta["task"]:
        raise ValueError("prediction task differs from selected checkpoint")
    feature_paths, values = _flatten(sample.inputs)
    if feature_paths != model.meta["paths"]:
        raise ValueError("prediction feature schema differs from selected checkpoint")
    raw = model.predict_raw(np.asarray([values], dtype=np.float64))[0]
    if sample.task == "regression":
        return {"value": float(max(0.0, raw))}
    probabilities = np.asarray(raw, dtype=np.float64)
    tied = np.flatnonzero(probabilities == probabilities.max())
    if len(tied) > 1:
        probabilities[int(tied[0])] += 1e-12
        probabilities /= probabilities.sum()
    return [
        {"label": label, "score": float(score)}
        for label, score in zip(model.meta["classes"], probabilities, strict=True)
    ]
