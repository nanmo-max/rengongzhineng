"""Strict public JSONL reader for one official training round."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .model import FormalModel


_MAX_DATA_BYTES = 128 * 1024 * 1024
_FORBIDDEN = {"truerul", "normalizedrul", "remainingusefullife", "rul", "totalsnapshots"}


@dataclass(frozen=True)
class DataBatch:
    ids: tuple[str, ...]
    x: np.ndarray
    y: np.ndarray
    sha256: str


def _flatten(inputs: Any) -> tuple[list[str], list[float]]:
    paths: list[str] = []
    values: list[float] = []

    def visit(value: Any, path: list[tuple[str, Any]], depth: int) -> None:
        if depth > 16:
            raise ValueError("input nesting exceeds limit")
        if isinstance(value, dict):
            for key in sorted(value):
                if not isinstance(key, str):
                    raise ValueError("input keys must be strings")
                normalized = "".join(character for character in key.lower() if character.isalnum())
                if normalized in _FORBIDDEN:
                    raise ValueError("target-derived input field is not allowed")
                visit(value[key], path + [("key", key)], depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + [("index", index)], depth + 1)
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            paths.append(json.dumps(path, ensure_ascii=False, separators=(",", ":")))
            values.append(float(value))
        else:
            raise ValueError("model inputs must contain finite numeric features only")

    visit(inputs, [], 0)
    if not 1 <= len(values) <= 4096:
        raise ValueError("expected 1..4096 numeric features")
    return paths, values


def load_rows(path: Path | str, model: FormalModel, *, require_answers: bool) -> DataBatch:
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > _MAX_DATA_BYTES:
        raise ValueError("data must be a regular JSONL file no larger than 128 MiB")
    raw = source.read_bytes()
    ids: list[str] = []
    features: list[list[float]] = []
    targets: list[int | float] = []
    seen: set[str] = set()
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or "id" not in row or "inputs" not in row:
            raise ValueError(f"line {line_number}: id and inputs are required")
        identity = row["id"]
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError(f"line {line_number}: sample IDs must be unique nonempty strings")
        paths, values = _flatten(row["inputs"])
        if paths != model.meta["paths"]:
            raise ValueError(f"line {line_number}: feature schema differs from parent checkpoint")
        if require_answers:
            if "answer" not in row:
                raise ValueError(f"line {line_number}: answer is required for training")
            answer = row["answer"]
            if model.meta["task"] == "classification":
                if not isinstance(answer, str) or answer not in model.meta["classes"]:
                    raise ValueError(f"line {line_number}: answer is outside parent classes")
                targets.append(model.meta["classes"].index(answer))
            else:
                if isinstance(answer, bool) or not isinstance(answer, (int, float)) or not math.isfinite(answer):
                    raise ValueError(f"line {line_number}: answer must be finite numeric")
                targets.append(float(answer))
        ids.append(identity)
        seen.add(identity)
        features.append(values)
    if not ids:
        raise ValueError("data batch is empty")
    return DataBatch(
        ids=tuple(ids),
        x=np.asarray(features, dtype=np.float64),
        y=np.asarray(targets, dtype=np.int64 if model.meta["task"] == "classification" else np.float64),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
