from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _write_candidate(root: Path) -> None:
    root.mkdir()
    params = {
        "w1": np.asarray([[0.5, -0.2], [0.1, 0.3]], dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.asarray([[0.8, -0.8], [-0.4, 0.4]], dtype=np.float64),
        "b2": np.zeros(2, dtype=np.float64),
    }
    metadata = {
        "format": "contest.cpu-mlp.v1", "device": "cpu", "profile": "test",
        "task": "classification",
        "paths": ['[["key","features"],["index",0]]', '[["key","features"],["index",1]]'],
        "classes": ["cold", "hot"], "hidden": 2, "seed": 42,
        "epochs": 1, "steps": 1, "learning_rate": 0.01, "batch_size": 4,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 0.0, "target_scale": 1.0,
    }
    np.savez(
        root / "checkpoint.npz",
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        mean=np.zeros(2), scale=np.ones(2),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


def test_local_host_returns_authoritative_nonempty_candidate_metrics(tmp_path: Path) -> None:
    from scripts.verify_workspace_v2_image import _score_candidate

    artifact = tmp_path / "artifact"
    _write_candidate(artifact)
    validation = tmp_path / "validation.jsonl"
    validation.write_text(
        "".join(
            json.dumps(
                {
                    "id": f"row-{index}",
                    "inputs": {"features": [float(index), float(index % 2)]},
                    "answer": "hot" if index >= 3 else "cold",
                }
            ) + "\n"
            for index in range(6)
        ),
        encoding="utf-8",
    )

    metrics = _score_candidate(artifact, validation)

    assert set(metrics) == {"accuracy", "macro_f1"}
    assert all(np.isfinite(value) for value in metrics.values())


def test_pytrio_gateway_attaches_official_prompt_once_and_returns_sanitized_receipt() -> None:
    from types import SimpleNamespace

    from scripts.verify_workspace_v2_image import PyTrioModelGateway

    captured: dict[str, object] = {}

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            captured["messages"] = messages
            captured["template_options"] = kwargs
            return "encoded prompt"

        def encode(self, text, add_special_tokens=False):
            captured["encoded_text"] = text
            captured["add_special_tokens"] = add_special_tokens
            return [11, 12, 13]

    class Sampler:
        def get_tokenizer(self):
            return Tokenizer()

        def sample(self, **kwargs):
            captured["sample"] = kwargs
            sequence = SimpleNamespace(
                text='{"recipe_id":"native_current"}',
                tokens=[21, 22],
                stop_reason="stop",
            )
            return SimpleNamespace(
                result=lambda: SimpleNamespace(
                    sequences=[sequence],
                    input_tokens=3,
                    output_tokens=2,
                    sampling_run_cuid="run-private-identifier",
                )
            )

    class Service:
        def get_supported_models(self):
            return ["Qwen/Qwen3.8-27B"]

        def create_sampling_client(self, **kwargs):
            captured["client"] = kwargs
            return Sampler()

    fake_trio = SimpleNamespace(
        ServiceClient=lambda: Service(),
        ModelInput=SimpleNamespace(from_ints=lambda tokens: ("tokens", tuple(tokens))),
        SamplingParams=lambda **kwargs: ("params", kwargs),
    )
    gateway = PyTrioModelGateway(
        "Qwen/Qwen3.8-27B",
        pytrio_module=fake_trio,
    )

    response, receipt = gateway.generate(
        [{"role": "user", "content": "choose one recipe"}],
        official_prompt="official system prompt",
        max_tokens=768,
        seed=20261124,
    )

    assert captured["client"] == {"base_model": "Qwen/Qwen3.8-27B"}
    assert captured["messages"] == [
        {"role": "system", "content": "official system prompt"},
        {"role": "user", "content": "choose one recipe"},
    ]
    assert captured["template_options"] == {
        "tokenize": False,
        "add_generation_prompt": True,
        "enable_thinking": False,
    }
    assert response["model"] == "Qwen/Qwen3.8-27B"
    assert response["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }
    assert receipt["provider"] == "pytrio"
    assert receipt["model"] == "Qwen/Qwen3.8-27B"
    assert receipt["input_tokens"] == 3
    assert receipt["output_tokens"] == 2
    assert len(receipt["response_sha256"]) == 64
    assert len(receipt["request_sha256"]) == 64
    assert len(receipt["sampling_run_sha256"]) == 64
    assert receipt["response_format_enforced"] is False
    assert receipt["stop_reason"] == "stop"
    assert "run-private-identifier" not in json.dumps(receipt)
    assert "api_key" not in json.dumps(receipt).lower()


def test_start_frame_and_local_response_use_selected_host_model() -> None:
    from scripts.verify_workspace_v2_image import _proposal, _start_frame

    parent = {
        "artifact_id": "baseline-A",
        "files": [
            {
                "path": "checkpoint.npz",
                "sha256": "sha256:" + "a" * 64,
                "size_bytes": 10,
            }
        ],
    }
    model_name = "Qwen/Qwen3.8-27B"
    frame = _start_frame(
        "A",
        1,
        parent,
        None,
        [parent],
        model_name=model_name,
    )
    response = _proposal(
        [
            {
                "role": "user",
                "content": (
                    'Required fields: recipe_id. Context: {"available_recipes":'
                    '[{"recipe_id":"native_current","history_policy":"current"}],'
                    '"history_summary":{"completed_rounds":0}}'
                ),
            }
        ],
        model_name=model_name,
    )

    assert frame["model_name"] == model_name
    assert response["model"] == model_name
