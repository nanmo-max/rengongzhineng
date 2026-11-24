from __future__ import annotations

import json
from pathlib import Path

from brace_formal.diagnosis import diagnose_drift
from brace_formal.drift import DriftReport, DriftStatus, FeatureDrift
from brace_formal.recipes import RecipeRegistry
from tests.competition_core.test_experiment_agent import AgentRound, _profile


def _diagnosis_payload() -> dict[str, object]:
    report = DriftReport(
        report_id="sha256:" + "d" * 64,
        status=DriftStatus.WARNING,
        calibration_method="block_permutation_maxT",
        reference_scope_sha256="e" * 64,
        current_scope_sha256="f" * 64,
        sample_count=32,
        history_window_count=3,
        global_score=3.5,
        alpha_run=0.05,
        alpha_window=0.005,
        alpha_spent=0.015,
        permutation_count=2047,
        minimum_empirical_p=1.0 / 2048.0,
        reference_epoch=1,
        features=(
            FeatureDrift(0, "location_shift", 1.2, 0.1, 0.8, 0.3, 0.0, 3.5, 0.001, 0.004, True, 1.0),
        ),
        limitations=(),
    )
    return diagnose_drift(report).as_dict()


def test_agent_accepts_only_authentic_diagnosis_evidence_refs(tmp_path: Path) -> None:
    from brace_formal.agent import request_experiment_proposal

    fact_id = str(_diagnosis_payload()["facts"][0]["fact_id"])  # type: ignore[index]
    rnd = AgentRound(
        [
            json.dumps(
                {
                    "recipe_id": "native_current",
                    "parameters": {},
                    "history_policy": "current",
                    "hypothesis": "test a bounded update under observed location shift",
                    "rationale": "the cited feature shift is calibrated",
                    "evidence_refs": [fact_id],
                    "expected_metric_effect": "improve the primary metric without changing schema",
                    "risk": "the shift may not affect predictive performance",
                }
            )
        ]
    )

    proposal = request_experiment_proposal(
        rnd,
        _profile(tmp_path),
        RecipeRegistry(),
        diagnosis_evidence=_diagnosis_payload(),
    )

    assert proposal.evidence_refs == (fact_id,)
    assert proposal.requested_evidence_refs == (fact_id,)
    assert proposal.parse_error is None
    prompt = rnd.calls[0][0][0]["content"]
    assert '"diagnosis_evidence"' in prompt
    assert fact_id in prompt


def test_agent_rejects_invented_evidence_reference_and_records_request(tmp_path: Path) -> None:
    from brace_formal.agent import request_experiment_proposal

    rnd = AgentRound(
        [
            json.dumps(
                {
                    "recipe_id": "native_current",
                    "parameters": {},
                    "history_policy": "current",
                    "hypothesis": "use an invented fact",
                    "rationale": "invalid",
                    "evidence_refs": ["drift.feature.999.location_shift"],
                    "expected_metric_effect": "unknown",
                    "risk": "unknown",
                }
            )
        ]
    )

    proposal = request_experiment_proposal(
        rnd,
        _profile(tmp_path),
        RecipeRegistry(),
        diagnosis_evidence=_diagnosis_payload(),
    )

    assert proposal.recipe_id == "class_weighted_current_fast"
    assert proposal.evidence_refs == ()
    assert proposal.requested_evidence_refs == ("drift.feature.999.location_shift",)
    assert "unknown evidence reference" in str(proposal.parse_error)
