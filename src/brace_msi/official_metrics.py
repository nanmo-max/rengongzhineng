"""Metrics named by the latest competition platform screenshots."""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error

MetricName = Literal["macro_f1", "rmse", "rmse_nasa"]


def nasa_asymmetric_score(targets: ArrayLike, predictions: ArrayLike) -> float:
    """Return the standard C-MAPSS asymmetric error sum (lower is better)."""

    target_array = np.asarray(targets, dtype=np.float64)
    prediction_array = np.asarray(predictions, dtype=np.float64)
    if target_array.shape != prediction_array.shape or target_array.ndim != 1:
        raise ValueError("NASA score requires aligned one-dimensional arrays")
    errors = np.clip(prediction_array - target_array, -700.0, 700.0)
    penalties = np.where(
        errors < 0.0,
        np.exp(-errors / 13.0) - 1.0,
        np.exp(errors / 10.0) - 1.0,
    )
    return float(np.sum(penalties))


def metric_bundle(
    metric_name: MetricName, targets: ArrayLike, predictions: ArrayLike
) -> dict[str, float]:
    y = np.asarray(targets)
    predicted = np.asarray(predictions)
    if y.shape != predicted.shape or y.ndim != 1:
        raise ValueError("metrics require aligned one-dimensional arrays")
    if metric_name == "macro_f1":
        return {
            "macro_f1": float(f1_score(y, predicted, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(y, predicted)),
        }
    rmse = float(mean_squared_error(y, predicted) ** 0.5)
    mae = float(mean_absolute_error(y, predicted))
    if metric_name == "rmse":
        return {"rmse": rmse, "mae": mae}
    if metric_name == "rmse_nasa":
        score = nasa_asymmetric_score(y, predicted)
        return {
            "rmse": rmse,
            "mae": mae,
            "nasa_score": score,
            "nasa_score_mean": score / max(1, len(y)),
        }
    raise ValueError(f"unsupported official metric: {metric_name}")


def primary_value(metric_name: MetricName, metrics: dict[str, float]) -> float:
    return metrics["macro_f1"] if metric_name == "macro_f1" else metrics["rmse"]


def higher_is_better(metric_name: MetricName) -> bool:
    return metric_name == "macro_f1"

