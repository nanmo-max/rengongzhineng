from __future__ import annotations

from brace_msi.advisor_evaluation import (
    build_frozen_deployment_cases,
    run_base_advisor_evaluation,
    score_deployment_decision,
    summarize_advisor_evaluation,
)


def test_frozen_cases_cover_metric_directions_and_safety() -> None:
    cases = build_frozen_deployment_cases()

    assert len(cases) >= 10
    assert {case.metric_direction for case in cases} == {"higher", "lower"}
    assert any(case.hard_safety_failures for case in cases)
    assert any(case.expected_decision == "deploy" for case in cases)
    assert any(case.expected_decision == "retain" for case in cases)
    assert len({case.case_id for case in cases}) == len(cases)


def test_scoring_marks_unsafe_deploy_as_critical_failure() -> None:
    case = next(
        item
        for item in build_frozen_deployment_cases()
        if item.expected_decision == "retain" and item.relation == "regressed"
    )

    score = score_deployment_decision(
        case,
        decision="deploy",
        schema_valid=True,
    )

    assert score["decision_correct"] is False
    assert score["safety_critical_failure"] is True


def test_summary_requires_no_critical_failure_and_counts_systematic_errors() -> None:
    rows = []
    for case in build_frozen_deployment_cases():
        rows.append(
            {
                "case_id": case.case_id,
                "schema_valid": True,
                "decision_correct": True,
                "safety_critical_failure": False,
                "input_tokens": 100,
                "output_tokens": 20,
                "latency_seconds": 0.5,
                "error_category": None,
            }
        )

    passed = summarize_advisor_evaluation(rows)
    assert passed["base_model_passed"] is True
    assert passed["sft_required"] is False

    rows[0]["decision_correct"] = False
    rows[0]["safety_critical_failure"] = True
    failed = summarize_advisor_evaluation(rows)
    assert failed["base_model_passed"] is False
    assert failed["sft_required"] is True


def test_base_evaluation_persists_hashes_not_raw_prompts(tmp_path) -> None:
    def fake_call(prompt: str, call_index: int):
        decision = (
            "deploy"
            if '"relation": "improved"' in prompt
            and '"hard_safety_failures": []' in prompt
            else "retain"
        )
        text = '{"decision":"%s","rationale":"bounded metric-consistent decision"}' % decision
        return text, 120 + call_index, 18, 0.1

    result = run_base_advisor_evaluation(tmp_path / "run", fake_call)

    assert result["summary"]["base_model_passed"] is True
    serialized = (tmp_path / "run" / "result.json").read_text(encoding="utf-8")
    assert "parent_metrics" not in serialized
    assert "bounded metric-consistent decision" not in serialized
    assert all(len(row["prompt_sha256"]) == 64 for row in result["cases"])
    assert all(len(row["response_sha256"]) == 64 for row in result["cases"])
