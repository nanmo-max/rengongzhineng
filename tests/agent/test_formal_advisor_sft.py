from __future__ import annotations

import json

from brace_msi.formal_advisor_sft import (
    FORMAL_ADVISOR_EVALUATION_SHA256,
    FORMAL_ADVISOR_SEED,
    FORMAL_ADVISOR_TRAIN_SHA256,
    build_formal_advisor_corpus,
    materialize_formal_advisor_corpus,
    score_formal_deployment_response,
)


def test_formal_advisor_corpus_is_disjoint_and_uses_runtime_prompt() -> None:
    corpus = build_formal_advisor_corpus()

    assert len(corpus.train) == 24
    assert len(corpus.evaluation) == 12
    assert {row.scenario_id for row in corpus.train}.isdisjoint(
        row.scenario_id for row in corpus.evaluation
    )
    assert all("Required fields: decision" in row.prompt for row in (*corpus.train, *corpus.evaluation))
    assert all("parent_metrics" in row.prompt for row in (*corpus.train, *corpus.evaluation))
    assert all(json.loads(row.completion)["decision"] in {"deploy", "retain"} for row in (*corpus.train, *corpus.evaluation))
    assert {row.archetype for row in corpus.train}.isdisjoint(
        {"history_improved", "history_regressed"}
    )
    assert {"history_improved", "history_regressed"}.issubset(
        {row.archetype for row in corpus.evaluation}
    )


def test_formal_advisor_manifest_contains_no_industrial_samples(tmp_path) -> None:
    manifest = materialize_formal_advisor_corpus(tmp_path, seed=FORMAL_ADVISOR_SEED)

    assert manifest["train_examples"] == 24
    assert manifest["evaluation_examples"] == 12
    assert manifest["contains_raw_samples"] is False
    assert manifest["contains_credentials"] is False
    assert len(manifest["train_sha256"]) == 64
    assert len(manifest["evaluation_sha256"]) == 64
    assert manifest["train_sha256"] == FORMAL_ADVISOR_TRAIN_SHA256
    assert manifest["evaluation_sha256"] == FORMAL_ADVISOR_EVALUATION_SHA256


def test_formal_response_score_handles_suffix_and_hard_risk() -> None:
    example = next(
        row
        for row in build_formal_advisor_corpus().evaluation
        if row.archetype == "hard_risk"
    )
    safe = score_formal_deployment_response(example.completion + "<|im_end|>", example)
    unsafe = score_formal_deployment_response(
        '{"decision":"deploy","rationale":"candidate metric improved"}', example
    )

    assert safe == {
        "schema_valid": True,
        "decision_match": True,
        "safety_safe": True,
        "policy_match": True,
    }
    assert unsafe["schema_valid"] is True
    assert unsafe["decision_match"] is False
    assert unsafe["safety_safe"] is False
