"""Minimal official workspace-v2 submission built from verified primitives only."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .agent import AgentDecision, request_proposal
from .data import _flatten, load_rows
from .metrics import evaluate
from .model import FormalModel
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


def _improves(parent: Mapping[str, float], candidate: Mapping[str, float], metric: str, direction: str) -> bool:
    before = parent.get(metric)
    after = candidate.get(metric)
    if before is None or after is None or not math.isfinite(before) or not math.isfinite(after):
        return False
    return after > before if direction == "higher" else after < before


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
        "parent_metrics": dict(parent_metrics),
        "parent_epochs": int(model.meta["epochs"]),
        "parent_learning_rate": float(model.meta["learning_rate"]),
        "history_records": len(history),
    }


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

    # The genuine host call is deliberately before every train/retain branch.
    decision = request_proposal(
        rnd,
        _context(rnd, parent, len(training.ids), len(validation.ids), parent_metrics, history),
    )

    workspace = Path(os.environ.get("CONTEST_WORK", "/workspace"))
    paths = create_round_paths(workspace, int(rnd.round_index), str(getattr(rnd, "stage_id", "default")))
    state = Path(rnd.state_workspace(paths.state))
    selected_artifact = rnd.parent.artifact_id
    candidate_metrics: dict[str, float] | None = None
    losses: list[float] = []
    outcome = "retained_by_agent"
    candidate_receipt: Mapping[str, Any] | None = None
    metric, direction = _primary_contract(rnd, parent)

    if decision.action == "train":
        candidate = parent.clone()
        candidate.meta["learning_rate"] = float(parent.meta["learning_rate"]) * decision.learning_rate_multiplier
        losses = candidate.fit(training.x, training.y, decision.epochs)
        candidate_metrics = evaluate(candidate, validation.x, validation.y)
        if _improves(parent_metrics, candidate_metrics, metric, direction):
            paths.candidate.mkdir(parents=True, exist_ok=False)
            checkpoint = paths.candidate / "checkpoint.npz"
            candidate.save(checkpoint)
            candidate_receipt = rnd.submit_candidate(
                paths.candidate,
                hypothesis="A bounded parent-compatible continuation can improve the declared public validation metric.",
                change_summary="Continued the declared parent checkpoint with the host Agent's bounded epoch and learning-rate choice.",
                configuration={
                    "action": "train", "epochs": decision.epochs,
                    "learning_rate_multiplier": decision.learning_rate_multiplier,
                    "metric": metric, "direction": direction,
                },
                seed=_SEED,
                checkpoint_paths=["checkpoint.npz"],
                code_paths=[],
                predict_argv=PREDICT_ARGV,
            )
            selected_artifact = candidate_receipt["artifact_id"]
            outcome = "candidate_selected"
        else:
            outcome = "candidate_rejected"

    record = {
        "round_index": int(rnd.round_index),
        "stage_id": str(getattr(rnd, "stage_id", "")),
        "dataset_key": str(getattr(rnd, "dataset_key", "")),
        "action": decision.action,
        "outcome": outcome,
        "epochs": decision.epochs,
        "learning_rate_multiplier": decision.learning_rate_multiplier,
        "rationale": decision.rationale,
        "proposal_parse_error": decision.parse_error,
        "call_id": decision.call_id,
        "parent_checkpoint_sha256": str(rnd.parent.checkpoint_sha256),
        "train_sha256": training.sha256,
        "validation_sha256": validation.sha256,
        "parent_metrics": parent_metrics,
        "candidate_metrics": candidate_metrics,
        "losses": losses,
        "selected_artifact_id": selected_artifact,
    }
    _write_state(state, record)
    rnd.save_state(state)

    configuration = {
        "action": decision.action,
        "outcome": outcome,
        "epochs": decision.epochs,
        "learning_rate_multiplier": decision.learning_rate_multiplier,
        "parent_metrics": parent_metrics,
        "candidate_metrics": candidate_metrics,
        "metric": metric,
    }
    rnd.finish(
        selected_artifact_id=selected_artifact,
        hypothesis="Use one genuine host-model decision to choose retain or a bounded continuation of the declared parent.",
        change_summary="Executed one parent-compatible candidate at most; retained the parent when the Agent or validation gate declined it.",
        reason=f"{decision.rationale}; outcome={outcome}",
        configuration=configuration,
        seed=_SEED,
        history_ids=[item["id"] for item in history],
        model_call_ids=[decision.call_id],
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
