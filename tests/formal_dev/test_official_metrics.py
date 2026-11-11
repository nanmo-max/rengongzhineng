from __future__ import annotations

import math

import numpy as np
import pytest

from brace_msi.official_metrics import metric_bundle, nasa_asymmetric_score, primary_value


def test_gas_metric_bundle_uses_macro_f1_as_primary() -> None:
    targets = np.asarray([1, 1, 2, 2, 3, 3])
    predictions = np.asarray([1, 1, 2, 1, 3, 2])

    metrics = metric_bundle("macro_f1", targets, predictions)

    assert set(metrics) == {"macro_f1", "accuracy"}
    assert primary_value("macro_f1", metrics) == metrics["macro_f1"]
    assert metrics["macro_f1"] != metrics["accuracy"]


def test_nasa_asymmetric_score_penalizes_late_predictions_more() -> None:
    targets = np.asarray([100.0])

    early = nasa_asymmetric_score(targets, np.asarray([90.0]))
    late = nasa_asymmetric_score(targets, np.asarray([110.0]))

    assert late > early > 0.0
    assert late == pytest.approx(math.exp(1.0) - 1.0)


def test_engine_metric_bundle_includes_nasa_score() -> None:
    metrics = metric_bundle(
        "rmse_nasa",
        np.asarray([10.0, 20.0]),
        np.asarray([12.0, 17.0]),
    )

    assert set(metrics) == {"rmse", "mae", "nasa_score", "nasa_score_mean"}
    assert all(math.isfinite(value) for value in metrics.values())

