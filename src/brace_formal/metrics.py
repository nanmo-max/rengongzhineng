"""Official task metrics used only for bounded candidate safety checks."""

from __future__ import annotations

import numpy as np

from .model import FormalModel


def evaluate(model: FormalModel, values: np.ndarray, targets: np.ndarray) -> dict[str, float]:
    raw = model.predict_raw(values)
    if model.meta["task"] == "classification":
        labels = raw.argmax(axis=1)
        observed = sorted(set(targets.tolist()) | set(labels.tolist()))
        scores: list[float] = []
        for label in observed:
            denominator = int(np.sum(labels == label) + np.sum(targets == label))
            numerator = 2 * int(np.sum((labels == label) & (targets == label)))
            scores.append(numerator / denominator if denominator else 0.0)
        return {"accuracy": float(np.mean(labels == targets)), "macro_f1": float(np.mean(scores))}
    error = raw - targets
    return {"mae": float(np.mean(np.abs(error))), "rmse": float(np.sqrt(np.mean(error**2)))}
