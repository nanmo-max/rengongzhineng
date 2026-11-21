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

    def fit(
        self,
        values: np.ndarray,
        targets: np.ndarray,
        epochs: int,
        *,
        sample_weights: np.ndarray | None = None,
        loss: str = "native",
        loss_parameters: dict[str, float] | None = None,
        optimizer: str = "adam",
        optimizer_parameters: dict[str, float] | None = None,
    ) -> list[float]:
        optimizer_options = dict(optimizer_parameters or {})
        allowed_optimizer_parameters = {
            "adam": set(),
            "l2sp": {"strength"},
            "sam": {"rho"},
            "adamw": {"weight_decay"},
        }
        if optimizer not in allowed_optimizer_parameters:
            raise ValueError("unsupported optimizer")
        unknown_optimizer_parameters = set(optimizer_options) - allowed_optimizer_parameters[optimizer]
        if unknown_optimizer_parameters:
            raise ValueError(f"unsupported optimizer parameter: {sorted(unknown_optimizer_parameters)[0]}")
        optimizer_parameter_name = {
            "l2sp": "strength",
            "sam": "rho",
            "adamw": "weight_decay",
        }.get(optimizer)
        optimizer_parameter = 0.0
        if optimizer_parameter_name is not None:
            raw_optimizer_parameter = optimizer_options.get(optimizer_parameter_name)
            if (
                isinstance(raw_optimizer_parameter, bool)
                or not isinstance(raw_optimizer_parameter, (int, float))
                or not math.isfinite(float(raw_optimizer_parameter))
                or float(raw_optimizer_parameter) <= 0.0
            ):
                raise ValueError(f"{optimizer_parameter_name} must be positive and finite")
            optimizer_parameter = float(raw_optimizer_parameter)
        reference_parameters = {
            name: self.params[name].copy()
            for name in ("w1", "w2")
        }
        normalized = self._normalized(values)
        if targets.shape != (len(normalized),) or not len(normalized):
            raise ValueError("target shape is invalid")
        parameters = dict(loss_parameters or {})
        weights = None if sample_weights is None else np.asarray(sample_weights, dtype=np.float64)
        if weights is not None and (
            weights.shape != (len(normalized),)
            or not np.all(np.isfinite(weights))
            or np.any(weights <= 0.0)
        ):
            raise ValueError("sample weights must be finite positive values aligned to targets")
        if self.meta["task"] == "regression":
            expected = (targets - float(self.meta["target_mean"])) / float(self.meta["target_scale"])
            if loss == "native":
                loss = "mse"
            if loss not in {"mse", "huber", "asymmetric"}:
                raise ValueError("unsupported regression loss")
            if loss == "huber":
                if set(parameters) - {"delta"}:
                    raise ValueError("unsupported Huber loss parameter")
                huber_delta = float(parameters.get("delta", 1.0))
                if not math.isfinite(huber_delta) or huber_delta <= 0.0:
                    raise ValueError("Huber delta must be positive")
            elif loss == "asymmetric":
                if set(parameters) - {"underprediction_weight", "overprediction_weight"}:
                    raise ValueError("unsupported asymmetric loss parameter")
                under_weight = float(parameters.get("underprediction_weight", 1.0))
                over_weight = float(parameters.get("overprediction_weight", 1.0))
                if (
                    not math.isfinite(under_weight)
                    or not math.isfinite(over_weight)
                    or under_weight <= 0.0
                    or over_weight <= 0.0
                ):
                    raise ValueError("asymmetric loss weights must be positive")
        else:
            expected = targets.astype(np.int64, copy=False)
            if np.any(expected < 0) or np.any(expected >= len(self.meta["classes"])):
                raise ValueError("classification target is unknown")
            if loss == "native":
                loss = "cross_entropy"
            if loss != "cross_entropy" or parameters:
                raise ValueError("unsupported classification loss")
        losses: list[float] = []
        for _ in range(epochs):
            rng = np.random.default_rng(np.random.SeedSequence([self.meta["seed"], self.meta["epochs"]]))
            order = rng.permutation(len(normalized))
            loss_sum = 0.0
            for start in range(0, len(order), self.meta["batch_size"]):
                indices = order[start : start + self.meta["batch_size"]]
                batch = normalized[indices]
                target = expected[indices]
                batch_weights = None if weights is None else weights[indices]
                weight_sum = float(len(indices)) if batch_weights is None else float(np.sum(batch_weights))

                def loss_and_gradients() -> tuple[float, dict[str, np.ndarray]]:
                    hidden = np.tanh(batch @ self.params["w1"] + self.params["b1"])
                    logits = hidden @ self.params["w2"] + self.params["b2"]
                    if self.meta["task"] == "classification":
                        logits -= logits.max(axis=1, keepdims=True)
                        probabilities = np.exp(logits)
                        probabilities /= probabilities.sum(axis=1, keepdims=True)
                        per_sample = -np.log(np.maximum(probabilities[np.arange(len(indices)), target], 1e-300))
                        batch_loss = float(np.sum(per_sample if batch_weights is None else per_sample * batch_weights))
                        output_delta = probabilities
                        output_delta[np.arange(len(indices)), target] -= 1.0
                        if batch_weights is not None:
                            output_delta *= batch_weights[:, None]
                        output_delta /= weight_sum
                    else:
                        error = logits[:, 0] - target
                        if loss == "huber":
                            absolute = np.abs(error)
                            per_sample = np.where(
                                absolute <= huber_delta,
                                0.5 * error**2,
                                huber_delta * (absolute - 0.5 * huber_delta),
                            )
                            derivative = np.clip(error, -huber_delta, huber_delta)
                        elif loss == "asymmetric":
                            factors = np.where(error < 0.0, under_weight, over_weight)
                            per_sample = factors * error**2
                            derivative = 2.0 * factors * error
                        else:
                            per_sample = error**2
                            derivative = 2.0 * error
                        batch_loss = float(np.sum(per_sample if batch_weights is None else per_sample * batch_weights))
                        if batch_weights is not None:
                            derivative *= batch_weights
                        output_delta = (derivative / weight_sum)[:, None]
                    result = {"w2": hidden.T @ output_delta, "b2": output_delta.sum(axis=0)}
                    hidden_delta = (output_delta @ self.params["w2"].T) * (1.0 - hidden**2)
                    result.update(w1=batch.T @ hidden_delta, b1=hidden_delta.sum(axis=0))
                    return batch_loss, result

                batch_loss, gradients = loss_and_gradients()
                loss_sum += batch_loss
                if optimizer == "sam":
                    first_norm = math.sqrt(sum(float(np.sum(value * value)) for value in gradients.values()))
                    if not math.isfinite(first_norm):
                        raise ValueError("nonfinite gradient")
                    perturbations = {
                        name: optimizer_parameter * gradient / max(first_norm, 1e-12)
                        for name, gradient in gradients.items()
                    }
                    for name, perturbation in perturbations.items():
                        self.params[name] += perturbation
                    try:
                        _, gradients = loss_and_gradients()
                    finally:
                        for name, perturbation in perturbations.items():
                            self.params[name] -= perturbation
                elif optimizer == "l2sp":
                    for name in reference_parameters:
                        gradients[name] += 2.0 * optimizer_parameter * (
                            self.params[name] - reference_parameters[name]
                        )
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
                    if optimizer == "adamw" and name in reference_parameters:
                        self.params[name] *= 1.0 - self.meta["learning_rate"] * optimizer_parameter
            self.meta["epochs"] += 1
            loss_denominator = float(len(normalized)) if weights is None else float(np.sum(weights))
            losses.append(loss_sum / loss_denominator)
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
