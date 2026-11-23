from __future__ import annotations

from brace_formal.drift import DriftReport, DriftStatus, FeatureDrift
import numpy as np


def _report(*, status: DriftStatus = DriftStatus.WARNING) -> DriftReport:
    feature = FeatureDrift(
        feature_index=3,
        dominant_statistic="scale_shift",
        location_shift=0.2,
        scale_shift=1.4,
        wasserstein_shift=0.5,
        ks_distance=0.2,
        missing_delta=0.0,
        omnibus_score=4.2,
        empirical_p=0.001,
        adjusted_p=0.004,
        selected=True,
        contribution=0.75,
    )
    return DriftReport(
        report_id="sha256:" + "a" * 64,
        status=status,
        calibration_method="block_permutation_maxT",
        reference_scope_sha256="b" * 64,
        current_scope_sha256="c" * 64,
        sample_count=48,
        history_window_count=3,
        global_score=4.2,
        alpha_run=0.05,
        alpha_window=0.005,
        alpha_spent=0.015,
        permutation_count=2047,
        minimum_empirical_p=1.0 / 2048.0,
        reference_epoch=1,
        features=(feature,),
        limitations=("group_identity_unavailable",),
    )


def test_diagnosis_separates_fact_hypothesis_unknown_and_experiment_need() -> None:
    from brace_formal.diagnosis import diagnose_drift

    diagnosis = diagnose_drift(_report())

    assert diagnosis.drift_status == "warning"
    assert diagnosis.facts[0].fact_id == "drift.feature.3.scale_shift"
    assert diagnosis.facts[0].feature_index == 3
    assert diagnosis.facts[0].scope_sha256 == "c" * 64
    assert diagnosis.hypotheses[0].kind == "scale_or_noise_shift"
    assert diagnosis.hypotheses[0].supports == (diagnosis.facts[0].fact_id,)
    assert diagnosis.experiment_needs[0].supported_by == (
        diagnosis.hypotheses[0].hypothesis_id,
    )
    assert diagnosis.performance_impact.as_dict()["status"] == "unknown"
    assert "performance_scope_not_supplied" in diagnosis.unknowns
    assert "physical_failure_not_established" in diagnosis.prohibited_claims


def test_noncomparable_performance_evidence_never_becomes_observed_impact() -> None:
    from brace_formal.diagnosis import diagnose_drift

    diagnosis = diagnose_drift(
        _report(),
        performance_evidence={
            "scope_comparable": False,
            "relation": "regressed",
            "metric": "rmse",
            "signed_gain": -12.0,
        },
    )

    impact = diagnosis.performance_impact.as_dict()
    assert impact["status"] == "unknown"
    assert impact["scope_comparable"] is False
    assert impact["metric_evidence"] == []
    assert "performance_scope_not_comparable" in diagnosis.unknowns


def test_insufficient_drift_report_produces_fact_without_causal_story() -> None:
    from brace_formal.diagnosis import diagnose_drift

    report = _report(status=DriftStatus.INSUFFICIENT_CALIBRATION)
    report = DriftReport(**{**report.__dict__, "features": (), "limitations": ("empirical_p_resolution_exceeds_alpha_budget",)})
    diagnosis = diagnose_drift(report)

    assert diagnosis.facts[0].kind == "insufficient_evidence"
    assert diagnosis.hypotheses == ()
    assert diagnosis.experiment_needs[0].need_id == "experiment.parent-compatible-baseline"
    assert "drift_attribution_not_established" in diagnosis.unknowns


def test_round_monitor_uses_real_historical_round_blocks_without_row_identity() -> None:
    from brace_formal.data import DataBatch
    from brace_formal.history import HistoryStore
    from brace_formal.model import FormalModel
    from brace_formal.round_core import _round_drift_diagnosis
    from tests.competition_core.support import write_parent
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "checkpoint.npz"
        write_parent(checkpoint, task="regression")
        store = HistoryStore(FormalModel.load(checkpoint))
        for round_index in range(1, 4):
            x = np.asarray([[float(round_index), float(index)] for index in range(8)], dtype=np.float64)
            y = np.arange(8, dtype=np.float64)
            store.append(
                DataBatch(tuple(f"r{round_index}-{index}" for index in range(8)), x, y, str(round_index) * 64),
                round_index,
            )
        current = DataBatch(
            tuple(f"current-{index}" for index in range(8)),
            np.asarray([[8.0, float(index)] for index in range(8)], dtype=np.float64),
            np.arange(8, dtype=np.float64),
            "c" * 64,
        )

        report, diagnosis = _round_drift_diagnosis(store, current, round_index=4)

    assert report.status is not DriftStatus.INSUFFICIENT_HISTORY
    assert report.history_window_count == 3
    assert "round_blocks_assumed_exchangeable" in report.limitations
    assert diagnosis.drift_status == report.status.value

