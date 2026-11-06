"""Performance and covariate-drift evidence computed from visible batches."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.stats import ks_2samp


@dataclass(frozen=True)
class Evidence:
    current_metric: float
    reference_metric: float
    performance_drop: float
    drift_score: float
    sample_count: int


def build_evidence(
    reference_X: ArrayLike,
    current_X: ArrayLike,
    *,
    current_metric: float,
    reference_metric: float,
    higher_is_better: bool,
) -> Evidence:
    reference = np.asarray(reference_X, dtype=np.float64)
    current = np.asarray(current_X, dtype=np.float64)
    if reference.ndim != 2 or current.ndim != 2:
        raise ValueError("drift evidence requires two 2D matrices")
    if reference.shape[1] != current.shape[1]:
        raise ValueError("reference and current feature counts must match")
    statistics = [
        ks_2samp(reference[:, index], current[:, index]).statistic
        for index in range(reference.shape[1])
    ]
    performance_drop = (
        reference_metric - current_metric
        if higher_is_better
        else current_metric - reference_metric
    )
    return Evidence(
        current_metric=float(current_metric),
        reference_metric=float(reference_metric),
        performance_drop=float(performance_drop),
        drift_score=float(np.mean(statistics)),
        sample_count=len(current),
    )
