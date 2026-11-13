from __future__ import annotations

import numpy as np
import pytest

from brace_msi.restricted_plugin import (
    PluginSandboxError,
    RestrictedPluginSandbox,
)


def test_valid_feature_transform_runs_in_child_and_records_diff() -> None:
    source = """
def transform_features(X):
    return np.clip(X, -1.0, 1.0)
"""
    X = np.asarray([[-2.0, 0.0], [0.5, 3.0]], dtype=np.float64)
    result = RestrictedPluginSandbox(timeout_seconds=2.0).execute(
        "feature_transform", source, X=X
    )

    assert result.output.shape == X.shape
    assert np.allclose(result.output, np.clip(X, -1.0, 1.0))
    assert result.changed_fraction > 0
    assert len(result.patch_sha256) == 64
    assert result.deterministic


@pytest.mark.parametrize(
    "source",
    [
        "def transform_features(X):\n    import os\n    return X\n",
        "def transform_features(X):\n    return open('secret.txt').read()\n",
        "def transform_features(X):\n    return __import__('socket').socket()\n",
        "def transform_features(X):\n    return X.__class__\n",
        "def transform_features(X):\n    return eval('X')\n",
        "def transform_features(X):\n    return getattr(X, 'shape')\n",
    ],
)
def test_file_network_reflection_and_dynamic_execution_fail_static_gate(source: str) -> None:
    with pytest.raises(PluginSandboxError):
        RestrictedPluginSandbox().execute(
            "feature_transform", source, X=np.ones((2, 2), dtype=np.float64)
        )


def test_infinite_loop_and_obvious_oom_allocation_fail_closed() -> None:
    infinite = "def transform_features(X):\n    while True:\n        pass\n    return X\n"
    oom = "def transform_features(X):\n    return np.ones((1000000000, 1000000000))\n"
    sandbox = RestrictedPluginSandbox()

    with pytest.raises(PluginSandboxError, match="forbidden_syntax"):
        sandbox.execute("feature_transform", infinite, X=np.ones((2, 2)))
    with pytest.raises(PluginSandboxError, match="unsafe_numpy_call"):
        sandbox.execute("feature_transform", oom, X=np.ones((2, 2)))


def test_hard_timeout_fails_closed_even_for_valid_source() -> None:
    source = "def transform_features(X):\n    return np.clip(X, 0.0, 1.0)\n"
    sandbox = RestrictedPluginSandbox(timeout_seconds=1e-9)
    with pytest.raises(PluginSandboxError, match="execution_timeout"):
        sandbox.execute("feature_transform", source, X=np.ones((2, 2)))


@pytest.mark.parametrize(
    "slot, source, kwargs, error",
    [
        (
            "feature_transform",
            "def transform_features(X):\n    return np.column_stack((X, X, X, X, X))\n",
            {"X": np.ones((3, 2))},
            "output_shape_invalid",
        ),
        (
            "sample_weights",
            "def sample_weights(X, y):\n    return np.where(y >= 0, -1.0, -1.0)\n",
            {"X": np.ones((3, 2)), "y": np.asarray([0, 1, 0])},
            "weights_invalid",
        ),
        (
            "prediction_postprocess",
            "def postprocess_predictions(predictions):\n    return predictions / 0.0\n",
            {"predictions": np.asarray([1.0, 2.0])},
            "non_finite_output",
        ),
    ],
)
def test_output_contracts_fail_closed(
    slot: str, source: str, kwargs: dict[str, np.ndarray], error: str
) -> None:
    with pytest.raises(PluginSandboxError, match=error):
        RestrictedPluginSandbox(timeout_seconds=2.0).execute(slot, source, **kwargs)


def test_runtime_determinism_check_rejects_mismatched_repeated_outputs() -> None:
    class UnstableSandbox(RestrictedPluginSandbox):
        calls = 0

        def _run_once(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls += 1
            return np.asarray([float(self.calls)])

    source = "def postprocess_predictions(predictions):\n    return predictions\n"
    with pytest.raises(PluginSandboxError, match="nondeterministic_output"):
        UnstableSandbox().execute(
            "prediction_postprocess", source, predictions=np.asarray([1.0])
        )
