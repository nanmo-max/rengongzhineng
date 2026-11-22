from __future__ import annotations

import numpy as np


def _monitor_case(*, dimensions: int = 4, shifted: bool = False):
    rng = np.random.default_rng(622001)
    reference = rng.normal(size=(80, dimensions))
    current = rng.normal(size=(80, dimensions))
    if shifted:
        current[:, 0] += 3.0
    blocks = np.repeat(np.arange(40), 4)
    return reference, current, blocks


def _compare(reference, current, blocks, **kwargs):
    from brace_formal.drift import DriftMonitor, MonitorConfig

    return DriftMonitor(
        MonitorConfig(permutations=199, effect_threshold=2.0, random_seed=622002)
    ).compare(
        reference,
        current,
        alpha_run=0.20,
        alpha_window=0.10,
        alpha_spent=0.10,
        reference_epoch=1,
        history_window_count=3,
        block_ids=blocks,
        **kwargs,
    )


def test_no_drift_and_insufficient_evidence_never_enter_reference_pool() -> None:
    from brace_formal.drift_state import (
        DriftState,
        Observation,
        ReferenceStateMachine,
        ReferenceStatus,
        StateMachineConfig,
    )

    machine = ReferenceStateMachine(StateMachineConfig(calibration_min_windows=2))
    state = DriftState.initial(alpha_run=0.05)
    state = machine.observe(state, "not-detected", Observation.NO_DRIFT_DETECTED)
    state = machine.observe(state, "underpowered", Observation.INSUFFICIENT_EVIDENCE)

    assert state.status is ReferenceStatus.CALIBRATING
    assert state.active_reference_ids == ()
    assert state.candidate_reference_ids == ()
    assert state.non_admissible_window_ids == ("not-detected", "underpowered")

    state = machine.observe(state, "stable-1", Observation.STABLE)
    state = machine.observe(state, "stable-2", Observation.STABLE)
    assert state.status is ReferenceStatus.STABLE
    assert state.active_reference_ids == ("stable-1", "stable-2")


def test_warning_does_not_recover_on_merely_non_detected_window() -> None:
    from brace_formal.drift_state import (
        DriftState,
        Observation,
        ReferenceStateMachine,
        ReferenceStatus,
        StateMachineConfig,
    )

    machine = ReferenceStateMachine(StateMachineConfig(calibration_min_windows=1))
    state = DriftState.initial(alpha_run=0.05)
    state = machine.observe(state, "stable", Observation.STABLE)
    state = machine.observe(state, "warning", Observation.WARNING)
    state = machine.observe(state, "not-detected", Observation.NO_DRIFT_DETECTED)

    assert state.status is ReferenceStatus.WARNING
    assert "not-detected" not in state.active_reference_ids


def test_outlier_transient_recovery_and_persistent_rebase_remain_auditable() -> None:
    from brace_formal.drift_state import (
        DriftState,
        Observation,
        ReferenceStateMachine,
        ReferenceStatus,
        StateMachineConfig,
    )

    machine = ReferenceStateMachine(
        StateMachineConfig(
            calibration_min_windows=1,
            confirmation_windows=2,
            recovery_windows=2,
            rebase_min_windows=2,
        )
    )
    state = machine.observe(DriftState.initial(alpha_run=0.05), "cal", Observation.STABLE)
    state = machine.observe(
        state, "outlier", Observation.NO_DRIFT_DETECTED, data_quality_ok=False
    )
    assert state.rejected_window_ids == ("outlier",)
    state = machine.observe(state, "transient", Observation.WARNING)
    state = machine.observe(state, "recovery-1", Observation.STABLE)
    state = machine.observe(state, "recovery-2", Observation.STABLE)
    assert state.status is ReferenceStatus.STABLE
    assert not {"outlier", "transient", "recovery-1", "recovery-2"}.intersection(
        state.active_reference_ids
    )

    state = machine.observe(state, "persistent-1", Observation.WARNING)
    state = machine.observe(state, "persistent-2", Observation.WARNING)
    state = machine.observe(
        state, "new-base-1", Observation.CONFIRMED, candidate_stable=True
    )
    state = machine.observe(
        state, "new-base-2", Observation.CONFIRMED, candidate_stable=True
    )
    assert state.status is ReferenceStatus.STABLE_NEW_BASELINE
    assert state.active_reference_ids == ("new-base-1", "new-base-2")


def test_sparse_outlier_quality_receipt_blocks_reference_admission() -> None:
    from brace_formal.drift import assess_window_quality

    rng = np.random.default_rng(622005)
    reference = rng.normal(size=(80, 4))
    current = rng.normal(size=(80, 4))
    current[0, 0] = 20.0

    receipt = assess_window_quality(reference, current)

    assert receipt.acceptable_for_reference is False
    assert receipt.maximum_feature_outlier_fraction > 0.01
    assert receipt.limitation == "sparse_extreme_contamination"


def test_feature_receipt_preserves_each_statistic_contribution() -> None:
    reference, current, blocks = _monitor_case(shifted=True)
    report = _compare(reference, current, blocks)

    receipt = report.features[0].statistic_contributions
    assert {item.name for item in receipt} == {
        "missing_delta",
        "location_shift",
        "scale_shift",
        "wasserstein_shift",
        "ks_distance",
    }
    assert all(0.0 <= item.empirical_p <= 1.0 for item in receipt)
    assert all(item.raw_value >= 0.0 for item in receipt)
    assert np.isclose(sum(item.contribution for item in receipt), 1.0)
    assert report.features[0].dominant_statistic == max(
        receipt, key=lambda item: item.standardized_score
    ).name


def test_group_identity_detects_composition_change_and_time_hints_are_audited() -> None:
    rng = np.random.default_rng(622003)
    reference = rng.normal(size=(80, 4))
    current = rng.normal(size=(80, 4))
    blocks = np.repeat(np.arange(40), 4)
    reference_groups = np.asarray(["a"] * 72 + ["b"] * 8)
    current_groups = np.asarray(["a"] * 8 + ["b"] * 72)
    reference_time = np.arange(80, dtype=np.float64)
    current_time = np.arange(80, 160, dtype=np.float64)

    report = _compare(
        reference,
        current,
        blocks,
        reference_group_ids=reference_groups,
        current_group_ids=current_groups,
        reference_time_hints=reference_time,
        current_time_hints=current_time,
    )

    assert report.group_evidence.available is True
    assert report.group_evidence.selected is True
    assert report.group_evidence.total_variation > 0.5
    assert report.time_evidence.available is True
    assert report.time_evidence.monotonic is True


def test_missing_group_and_time_hints_degrade_explicitly_without_row_surrogates() -> None:
    reference, current, blocks = _monitor_case(shifted=False)
    report = _compare(reference, current, blocks)

    assert report.group_evidence.available is False
    assert report.time_evidence.available is False
    assert "group_identity_unavailable" in report.limitations
    assert "time_hints_unavailable" in report.limitations


def test_by_reports_insufficient_when_empirical_resolution_cannot_cross_rank_one() -> None:
    from brace_formal.drift import DriftMonitor, DriftStatus, MonitorConfig

    reference, current, blocks = _monitor_case(dimensions=24, shifted=True)
    report = DriftMonitor(
        MonitorConfig(
            calibration_method="by_fallback",
            permutations=2047,
            effect_threshold=2.0,
            random_seed=622004,
        )
    ).compare(
        reference,
        current,
        alpha_run=0.05,
        alpha_window=0.005,
        alpha_spent=0.005,
        reference_epoch=1,
        history_window_count=3,
        block_ids=blocks,
    )

    assert report.status is DriftStatus.INSUFFICIENT_CALIBRATION
    assert "by_rank_one_empirical_p_resolution_insufficient" in report.limitations


def test_scale_receipt_uses_mad_when_iqr_is_unchanged() -> None:
    from brace_formal.drift import _feature_statistics

    reference = np.asarray([[-5.0], [-3.0], [-3.0], [-2.0], [0.0], [1.0], [3.0], [4.0]])
    current = np.asarray([[-3.0], [-2.0], [0.0], [2.0], [4.0], [4.0], [4.0], [4.0]])
    stats = _feature_statistics(reference, current, numeric_floor=1e-12)

    reference_iqr = np.diff(np.quantile(reference[:, 0], [0.25, 0.75]))[0]
    current_iqr = np.diff(np.quantile(current[:, 0], [0.25, 0.75]))[0]
    assert np.isclose(reference_iqr, current_iqr)
    assert stats[0, 2] > 0.0
