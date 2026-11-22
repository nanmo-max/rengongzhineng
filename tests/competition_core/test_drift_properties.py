from __future__ import annotations

import numpy as np
import pytest


def _case() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(81)
    reference = rng.normal(size=(48, 3))
    current = rng.normal(size=(48, 3))
    current[:, 1] += 2.75
    blocks = np.repeat(np.arange(24), 4)
    return reference, current, blocks


def _report(reference: np.ndarray, current: np.ndarray, blocks: np.ndarray):
    from brace_formal.drift import DriftMonitor, MonitorConfig

    return DriftMonitor(
        MonitorConfig(permutations=99, effect_threshold=1.5, random_seed=14)
    ).compare(
        reference,
        current,
        alpha_run=0.20,
        alpha_window=0.10,
        alpha_spent=0.10,
        reference_epoch=1,
        history_window_count=3,
        block_ids=blocks,
    )


def test_positive_affine_feature_transform_preserves_calibrated_decision() -> None:
    reference, current, blocks = _case()
    original = _report(reference, current, blocks)
    scale = np.asarray([3.0, 0.5, 7.0])
    offset = np.asarray([20.0, -4.0, 100.0])
    transformed = _report(reference * scale + offset, current * scale + offset, blocks)

    assert [item.selected for item in transformed.features] == [
        item.selected for item in original.features
    ]
    assert np.allclose(
        [item.adjusted_p for item in transformed.features],
        [item.adjusted_p for item in original.features],
    )


def test_feature_permutation_is_equivariant() -> None:
    reference, current, blocks = _case()
    original = _report(reference, current, blocks)
    order = np.asarray([2, 0, 1])
    permuted = _report(reference[:, order], current[:, order], blocks)

    original_selected = np.asarray([item.selected for item in original.features])
    original_adjusted = np.asarray([item.adjusted_p for item in original.features])
    assert np.asarray([item.selected for item in permuted.features]).tolist() == original_selected[
        order
    ].tolist()
    assert np.allclose(
        [item.adjusted_p for item in permuted.features],
        original_adjusted[order],
    )


@pytest.mark.parametrize("bad_shape", [(10,), (2, 3, 4)])
def test_monitor_rejects_non_matrix_inputs(bad_shape: tuple[int, ...]) -> None:
    from brace_formal.drift import DriftMonitor

    reference = np.zeros(bad_shape)
    current = np.zeros((10, 2))
    with pytest.raises(ValueError, match="two-dimensional"):
        DriftMonitor().compare(
            reference,
            current,
            alpha_run=0.05,
            alpha_window=0.005,
            alpha_spent=0.005,
            reference_epoch=1,
            history_window_count=3,
            block_ids=None,
        )


def test_by_adjustment_is_order_equivariant_and_bounded() -> None:
    from brace_formal.drift import adjust_pvalues_by

    rng = np.random.default_rng(99)
    values = rng.uniform(0.0, 1.0, size=40)
    order = rng.permutation(len(values))
    original = adjust_pvalues_by(values)
    permuted = adjust_pvalues_by(values[order])

    assert np.all((0.0 <= original) & (original <= 1.0))
    assert np.allclose(permuted, original[order])
