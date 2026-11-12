from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from brace_msi.pytrio_agent import parse_experiment_proposal
from brace_msi.pytrio_sft import (
    FROZEN_EVALUATION_SHA256,
    FROZEN_TRAIN_SHA256,
    PyTrioSftRunConfig,
    build_brace_sft_corpus,
    encode_sft_example,
    materialize_brace_sft_corpus,
    run_remote_pytrio_sft,
    score_proposal_response,
)


def test_corpus_is_deterministic_disjoint_and_runtime_valid() -> None:
    first = build_brace_sft_corpus(seed=20261112)
    second = build_brace_sft_corpus(seed=20261112)

    assert first == second
    assert len(first.train) >= 24
    assert len(first.evaluation) >= 8
    assert {row.scenario_id for row in first.train}.isdisjoint(
        row.scenario_id for row in first.evaluation
    )
    assert {row.archetype for row in first.train}.isdisjoint(
        row.archetype for row in first.evaluation
    )

    for row in (*first.train, *first.evaluation):
        proposal = parse_experiment_proposal(row.completion)
        assert proposal.action.value in {
            "noop",
            "incremental_update",
            "replay_refit",
        }
        assert row.messages == ({"role": "user", "content": row.prompt},)
        assert "api_key" not in row.prompt.lower()
        assert "dataset" not in row.prompt.lower()


def test_corpus_contains_safety_and_update_decisions_for_both_task_kinds() -> None:
    corpus = build_brace_sft_corpus(seed=20261112)
    rows = (*corpus.train, *corpus.evaluation)
    task_kinds = {row.task_kind for row in rows}
    actions = {
        parse_experiment_proposal(row.completion).action.value for row in rows
    }

    assert task_kinds == {"classification", "regression"}
    assert actions == {"noop", "incremental_update", "replay_refit"}
    assert any(row.archetype == "budget_exhausted" for row in rows)
    assert any(row.archetype == "unsafe_evidence" for row in rows)


def test_materialized_corpus_has_hashes_and_no_raw_results(tmp_path: Path) -> None:
    manifest = materialize_brace_sft_corpus(
        tmp_path,
        seed=20261112,
    )

    assert manifest["format"] == "brace-msi.pytrio-sft-corpus.v1"
    assert manifest["train_examples"] >= 24
    assert manifest["evaluation_examples"] >= 8
    assert len(manifest["train_sha256"]) == 64
    assert len(manifest["evaluation_sha256"]) == 64
    assert manifest["train_sha256"] == FROZEN_TRAIN_SHA256
    assert manifest["evaluation_sha256"] == FROZEN_EVALUATION_SHA256

    train_rows = [
        json.loads(line)
        for line in (tmp_path / "train.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert set(train_rows[0]) == {
        "format",
        "scenario_id",
        "archetype",
        "task_kind",
        "messages",
    }
    encoded = json.dumps(train_rows, ensure_ascii=False).lower()
    assert "api_key" not in encoded
    assert "raw_feature" not in encoded
    assert "sample_id" not in encoded


class _FakeTokenizer:
    eos_token_id = 999

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs["tokenize"] is False
        assert kwargs["add_generation_prompt"] is True
        assert kwargs["enable_thinking"] is False
        return "PROMPT:" + messages[0]["content"]

    def encode(self, text, *, add_special_tokens=False):
        assert add_special_tokens is False
        return list(range(10, 10 + len(text)))


class _FakeModelInput:
    @staticmethod
    def from_ints(tokens):
        return tuple(tokens)


class _FakeDatum:
    def __init__(self, *, model_input, loss_fn_inputs):
        self.model_input = model_input
        self.loss_fn_inputs = loss_fn_inputs


class _FakeTrio:
    Datum = _FakeDatum
    ModelInput = _FakeModelInput


def test_encoding_masks_prompt_and_trains_completion_only() -> None:
    example = build_brace_sft_corpus().train[0]
    datum = encode_sft_example(example, _FakeTokenizer(), _FakeTrio)

    prompt_len = len("PROMPT:" + example.prompt)
    completion_len = len(example.completion) + 1  # persisted EOS
    assert len(datum.model_input) == prompt_len + completion_len - 1
    weights = datum.loss_fn_inputs["weights"]
    assert weights.shape == datum.loss_fn_inputs["target_tokens"].shape
    assert weights[: prompt_len - 1].sum() == 0
    assert weights[prompt_len - 1 :].sum() == completion_len


def test_response_scoring_separates_schema_from_policy_match() -> None:
    expected = build_brace_sft_corpus().evaluation[0]
    exact = score_proposal_response(expected.completion, expected)
    malformed = score_proposal_response("not-json", expected)

    assert exact == {
        "schema_valid": True,
        "action_match": True,
        "tool_match": True,
        "budget_safe": True,
        "policy_match": True,
    }
    assert malformed == {
        "schema_valid": False,
        "action_match": False,
        "tool_match": False,
        "budget_safe": False,
        "policy_match": False,
    }


def test_remote_run_config_is_bounded() -> None:
    config = PyTrioSftRunConfig()

    assert config.base_model == "Qwen/Qwen3.5-4B"
    assert config.rank <= 32
    assert config.epochs <= 3
    assert config.batch_size <= 8
    assert config.weight_name == "brace-msi-agent-sft-v1"


class _Future:
    def __init__(self, value):
        self.value = value

    def result(self):
        return self.value


class _Sequence:
    def __init__(self, text: str):
        self.text = text
        self.tokens = list(range(len(text)))


class _Sampler:
    def __init__(self, responses: list[str], *, fail_after: int | None = None):
        self.responses = iter(responses)
        self.fail_after = fail_after
        self.calls = 0

    def sample(self, **kwargs):
        if self.fail_after is not None and self.calls >= self.fail_after:
            raise RuntimeError("simulated tuned evaluation failure")
        self.calls += 1
        return _Future(
            type("Response", (), {"sequences": [_Sequence(next(self.responses))]})()
        )


class _Trainer:
    def __init__(self):
        self.save_calls = []

    def get_tokenizer(self):
        return _FakeTokenizer()

    def forward_backward(self, batch, loss_fn):
        assert loss_fn == "cross_entropy"
        outputs = [
            {"logprobs": np.full(item.loss_fn_inputs["weights"].shape, -1.0)}
            for item in batch
        ]
        return _Future(type("Forward", (), {"loss_fn_outputs": outputs})())

    def optim_step(self, params):
        return _Future(object())

    def save_weights_for_sampler(self, **kwargs):
        self.save_calls.append(kwargs)
        return _Future(
            type(
                "Saved",
                (),
                {
                    "path": "trio://run-test/sampler_weights/brace-msi-agent-sft-v1",
                    "model": "Qwen/Qwen3.5-4B",
                    "size": 123,
                },
            )()
        )


class _Service:
    def __init__(self, *, tuned_fail_after: int | None = None):
        corpus = build_brace_sft_corpus()
        completions = [row.completion for row in corpus.evaluation]
        self.base_sampler = _Sampler(list(completions))
        self.tuned_sampler = _Sampler(
            list(completions), fail_after=tuned_fail_after
        )
        self.trainer = _Trainer()
        self.training_kwargs = None

    def get_supported_models(self):
        return ["Qwen/Qwen3.5-4B", "Qwen/Qwen3.8-27B"]

    def create_lora_training_client(self, **kwargs):
        self.training_kwargs = kwargs
        return self.trainer

    def create_sampling_client(self, **kwargs):
        return self.tuned_sampler if "model_path" in kwargs else self.base_sampler


class _Params:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _RemoteFakeTrio(_FakeTrio):
    SamplingParams = _Params
    AdamParams = _Params

    def __init__(self, service: _Service):
        self.service = service

    def ServiceClient(self):
        return self.service


def test_remote_run_is_non_overwriting_and_persists_sampler(tmp_path: Path) -> None:
    service = _Service()
    trio = _RemoteFakeTrio(service)
    output = tmp_path / "new-run"

    result = run_remote_pytrio_sft(output, PyTrioSftRunConfig(), trio_module=trio)

    assert result["status"] == "succeeded"
    assert result["sampler_model_path"].startswith("trio://")
    assert service.trainer.save_calls == [
        {"name": "brace-msi-agent-sft-v1", "ttl_seconds": None}
    ]
    assert (output / "persistent_sampler.json").is_file()
    assert json.loads(
        (output / "base_evaluation.json").read_text(encoding="utf-8")
    )["status"] == "complete"
    assert result["base_evaluation"]["budget_safe_rate"] == 1.0
    assert result["tuned_evaluation"]["policy_match_rate"] == 1.0

    with pytest.raises(FileExistsError, match="new path"):
        run_remote_pytrio_sft(output, PyTrioSftRunConfig(), trio_module=trio)


def test_saved_sampler_path_survives_tuned_evaluation_failure(tmp_path: Path) -> None:
    service = _Service(tuned_fail_after=2)
    output = tmp_path / "failed-after-save"

    with pytest.raises(RuntimeError, match="simulated"):
        run_remote_pytrio_sft(
            output,
            PyTrioSftRunConfig(),
            trio_module=_RemoteFakeTrio(service),
        )

    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    sampler = json.loads(
        (output / "persistent_sampler.json").read_text(encoding="utf-8")
    )
    assert failure["failed_stage"] == "tuned_evaluation"
    assert failure["sampler_model_path"] == sampler["model_path"]
    assert failure["training_steps_completed"] == 18
    assert failure["base_evaluation_partial"]["examples"] == 12
    assert failure["tuned_evaluation_partial"]["examples"] == 2
    assert failure["tuned_evaluation_partial"]["output_tokens"] > 0


def test_changed_seed_fails_before_service_call(tmp_path: Path) -> None:
    class _NoService(_RemoteFakeTrio):
        def ServiceClient(self):
            raise AssertionError("service must not be called")

    with pytest.raises(ValueError, match="preregistered seed"):
        output = tmp_path / "wrong-seed"
        run_remote_pytrio_sft(
            output,
            PyTrioSftRunConfig(seed=20261113),
            trio_module=_NoService(_Service()),
        )
    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert failure["failed_stage"] == "preflight"
    assert failure["error_category"] == "ValueError"

