from __future__ import annotations

import pickle
import warnings

import numpy as np
import pytest

from brace_msi.modeling import CpuModelAdapter
from sklearn.exceptions import ConvergenceWarning


@pytest.mark.parametrize(
    "task_kind,n_features,n_outputs,expected",
    [
        ("classification", 128, 6, 4326),
        ("regression", 25, 1, 865),
        ("regression", 24, 1, 833),
    ],
)
def test_mlp_parameter_counts_match_platform_summary(
    task_kind: str, n_features: int, n_outputs: int, expected: int
) -> None:
    rng = np.random.default_rng(4)
    X = rng.normal(size=(72, n_features))
    y = (
        np.tile(np.arange(1, n_outputs + 1), 12)
        if task_kind == "classification"
        else rng.normal(size=72)
    )

    model = CpuModelAdapter(
        task_kind=task_kind,
        family="mlp",
        seed=20261111,
        params={"max_iter": 8},
    ).fit(X, y)

    assert model.parameter_count == expected
    assert model.capabilities.supports_partial_fit is True


def test_mlp_checkpoint_round_trip_preserves_predictions() -> None:
    rng = np.random.default_rng(5)
    X = rng.normal(size=(64, 24))
    y = X[:, 0] * 2.0 - X[:, 1]
    model = CpuModelAdapter(
        task_kind="regression",
        family="mlp",
        seed=8,
        params={"max_iter": 12},
    ).fit(X, y)

    restored = pickle.loads(pickle.dumps(model))

    assert np.allclose(restored.predict(X[:8]), model.predict(X[:8]))
    assert restored.parameter_count == 833


def test_mlp_fit_does_not_pollute_unattended_logs_with_expected_warnings() -> None:
    rng = np.random.default_rng(6)
    X = rng.normal(size=(12, 24))
    y = rng.normal(size=12)

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        CpuModelAdapter(
            task_kind="regression",
            family="mlp",
            seed=9,
            params={"max_iter": 2},
        ).fit(X, y)

    assert not any(isinstance(item.message, ConvergenceWarning) for item in recorded)
    assert not any("batch_size" in str(item.message) for item in recorded)

