"""Strict public JSONL reader for one official training round."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

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

    def select(self, indices: Sequence[int]) -> "DataBatch":
        selected = tuple(int(index) for index in indices)
        if not selected or len(set(selected)) != len(selected):
            raise ValueError("selection indices must be nonempty and unique")
        if any(index < 0 or index >= len(self.ids) for index in selected):
            raise ValueError("selection index is outside the batch")
        digest = hashlib.sha256(
            json.dumps(
                {"source_sha256": self.sha256, "indices": selected},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        array_indices = np.asarray(selected, dtype=np.int64)
        return DataBatch(
            ids=tuple(self.ids[index] for index in selected),
            x=self.x[array_indices].copy(),
            y=self.y[array_indices].copy(),
            sha256=digest,
        )

    @staticmethod
    def concat(batches: Iterable["DataBatch"]) -> "DataBatch":
        parts = tuple(batches)
        if not parts:
            raise ValueError("at least one batch is required")
        feature_count = parts[0].x.shape[1] if parts[0].x.ndim == 2 else -1
        if feature_count < 1 or any(batch.x.ndim != 2 or batch.x.shape[1] != feature_count for batch in parts):
            raise ValueError("batch feature schemas differ")
        ids = tuple(identity for batch in parts for identity in batch.ids)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate sample ID across batches")
        if any(batch.y.ndim != 1 or len(batch.ids) != len(batch.x) or len(batch.y) != len(batch.x) for batch in parts):
            raise ValueError("batch shapes are inconsistent")
        digest = hashlib.sha256(
            json.dumps(
                [{"sha256": batch.sha256, "samples": len(batch.ids)} for batch in parts],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return DataBatch(
            ids=ids,
            x=np.concatenate([batch.x for batch in parts], axis=0),
            y=np.concatenate([batch.y for batch in parts], axis=0),
            sha256=digest,
        )


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
