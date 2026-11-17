"""Minimal NumPy continuation for the official ``contest.cpu-mlp.v1`` format."""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
import zipfile

import numpy as np


_PARAMETERS = ("w1", "b1", "w2", "b2")
_MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024


class FormalModel:
    def __init__(self, arrays: dict[str, np.ndarray], metadata: dict[str, object]) -> None:
        self.params = {name: arrays[name].copy() for name in _PARAMETERS}
        self.first = {name: arrays[f"adam_first_{name}"].copy() for name in _PARAMETERS}
        self.second = {name: arrays[f"adam_second_{name}"].copy() for name in _PARAMETERS}
        self.mean = arrays["mean"].copy()
        self.scale = arrays["scale"].copy()
        self.meta = dict(metadata)
        self.validate()

    @classmethod
    def load(cls, path: Path | str) -> "FormalModel":
        path = Path(path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_CHECKPOINT_BYTES:
            raise ValueError("checkpoint must be a regular file no larger than 64 MiB")
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

    def clone(self) -> "FormalModel":
        arrays = {
            **{name: value.copy() for name, value in self.params.items()},
            **{f"adam_first_{name}": value.copy() for name, value in self.first.items()},
            **{f"adam_second_{name}": value.copy() for name, value in self.second.items()},
            "mean": self.mean.copy(),
            "scale": self.scale.copy(),
        }
        return FormalModel(arrays, self.meta)

    def validate(self) -> None:
        meta = self.meta
        if meta.get("format") != "contest.cpu-mlp.v1" or meta.get("device") != "cpu" or meta.get("task") not in {"classification", "regression"}:
            raise ValueError("unsupported parent checkpoint")
        paths = meta.get("paths")
        classes = meta.get("classes")
        hidden = meta.get("hidden")
        if not isinstance(paths, list) or not 1 <= len(paths) <= 4096 or not all(isinstance(value, str) for value in paths) or len(set(paths)) != len(paths):
            raise ValueError("checkpoint feature paths are invalid")
        if not isinstance(classes, list) or any(not isinstance(value, str) or not value for value in classes) or len(set(classes)) != len(classes) or (meta["task"] == "classification" and len(classes) < 2) or (meta["task"] == "regression" and classes):
            raise ValueError("checkpoint classes are invalid")
        if not isinstance(hidden, int) or not 1 <= hidden <= 128:
            raise ValueError("checkpoint hidden width is invalid")
        for field in ("epochs", "steps", "seed", "batch_size", "parameter_count"):
            if type(meta.get(field)) is not int or meta[field] < 0:
                raise ValueError("checkpoint integer state is invalid")
        if not 0 <= meta["seed"] < 2**32 or not 1 <= meta["batch_size"] <= 65536 or not 0 < meta["parameter_count"] < 100000:
            raise ValueError("checkpoint architecture is invalid")
        for field in ("learning_rate", "target_mean", "target_scale"):
            value = meta.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("checkpoint numeric state is invalid")
        if not 0 < meta["learning_rate"] <= 1 or meta["target_scale"] <= 0:
            raise ValueError("checkpoint optimizer/scaler state is invalid")
        output = len(classes) if meta["task"] == "classification" else 1
        shapes = {"w1": (len(paths), hidden), "b1": (hidden,), "w2": (hidden, output), "b2": (output,)}
        for group in (self.params, self.first, self.second):
            for name, shape in shapes.items():
                value = group[name]
                if value.shape != shape or value.dtype != np.dtype("float64") or not np.all(np.isfinite(value)):
                    raise ValueError("checkpoint tensor is invalid")
        if sum(value.size for value in self.params.values()) != meta["parameter_count"]:
            raise ValueError("checkpoint parameter count is invalid")
        if self.mean.shape != (len(paths),) or self.scale.shape != (len(paths),):
            raise ValueError("checkpoint preprocessing state is invalid")
        if self.mean.dtype != np.dtype("float64") or self.scale.dtype != np.dtype("float64") or not np.all(np.isfinite(self.mean)) or not np.all(np.isfinite(self.scale)) or np.any(self.scale <= 0):
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
            rng = np.random.default_rng(np.random.SeedSequence([self.meta["seed"], self.meta["epochs"]]))
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
                    loss_sum -= float(np.log(np.maximum(probabilities[np.arange(len(indices)), target], 1e-300)).sum())
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

    def save(self, path: Path | str) -> None:
        self.validate()
        arrays: dict[str, np.ndarray] = {
            **self.params,
            **{f"adam_first_{name}": value for name, value in self.first.items()},
            **{f"adam_second_{name}": value for name, value in self.second.items()},
            "mean": self.mean,
            "scale": self.scale,
            "metadata": np.asarray(json.dumps(self.meta, sort_keys=True, separators=(",", ":"), allow_nan=False)),
        }
        with Path(path).open("xb") as stream, zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(arrays):
                buffer = io.BytesIO()
                np.lib.format.write_array(buffer, arrays[name], allow_pickle=False)
                info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o600 << 16
                archive.writestr(info, buffer.getvalue())
