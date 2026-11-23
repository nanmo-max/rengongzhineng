"""Evidence-bounded attribution derived from a calibrated :mod:`drift` report."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping

from .drift import DriftReport, DriftStatus, FeatureDrift


@dataclass(frozen=True)
class DiagnosisFact:
    fact_id: str
    kind: str
    effect: float
    contribution: float
    confidence: str
    feature_index: int | None = None
    scope_sha256: str | None = None
    method: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "kind": self.kind,
            "effect": self.effect,
            "contribution": self.contribution,
            "confidence": self.confidence,
            "feature_index": self.feature_index,
            "scope_sha256": self.scope_sha256,
            "method": self.method,
        }

@dataclass(frozen=True)
class DiagnosisHypothesis:
    hypothesis_id: str
    kind: str
    supports: tuple[str, ...]
    contradicts: tuple[str, ...]
    claim_strength: str
    requires_validation: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "kind": self.kind,
            "supports": list(self.supports),
            "contradicts": list(self.contradicts),
            "claim_strength": self.claim_strength,
            "requires_validation": self.requires_validation,
        }


@dataclass(frozen=True)
class ExperimentNeed:
    need_id: str
    supported_by: tuple[str, ...]
    objective: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "need_id": self.need_id,
            "supported_by": list(self.supported_by),
            "objective": self.objective,
        }


@dataclass(frozen=True)
class PerformanceImpact:
    status: str
    scope_comparable: bool
    metric_evidence: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scope_comparable": self.scope_comparable,
            "metric_evidence": [dict(item) for item in self.metric_evidence],
        }


@dataclass(frozen=True)
class DiagnosisReport:
    diagnosis_id: str
    drift_status: str
    facts: tuple[DiagnosisFact, ...]
    hypotheses: tuple[DiagnosisHypothesis, ...]
    performance_impact: PerformanceImpact | str
    experiment_needs: tuple[ExperimentNeed, ...]
    unknowns: tuple[str, ...]
    prohibited_claims: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": "brace-formal.diagnosis-report.v1",
            "diagnosis_id": self.diagnosis_id,
            "drift_status": self.drift_status,
            "facts": [item.as_dict() for item in self.facts],
            "hypotheses": [item.as_dict() for item in self.hypotheses],
            "performance_impact": (
                self.performance_impact.as_dict()
                if isinstance(self.performance_impact, PerformanceImpact)
                else self.performance_impact
            ),
            "experiment_needs": [item.as_dict() for item in self.experiment_needs],
            "unknowns": list(self.unknowns),
            "prohibited_claims": list(self.prohibited_claims),
        }


_HYPOTHESIS_BY_STATISTIC = {
    "missingness_shift": "data_quality_shift",
    "location_shift": "location_shift",
    "scale_shift": "scale_or_noise_shift",
    "wasserstein_shift": "shape_shift",
    "ks_distance": "shape_shift",
}

_NEED_BY_HYPOTHESIS = {
    "data_quality_shift": (
        "experiment.input-contract-check",
        "test a parent-compatible data-quality handling experiment without asserting a physical fault",
    ),
    "location_shift": (
        "experiment.current-distribution-update",
        "test whether a bounded parent-compatible update improves the current legal metric",
    ),
    "scale_or_noise_shift": (
        "experiment.robust-current-data",
        "test whether a robust parent-compatible update reduces sensitivity to the observed scale change",
    ),
    "shape_shift": (
        "experiment.replay-or-robust-loss",
        "compare a bounded current-data update with a legal replay-compatible robust experiment",
    ),
}


def _feature_effect(feature: FeatureDrift) -> float:
    values = {
        "missingness_shift": feature.missing_delta,
        "location_shift": feature.location_shift,
        "scale_shift": feature.scale_shift,
        "wasserstein_shift": feature.wasserstein_shift,
        "ks_distance": feature.ks_distance,
    }
    return float(values.get(feature.dominant_statistic, feature.omnibus_score))


def _performance_impact(
    evidence: Mapping[str, Any] | None,
) -> tuple[PerformanceImpact, tuple[str, ...]]:
    if evidence is None:
        return PerformanceImpact("unknown", False), ("performance_scope_not_supplied",)
    comparable = evidence.get("scope_comparable") is True
    if not comparable:
        return PerformanceImpact("unknown", False), ("performance_scope_not_comparable",)
    relation = evidence.get("relation")
    metric = evidence.get("metric")
    signed_gain = evidence.get("signed_gain")
    if relation not in {"improved", "equivalent", "regressed"}:
        return PerformanceImpact("unknown", True), ("performance_relation_unavailable",)
    metric_evidence: tuple[dict[str, Any], ...] = ()
    if isinstance(metric, str) and metric and isinstance(signed_gain, (int, float)) and not isinstance(signed_gain, bool) and math.isfinite(float(signed_gain)):
        metric_evidence = ({"metric": metric, "signed_gain": float(signed_gain), "relation": relation},)
    status = "observed" if relation == "regressed" else "not_observed"
    return PerformanceImpact(status, True, metric_evidence), ()


def diagnose_drift(
    report: DriftReport,
    *,
    performance_evidence: Mapping[str, Any] | None = None,
    top_k: int = 8,
) -> DiagnosisReport:
    """Convert calibrated change evidence into facts, hypotheses and experiment needs.

    The function never assigns a physical cause.  Performance impact is only
    considered observed when explicitly supplied evidence has a comparable
    evaluation scope.
    """

    if not isinstance(report, DriftReport):
        raise TypeError("report must be a DriftReport")
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    facts: list[DiagnosisFact] = []
    hypotheses: list[DiagnosisHypothesis] = []
    needs: list[ExperimentNeed] = []
    unknowns: list[str] = list(report.limitations)

    selected = sorted(
        (feature for feature in report.features if feature.selected),
        key=lambda feature: (-feature.contribution, feature.feature_index),
    )[:top_k]
    if report.status in {DriftStatus.INSUFFICIENT_HISTORY, DriftStatus.INSUFFICIENT_CALIBRATION}:
        facts.append(
            DiagnosisFact(
                fact_id=f"drift.status.{report.status.value}",
                kind="insufficient_evidence",
                effect=0.0,
                contribution=0.0,
                confidence="insufficient",
                scope_sha256=report.current_scope_sha256,
                method=report.calibration_method,
            )
        )
        unknowns.append("drift_attribution_not_established")
        needs.append(
            ExperimentNeed(
                "experiment.parent-compatible-baseline",
                (facts[0].fact_id,),
                "run a bounded parent-compatible baseline while retaining the evidence limitation",
            )
        )
    elif not selected:
        facts.append(
            DiagnosisFact(
                fact_id="drift.status.stable_observed",
                kind="stable_observed",
                effect=float(report.global_score),
                contribution=0.0,
                confidence="calibrated",
                scope_sha256=report.current_scope_sha256,
                method=report.calibration_method,
            )
        )
        needs.append(
            ExperimentNeed(
                "experiment.low-cost-baseline",
                (facts[0].fact_id,),
                "retain a low-cost parent-compatible experiment as a measured baseline",
            )
        )
    else:
        facts.extend(
            DiagnosisFact(
                fact_id=f"drift.feature.{feature.feature_index}.{feature.dominant_statistic}",
                kind=feature.dominant_statistic,
                effect=_feature_effect(feature),
                contribution=float(feature.contribution),
                confidence="calibrated",
                feature_index=int(feature.feature_index),
                scope_sha256=report.current_scope_sha256,
                method=report.calibration_method,
            )
            for feature in selected
        )
        grouped: dict[str, list[str]] = {}
        for fact in facts:
            kind = _HYPOTHESIS_BY_STATISTIC.get(fact.kind, "distribution_shift")
            grouped.setdefault(kind, []).append(fact.fact_id)
        for index, (kind, supporting) in enumerate(sorted(grouped.items()), 1):
            hypothesis = DiagnosisHypothesis(
                hypothesis_id=f"diagnosis.{kind}.{index}",
                kind=kind,
                supports=tuple(supporting),
                contradicts=(),
                claim_strength="possible",
                requires_validation=True,
            )
            hypotheses.append(hypothesis)
            need_id, objective = _NEED_BY_HYPOTHESIS.get(
                kind,
                ("experiment.bounded-distribution-test", "test a bounded parent-compatible response to the observed distribution change"),
            )
            needs.append(ExperimentNeed(need_id, (hypothesis.hypothesis_id,), objective))

    impact, performance_unknowns = _performance_impact(performance_evidence)
    unknowns.extend(performance_unknowns)
    payload = {
        "drift_report_id": report.report_id,
        "facts": [item.as_dict() for item in facts],
        "hypotheses": [item.as_dict() for item in hypotheses],
        "performance_impact": impact.as_dict(),
        "experiment_needs": [item.as_dict() for item in needs],
        "unknowns": sorted(set(unknowns)),
    }
    diagnosis_id = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return DiagnosisReport(
        diagnosis_id=diagnosis_id,
        drift_status=report.status.value,
        facts=tuple(facts),
        hypotheses=tuple(hypotheses),
        performance_impact=impact,
        experiment_needs=tuple(needs),
        unknowns=tuple(sorted(set(unknowns))),
        prohibited_claims=(
            "physical_failure_not_established",
            "causal_origin_not_established",
            "performance_impact_requires_comparable_metric_evidence",
        ),
    )
