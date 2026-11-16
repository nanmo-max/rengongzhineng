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
