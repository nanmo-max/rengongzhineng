from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brace_msi.formal_advisor_sft import (
    build_competition_agent_corpus,
    build_competition_agent_swanlab_spool,
    materialize_competition_agent_corpus,
    CompetitionAgentSftConfig,
    run_remote_competition_agent_sft,
    score_competition_agent_response,
)
from brace_msi.pytrio_sft import encode_sft_example


class _Tokenizer:
    eos_token_id = 99

    def apply_chat_template(self, messages, **_):
        return "PROMPT:" + messages[0]["content"]

    def encode(self, text, **_):
        return list(range(1, len(text.split()) + 1))


class _ModelInput:
    @staticmethod
    def from_ints(tokens):
        return tuple(tokens)


class _Trio:
    ModelInput = _ModelInput

    class Datum:
        def __init__(self, model_input, loss_fn_inputs):
            self.model_input = model_input
            self.loss_fn_inputs = loss_fn_inputs


def test_competition_corpus_covers_both_calls_and_has_family_holdout() -> None:
    corpus = build_competition_agent_corpus()
    assert len(corpus.train) == 48
    assert len(corpus.evaluation) == 24
    assert {row.phase for row in corpus.train} == {"proposal", "deployment"}
    assert {row.phase for row in corpus.evaluation} == {"proposal", "deployment"}
    assert {row.scenario_family for row in corpus.train}.isdisjoint(
        row.scenario_family for row in corpus.evaluation
    )
    assert {row.scenario_id for row in corpus.train}.isdisjoint(
        row.scenario_id for row in corpus.evaluation
    )
    text = "\n".join(row.prompt + row.completion for row in (*corpus.train, *corpus.evaluation))
    assert "Gas" not in text and "Bearing" not in text and "Engine" not in text
    assert "trio://" not in text and "api_key" not in text.lower()


def test_materialized_corpus_is_redacted_and_source_bound(tmp_path) -> None:
    manifest = materialize_competition_agent_corpus(tmp_path)
    assert manifest["contains_raw_samples"] is False
    assert manifest["contains_credentials"] is False
    assert manifest["contains_sampler_path"] is False
    assert manifest["train_examples"] == 48
    assert manifest["evaluation_examples"] == 24
    assert len(manifest["source_summaries"]) == 3
    assert all(item["verified"] for item in manifest["source_summaries"])
    payload = (tmp_path / "train.jsonl").read_text(encoding="utf-8")
    assert "D:/" not in payload and "trio://" not in payload


def test_assistant_only_loss_masks_prompt() -> None:
    example = build_competition_agent_corpus().train[0]
    datum = encode_sft_example(example, _Tokenizer(), _Trio)
    weights = np.asarray(datum.loss_fn_inputs["weights"])
    completion_tokens = len(_Tokenizer().encode(example.completion)) + 1
    assert np.all(weights[:-completion_tokens] == 0.0)
    assert np.all(weights[-completion_tokens:] == 1.0)


def test_all_expected_responses_are_executable_and_score_perfectly() -> None:
    corpus = build_competition_agent_corpus()
    for example in (*corpus.train, *corpus.evaluation):
        score = score_competition_agent_response(example.completion, example)
        assert score["schema_valid"]
        assert score["structure_match"]
        assert score["policy_match"]
        assert score["numeric_safe"]
        if example.phase == "proposal":
            payload = json.loads(example.completion)
            assert payload["recipe_id"] in example.legal_choices
            assert payload["history_policy"] == example.expected_history_policy
        else:
            assert json.loads(example.completion)["artifact_id"] in example.legal_choices


def test_proposal_prompt_contains_discriminating_aggregate_evidence() -> None:
    proposals = [row for row in build_competition_agent_corpus().train if row.phase == "proposal"]
    assert all('"mechanism_evidence"' in row.prompt for row in proposals)
    evidence_values = {
        json.loads(row.prompt.split("Context: ", 1)[1])["history_summary"]["mechanism_evidence"]
        for row in proposals
    }
    assert len(evidence_values) >= 6


def test_scoring_matches_production_single_json_extraction() -> None:
    example = build_competition_agent_corpus().evaluation[0]
    score = score_competition_agent_response("answer: " + example.completion + "<|im_end|>", example)
    assert score["schema_valid"]
    assert score["policy_match"]


def test_numeric_regression_and_wrong_history_are_rejected() -> None:
    corpus = build_competition_agent_corpus()
    deployment = next(row for row in corpus.evaluation if row.phase == "deployment" and row.expected_role == "parent")
    wrong = json.dumps({"artifact_id": "candidate", "rationale": "candidate is better"})
    score = score_competition_agent_response(wrong, deployment)
    assert score["schema_valid"]
    assert not score["policy_match"]
    assert not score["numeric_safe"]

    proposal = next(row for row in corpus.evaluation if row.phase == "proposal")
    payload = json.loads(proposal.completion)
    payload["history_policy"] = "current" if payload["history_policy"] != "current" else "current_plus_history"
    score = score_competition_agent_response(json.dumps(payload), proposal)
    assert not score["schema_valid"]
    assert not score["policy_match"]


class _Future:
    def __init__(self, value): self.value = value
    def result(self): return self.value


class _Sequence:
    def __init__(self, text): self.text, self.tokens = text, list(range(len(text)))


class _Sampler:
    def __init__(self, responses): self.responses = iter(responses)
    def sample(self, **_): return _Future(type("R", (), {"sequences": [_Sequence(next(self.responses))]})())


class _Trainer:
    def get_tokenizer(self): return _Tokenizer()
    def forward_backward(self, batch, _):
        outputs = [{"logprobs": np.full(item.loss_fn_inputs["weights"].shape, -1.0)} for item in batch]
        return _Future(type("F", (), {"loss_fn_outputs": outputs})())
    def optim_step(self, _): return _Future(object())
    def save_weights_for_sampler(self, **_):
        return _Future(type("S", (), {"path": "trio://run/sampler_weights/competition", "model": "Qwen/Qwen3.5-4B", "size": 10})())


class _Service:
    def __init__(self):
        completions = [row.completion for row in build_competition_agent_corpus().evaluation]
        self.samplers = [_Sampler(list(completions)) for _ in range(3)]
        self.sampling_kwargs = []
        self.trainer = _Trainer()
    def get_supported_models(self): return ["Qwen/Qwen3.5-4B"]
    def create_lora_training_client(self, **_): return self.trainer
    def create_sampling_client(self, **kwargs):
        self.sampling_kwargs.append(kwargs)
        return self.samplers.pop(0)


class _Params:
    def __init__(self, **kwargs): self.kwargs = kwargs


class _RemoteTrio(_Trio):
    SamplingParams = _Params
    AdamParams = _Params
    def __init__(self, service): self.service = service
    def ServiceClient(self): return self.service


def test_remote_run_reloads_persisted_sampler_for_final_evaluation(tmp_path: Path) -> None:
    service = _Service()
    result = run_remote_competition_agent_sft(
        tmp_path / "run", CompetitionAgentSftConfig(epochs=1), trio_module=_RemoteTrio(service)
    )
    assert result["status"] == "succeeded"
    assert result["reload_evaluation"]["policy_match_rate"] == 1.0
    assert len(service.sampling_kwargs) == 3
    assert service.sampling_kwargs[1]["model_path"].startswith("trio://")
    assert service.sampling_kwargs[2]["model_path"] == service.sampling_kwargs[1]["model_path"]
    assert (tmp_path / "run" / "reload_evaluation.json").is_file()
    spool = tmp_path / "public.jsonl"
    receipt = build_competition_agent_swanlab_spool(tmp_path / "run", spool)
    assert receipt["record_count"] == result["training_steps"] + 3
    text = spool.read_text(encoding="utf-8").lower()
    assert "trio://" not in text and "model_path" not in text and "prompt" not in text
