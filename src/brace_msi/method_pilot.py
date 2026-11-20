"""Low-cost method-level transfer probes over adjacent legal stream batches.

This module is research-only: heterogeneous estimators are temporary teachers and
must not be emitted as formal contest checkpoints.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .platform_runtime import _NativeModel


def discover_transition_paths(profile_root: Path) -> list[tuple[Path, Path]]:
    """Return the nine adjacent legal feedback transitions, excluding confirmation."""

    inputs = Path(profile_root) / "runtime-inputs"
    feedback_paths: list[Path] = []
    for index in range(1, 11):
        path = inputs / f"round-{index:02d}" / "feedback.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"missing legal stream feedback: {path}")
        feedback_paths.append(path)
    return list(zip(feedback_paths[:-1], feedback_paths[1:]))


def _metrics(task: str, target: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    if task == "classification":
        return {
            "accuracy": float(accuracy_score(target, prediction)),
            "macro_f1": float(
                f1_score(target, prediction, average="macro", zero_division=0)
            ),
        }
    return {
        "mae": float(mean_absolute_error(target, prediction)),
        "rmse": float(mean_squared_error(target, prediction) ** 0.5),
    }


def _signed_gain(
    task: str, baseline: dict[str, float], candidate: dict[str, float]
) -> float:
    if task == "classification":
        return float(candidate["macro_f1"] - baseline["macro_f1"])
    return float(baseline["rmse"] - candidate["rmse"])


def _native_prediction(model: _NativeModel, values: np.ndarray) -> np.ndarray:
    raw = model.predict_raw(values)
    if model.meta["task"] == "classification":
        return np.argmax(raw, axis=1).astype(np.int64)
    return np.asarray(raw, dtype=np.float64)


def _aligned_probabilities(
    estimator: Any, values: np.ndarray, class_count: int
) -> np.ndarray:
    probabilities = np.asarray(estimator.predict_proba(values), dtype=np.float64)
    result = np.zeros((len(values), class_count), dtype=np.float64)
    for source, label in enumerate(np.asarray(estimator.classes_).tolist()):
        index = int(label)
        if not 0 <= index < class_count:
            raise ValueError("teacher returned an unknown class")
        result[:, index] = probabilities[:, source]
    row_sum = result.sum(axis=1, keepdims=True)
    if np.any(row_sum <= 0.0):
        raise ValueError("teacher probabilities do not cover a known class")
    return result / row_sum


def _validate_arrays(
    parent: _NativeModel,
    *,
    history_x: np.ndarray,
    history_y: np.ndarray,
    current_x: np.ndarray,
    current_y: np.ndarray,
    next_x: np.ndarray,
    next_y: np.ndarray,
) -> None:
    width = len(parent.meta["paths"])
    task = parent.meta["task"]
    for name, values, targets in (
        ("history", history_x, history_y),
        ("current", current_x, current_y),
        ("next", next_x, next_y),
    ):
        if values.ndim != 2 or values.shape[1] != width:
            raise ValueError(f"{name} feature shape is invalid")
        if targets.shape != (len(values),):
            raise ValueError(f"{name} target shape is invalid")
        if not np.all(np.isfinite(values)) or not np.all(np.isfinite(targets)):
            raise ValueError(f"{name} data contains nonfinite values")
    if not len(current_x) or not len(next_x):
        raise ValueError("current and next batches must be nonempty")
    if task == "classification":
        class_count = len(parent.meta["classes"])
        for targets in (history_y, current_y, next_y):
            if np.any(targets < 0) or np.any(targets >= class_count):
                raise ValueError("classification target is outside the parent schema")


def run_transition(
    parent: _NativeModel,
    *,
    history_x: np.ndarray,
    history_y: np.ndarray,
    current_x: np.ndarray,
    current_y: np.ndarray,
    next_x: np.ndarray,
    next_y: np.ndarray,
    seed: int,
    low_budget: bool = False,
) -> list[dict[str, Any]]:
    """Train method-level probes on batches through t and score only on t+1."""

    arrays = {
        "history_x": np.asarray(history_x, dtype=np.float64),
        "history_y": np.asarray(history_y),
        "current_x": np.asarray(current_x, dtype=np.float64),
        "current_y": np.asarray(current_y),
        "next_x": np.asarray(next_x, dtype=np.float64),
        "next_y": np.asarray(next_y),
    }
    _validate_arrays(parent, **arrays)
    history_x = arrays["history_x"]
    history_y = arrays["history_y"]
    current_x = arrays["current_x"]
    current_y = arrays["current_y"]
    next_x = arrays["next_x"]
    next_y = arrays["next_y"]
    cumulative_x = np.concatenate((history_x, current_x), axis=0)
    cumulative_y = np.concatenate((history_y, current_y), axis=0)
    task = str(parent.meta["task"])
    baseline_prediction = _native_prediction(parent, next_x)
    baseline_metrics = _metrics(task, next_y, baseline_prediction)
    rows: list[dict[str, Any]] = [
        {
            "method": "static_parent",
            "available": True,
            "metrics": baseline_metrics,
            "signed_gain": 0.0,
            "cpu_seconds": 0.0,
            "error": None,
        }
    ]

    def record(method: str, operation: Callable[[], np.ndarray]) -> np.ndarray | None:
        started = time.process_time()
        try:
            prediction = np.asarray(operation())
            candidate_metrics = _metrics(task, next_y, prediction)
            gain = _signed_gain(task, baseline_metrics, candidate_metrics)
            if not math.isfinite(gain):
                raise ValueError("candidate gain is nonfinite")
            rows.append(
                {
                    "method": method,
                    "available": True,
                    "metrics": candidate_metrics,
                    "signed_gain": gain,
                    "cpu_seconds": time.process_time() - started,
                    "error": None,
                }
            )
            return prediction
        except (ValueError, FloatingPointError) as exc:
            rows.append(
                {
                    "method": method,
                    "available": False,
                    "metrics": None,
                    "signed_gain": None,
                    "cpu_seconds": time.process_time() - started,
                    "error": type(exc).__name__,
                }
            )
            return None

    def native_prediction(values: np.ndarray, targets: np.ndarray) -> np.ndarray:
        model = parent.clone()
        model.fit(values, targets, 1)
        return _native_prediction(model, next_x)

    record("native_current", lambda: native_prediction(current_x, current_y))
    record("native_cumulative", lambda: native_prediction(cumulative_x, cumulative_y))

    estimators: dict[str, Any] = {}
    if task == "classification":
        estimator_builders: dict[str, Callable[[], Any]] = {
            "linear_cumulative": lambda: make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    max_iter=300,
                    class_weight="balanced",
                    random_state=seed,
                ),
            ),
            "hgb_cumulative": lambda: HistGradientBoostingClassifier(
                max_iter=30 if low_budget else 100,
                learning_rate=0.08,
                l2_regularization=1.0,
                random_state=seed,
            ),
            "extra_trees_cumulative": lambda: ExtraTreesClassifier(
                n_estimators=30 if low_budget else 120,
                min_samples_leaf=2,
                max_features=0.8,
                class_weight="balanced",
                n_jobs=1,
                random_state=seed,
            ),
        }
    else:
        estimator_builders = {
            "linear_cumulative": lambda: make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
            "hgb_cumulative": lambda: HistGradientBoostingRegressor(
                max_iter=30 if low_budget else 100,
                learning_rate=0.08,
                l2_regularization=1.0,
                max_leaf_nodes=31,
                random_state=seed,
            ),
            "extra_trees_cumulative": lambda: ExtraTreesRegressor(
                n_estimators=30 if low_budget else 120,
                min_samples_leaf=2,
                max_features=0.8,
                n_jobs=1,
                random_state=seed,
            ),
        }

    teacher_predictions: dict[str, np.ndarray] = {}
    for method, build in estimator_builders.items():
        def operation(method: str = method, build: Callable[[], Any] = build) -> np.ndarray:
            if task == "classification" and len(np.unique(cumulative_y)) < 2:
                raise ValueError("classification teacher needs at least two classes")
            estimator = build()
            estimator.fit(cumulative_x, cumulative_y)
            estimators[method] = estimator
            if task == "classification":
                probabilities = _aligned_probabilities(
                    estimator, next_x, len(parent.meta["classes"])
                )
                teacher_predictions[method] = probabilities
                return np.argmax(probabilities, axis=1).astype(np.int64)
            prediction = np.maximum(
                0.0, np.asarray(estimator.predict(next_x), dtype=np.float64)
            )
            teacher_predictions[method] = prediction
            return prediction

        record(method, operation)

    def ensemble_prediction() -> np.ndarray:
        required = ("hgb_cumulative", "extra_trees_cumulative")
        if any(name not in teacher_predictions for name in required):
            raise ValueError("tree teachers are unavailable")
        averaged = 0.5 * (
            teacher_predictions[required[0]] + teacher_predictions[required[1]]
        )
        if task == "classification":
            return np.argmax(averaged, axis=1).astype(np.int64)
        return np.maximum(0.0, averaged)

    record("tree_ensemble", ensemble_prediction)
    return rows


def run_native_candidates(
    parent: _NativeModel,
    *,
    history_x: np.ndarray,
    history_y: np.ndarray,
    current_x: np.ndarray,
    current_y: np.ndarray,
    next_x: np.ndarray,
    next_y: np.ndarray,
) -> list[dict[str, Any]]:
    """Probe official-schema continuation, replay, reset and weight soups."""

    arrays = {
        "history_x": np.asarray(history_x, dtype=np.float64),
        "history_y": np.asarray(history_y),
        "current_x": np.asarray(current_x, dtype=np.float64),
        "current_y": np.asarray(current_y),
        "next_x": np.asarray(next_x, dtype=np.float64),
        "next_y": np.asarray(next_y),
    }
    _validate_arrays(parent, **arrays)
    history_x = arrays["history_x"]
    history_y = arrays["history_y"]
    current_x = arrays["current_x"]
    current_y = arrays["current_y"]
    next_x = arrays["next_x"]
    next_y = arrays["next_y"]
    cumulative_x = np.concatenate((history_x, current_x), axis=0)
    cumulative_y = np.concatenate((history_y, current_y), axis=0)
    recent_count = min(len(history_x), 2 * len(current_x))
    recent_x = np.concatenate((history_x[-recent_count:], current_x), axis=0)
    recent_y = np.concatenate((history_y[-recent_count:], current_y), axis=0)
    task = str(parent.meta["task"])
    baseline = _metrics(task, next_y, _native_prediction(parent, next_x))
    rows: list[dict[str, Any]] = []
    trained: dict[str, _NativeModel] = {}

    def train(
        method: str,
        values: np.ndarray,
        targets: np.ndarray,
        epochs: int,
        *,
        learning_rate_multiplier: float = 1.0,
        reset_optimizer: bool = False,
    ) -> None:
        started = time.process_time()
        model = parent.clone()
        model.meta["learning_rate"] = float(
            model.meta["learning_rate"] * learning_rate_multiplier
        )
        if reset_optimizer:
            model.first = {name: np.zeros_like(value) for name, value in model.first.items()}
            model.second = {name: np.zeros_like(value) for name, value in model.second.items()}
            model.meta["steps"] = 0
        model.fit(values, targets, epochs)
        metrics = _metrics(task, next_y, _native_prediction(model, next_x))
        rows.append(
            {
                "method": method,
                "available": True,
                "checkpoint_format": str(model.meta["format"]),
                "metrics": metrics,
                "signed_gain": _signed_gain(task, baseline, metrics),
                "cpu_seconds": time.process_time() - started,
                "epochs": epochs,
                "learning_rate_multiplier": learning_rate_multiplier,
                "reset_optimizer": reset_optimizer,
            }
        )
        trained[method] = model

    for scope, values, targets in (
        ("current", current_x, current_y),
        ("cumulative", cumulative_x, cumulative_y),
    ):
        for epochs in (1, 3):
            train(f"native_{scope}_e{epochs}", values, targets, epochs)
        for multiplier in (0.3, 3.0):
            train(
                f"native_{scope}_e3_lr{multiplier:g}",
                values,
                targets,
                3,
                learning_rate_multiplier=multiplier,
            )
        train(
            f"native_{scope}_e3_reset",
            values,
            targets,
            3,
            reset_optimizer=True,
        )
    train("native_recent_e3", recent_x, recent_y, 3)

    for source in ("native_current_e3", "native_cumulative_e3"):
        candidate = trained[source]
        for alpha in (0.25, 0.5, 0.75):
            started = time.process_time()
            soup = parent.clone()
            for name in soup.params:
                soup.params[name] = (
                    (1.0 - alpha) * parent.params[name]
                    + alpha * candidate.params[name]
                )
            soup.validate()
            metrics = _metrics(task, next_y, _native_prediction(soup, next_x))
            rows.append(
                {
                    "method": f"soup_{source.removeprefix('native_')}_alpha{alpha:g}",
                    "available": True,
                    "checkpoint_format": str(soup.meta["format"]),
                    "metrics": metrics,
                    "signed_gain": _signed_gain(task, baseline, metrics),
                    "cpu_seconds": time.process_time() - started,
                    "epochs": 3,
                    "learning_rate_multiplier": 1.0,
                    "reset_optimizer": False,
                }
            )
    return rows


def fit_native_recipe(
    parent: _NativeModel,
    *,
    recipe: str,
    history_x: np.ndarray,
    history_y: np.ndarray,
    current_x: np.ndarray,
    current_y: np.ndarray,
) -> _NativeModel:
    """Fit one preregistered official-schema recipe from a parent checkpoint."""

    history_x = np.asarray(history_x, dtype=np.float64)
    history_y = np.asarray(history_y)
    current_x = np.asarray(current_x, dtype=np.float64)
    current_y = np.asarray(current_y)
    width = len(parent.meta["paths"])
    if history_x.ndim != 2 or history_x.shape[1] != width:
        raise ValueError("history feature shape is invalid")
    if current_x.ndim != 2 or current_x.shape[1] != width or not len(current_x):
        raise ValueError("current feature shape is invalid")
    if history_y.shape != (len(history_x),) or current_y.shape != (len(current_x),):
        raise ValueError("recipe target shape is invalid")
    cumulative_x = np.concatenate((history_x, current_x), axis=0)
    cumulative_y = np.concatenate((history_y, current_y), axis=0)
    recent_count = min(len(history_x), 2 * len(current_x))
    recent_x = np.concatenate((history_x[-recent_count:], current_x), axis=0)
    recent_y = np.concatenate((history_y[-recent_count:], current_y), axis=0)
    specifications: dict[str, tuple[np.ndarray, np.ndarray, int, float]] = {
        "current_e1": (current_x, current_y, 1, 1.0),
        "current_e3_lr3": (current_x, current_y, 3, 3.0),
        "cumulative_e1": (cumulative_x, cumulative_y, 1, 1.0),
        "cumulative_e3": (cumulative_x, cumulative_y, 3, 1.0),
        "cumulative_e3_lr0.3": (cumulative_x, cumulative_y, 3, 0.3),
        "recent_e3": (recent_x, recent_y, 3, 1.0),
    }
    soup_prefix = "soup_current_e3_alpha"
    if recipe.startswith(soup_prefix):
        try:
            alpha = float(recipe.removeprefix(soup_prefix))
        except ValueError as exc:
            raise ValueError("invalid soup recipe") from exc
        if alpha not in {0.25, 0.5, 0.75}:
            raise ValueError("unsupported soup alpha")
        candidate = parent.clone()
        candidate.fit(current_x, current_y, 3)
        soup = candidate.clone()
        for name in soup.params:
            soup.params[name] = (
                (1.0 - alpha) * parent.params[name] + alpha * candidate.params[name]
            )
        soup.validate()
        return soup
    if recipe not in specifications:
        raise ValueError(f"unsupported native recipe: {recipe}")
    values, targets, epochs, multiplier = specifications[recipe]
    candidate = parent.clone()
    parent_rate = float(candidate.meta["learning_rate"])
    candidate.meta["learning_rate"] = float(parent_rate * multiplier)
    candidate.fit(values, targets, epochs)
    candidate.meta["learning_rate"] = parent_rate
    candidate.validate()
    return candidate


def fit_native_objective(
    parent: _NativeModel,
    *,
    values: np.ndarray,
    targets: np.ndarray,
    epochs: int,
    objective: str,
    learning_rate_multiplier: float = 1.0,
    huber_delta: float = 1.0,
    overprediction_weight: float = 1.0,
    prior_calibration_strength: float = 0.0,
    bias_correction_strength: float = 0.0,
) -> _NativeModel:
    """Research-only native continuation with bounded loss/calibration variants.

    The returned object keeps the official checkpoint schema and inherited Adam
    state.  The helper deliberately lives outside ``_NativeModel.fit`` until a
    method proves useful on unseen adjacent stages.
    """

    values = np.asarray(values, dtype=np.float64)
    targets = np.asarray(targets)
    if type(epochs) is not int or epochs < 1:
        raise ValueError("epochs must be a positive integer")
    if not math.isfinite(learning_rate_multiplier) or learning_rate_multiplier <= 0:
        raise ValueError("learning-rate multiplier must be positive")
    if not math.isfinite(huber_delta) or huber_delta <= 0:
        raise ValueError("Huber delta must be positive")
    if not math.isfinite(overprediction_weight) or overprediction_weight < 1.0:
        raise ValueError("overprediction weight must be at least one")
    for name, strength in (
        ("prior calibration", prior_calibration_strength),
        ("bias correction", bias_correction_strength),
    ):
        if not math.isfinite(strength) or not 0.0 <= strength <= 1.0:
            raise ValueError(f"{name} strength must be within [0, 1]")

    candidate = parent.clone()
    normalized = candidate._normalized(values)
    if targets.shape != (len(normalized),) or not len(normalized):
        raise ValueError("target shape is invalid")
    task = str(candidate.meta["task"])
    allowed = (
        {"cross_entropy", "balanced_cross_entropy"}
        if task == "classification"
        else {"mse", "huber", "asymmetric_huber"}
    )
    if objective not in allowed:
        raise ValueError("objective is incompatible with the task")

    if task == "classification":
        expected = targets.astype(np.int64, copy=False)
        class_count = len(candidate.meta["classes"])
        if np.any(expected < 0) or np.any(expected >= class_count):
            raise ValueError("classification target is unknown")
        sample_weights = np.ones(len(expected), dtype=np.float64)
        if objective == "balanced_cross_entropy":
            counts = np.bincount(expected, minlength=class_count).astype(np.float64)
            observed = counts > 0
            class_weights = np.zeros(class_count, dtype=np.float64)
            class_weights[observed] = len(expected) / (
                float(np.sum(observed)) * counts[observed]
            )
            sample_weights = class_weights[expected]
    else:
        expected = (
            targets.astype(np.float64, copy=False)
            - float(candidate.meta["target_mean"])
        ) / float(candidate.meta["target_scale"])
        if not np.all(np.isfinite(expected)):
            raise ValueError("regression target contains nonfinite values")
        sample_weights = np.ones(len(expected), dtype=np.float64)

    original_rate = float(candidate.meta["learning_rate"])
    candidate.meta["learning_rate"] = original_rate * learning_rate_multiplier
    if not 0 < candidate.meta["learning_rate"] <= 1.0:
        raise ValueError("temporary learning rate is outside checkpoint limits")
    for _ in range(epochs):
        rng = np.random.default_rng(
            np.random.SeedSequence([candidate.meta["seed"], candidate.meta["epochs"]])
        )
        order = rng.permutation(len(normalized))
        for start in range(0, len(order), candidate.meta["batch_size"]):
            indices = order[start : start + candidate.meta["batch_size"]]
            batch = normalized[indices]
            target = expected[indices]
            weights = sample_weights[indices]
            hidden = np.tanh(batch @ candidate.params["w1"] + candidate.params["b1"])
            logits = hidden @ candidate.params["w2"] + candidate.params["b2"]
            if task == "classification":
                logits -= logits.max(axis=1, keepdims=True)
                probabilities = np.exp(logits)
                probabilities /= probabilities.sum(axis=1, keepdims=True)
                delta = probabilities
                delta[np.arange(len(indices)), target] -= 1.0
                delta *= (weights / max(float(np.sum(weights)), 1e-12))[:, None]
            else:
                error = logits[:, 0] - target
                if objective == "mse":
                    derivative = 2.0 * error
                else:
                    derivative = 2.0 * np.clip(error, -huber_delta, huber_delta)
                    if objective == "asymmetric_huber":
                        derivative = derivative * np.where(
                            error > 0.0, overprediction_weight, 1.0
                        )
                delta = (derivative / len(indices))[:, None]
            gradients = {"w2": hidden.T @ delta, "b2": delta.sum(axis=0)}
            hidden_delta = (delta @ candidate.params["w2"].T) * (1.0 - hidden**2)
            gradients.update(w1=batch.T @ hidden_delta, b1=hidden_delta.sum(axis=0))
            norm = math.sqrt(
                sum(float(np.sum(gradient * gradient)) for gradient in gradients.values())
            )
            if not math.isfinite(norm):
                raise ValueError("nonfinite gradient")
            candidate.meta["steps"] += 1
            for name, gradient in gradients.items():
                gradient *= min(1.0, 5.0 / max(norm, 1e-12))
                candidate.first[name] = 0.9 * candidate.first[name] + 0.1 * gradient
                candidate.second[name] = (
                    0.999 * candidate.second[name] + 0.001 * gradient**2
                )
                first = candidate.first[name] / (
                    1.0 - 0.9 ** candidate.meta["steps"]
                )
                second = candidate.second[name] / (
                    1.0 - 0.999 ** candidate.meta["steps"]
                )
                candidate.params[name] -= (
                    candidate.meta["learning_rate"]
                    * first
                    / (np.sqrt(second) + 1e-8)
                )
        candidate.meta["epochs"] += 1

    candidate.meta["learning_rate"] = original_rate
    if task == "classification" and prior_calibration_strength > 0.0:
        probabilities = candidate.predict_raw(values)
        empirical = np.bincount(expected, minlength=len(candidate.meta["classes"]))
        empirical = (empirical + 1.0) / (len(expected) + len(empirical))
        predicted = np.maximum(np.mean(probabilities, axis=0), 1e-9)
        shift = np.log(empirical) - np.log(predicted)
        shift -= float(np.mean(shift))
        candidate.params["b2"] += prior_calibration_strength * shift
    if task == "regression" and bias_correction_strength > 0.0:
        predicted = candidate.predict_raw(values)
        residual = np.asarray(targets, dtype=np.float64) - predicted
        normalized_shift = float(np.median(residual)) / float(
            candidate.meta["target_scale"]
        )
        candidate.params["b2"][0] += bias_correction_strength * float(
            np.clip(normalized_shift, -1.0, 1.0)
        )
    candidate.validate()
    return candidate


def performance_method_names(task: str, portfolio: str = "a1") -> tuple[str, ...]:
    """Return the preregistered bounded method set for a task contract."""

    if portfolio == "bias_followup":
        if task == "classification":
            return ()
        if task == "regression":
            return (
                "soup_current_e3_alpha0.25",
                "soup_bias_down_0.1",
                "soup_bias_down_0.25",
            )
        raise ValueError("unsupported task")
    if portfolio != "a1":
        raise ValueError("unsupported performance portfolio")
    if task == "classification":
        return (
            "native_recent_e3",
            "balanced_current_e3",
            "balanced_recent_e3",
            "balanced_prior_recent_e3",
        )
    if task == "regression":
        return (
            "native_current_e3_lr3",
            "soup_current_e3_alpha0.25",
            "huber_current_e3_lr3",
            "huber_recent_e3",
            "asymmetric_current_e3_lr3",
            "asymmetric_soup_bias",
        )
    raise ValueError("unsupported task")


def fit_performance_method(
    parent: _NativeModel,
    *,
    method: str,
    history_x: np.ndarray,
    history_y: np.ndarray,
    current_x: np.ndarray,
    current_y: np.ndarray,
) -> _NativeModel:
    """Fit one preregistered low-cost method without changing checkpoint schema."""

    task = str(parent.meta["task"])
    allowed_methods = set(performance_method_names(task)) | set(
        performance_method_names(task, "bias_followup")
    )
    if method not in allowed_methods:
        raise ValueError("method is incompatible with the task contract")
    history_x = np.asarray(history_x, dtype=np.float64)
    history_y = np.asarray(history_y)
    current_x = np.asarray(current_x, dtype=np.float64)
    current_y = np.asarray(current_y)
    width = len(parent.meta["paths"])
    if history_x.shape != (len(history_y), width):
        raise ValueError("history arrays are invalid")
    if current_x.shape != (len(current_y), width) or not len(current_x):
        raise ValueError("current arrays are invalid")
    recent_count = min(len(history_x), 2 * len(current_x))
    recent_x = np.concatenate((history_x[-recent_count:], current_x), axis=0)
    recent_y = np.concatenate((history_y[-recent_count:], current_y), axis=0)

    if method == "native_recent_e3":
        return fit_native_recipe(
            parent,
            recipe="recent_e3",
            history_x=history_x,
            history_y=history_y,
            current_x=current_x,
            current_y=current_y,
        )
    if method == "balanced_current_e3":
        return fit_native_objective(
            parent,
            values=current_x,
            targets=current_y,
            epochs=3,
            objective="balanced_cross_entropy",
        )
    if method in {"balanced_recent_e3", "balanced_prior_recent_e3"}:
        return fit_native_objective(
            parent,
            values=recent_x,
            targets=recent_y,
            epochs=3,
            objective="balanced_cross_entropy",
            prior_calibration_strength=(
                0.25 if method == "balanced_prior_recent_e3" else 0.0
            ),
        )
    if method in {"native_current_e3_lr3", "soup_current_e3_alpha0.25"}:
        recipe = (
            "current_e3_lr3"
            if method == "native_current_e3_lr3"
            else "soup_current_e3_alpha0.25"
        )
        return fit_native_recipe(
            parent,
            recipe=recipe,
            history_x=history_x,
            history_y=history_y,
            current_x=current_x,
            current_y=current_y,
        )
    if method == "huber_current_e3_lr3":
        return fit_native_objective(
            parent,
            values=current_x,
            targets=current_y,
            epochs=3,
            objective="huber",
            learning_rate_multiplier=3.0,
        )
    if method == "huber_recent_e3":
        return fit_native_objective(
            parent,
            values=recent_x,
            targets=recent_y,
            epochs=3,
            objective="huber",
        )
    if method == "asymmetric_current_e3_lr3":
        return fit_native_objective(
            parent,
            values=current_x,
            targets=current_y,
            epochs=3,
            objective="asymmetric_huber",
            learning_rate_multiplier=3.0,
            overprediction_weight=1.5,
        )
    if method == "asymmetric_soup_bias":
        candidate = fit_native_objective(
            parent,
            values=current_x,
            targets=current_y,
            epochs=3,
            objective="asymmetric_huber",
            overprediction_weight=1.5,
            bias_correction_strength=0.25,
        )
        for name in candidate.params:
            candidate.params[name] = (
                0.75 * parent.params[name] + 0.25 * candidate.params[name]
            )
        candidate.validate()
        return candidate
    if method in {"soup_bias_down_0.1", "soup_bias_down_0.25"}:
        strength = 0.1 if method.endswith("0.1") else 0.25
        candidate = fit_native_recipe(
            parent,
            recipe="soup_current_e3_alpha0.25",
            history_x=history_x,
            history_y=history_y,
            current_x=current_x,
            current_y=current_y,
        )
        error = candidate.predict_raw(current_x) - current_y.astype(
            np.float64, copy=False
        )
        overprediction = max(0.0, float(np.median(error)))
        normalized_shift = min(
            1.0, overprediction / float(candidate.meta["target_scale"])
        )
        candidate.params["b2"][0] -= strength * normalized_shift
        candidate.first["b2"].fill(0.0)
        candidate.second["b2"].fill(0.0)
        candidate.validate()
        return candidate
    raise AssertionError("unreachable performance method")


def summarize_transitions(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("available"):
            grouped.setdefault(str(row["method"]), []).append(row)
    result: dict[str, dict[str, float]] = {}
    for method, method_rows in grouped.items():
        gains = np.asarray([float(row["signed_gain"]) for row in method_rows])
        cpu = np.asarray([float(row["cpu_seconds"]) for row in method_rows])
        result[method] = {
            "transitions": float(len(method_rows)),
            "mean_signed_gain": float(np.mean(gains)),
            "median_signed_gain": float(np.median(gains)),
            "worst_signed_gain": float(np.min(gains)),
            "win_rate": float(np.mean(gains > 0.0)),
            "cpu_seconds": float(np.sum(cpu)),
        }
    return result
