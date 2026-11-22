"""Immutable diagnosis evidence contracts; attribution logic is outside P5 phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiagnosisFact:
    fact_id: str
    kind: str
    effect: float
    contribution: float
    confidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "kind": self.kind,
            "effect": self.effect,
            "contribution": self.contribution,
            "confidence": self.confidence,
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
class DiagnosisReport:
    diagnosis_id: str
    drift_status: str
    facts: tuple[DiagnosisFact, ...]
    hypotheses: tuple[DiagnosisHypothesis, ...]
    performance_impact: str
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
            "performance_impact": self.performance_impact,
            "experiment_needs": [item.as_dict() for item in self.experiment_needs],
            "unknowns": list(self.unknowns),
            "prohibited_claims": list(self.prohibited_claims),
        }
