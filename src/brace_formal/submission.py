"""Thin official entry adapter and independently callable prediction path."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .data import _flatten
from .metrics import evaluate
from .model import FormalModel


TASKS = ("classification", "regression")


def _state_payload(state_root: Path) -> dict[str, Any]:
    """Read legacy formal state for migration tooling and compatibility tests."""

    path = Path(state_root) / "formal-state.json"
    if not path.exists():
        return {"format": "brace-formal-state.v2", "rounds": []}
    if path.is_symlink() or not path.is_file():
        raise ValueError("formal state must be a regular file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("format") not in {"brace-formal-state.v1", "brace-formal-state.v2"}
        or not isinstance(payload.get("rounds"), list)
    ):
        raise ValueError("formal state is invalid")
    if payload["format"] == "brace-formal-state.v1":
        for record in payload["rounds"]:
            if isinstance(record, dict):
                record.setdefault("legacy_source_format", "brace-formal-state.v1")
                record.setdefault("candidate_artifact_id", None)
                record.setdefault("best_stable_artifact_id", None)
    payload["format"] = "brace-formal-state.v2"
    return payload


def _hard_gate(parent: FormalModel, checkpoint: Path, metrics: Mapping[str, float]) -> list[str]:
    """Compatibility injection point around the Competition Core hard gate."""

    from .round_core import _hard_failures

    return list(_hard_failures(parent, checkpoint, metrics))


def train(rnd: Any) -> None:
    """Run exactly one Competition Core transaction for the official Round."""

    from .round_core import run_competition_round

    run_competition_round(rnd, evaluator=evaluate, hard_gate=_hard_gate)


def _checkpoint_path(model_dir: Path) -> Path:
    root = model_dir.resolve()
    configured = os.environ.get("CONTEST_ARTIFACT_PATH")
    path = (Path(configured) if configured else root / "checkpoint.npz").resolve()
    if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
        raise ValueError("selected checkpoint must be a regular file inside the model mount")
    return path


def predict(sample: Any, model_dir: Path) -> Any:
    """Predict from only the exact selected checkpoint mounted by the host."""

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
