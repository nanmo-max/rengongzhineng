"""Resumable serial experiment queue for XJTU-SY local development."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .budget import BudgetLimits
from .data.types import TaskStream
from .experiment import build_policy
from .modeling import CpuModelAdapter
from .resources import ResourceTracker
from .runner import RunConfig, run_stream
from .safety import GateConfig


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(child) for child in value)
    return True


def _static_round(
    stream: TaskStream,
    *,
    family: str,
    seed: int,
    round_id: str,
    validation_fraction: float,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if family == "extra_trees":
        params = {"n_estimators": 160, "max_depth": 24}
    elif family == "hist_gradient_boosting":
        params = {"max_iter": 128, "max_leaf_nodes": 31}
    indices = np.arange(len(stream.initial.y))
    if stream.initial.group_ids and len(set(stream.initial.group_ids)) > 1:
        groups = sorted(set(stream.initial.group_ids), key=int)
        anchor_count = max(1, int(round(len(groups) * validation_fraction)))
        anchor_groups = set(groups[-anchor_count:])
        train_mask = np.asarray(
            [group not in anchor_groups for group in stream.initial.group_ids]
        )
        train_indices = indices[train_mask]
    else:
        cut = max(1, int(len(indices) * (1.0 - validation_fraction)))
        train_indices = indices[:cut]
    if len(train_indices) == 0:
        raise RuntimeError("static baseline split produced no training samples")
    train_X = stream.initial.X[train_indices]
    train_y = stream.initial.y[train_indices]
    with ResourceTracker() as tracker:
        model = CpuModelAdapter(
            task_kind="regression", family=family, seed=seed, params=params
        ).fit(train_X, train_y)
    predictions = [model.predict(batch.X) for batch in stream.development]
    targets = [batch.y for batch in stream.development]
    y = np.concatenate(targets)
    predicted = np.concatenate(predictions)
    batch_metrics = [
        {
            "batch_id": batch.batch_id,
            "sample_count": len(batch.y),
            "rmse": float(mean_squared_error(batch.y, prediction) ** 0.5),
            "mae": float(mean_absolute_error(batch.y, prediction)),
        }
        for batch, prediction in zip(stream.development, predictions)
    ]
    usage = tracker.usage
    if usage is None:
        raise RuntimeError("static round did not record resource usage")
    return {
        "round_id": round_id,
        "kind": "static",
        "family": family,
        "local_development_only": True,
        "metrics": {
            "rmse": float(mean_squared_error(y, predicted) ** 0.5),
            "mae": float(mean_absolute_error(y, predicted)),
        },
        "batch_metrics": batch_metrics,
        "resources": asdict(usage),
        "training_samples": len(train_y),
    }


def _policy_round(
    stream: TaskStream, *, round_spec: dict[str, Any], config: dict[str, Any], output: Path
) -> dict[str, Any]:
    policy_name = str(round_spec["policy"])
    policy = build_policy(policy_name, task_kind="regression", config=config)
    summary = run_stream(
        stream,
        policy=policy,
        config=RunConfig(
            seed=int(config["seed"]),
            budget=BudgetLimits(**config["budget"]),
            gate=GateConfig(**config["gate"]),
        ),
        audit_path=output / "rounds" / f"{round_spec['id']}.jsonl",
        include_sealed=False,
    )
    return {
        "round_id": round_spec["id"],
        "kind": "policy",
        "policy": policy_name,
        "local_development_only": True,
        "metrics": summary.development_metrics,
        "batch_metrics": [asdict(item) for item in summary.batch_results],
        "candidate_events": [asdict(item) for item in summary.candidate_events],
        "candidate_count": summary.candidate_count,
    }


def run_serial_experiments(
    stream: TaskStream,
    config: dict[str, Any],
    output_dir: Path,
    *,
    max_rounds: int | None = None,
) -> dict[str, Any]:
    if config.get("local_development_only") is not True:
        raise ValueError("XJTU serial runs must be marked local_development_only")
    if stream.metadata.get("local_development_only") is not True or stream.sealed:
        raise ValueError("serial development queue must not load the sealed partition")
    output_dir = Path(output_dir)
    rounds_dir = output_dir / "rounds"
    rounds_dir.mkdir(parents=True, exist_ok=True)
    round_specs = list(config["rounds"])
    completed = [
        spec for spec in round_specs if (rounds_dir / f"{spec['id']}.json").exists()
    ]
    allowed_total = len(round_specs) if max_rounds is None else min(max_rounds, len(round_specs))
    try:
        for round_spec in round_specs:
            round_path = rounds_dir / f"{round_spec['id']}.json"
            if round_path.exists():
                continue
            if len(completed) >= allowed_total:
                break
            if round_spec["kind"] == "static":
                result = _static_round(
                    stream,
                    family=str(round_spec["family"]),
                    seed=int(config["seed"]),
                    round_id=str(round_spec["id"]),
                    validation_fraction=float(config.get("validation_fraction", 0.25)),
                )
            elif round_spec["kind"] == "policy":
                result = _policy_round(
                    stream, round_spec=round_spec, config=config, output=output_dir
                )
            else:
                raise ValueError(f"unknown serial round kind: {round_spec['kind']}")
            if not _finite(result):
                raise RuntimeError(f"non-finite result in round {round_spec['id']}")
            _atomic_json(round_path, result)
            completed.append(round_spec)
            state = {
                "experiment_id": config["experiment_id"],
                "status": "running",
                "completed_rounds": len(completed),
                "total_rounds": len(round_specs),
                "last_round": round_spec["id"],
                "health": {"finite_metrics": True},
            }
            _atomic_json(output_dir / "status.json", state)
    except Exception as exc:
        _atomic_json(
            output_dir / "status.json",
            {
                "experiment_id": config["experiment_id"],
                "status": "failed",
                "completed_rounds": len(completed),
                "total_rounds": len(round_specs),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise
    status = "completed" if len(completed) == len(round_specs) else "paused"
    state = {
        "experiment_id": config["experiment_id"],
        "status": status,
        "completed_rounds": len(completed),
        "total_rounds": len(round_specs),
        "last_round": completed[-1]["id"] if completed else None,
        "health": {"finite_metrics": True},
    }
    _atomic_json(output_dir / "status.json", state)
    return state


def validate_serial_output(
    output_dir: Path,
    *,
    expected_round_ids: tuple[str, ...],
    minimum_real_candidates: int,
) -> dict[str, Any]:
    """Fail closed when a completed serial queue lacks auditable evidence."""

    output_dir = Path(output_dir)
    try:
        status = json.loads((output_dir / "status.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("missing or invalid XJTU serial status") from exc
    if status.get("status") != "completed":
        raise RuntimeError("XJTU serial queue is not completed")
    if status.get("completed_rounds") != len(expected_round_ids):
        raise RuntimeError("XJTU serial completed-round count is inconsistent")

    real_candidates = 0
    results: list[dict[str, Any]] = []
    for round_id in expected_round_ids:
        path = output_dir / "rounds" / f"{round_id}.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"missing or invalid round evidence: {round_id}") from exc
        if result.get("round_id") != round_id:
            raise RuntimeError(f"round identity mismatch: {round_id}")
        if result.get("local_development_only") is not True:
            raise RuntimeError(f"unsafe experiment boundary in round: {round_id}")
        metrics = result.get("metrics", {})
        if set(metrics) != {"rmse", "mae"} or not _finite(metrics):
            raise RuntimeError(f"missing or non-finite metrics in round: {round_id}")
        if "sealed_metrics" in result:
            raise RuntimeError(f"sealed output is forbidden in local queue: {round_id}")
        real_candidates += int(result.get("candidate_count", 0))
        results.append(result)
    if real_candidates < minimum_real_candidates:
        raise RuntimeError("insufficient real candidate iterations")
    return {
        "valid": True,
        "finite_metrics": True,
        "round_count": len(results),
        "real_candidates": real_candidates,
        "round_ids": list(expected_round_ids),
    }

