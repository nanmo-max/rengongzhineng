from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib

import pytest


def test_p5_schema_modules_exist() -> None:
    for module_name in (
        "brace_formal.drift",
        "brace_formal.diagnosis",
        "brace_formal.drift_state",
    ):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            pytest.fail(f"missing approved P5 schema module: {exc}")
        assert module is not None


def test_drift_report_is_immutable_and_serializable() -> None:
    from brace_formal.drift import DriftReport, DriftStatus, FeatureDrift

    feature = FeatureDrift(
        feature_index=0,
        dominant_statistic="location_shift",
        location_shift=1.5,
        scale_shift=0.1,
        wasserstein_shift=1.2,
        ks_distance=0.4,
        missing_delta=0.0,
        omnibus_score=3.0,
        empirical_p=0.01,
        adjusted_p=0.02,
        selected=True,
        contribution=1.0,
    )
    report = DriftReport(
        report_id="sha256:" + "a" * 64,
        status=DriftStatus.WARNING,
        calibration_method="block_permutation_maxT",
        reference_scope_sha256="a" * 64,
        current_scope_sha256="b" * 64,
        sample_count=32,
        history_window_count=3,
        global_score=3.0,
        alpha_run=0.05,
        alpha_window=0.005,
        alpha_spent=0.005,
        permutation_count=2047,
        minimum_empirical_p=1.0 / 2048.0,
        reference_epoch=1,
        features=(feature,),
        limitations=(),
    )

    assert report.as_dict()["format"] == "brace-formal.drift-report.v1"
    assert report.as_dict()["features"][0]["selected"] is True
    with pytest.raises(FrozenInstanceError):
        report.status = DriftStatus.STABLE  # type: ignore[misc]


def test_diagnosis_report_interface_is_immutable() -> None:
    from brace_formal.diagnosis import DiagnosisFact, DiagnosisReport

    fact = DiagnosisFact(
        fact_id="drift.feature.0.location",
        kind="location_shift",
        effect=1.5,
        contribution=1.0,
        confidence="calibrated",
    )
    report = DiagnosisReport(
        diagnosis_id="sha256:" + "c" * 64,
        drift_status="warning",
        facts=(fact,),
        hypotheses=(),
        performance_impact="unknown",
        experiment_needs=(),
        unknowns=("labels_unavailable",),
        prohibited_claims=("physical_failure_not_established",),
    )

    payload = report.as_dict()
    assert payload["format"] == "brace-formal.diagnosis-report.v1"
    assert payload["facts"][0]["fact_id"] == fact.fact_id
    with pytest.raises(FrozenInstanceError):
        report.performance_impact = "observed"  # type: ignore[misc]


def test_drift_state_interface_starts_in_calibration() -> None:
    from brace_formal.drift_state import DriftState, ReferenceStatus

    state = DriftState.initial(alpha_run=0.05)

    assert state.status is ReferenceStatus.CALIBRATING
    assert state.reference_epoch == 0
    assert state.alpha_spent == 0.0
    assert state.active_reference_ids == ()
    assert state.as_dict()["format"] == "brace-formal.drift-state.v1"
