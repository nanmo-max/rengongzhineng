"""Native platform runtime for ``/data`` + ``/previous`` mounted evaluations.

This module deliberately does not depend on the immutable development-package tree.
It validates and continues the platform-supplied parent checkpoint directly, while the
older package audit remains available for local research and supply-chain verification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Protocol
import zipfile

import numpy as np
import psutil

from .competitive_policy import PortfolioEvidence, build_candidate_plan
from .policies import Action
from .pytrio_agent import (
    AdvisorOutcome,
    AgentContext,
    AgentTrigger,
    validate_experiment_proposal,
)


_PARAMETERS = ("w1", "b1", "w2", "b2")
_MAX_DATA_BYTES = 128 * 1024 * 1024
_MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024
_FORBIDDEN_INPUTS = {
    "truerul",
    "normalizedrul",
    "remainingusefullife",
    "rul",
    "totalsnapshots",
}
_PLATFORM_ACTIONS = {Action.NOOP, Action.INCREMENTAL_UPDATE, Action.REPLAY_REFIT}
_COMPETITIVE_SCHEDULES: dict[str, tuple[tuple[int, int, float], ...]] = {
    "A": ((1, 1, 1.0), (5, 1, 1.0), (9, 1, 1.0)),
    "B": ((1, 1, 1.0), (5, 1, 0.3), (9, 5, 3.0)),
    "C": ((1, 1, 1.0), (5, 1, 0.3), (9, 5, 1.0)),
}


class PlatformAdvisor(Protocol):
    def advise(self, context: AgentContext, trigger: AgentTrigger) -> AdvisorOutcome: ...


@dataclass(frozen=True)
class PlatformRuntimeConfig:
    policy_mode: str = "protocol"
    protocol_profiles: tuple[str, ...] = ()
    epochs: int = 1
    learning_rate_multiplier: float = 1.0
    gate_fraction: float = 0.2
    min_primary_improvement: float = 0.0
    min_relative_improvement: float = 0.05
    max_training_rounds: int = 10
    max_anchor_degradation: float = 0.0
    max_replay_samples: int = 4096
    arrival_drop_trigger: float = 0.02

    def __post_init__(self) -> None:
        if self.policy_mode not in {"protocol", "competitive", "sequential", "portfolio"}:
            raise ValueError(
                "policy mode must be protocol, competitive, sequential, or portfolio"
            )
        if any(not value.strip() for value in self.protocol_profiles):
            raise ValueError("protocol profiles must be non-empty strings")
        if not 1 <= self.epochs <= 5:
            raise ValueError("epochs must be in 1..5")
        if not 0.1 <= self.learning_rate_multiplier <= 3.0:
            raise ValueError("learning-rate multiplier must be in 0.1..3")
        if not 0.05 <= self.gate_fraction <= 0.4:
            raise ValueError("gate fraction must be in 0.05..0.4")
        if not math.isfinite(self.min_primary_improvement):
            raise ValueError("minimum improvement must be finite")
        if not math.isfinite(self.min_relative_improvement) or not -1.0 <= self.min_relative_improvement <= 1.0:
            raise ValueError("minimum relative improvement must be in -1..1")
        if not 0 <= self.max_training_rounds <= 10:
            raise ValueError("max training rounds must be in 0..10")
        if not math.isfinite(self.max_anchor_degradation) or self.max_anchor_degradation < 0:
            raise ValueError("maximum anchor degradation must be finite and nonnegative")
        if not 0 <= self.max_replay_samples <= 100_000:
            raise ValueError("maximum replay samples must be in 0..100000")
        if not math.isfinite(self.arrival_drop_trigger) or not 0 <= self.arrival_drop_trigger <= 1:
            raise ValueError("arrival drop trigger must be in 0..1")


@dataclass(frozen=True)
class ArrivalEvidence:
    metrics: dict[str, float]
    previous_metrics: dict[str, float] | None
    sample_count: int
    delayed_gain: float | None


def _validate_arrival_evidence(
    evidence: ArrivalEvidence | None, *, task: str, expected_count: int
) -> None:
    if evidence is None:
        return
    required = {"macro_f1", "accuracy"} if task == "classification" else {"rmse", "mae"}
    for metrics in (evidence.metrics, evidence.previous_metrics):
        if metrics is None:
            continue
        if not required.issubset(metrics):
            raise ValueError("arrival evidence is missing required metrics")
        if any(not math.isfinite(float(value)) for value in metrics.values()):
            raise ValueError("arrival evidence metrics must be finite")
    if evidence.sample_count != expected_count:
        raise ValueError("arrival evidence sample count does not match the current batch")
    if evidence.delayed_gain is not None and not math.isfinite(evidence.delayed_gain):
        raise ValueError("delayed gain must be finite")


@dataclass(frozen=True)
class CompetitiveGateOutcome:
    accepted: bool
    reason: str
    primary_improvement: float
    relative_improvement: float
    relative_anchor_degradation: float
    relative_replay_degradation: float | None


def describe_runtime() -> dict[str, Any]:
    return {
        "format": "brace-msi.platform-native.v1",
        "data_root": "/data",
        "parent_checkpoint": "/previous/checkpoint.npz",
        "workspace_root": "/workspace",
        "output_root": "/output",
        "checkpoint_format": "contest.cpu-mlp.v1",
        "operations": ["describe", "start", "submit"],
        "task_kinds": ["classification", "regression"],
        "requires_network": False,
        "requires_gpu": False,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _atomic_npz(path: Path, *, x: np.ndarray, y: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        np.savez(stream, x=np.asarray(x), y=np.asarray(y))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _load_buffer(path: Path, *, feature_count: int, task: str) -> tuple[np.ndarray, np.ndarray]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"workspace buffer is missing or invalid: {path.name}")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != {"x", "y"}:
            raise ValueError(f"workspace buffer schema is invalid: {path.name}")
        x = np.asarray(archive["x"], dtype=np.float64)
        y = np.asarray(
            archive["y"], dtype=np.int64 if task == "classification" else np.float64
        )
    if x.ndim != 2 or x.shape[1] != feature_count or y.shape != (len(x),):
        raise ValueError(f"workspace buffer shape is invalid: {path.name}")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError(f"workspace buffer contains nonfinite values: {path.name}")
    return x, y


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json_value(raw: str) -> Any:
    def reject(_: str) -> None:
        raise ValueError("nonfinite JSON number")

    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=reject)


def _flatten(inputs: Any) -> tuple[list[str], list[float]]:
    paths: list[str] = []
    values: list[float] = []

    def visit(value: Any, path: list[tuple[str, Any]], depth: int) -> None:
        if depth > 16:
            raise ValueError("input nesting exceeds limit")
        if isinstance(value, dict):
            for key in sorted(value):
                normalized = "".join(character for character in key.lower() if character.isalnum())
                if not isinstance(key, str) or normalized in _FORBIDDEN_INPUTS:
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


class _NativeModel:
    def __init__(self, arrays: dict[str, np.ndarray], metadata: dict[str, Any]) -> None:
        self.params = {name: arrays[name].copy() for name in _PARAMETERS}
        self.first = {name: arrays[f"adam_first_{name}"].copy() for name in _PARAMETERS}
        self.second = {name: arrays[f"adam_second_{name}"].copy() for name in _PARAMETERS}
        self.mean = arrays["mean"].copy()
        self.scale = arrays["scale"].copy()
        self.meta = dict(metadata)
        self.validate()

    @classmethod
    def load(cls, path: Path) -> "_NativeModel":
        path = Path(path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_CHECKPOINT_BYTES:
            raise ValueError("parent checkpoint must be a regular file no larger than 64 MiB")
        required = {
            *_PARAMETERS,
            *(f"adam_first_{name}" for name in _PARAMETERS),
            *(f"adam_second_{name}" for name in _PARAMETERS),
            "mean",
            "scale",
            "metadata",
        }
        try:
            with np.load(path, allow_pickle=False) as archive:
                if set(archive.files) != required:
                    raise ValueError("checkpoint schema is not contest.cpu-mlp.v1")
                raw_metadata = archive["metadata"]
                if raw_metadata.shape != () or raw_metadata.dtype.kind != "U":
                    raise ValueError("checkpoint metadata is invalid")
                metadata = json.loads(str(raw_metadata.item()))
                arrays = {name: archive[name].copy() for name in required - {"metadata"}}
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError("checkpoint could not be loaded") from exc
        return cls(arrays, metadata)

    def clone(self) -> "_NativeModel":
        arrays = {
            **{name: value.copy() for name, value in self.params.items()},
            **{f"adam_first_{name}": value.copy() for name, value in self.first.items()},
            **{f"adam_second_{name}": value.copy() for name, value in self.second.items()},
            "mean": self.mean.copy(),
            "scale": self.scale.copy(),
        }
        return _NativeModel(arrays, self.meta)

    def validate(self) -> None:
        meta = self.meta
        if (
            meta.get("format") != "contest.cpu-mlp.v1"
            or meta.get("device") != "cpu"
            or meta.get("task") not in {"classification", "regression"}
        ):
            raise ValueError("unsupported parent checkpoint")
        paths = meta.get("paths")
        classes = meta.get("classes")
        hidden = meta.get("hidden")
        if (
            not isinstance(paths, list)
            or not 1 <= len(paths) <= 4096
            or not all(isinstance(value, str) for value in paths)
            or len(set(paths)) != len(paths)
        ):
            raise ValueError("checkpoint feature paths are invalid")
        if (
            not isinstance(classes, list)
            or any(not isinstance(value, str) or not value for value in classes)
            or len(set(classes)) != len(classes)
            or (meta["task"] == "classification" and len(classes) < 2)
            or (meta["task"] == "regression" and classes)
        ):
            raise ValueError("checkpoint classes are invalid")
        if not isinstance(hidden, int) or not 1 <= hidden <= 128:
            raise ValueError("checkpoint hidden width is invalid")
        for field in ("epochs", "steps", "seed", "batch_size", "parameter_count"):
            if type(meta.get(field)) is not int or meta[field] < 0:
                raise ValueError("checkpoint integer state is invalid")
        if (
            not 0 <= meta["seed"] < 2**32
            or not 1 <= meta["batch_size"] <= 65536
            or not 0 < meta["parameter_count"] < 100000
        ):
            raise ValueError("checkpoint architecture is invalid")
        for field in ("learning_rate", "target_mean", "target_scale"):
            value = meta.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("checkpoint numeric state is invalid")
        if not 0 < meta["learning_rate"] <= 1 or meta["target_scale"] <= 0:
            raise ValueError("checkpoint optimizer/scaler state is invalid")
        output = len(classes) if meta["task"] == "classification" else 1
        shapes = {
            "w1": (len(paths), hidden),
            "b1": (hidden,),
            "w2": (hidden, output),
            "b2": (output,),
        }
        for group in (self.params, self.first, self.second):
            for name, shape in shapes.items():
                value = group[name]
                if value.shape != shape or value.dtype != np.dtype("float64") or not np.all(np.isfinite(value)):
                    raise ValueError("checkpoint tensor is invalid")
        if sum(value.size for value in self.params.values()) != meta["parameter_count"]:
            raise ValueError("checkpoint parameter count is invalid")
        if self.mean.shape != (len(paths),) or self.scale.shape != (len(paths),):
            raise ValueError("checkpoint preprocessing state is invalid")
        if (
            self.mean.dtype != np.dtype("float64")
            or self.scale.dtype != np.dtype("float64")
            or not np.all(np.isfinite(self.mean))
            or not np.all(np.isfinite(self.scale))
            or np.any(self.scale <= 0)
        ):
            raise ValueError("checkpoint preprocessing state is invalid")
        if any(np.any(value < 0) for value in self.second.values()):
            raise ValueError("invalid Adam second moment")

    def _normalized(self, values: np.ndarray) -> np.ndarray:
        if values.ndim != 2 or values.shape[1] != len(self.meta["paths"]):
            raise ValueError("feature schema differs from parent checkpoint")
        if not np.all(np.isfinite(values)):
            raise ValueError("features contain nonfinite values")
        return np.clip((values - self.mean) / self.scale, -10.0, 10.0)

    def predict_raw(self, values: np.ndarray) -> np.ndarray:
        normalized = self._normalized(values)
        hidden = np.tanh(normalized @ self.params["w1"] + self.params["b1"])
        logits = hidden @ self.params["w2"] + self.params["b2"]
        if self.meta["task"] == "classification":
            logits -= logits.max(axis=1, keepdims=True)
            probabilities = np.exp(logits)
            return probabilities / probabilities.sum(axis=1, keepdims=True)
        result = logits[:, 0] * float(self.meta["target_scale"]) + float(self.meta["target_mean"])
        return np.maximum(0.0, result)

    def fit(self, values: np.ndarray, targets: np.ndarray, epochs: int) -> list[float]:
        normalized = self._normalized(values)
        if targets.shape != (len(normalized),) or not len(normalized):
            raise ValueError("target shape is invalid")
        if self.meta["task"] == "regression":
            expected = (targets - float(self.meta["target_mean"])) / float(self.meta["target_scale"])
        else:
            expected = targets.astype(np.int64, copy=False)
            if np.any(expected < 0) or np.any(expected >= len(self.meta["classes"])):
                raise ValueError("classification target is unknown")
        losses: list[float] = []
        for _ in range(epochs):
            rng = np.random.default_rng(
                np.random.SeedSequence([self.meta["seed"], self.meta["epochs"]])
            )
            order = rng.permutation(len(normalized))
            loss_sum = 0.0
            for start in range(0, len(order), self.meta["batch_size"]):
                indices = order[start : start + self.meta["batch_size"]]
                batch = normalized[indices]
                target = expected[indices]
                hidden = np.tanh(batch @ self.params["w1"] + self.params["b1"])
                logits = hidden @ self.params["w2"] + self.params["b2"]
                if self.meta["task"] == "classification":
                    logits -= logits.max(axis=1, keepdims=True)
                    probabilities = np.exp(logits)
                    probabilities /= probabilities.sum(axis=1, keepdims=True)
                    loss_sum -= float(
                        np.log(np.maximum(probabilities[np.arange(len(indices)), target], 1e-300)).sum()
                    )
                    delta = probabilities
                    delta[np.arange(len(indices)), target] -= 1.0
                    delta /= len(indices)
                else:
                    error = logits[:, 0] - target
                    loss_sum += float(np.sum(error**2))
                    delta = (2.0 * error / len(indices))[:, None]
                gradients = {"w2": hidden.T @ delta, "b2": delta.sum(axis=0)}
                hidden_delta = (delta @ self.params["w2"].T) * (1.0 - hidden**2)
                gradients.update(w1=batch.T @ hidden_delta, b1=hidden_delta.sum(axis=0))
                norm = math.sqrt(sum(float(np.sum(value * value)) for value in gradients.values()))
                if not math.isfinite(norm):
                    raise ValueError("nonfinite gradient")
                self.meta["steps"] += 1
                for name, gradient in gradients.items():
                    gradient *= min(1.0, 5.0 / max(norm, 1e-12))
                    self.first[name] = 0.9 * self.first[name] + 0.1 * gradient
                    self.second[name] = 0.999 * self.second[name] + 0.001 * gradient**2
                    first = self.first[name] / (1.0 - 0.9 ** self.meta["steps"])
                    second = self.second[name] / (1.0 - 0.999 ** self.meta["steps"])
                    self.params[name] -= self.meta["learning_rate"] * first / (np.sqrt(second) + 1e-8)
            self.meta["epochs"] += 1
            losses.append(loss_sum / len(normalized))
        self.validate()
        return losses

    def save(self, path: Path) -> None:
        self.validate()
        arrays: dict[str, np.ndarray] = {
            **self.params,
            **{f"adam_first_{name}": value for name, value in self.first.items()},
            **{f"adam_second_{name}": value for name, value in self.second.items()},
            "mean": self.mean,
            "scale": self.scale,
            "metadata": np.asarray(
                json.dumps(self.meta, sort_keys=True, separators=(",", ":"), allow_nan=False)
            ),
        }
        with Path(path).open("xb") as stream, zipfile.ZipFile(
            stream, "w", compression=zipfile.ZIP_STORED
        ) as archive:
            for name in sorted(arrays):
                buffer = io.BytesIO()
                np.lib.format.write_array(buffer, arrays[name], allow_pickle=False)
                info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o600 << 16
                archive.writestr(info, buffer.getvalue())


def _fit_portfolio_recipe(
    parent: _NativeModel,
    *,
    recipe: str,
    replay_x: np.ndarray,
    replay_y: np.ndarray,
    update_x: np.ndarray,
    update_y: np.ndarray,
) -> _NativeModel:
    """Fit a bounded recipe while preserving the official checkpoint schema."""

    cumulative_x = np.concatenate((replay_x, update_x), axis=0)
    cumulative_y = np.concatenate((replay_y, update_y), axis=0)
    recent_count = min(len(replay_x), 2 * len(update_x))
    recent_x = np.concatenate((replay_x[-recent_count:], update_x), axis=0)
    recent_y = np.concatenate((replay_y[-recent_count:], update_y), axis=0)
    specifications: dict[str, tuple[np.ndarray, np.ndarray, int, float]] = {
        "current_e3_lr3": (update_x, update_y, 3, 3.0),
        "cumulative_e3_lr0.3": (cumulative_x, cumulative_y, 3, 0.3),
        "recent_e3": (recent_x, recent_y, 3, 1.0),
    }
    if recipe == "soup_current_e3_alpha0.25":
        trained = parent.clone()
        trained.fit(update_x, update_y, 3)
        result = trained.clone()
        for name in result.params:
            result.params[name] = 0.75 * parent.params[name] + 0.25 * trained.params[name]
        result.validate()
        return result
    if recipe not in specifications:
        raise ValueError("unsupported portfolio recipe")
    values, targets, epochs, multiplier = specifications[recipe]
    candidate = parent.clone()
    parent_rate = float(parent.meta["learning_rate"])
    candidate.meta["learning_rate"] = parent_rate * multiplier
    candidate.fit(values, targets, epochs)
    candidate.meta["learning_rate"] = parent_rate
    candidate.validate()
    return candidate


def _resolve_data_file(path: Path) -> Path:
    path = Path(path)
    if path.is_file() and not path.is_symlink():
        return path
    if not path.is_dir() or path.is_symlink():
        raise ValueError("data path must be a regular JSONL file or directory")
    preferred = [path / name for name in ("data.jsonl", "batch.jsonl", "train.jsonl")]
    matches = [candidate for candidate in preferred if candidate.is_file() and not candidate.is_symlink()]
    if len(matches) == 1:
        return matches[0]
    jsonl = [candidate for candidate in path.glob("*.jsonl") if candidate.is_file() and not candidate.is_symlink()]
    if len(jsonl) != 1:
        raise ValueError("data directory must contain one unambiguous JSONL batch")
    return jsonl[0]


def _read_rows(path: Path, model: _NativeModel, *, require_answers: bool) -> dict[str, Any]:
    path = _resolve_data_file(path)
    if path.stat().st_size > _MAX_DATA_BYTES:
        raise ValueError("data file exceeds 128 MiB")
    raw = path.read_bytes()
    ids: list[str] = []
    features: list[list[float]] = []
    targets: list[float | int] = []
    seen: set[str] = set()
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = _json_value(line)
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
    return {
        "path": path,
        "ids": ids,
        "x": np.asarray(features, dtype=np.float64),
        "y": np.asarray(
            targets,
            dtype=np.int64 if model.meta["task"] == "classification" else np.float64,
        ),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _split_indices(targets: np.ndarray, task: str, fraction: float) -> tuple[np.ndarray, np.ndarray]:
    count = len(targets)
    if count < 5:
        raise ValueError("at least five labeled samples are required")
    gate: list[int] = []
    if task == "classification":
        for label in sorted(set(targets.tolist())):
            members = np.flatnonzero(targets == label)
            if len(members) >= 2:
                gate_count = max(1, int(round(len(members) * fraction)))
                gate.extend(members[-min(gate_count, len(members) - 1) :].tolist())
    if not gate:
        gate_count = max(1, min(count - 1, int(round(count * fraction))))
        gate = list(range(count - gate_count, count))
    gate_array = np.asarray(sorted(set(gate)), dtype=np.int64)
    update_array = np.asarray([index for index in range(count) if index not in set(gate)], dtype=np.int64)
    if not len(update_array) or not len(gate_array):
        raise ValueError("data batch cannot form disjoint Update and Gate sets")
    return update_array, gate_array


def _metrics(model: _NativeModel, values: np.ndarray, targets: np.ndarray) -> dict[str, float]:
    raw = model.predict_raw(values)
    if model.meta["task"] == "classification":
        labels = raw.argmax(axis=1)
        observed = sorted(set(targets.tolist()) | set(labels.tolist()))
        f1 = []
        for label in observed:
            denominator = int(np.sum(labels == label) + np.sum(targets == label))
            numerator = 2 * int(np.sum((labels == label) & (targets == label)))
            f1.append(numerator / denominator if denominator else 0.0)
        return {
            "accuracy": float(np.mean(labels == targets)),
            "macro_f1": float(np.mean(f1)),
        }
    error = raw - targets
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
    }


def _primary_improvement(task: str, before: dict[str, float], after: dict[str, float]) -> float:
    if task == "classification":
        return after["macro_f1"] - before["macro_f1"]
    return before["rmse"] - after["rmse"]


def _relative_improvement(task: str, before: dict[str, float], after: dict[str, float]) -> float:
    absolute = _primary_improvement(task, before, after)
    baseline = before["macro_f1"] if task == "classification" else before["rmse"]
    return absolute / max(abs(baseline), 1e-12)


def _primary_value(task: str, metrics: dict[str, float]) -> float:
    return metrics["macro_f1"] if task == "classification" else metrics["rmse"]


def _competitive_gate(
    *,
    profile: str,
    task: str,
    before: dict[str, float],
    candidate: dict[str, float],
    anchor_before: dict[str, float],
    anchor_candidate: dict[str, float],
    replay_before: dict[str, float] | None = None,
    replay_candidate: dict[str, float] | None = None,
) -> CompetitiveGateOutcome:
    """Apply a task-contract gate using only current and historical train evidence."""

    primary_improvement = _primary_improvement(task, before, candidate)
    relative_improvement = _relative_improvement(task, before, candidate)
    if task == "classification":
        relative_anchor_degradation = (
            anchor_before["macro_f1"] - anchor_candidate["macro_f1"]
        ) / max(abs(anchor_before["macro_f1"]), 1e-12)
        secondary_safe = candidate["accuracy"] + 1e-12 >= before["accuracy"]
        secondary_relative_degradation = max(
            0.0,
            (before["accuracy"] - candidate["accuracy"])
            / max(abs(before["accuracy"]), 1e-12),
        )
    else:
        relative_anchor_degradation = (
            anchor_candidate["rmse"] - anchor_before["rmse"]
        ) / max(abs(anchor_before["rmse"]), 1e-12)
        secondary_safe = candidate["mae"] <= before["mae"] + 1e-12
        secondary_relative_degradation = max(
            0.0,
            (candidate["mae"] - before["mae"])
            / max(abs(before["mae"]), 1e-12),
        )

    min_relative = {"A": 0.0, "B": 0.005, "C": 0.005}.get(profile, 0.01)
    max_anchor_relative = {"A": 0.01, "B": 0.02, "C": 0.02}.get(profile, 0.01)
    relative_replay_degradation: float | None = None
    replay_secondary_safe = False
    if replay_before is not None and replay_candidate is not None:
        replay_key = "macro_f1" if task == "classification" else "rmse"
        if task == "classification":
            replay_absolute = replay_before[replay_key] - replay_candidate[replay_key]
            replay_secondary_safe = (
                replay_candidate["accuracy"] + 1e-12 >= replay_before["accuracy"]
            )
        else:
            replay_absolute = replay_candidate[replay_key] - replay_before[replay_key]
            replay_secondary_safe = replay_candidate["mae"] <= replay_before["mae"] + 1e-12
        relative_replay_degradation = replay_absolute / max(
            abs(replay_before[replay_key]), 1e-12
        )
    safe_replay_gain = (
        primary_improvement >= 0
        and (secondary_safe or secondary_relative_degradation <= 0.01)
        and relative_replay_degradation is not None
        and -relative_replay_degradation > min_relative
        and replay_secondary_safe
    )
    if (
        primary_improvement <= 0 or relative_improvement < min_relative
    ) and not safe_replay_gain:
        accepted, reason = False, "primary_gain_below_task_contract"
    elif not secondary_safe and not safe_replay_gain:
        accepted, reason = False, "secondary_metric_regressed"
    elif relative_anchor_degradation > max_anchor_relative:
        accepted, reason = False, "anchor_risk_exceeded"
    elif relative_replay_degradation is not None and relative_replay_degradation > 0.02:
        accepted, reason = False, "replay_history_regressed"
    elif safe_replay_gain:
        accepted, reason = True, "safe_replay_gain"
    else:
        accepted, reason = True, "competitive_gate_passed"
    return CompetitiveGateOutcome(
        accepted=accepted,
        reason=reason,
        primary_improvement=float(primary_improvement),
        relative_improvement=float(relative_improvement),
        relative_anchor_degradation=float(relative_anchor_degradation),
        relative_replay_degradation=(
            float(relative_replay_degradation)
            if relative_replay_degradation is not None
            else None
        ),
    )


def _decision_for_round(
    *,
    parent: _NativeModel,
    before: dict[str, float],
    update_x: np.ndarray,
    replay_x: np.ndarray,
    anchor_x: np.ndarray,
    state: dict[str, Any],
    round_index: int,
    config: PlatformRuntimeConfig,
    advisor: PlatformAdvisor | None,
    arrival_evidence: ArrivalEvidence | None,
    rollback_available: bool,
    current_target_mean: float,
) -> tuple[dict[str, Any], Action, int, float]:
    """Choose a bounded action; model text never crosses the effect boundary directly."""

    history = state["rounds"]
    current_metrics = arrival_evidence.metrics if arrival_evidence is not None else before
    current_value = _primary_value(parent.meta["task"], current_metrics)
    previous_value = current_value
    if arrival_evidence is not None and arrival_evidence.previous_metrics is not None:
        previous_value = _primary_value(parent.meta["task"], arrival_evidence.previous_metrics)
    elif history:
        previous = history[-1]
        selected = (
            previous.get("metrics_candidate")
            if previous.get("deployed")
            else previous.get("metrics_before")
        )
        if isinstance(selected, dict):
            previous_value = _primary_value(parent.meta["task"], selected)
    performance_drop = (
        max(0.0, previous_value - current_value)
        if parent.meta["task"] == "classification"
        else max(0.0, current_value - previous_value)
    ) / max(abs(previous_value), 1e-12)
    reference_x = replay_x if len(replay_x) else anchor_x
    drift_complexity = float(
        np.clip(
            np.mean(
                np.abs(update_x.mean(axis=0) - reference_x.mean(axis=0))
                / np.maximum(parent.scale, 1e-12)
            ),
            0.0,
            1.0,
        )
    )
    failure_streak = 0
    for row in reversed(history):
        if row.get("deployed"):
            break
        failure_streak += 1
    action_uncertainty = 1.0 / math.sqrt(max(1, round_index))
    trigger = AgentTrigger.evaluate(
        performance_drop=performance_drop,
        drift_complexity=drift_complexity,
        failure_streak=failure_streak,
        action_uncertainty=action_uncertainty,
        pareto_indistinguishable=not history,
    )
    context = AgentContext(
        task_kind=parent.meta["task"],
        metric_name="macro_f1" if parent.meta["task"] == "classification" else "rmse",
        higher_is_better=parent.meta["task"] == "classification",
        round_index=round_index,
        evidence={
            "current_metric": current_value,
            "previous_metric": previous_value,
            "performance_drop": performance_drop,
            "drift_score": drift_complexity,
            "failure_streak": failure_streak,
            "update_count": len(update_x),
            "replay_count": len(replay_x),
        },
        history=tuple(
            {
                "round_index": int(row["round_index"]),
                "executed_action": row.get("decision", {}).get("executed_action"),
                "accepted": bool(row.get("deployed")),
                "primary_improvement": row.get("primary_improvement"),
                "cpu_seconds": row.get("cpu_seconds"),
            }
            for row in history[-10:]
        ),
        budget={
            "rounds_remaining": 10 - round_index,
            "candidate_slots_this_round": 1,
            "max_epochs": 5,
            "max_learning_rate_multiplier": 3.0,
        },
        capabilities={
            "official_parent_continuation": True,
            "incremental_update": True,
            "replay_refit": True,
            "rollback": rollback_available,
            "retain": True,
            "allowed_actions": [
                Action.NOOP.value,
                Action.INCREMENTAL_UPDATE.value,
                Action.REPLAY_REFIT.value,
                *([Action.ROLLBACK.value] if rollback_available else []),
            ],
            "allowed_parameters": ["epochs", "learning_rate"],
            "family_switch": False,
            "bounded_hpo": False,
        },
    )
    policy_mode = (
        "protocol"
        if str(parent.meta.get("profile")) in config.protocol_profiles
        else config.policy_mode
    )
    candidate_events = sum(bool(row.get("candidate_trained")) for row in history)
    base_learning_rate = float(
        state.get("base_learning_rate", parent.meta["learning_rate"])
    )
    schedule = _COMPETITIVE_SCHEDULES.get(str(parent.meta.get("profile")))
    scheduled = (
        next(
            ((epochs, multiplier) for round_number, epochs, multiplier in schedule if round_number == round_index),
            None,
        )
        if schedule is not None
        else None
    )
    candidate_budget_available = candidate_events < config.max_training_rounds
    portfolio_plan = None
    portfolio_recipe: str | None = None
    forward_override = False
    if policy_mode == "portfolio":
        target_means = tuple(
            float(row["target_mean"])
            for row in history
            if isinstance(row.get("target_mean"), (int, float))
        ) + (float(current_target_mean),)
        consecutive_aggressive = 0
        for row in reversed(history):
            if row.get("recipe") != "current_e3_lr3" or not row.get("deployed"):
                break
            consecutive_aggressive += 1
        portfolio_plan = build_candidate_plan(
            PortfolioEvidence(
                task_kind=str(parent.meta["task"]),
                target_batch_means=target_means,
                target_scale=float(parent.meta["target_scale"]),
                previous_delayed_gain=(
                    arrival_evidence.delayed_gain
                    if arrival_evidence is not None
                    else None
                ),
                failure_streak=failure_streak,
                consecutive_aggressive=consecutive_aggressive,
            )
        )
        if portfolio_plan.secondary_recipe in {"recent_e3", "current_e3_lr3"}:
            portfolio_recipe = portfolio_plan.secondary_recipe
        else:
            portfolio_recipe = portfolio_plan.primary_recipe
        forward_override = portfolio_recipe == "current_e3_lr3"
        negative_delayed_gain = (
            arrival_evidence is not None
            and arrival_evidence.delayed_gain is not None
            and arrival_evidence.delayed_gain < 0.0
        )
        if negative_delayed_gain and rollback_available:
            default_action = Action.ROLLBACK
            epochs = 0
            learning_rate = base_learning_rate
            portfolio_recipe = None
        elif candidate_budget_available and round_index < 10:
            default_action = (
                Action.REPLAY_REFIT
                if portfolio_recipe in {"recent_e3", "cumulative_e3_lr0.3"}
                and len(replay_x)
                else Action.INCREMENTAL_UPDATE
            )
            epochs = 3
            learning_rate = base_learning_rate
        else:
            default_action = Action.NOOP
            epochs = 0
            learning_rate = base_learning_rate
            portfolio_recipe = None
    elif policy_mode == "sequential":
        cold_start = arrival_evidence is not None and arrival_evidence.previous_metrics is None
        negative_delayed_gain = (
            arrival_evidence is not None
            and arrival_evidence.delayed_gain is not None
            and arrival_evidence.delayed_gain < 0.0
        )
        needs_candidate = cold_start or performance_drop >= config.arrival_drop_trigger
        if negative_delayed_gain and rollback_available:
            default_action = Action.ROLLBACK
            epochs = 0
            learning_rate = base_learning_rate
        elif candidate_budget_available and (needs_candidate or negative_delayed_gain):
            default_action = Action.REPLAY_REFIT if len(replay_x) else Action.INCREMENTAL_UPDATE
            epochs = config.epochs
            learning_rate = base_learning_rate * config.learning_rate_multiplier
        else:
            default_action = Action.NOOP
            epochs = 0
            learning_rate = base_learning_rate
    elif policy_mode == "competitive" and (
        not candidate_budget_available
        or (schedule is not None and scheduled is None)
    ):
        default_action = Action.NOOP
        epochs = 0
        learning_rate = base_learning_rate
    else:
        default_action = Action.REPLAY_REFIT if len(replay_x) else Action.INCREMENTAL_UPDATE
        if policy_mode == "competitive" and scheduled is not None:
            epochs, multiplier = scheduled
            learning_rate = base_learning_rate * multiplier
        else:
            epochs = config.epochs
            learning_rate = base_learning_rate * config.learning_rate_multiplier
    action = default_action
    proposed_action: str | None = None
    proposal_accepted = False
    fallback_reason: str | None = None
    advisor_source = "not_configured"
    advisor_receipt: dict[str, Any] | None = None
    policy_constraints_applied: list[str] = []
    rationale = "deterministic bounded continuation"
    if advisor is not None and default_action is not Action.ROLLBACK:
        outcome = advisor.advise(context, trigger)
        advisor_source = outcome.source
        advisor_receipt = asdict(outcome.receipt)
        proposal = outcome.proposal
        if proposal is not None:
            proposed_action = proposal.action.value
            try:
                validate_experiment_proposal(proposal)
                if proposal.action not in _PLATFORM_ACTIONS:
                    raise ValueError("unsupported_platform_action")
                if proposal.action is not Action.NOOP and not candidate_budget_available:
                    raise ValueError("candidate_budget_exhausted")
                if set(proposal.parameters) - {"epochs", "learning_rate"}:
                    raise ValueError("unsupported_platform_parameter")
                proposed_epochs = (
                    0
                    if proposal.action is Action.NOOP
                    else proposal.parameters.get("epochs", epochs)
                )
                proposed_learning_rate = (
                    base_learning_rate
                    if proposal.action is Action.NOOP
                    else proposal.parameters.get("learning_rate", learning_rate)
                )
                if (
                    proposal.action is not Action.NOOP
                    and (
                        isinstance(proposed_epochs, bool)
                        or not isinstance(proposed_epochs, int)
                        or not 1 <= proposed_epochs <= 5
                    )
                ):
                    raise ValueError("epochs_out_of_bounds")
                if (
                    proposal.action is not Action.NOOP
                    and (
                        isinstance(proposed_learning_rate, bool)
                        or not isinstance(proposed_learning_rate, (int, float))
                        or not math.isfinite(float(proposed_learning_rate))
                        or not (
                            base_learning_rate * 0.1
                            <= float(proposed_learning_rate)
                            <= base_learning_rate * 3.0
                        )
                    )
                ):
                    raise ValueError("learning_rate_out_of_bounds")
                if outcome.source == "deterministic_recovery":
                    action = Action.NOOP
                    epochs = 0
                    learning_rate = base_learning_rate
                    rationale = proposal.rationale
                    proposal_accepted = True
                elif (
                    policy_mode == "competitive"
                    and schedule is not None
                    and scheduled is None
                    and proposal.action is not Action.NOOP
                ):
                    raise ValueError("outside_frozen_candidate_schedule")
                elif default_action is not Action.NOOP:
                    if proposal.action is Action.NOOP:
                        raise ValueError("frozen_candidate_required")
                    if proposal.action is not default_action:
                        policy_constraints_applied.append("action")
                    if proposed_epochs != epochs:
                        policy_constraints_applied.append("epochs")
                    if not math.isclose(
                        float(proposed_learning_rate), learning_rate, rel_tol=0.0, abs_tol=1e-15
                    ):
                        policy_constraints_applied.append("learning_rate")
                    action = default_action
                    rationale = proposal.rationale
                    proposal_accepted = True
                else:
                    action = Action.NOOP
                    epochs = 0
                    learning_rate = base_learning_rate
                    rationale = proposal.rationale
                    proposal_accepted = True
            except ValueError as exc:
                fallback_reason = str(exc)
    outcome = (
        "retain"
        if action is Action.NOOP
        else "rollback"
        if action is Action.ROLLBACK
        else "candidate"
    )
    decision = {
        "format": "brace-msi.platform-decision.v1",
        "source": advisor_source if proposal_accepted else "deterministic_policy",
        "advisor_source": advisor_source,
        "triggered": trigger.should_call,
        "trigger_reasons": list(trigger.reasons),
        "proposed_action": proposed_action,
        "executed_action": action.value,
        "proposal_accepted": proposal_accepted,
        "fallback_reason": fallback_reason,
        "policy_constraints_applied": policy_constraints_applied,
        "rationale": rationale,
        "outcome": outcome,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "recipe": portfolio_recipe,
        "portfolio_plan": asdict(portfolio_plan) if portfolio_plan is not None else None,
        "forward_override": forward_override,
        "arrival_evidence": asdict(arrival_evidence) if arrival_evidence is not None else None,
        "performance_drop": performance_drop,
        "drift_complexity": drift_complexity,
        "advisor_receipt": advisor_receipt,
    }
    return decision, action, epochs, learning_rate


def start_round(
    data_path: Path,
    previous_checkpoint: Path,
    workspace_root: Path,
    output_root: Path,
    config: PlatformRuntimeConfig = PlatformRuntimeConfig(),
    *,
    advisor: PlatformAdvisor | None = None,
    gate_data_path: Path | None = None,
    arrival_evidence: ArrivalEvidence | None = None,
    rollback_checkpoint: Path | None = None,
) -> dict[str, Any]:
    """Execute one platform round and atomically publish the selected checkpoint."""

    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    parent_path = Path(previous_checkpoint).resolve()
    workspace = Path(workspace_root).resolve()
    output = Path(output_root).resolve()
    output_is_mount = output.exists()
    if output_is_mount:
        if output.is_symlink() or not output.is_dir():
            raise FileExistsError("output root must be a directory mount")
        if any(output.iterdir()):
            raise FileExistsError("existing output mount must be empty")
    workspace.mkdir(parents=True, exist_ok=True)
    state_path = workspace / "state.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.is_file()
        else {"format": "brace-msi.platform-state.v1", "rounds": []}
    )
    if not isinstance(state, dict) or not isinstance(state.get("rounds"), list):
        raise ValueError("workspace state is invalid")
    round_index = len(state["rounds"]) + 1
    if round_index > 10:
        raise ValueError("platform runtime supports at most ten rounds")
    parent_sha = _sha256(parent_path)
    if state["rounds"] and state["rounds"][-1].get("checkpoint_sha256") != parent_sha:
        raise ValueError("platform parent does not match the previous committed round")

    parent = _NativeModel.load(parent_path)
    shadow_predecessor_path = workspace / "shadow-predecessor.npz"
    rollback_path = (
        Path(rollback_checkpoint).resolve()
        if rollback_checkpoint is not None
        else shadow_predecessor_path.resolve()
        if config.policy_mode == "portfolio" and shadow_predecessor_path.is_file()
        else None
    )
    rollback_model: _NativeModel | None = None
    rollback_sha: str | None = None
    if rollback_path is not None:
        rollback_model = _NativeModel.load(rollback_path)
        structural_fields = (
            "format",
            "device",
            "task",
            "profile",
            "paths",
            "classes",
            "hidden",
            "parameter_count",
        )
        if any(
            rollback_model.meta.get(field) != parent.meta.get(field)
            for field in structural_fields
        ):
            raise ValueError("rollback checkpoint is incompatible with the current parent")
        rollback_sha = _sha256(rollback_path)
        if (
            not state["rounds"]
            or state["rounds"][-1].get("parent_checkpoint_sha256") != rollback_sha
        ):
            raise ValueError("rollback checkpoint must be the direct predecessor")
    if "base_learning_rate" not in state:
        state["base_learning_rate"] = float(parent.meta["learning_rate"])
    update_batch = _read_rows(Path(data_path), parent, require_answers=True)
    if gate_data_path is None:
        batch = update_batch
        update_indices, gate_indices = _split_indices(
            batch["y"], parent.meta["task"], config.gate_fraction
        )
        partition_mode = "internal_split"
        feedback_update_count = len(batch["ids"])
        feedback_update_sha256 = batch["sha256"]
        feedback_gate_sha256 = None
    else:
        gate_batch = _read_rows(Path(gate_data_path), parent, require_answers=True)
        if set(update_batch["ids"]) & set(gate_batch["ids"]):
            raise ValueError("explicit Update and Gate sample IDs overlap")
        if len(update_batch["ids"]) < 2:
            raise ValueError("explicit Update needs at least two samples")
        batch = {
            "path": update_batch["path"],
            "ids": [*update_batch["ids"], *gate_batch["ids"]],
            "x": np.concatenate((update_batch["x"], gate_batch["x"]), axis=0),
            "y": np.concatenate((update_batch["y"], gate_batch["y"]), axis=0),
            "sha256": hashlib.sha256(
                (update_batch["sha256"] + gate_batch["sha256"]).encode("ascii")
            ).hexdigest(),
        }
        update_indices = np.arange(len(update_batch["ids"]), dtype=np.int64)
        gate_indices = np.arange(
            len(update_batch["ids"]), len(batch["ids"]), dtype=np.int64
        )
        partition_mode = "explicit_update_gate"
        feedback_update_count = len(update_batch["ids"])
        feedback_update_sha256 = update_batch["sha256"]
        feedback_gate_sha256 = gate_batch["sha256"]
    if arrival_evidence is None and config.policy_mode == "portfolio":
        automatic_metrics = _metrics(parent, batch["x"], batch["y"])
        predecessor_metrics = (
            _metrics(rollback_model, batch["x"], batch["y"])
            if rollback_model is not None
            else None
        )
        arrival_evidence = ArrivalEvidence(
            metrics=automatic_metrics,
            previous_metrics=(
                state["rounds"][-1].get("arrival_metrics")
                if state["rounds"]
                and isinstance(state["rounds"][-1].get("arrival_metrics"), dict)
                else None
            ),
            sample_count=len(batch["ids"]),
            delayed_gain=(
                _primary_improvement(
                    parent.meta["task"], predecessor_metrics, automatic_metrics
                )
                if predecessor_metrics is not None
                else None
            ),
        )
    _validate_arrival_evidence(
        arrival_evidence,
        task=parent.meta["task"],
        expected_count=len(batch["ids"]),
    )
    anchor_path = workspace / "anchor.npz"
    replay_path = workspace / "replay.npz"
    new_anchor = not anchor_path.exists()
    if new_anchor:
        anchor_count = max(1, int(round(len(batch["ids"]) * 0.1)))
        anchor_count = min(anchor_count, len(update_indices) - 1)
        anchor_indices = update_indices[:anchor_count]
        update_indices = update_indices[anchor_count:]
        anchor_x = batch["x"][anchor_indices]
        anchor_y = batch["y"][anchor_indices]
    else:
        anchor_x, anchor_y = _load_buffer(
            anchor_path,
            feature_count=len(parent.meta["paths"]),
            task=parent.meta["task"],
        )
    if replay_path.exists():
        replay_x, replay_y = _load_buffer(
            replay_path,
            feature_count=len(parent.meta["paths"]),
            task=parent.meta["task"],
        )
    else:
        replay_x = np.empty((0, len(parent.meta["paths"])), dtype=np.float64)
        replay_y = np.empty(
            (0,), dtype=np.int64 if parent.meta["task"] == "classification" else np.float64
        )
    before = _metrics(parent, batch["x"][gate_indices], batch["y"][gate_indices])
    anchor_before = _metrics(parent, anchor_x, anchor_y)
    replay_before = _metrics(parent, replay_x, replay_y) if len(replay_x) else None
    decision, executed_action, selected_epochs, selected_learning_rate = _decision_for_round(
        parent=parent,
        before=before,
        update_x=batch["x"][update_indices],
        replay_x=replay_x,
        anchor_x=anchor_x,
        state=state,
        round_index=round_index,
        config=config,
        advisor=advisor,
        arrival_evidence=arrival_evidence,
        rollback_available=rollback_model is not None,
        current_target_mean=float(np.mean(batch["y"][update_indices])),
    )
    use_replay = executed_action is Action.REPLAY_REFIT and len(replay_x) > 0
    training_x = (
        np.concatenate((batch["x"][update_indices], replay_x), axis=0)
        if use_replay
        else batch["x"][update_indices]
    )
    training_y = (
        np.concatenate((batch["y"][update_indices], replay_y), axis=0)
        if use_replay
        else batch["y"][update_indices]
    )
    candidate_events = sum(
        bool(row.get("candidate_trained")) for row in state["rounds"]
    )
    candidate_trained = (
        executed_action in {Action.INCREMENTAL_UPDATE, Action.REPLAY_REFIT}
        and candidate_events < config.max_training_rounds
    )
    deployed = False
    candidate_metrics: dict[str, float] | None = None
    anchor_candidate_metrics: dict[str, float] | None = None
    replay_candidate_metrics: dict[str, float] | None = None
    anchor_degradation: float | None = None
    relative_improvement: float | None = None
    losses: list[float] = []
    candidate_sha: str | None = None
    candidate = parent.clone()
    candidate.meta["learning_rate"] = selected_learning_rate
    gate_reason = "retain_no_candidate"
    relative_anchor_degradation: float | None = None
    relative_replay_degradation: float | None = None

    staging_parent = output if output_is_mount else workspace
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=staging_parent))
    try:
        candidate_path = temporary / "candidate.npz"
        if executed_action is Action.ROLLBACK:
            if rollback_model is None or rollback_path is None or rollback_sha is None:
                raise ValueError("rollback action requires a compatible direct predecessor")
            candidate = rollback_model
            candidate_metrics = _metrics(
                candidate, batch["x"][gate_indices], batch["y"][gate_indices]
            )
            anchor_candidate_metrics = _metrics(candidate, anchor_x, anchor_y)
            replay_candidate_metrics = (
                _metrics(candidate, replay_x, replay_y) if len(replay_x) else None
            )
            if parent.meta["task"] == "classification":
                anchor_degradation = (
                    anchor_before["macro_f1"] - anchor_candidate_metrics["macro_f1"]
                )
            else:
                anchor_degradation = anchor_candidate_metrics["rmse"] - anchor_before["rmse"]
            relative_improvement = _relative_improvement(
                parent.meta["task"], before, candidate_metrics
            )
            anchor_baseline = (
                anchor_before["macro_f1"]
                if parent.meta["task"] == "classification"
                else anchor_before["rmse"]
            )
            relative_anchor_degradation = anchor_degradation / max(
                abs(anchor_baseline), 1e-12
            )
            if replay_before is not None and replay_candidate_metrics is not None:
                relative_replay_degradation = -_relative_improvement(
                    parent.meta["task"], replay_before, replay_candidate_metrics
                )
            deployed = True
            gate_reason = "negative_delayed_gain_rollback"
            candidate_sha = rollback_sha
        elif candidate_trained:
            policy_mode = (
                "protocol"
                if str(parent.meta.get("profile")) in config.protocol_profiles
                else config.policy_mode
            )
            if policy_mode == "portfolio":
                recipe = decision.get("recipe")
                if not isinstance(recipe, str):
                    raise ValueError("portfolio candidate requires a recipe")
                candidate = _fit_portfolio_recipe(
                    parent,
                    recipe=recipe,
                    replay_x=replay_x,
                    replay_y=replay_y,
                    update_x=batch["x"][update_indices],
                    update_y=batch["y"][update_indices],
                )
                losses = []
            else:
                losses = candidate.fit(training_x, training_y, selected_epochs)
            candidate_metrics = _metrics(
                candidate, batch["x"][gate_indices], batch["y"][gate_indices]
            )
            anchor_candidate_metrics = _metrics(candidate, anchor_x, anchor_y)
            replay_candidate_metrics = (
                _metrics(candidate, replay_x, replay_y) if len(replay_x) else None
            )
            if parent.meta["task"] == "classification":
                anchor_degradation = (
                    anchor_before["macro_f1"] - anchor_candidate_metrics["macro_f1"]
                )
            else:
                anchor_degradation = anchor_candidate_metrics["rmse"] - anchor_before["rmse"]
            relative_improvement = _relative_improvement(
                parent.meta["task"], before, candidate_metrics
            )
            if policy_mode == "competitive":
                gate_outcome = _competitive_gate(
                    profile=str(parent.meta.get("profile", "")),
                    task=parent.meta["task"],
                    before=before,
                    candidate=candidate_metrics,
                    anchor_before=anchor_before,
                    anchor_candidate=anchor_candidate_metrics,
                    replay_before=replay_before,
                    replay_candidate=replay_candidate_metrics,
                )
                deployed = gate_outcome.accepted
                gate_reason = gate_outcome.reason
                relative_anchor_degradation = gate_outcome.relative_anchor_degradation
                relative_replay_degradation = gate_outcome.relative_replay_degradation
                if not len(replay_x):
                    deployed = False
                    gate_reason = "insufficient_history_for_deployment"
            elif policy_mode == "portfolio":
                primary_gain = _primary_improvement(
                    parent.meta["task"], before, candidate_metrics
                )
                deployed = primary_gain > 0.0 or bool(decision.get("forward_override"))
                gate_reason = (
                    "portfolio_forward_trend"
                    if bool(decision.get("forward_override"))
                    else "portfolio_gate_passed"
                    if deployed
                    else "portfolio_gate_rejected"
                )
                anchor_baseline = (
                    anchor_before["macro_f1"]
                    if parent.meta["task"] == "classification"
                    else anchor_before["rmse"]
                )
                relative_anchor_degradation = anchor_degradation / max(
                    abs(anchor_baseline), 1e-12
                )
            else:
                deployed = (
                    _primary_improvement(parent.meta["task"], before, candidate_metrics)
                    > config.min_primary_improvement
                    and relative_improvement >= config.min_relative_improvement
                    and anchor_degradation <= config.max_anchor_degradation
                )
                gate_reason = "protocol_gate_passed" if deployed else "protocol_gate_rejected"
                anchor_baseline = (
                    anchor_before["macro_f1"]
                    if parent.meta["task"] == "classification"
                    else anchor_before["rmse"]
                )
                relative_anchor_degradation = anchor_degradation / max(
                    abs(anchor_baseline), 1e-12
                )
                relative_replay_degradation = None
            candidate.save(candidate_path)
            candidate_sha = _sha256(candidate_path)
        checkpoint = temporary / "checkpoint.npz"
        if executed_action is Action.ROLLBACK and deployed:
            shutil.copy2(rollback_path, checkpoint)
        elif deployed:
            os.replace(candidate_path, checkpoint)
        else:
            shutil.copy2(parent_path, checkpoint)
            if candidate_path.exists():
                candidate_path.unlink()
        checkpoint_sha = _sha256(checkpoint)
        if checkpoint.stat().st_size > _MAX_CHECKPOINT_BYTES:
            raise ValueError("checkpoint exceeds 64 MiB")
        wall_seconds = time.perf_counter() - started_wall
        cpu_seconds = time.process_time() - started_cpu
        peak_rss = psutil.Process().memory_info().rss
        receipt: dict[str, Any] = {
            "format": "brace-msi.platform-round.v1",
            "status": "completed",
            "round_index": round_index,
            "task": parent.meta["task"],
            "sample_count": len(batch["ids"]),
            "target_mean": float(np.mean(batch["y"][update_indices])),
            "partition_mode": partition_mode,
            "feedback_update_sample_count": feedback_update_count,
            "feedback_update_sha256": feedback_update_sha256,
            "feedback_gate_sha256": feedback_gate_sha256,
            "update_count": len(update_indices),
            "gate_count": len(gate_indices),
            "anchor_count": len(anchor_x),
            "replay_count": len(replay_x),
            "training_sample_count": len(training_x) if candidate_trained else 0,
            "data_sha256": batch["sha256"],
            "parent_loaded": True,
            "parent_checkpoint_sha256": parent_sha,
            "candidate_checkpoint_sha256": candidate_sha,
            "rollback_checkpoint_sha256": (
                rollback_sha if executed_action is Action.ROLLBACK else None
            ),
            "checkpoint_sha256": checkpoint_sha,
            "candidate_trained": candidate_trained,
            "recipe": decision.get("recipe"),
            "decision": decision,
            "arrival_metrics": (
                arrival_evidence.metrics if arrival_evidence is not None else None
            ),
            "deployed": deployed,
            "primary_improvement": (
                _primary_improvement(parent.meta["task"], before, candidate_metrics)
                if candidate_metrics is not None
                else None
            ),
            "relative_improvement": relative_improvement,
            "metrics_before": before,
            "metrics_candidate": candidate_metrics,
            "anchor_metrics_before": anchor_before,
            "anchor_metrics_candidate": anchor_candidate_metrics,
            "replay_metrics_before": replay_before,
            "replay_metrics_candidate": replay_candidate_metrics,
            "anchor_degradation": anchor_degradation,
            "relative_anchor_degradation": relative_anchor_degradation,
            "relative_replay_degradation": relative_replay_degradation,
            "gate_reason": gate_reason,
            "epochs": selected_epochs if candidate_trained else 0,
            "learning_rate": candidate.meta["learning_rate"] if candidate_trained else None,
            "batch_size": parent.meta["batch_size"],
            "losses": losses,
            "cpu_seconds": cpu_seconds,
            "wall_seconds": wall_seconds,
            "peak_rss_bytes": peak_rss,
            "input_tokens": int(
                (decision.get("advisor_receipt") or {}).get("total_input_tokens", 0)
            ),
            "output_tokens": int(
                (decision.get("advisor_receipt") or {}).get("total_output_tokens", 0)
            ),
        }
        _atomic_json(temporary / "training.json", receipt)
        with (temporary / "history.jsonl").open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")
        if output_is_mount:
            for name in ("training.json", "history.jsonl", "checkpoint.npz"):
                os.replace(temporary / name, output / name)
            temporary.rmdir()
        else:
            os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    state["rounds"].append(receipt)
    if config.policy_mode == "portfolio" and deployed and executed_action is not Action.ROLLBACK:
        shutil.copy2(parent_path, shadow_predecessor_path)
    elif shadow_predecessor_path.exists():
        shadow_predecessor_path.unlink()
    if new_anchor:
        _atomic_npz(anchor_path, x=anchor_x, y=anchor_y)
    next_replay_x = np.concatenate((replay_x, batch["x"][update_indices]), axis=0)
    next_replay_y = np.concatenate((replay_y, batch["y"][update_indices]), axis=0)
    if len(next_replay_x) > config.max_replay_samples:
        next_replay_x = next_replay_x[-config.max_replay_samples :]
        next_replay_y = next_replay_y[-config.max_replay_samples :]
    _atomic_npz(replay_path, x=next_replay_x, y=next_replay_y)
    _atomic_json(state_path, state)
    spool = workspace / "public-spool.jsonl"
    public_record = {
        "schema_version": 1,
        "formal_runtime": True,
        "event": "round_completed",
        "round_index": round_index,
        "task_kind": parent.meta["task"],
        "sample_count": len(batch["ids"]),
        "candidate_count": int(candidate_trained),
        "training_started": candidate_trained,
        "accepted": deployed,
        "primary_metric": (
            (candidate_metrics or before).get("macro_f1")
            if parent.meta["task"] == "classification"
            else (candidate_metrics or before).get("rmse")
        ),
        "cpu_seconds": receipt["cpu_seconds"],
        "wall_seconds": receipt["wall_seconds"],
        "peak_rss_bytes": receipt["peak_rss_bytes"],
        "status": "completed",
    }
    with spool.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(public_record, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")
    return receipt


def submit_predictions(
    checkpoint_path: Path,
    request_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Run the independent prediction protocol over unlabeled JSONL requests."""

    model = _NativeModel.load(Path(checkpoint_path))
    batch = _read_rows(Path(request_path), model, require_answers=False)
    raw = model.predict_raw(batch["x"])
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
        for index, identity in enumerate(batch["ids"]):
            if model.meta["task"] == "classification":
                outputs: Any = [
                    {"label": label, "score": float(score)}
                    for label, score in zip(model.meta["classes"], raw[index], strict=True)
                ]
            else:
                outputs = {"value": float(raw[index])}
            stream.write(
                json.dumps(
                    {"id": identity, "outputs": outputs},
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, output)
    return {"status": "completed", "sample_count": len(batch["ids"]), "task": model.meta["task"]}


def evaluate_checkpoint(checkpoint_path: Path, labeled_data_path: Path) -> dict[str, float]:
    """Local-only metric evaluation; labels never enter the prediction entry."""

    model = _NativeModel.load(Path(checkpoint_path))
    batch = _read_rows(Path(labeled_data_path), model, require_answers=True)
    return _metrics(model, batch["x"], batch["y"])

