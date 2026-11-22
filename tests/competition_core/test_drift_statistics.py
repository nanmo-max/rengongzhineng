from __future__ import annotations

import numpy as np


def _correlated_windows(*, shifted: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20261122)
    covariance = np.full((4, 4), 0.55, dtype=np.float64)
    np.fill_diagonal(covariance, 1.0)
    reference = rng.multivariate_normal(np.zeros(4), covariance, size=60)
    current = rng.multivariate_normal(np.zeros(4), covariance, size=60)
    if shifted:
        current[:, 0] += 3.5
    blocks = np.repeat(np.arange(30), 4)
    return reference, current, blocks


def test_by_adjustment_matches_known_three_hypothesis_example() -> None:
    from brace_formal.drift import adjust_pvalues_by

    adjusted = adjust_pvalues_by(np.asarray([0.01, 0.04, 0.03]))

    assert np.allclose(adjusted, [0.055, 0.07333333333333333, 0.07333333333333333])
    assert np.all(adjusted >= np.asarray([0.01, 0.04, 0.03]))


def test_effect_gate_requires_statistical_and_practical_significance() -> None:
    from brace_formal.drift import apply_effect_gate

    selected = apply_effect_gate(
        adjusted_p=np.asarray([0.01, 0.01, 0.20]),
        omnibus_score=np.asarray([1.9, 2.1, 9.0]),
        alpha=0.05,
        effect_threshold=2.0,
    )

    assert selected.tolist() == [False, True, False]


def test_synchronized_block_max_t_detects_shift_and_preserves_feature_dependence() -> None:
    from brace_formal.drift import DriftMonitor, DriftStatus, MonitorConfig

    reference, current, blocks = _correlated_windows(shifted=True)
    monitor = DriftMonitor(
        MonitorConfig(
            calibration_method="block_permutation_maxT",
            permutations=199,
            effect_threshold=2.0,
            random_seed=7,
        )
    )

    report = monitor.compare(
        reference,
        current,
        alpha_run=0.20,
        alpha_window=0.10,
        alpha_spent=0.10,
        reference_epoch=1,
        history_window_count=3,
        block_ids=blocks,
    )

    assert report.status is DriftStatus.WARNING
    assert report.calibration_method == "block_permutation_maxT"
    assert report.minimum_empirical_p == 1.0 / 200.0
    assert report.features[0].selected is True
    assert report.features[0].adjusted_p <= 0.10
    assert report.features[0].dominant_statistic in {
        "location_shift",
        "wasserstein_shift",
        "ks_distance",
    }
    assert np.isclose(sum(item.contribution for item in report.features), 1.0)


def test_by_fallback_uses_omnibus_p_values_without_independence_claim() -> None:
    from brace_formal.drift import DriftMonitor, DriftStatus, MonitorConfig

    reference, current, blocks = _correlated_windows(shifted=True)
    report = DriftMonitor(
        MonitorConfig(
            calibration_method="by_fallback",
            permutations=199,
            effect_threshold=2.0,
            random_seed=7,
        )
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

    assert report.status is DriftStatus.WARNING
    assert report.features[0].selected is True
    assert report.features[0].adjusted_p >= report.features[0].empirical_p


def test_insufficient_permutation_resolution_cannot_be_reported_as_stable() -> None:
    from brace_formal.drift import DriftMonitor, DriftStatus, MonitorConfig

    reference, current, blocks = _correlated_windows(shifted=False)
    report = DriftMonitor(
        MonitorConfig(permutations=19, effect_threshold=2.0, random_seed=1)
    ).compare(
        reference,
        current,
        alpha_run=0.05,
        alpha_window=0.05,
        alpha_spent=0.05,
        reference_epoch=1,
        history_window_count=3,
        block_ids=blocks,
    )

    assert report.status is DriftStatus.INSUFFICIENT_CALIBRATION
    assert report.features == ()
    assert "empirical_p_resolution_exceeds_alpha_budget" in report.limitations


def test_blocks_crossing_window_boundary_fail_closed() -> None:
    from brace_formal.drift import DriftMonitor, DriftStatus, MonitorConfig

    reference, current, _ = _correlated_windows(shifted=False)
    crossing = np.tile(np.arange(15), 8)
    report = DriftMonitor(
        MonitorConfig(permutations=199, random_seed=2)
    ).compare(
        reference,
        current,
        alpha_run=0.20,
        alpha_window=0.10,
        alpha_spent=0.10,
        reference_epoch=1,
        history_window_count=3,
        block_ids=crossing,
    )

    assert report.status is DriftStatus.INSUFFICIENT_CALIBRATION
    assert "blocks_cross_window_boundary" in report.limitations


def test_unequal_but_complete_blocks_are_permuted_as_whole_units() -> None:
    from brace_formal.drift import DriftMonitor, DriftStatus, MonitorConfig

    rng = np.random.default_rng(118)
    reference = rng.normal(size=(12, 2))
    current = rng.normal(size=(12, 2))
    block_ids = np.asarray(
        ["r1"] * 3
        + ["r2"] * 5
        + ["r3"] * 4
        + ["c1"] * 2
        + ["c2"] * 6
        + ["c3"] * 4
    )

    report = DriftMonitor(
        MonitorConfig(permutations=99, random_seed=5)
    ).compare(
        reference,
        current,
        alpha_run=0.20,
        alpha_window=0.10,
        alpha_spent=0.10,
        reference_epoch=1,
        history_window_count=3,
        block_ids=block_ids,
    )

    assert report.status in {DriftStatus.STABLE, DriftStatus.WARNING}
    assert "blocks_must_be_equal_sized" not in report.limitations
