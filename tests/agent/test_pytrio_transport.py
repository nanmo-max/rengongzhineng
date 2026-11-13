from __future__ import annotations

from dataclasses import dataclass

from brace_msi.pytrio_agent import PyTrioSamplingTransport


class FakeFuture:
    def __init__(self, value: object) -> None:
        self.value = value

    def result(self, timeout: float | None = None) -> object:
        self.timeout = timeout
        return self.value


class FakeTokenizer:
    def apply_chat_template(
        self, messages, *, tokenize, add_generation_prompt, enable_thinking
    ):
        assert tokenize is False
        assert add_generation_prompt is True
        assert enable_thinking is False
        return messages[0]["content"]

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert add_special_tokens is False
        return list(range(len(text.split())))


@dataclass
class FakeSequence:
    text: str
    tokens: list[int]


class FakeSamplingClient:
    def __init__(self) -> None:
        self.kwargs = None
        self.future = None

    def get_tokenizer(self) -> FakeTokenizer:
        return FakeTokenizer()

    def sample(self, **kwargs):
        self.kwargs = kwargs
        self.future = FakeFuture(
            type("Response", (), {"sequences": [FakeSequence("{}", [1, 2, 3])]})()
        )
        return self.future


class FakeServiceClient:
    def __init__(self, sampling_client: FakeSamplingClient) -> None:
        self.sampling_client = sampling_client
        self.created = None

    def create_sampling_client(self, **kwargs):
        self.created = kwargs
        return self.sampling_client


class FakePyTrio:
    class SamplingParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class ModelInput:
        @staticmethod
        def from_ints(tokens):
            return tuple(tokens)

    def __init__(self, service: FakeServiceClient) -> None:
        self.service = service
        self.configured = None

    def configure(self, **kwargs):
        self.configured = kwargs

    def ServiceClient(self):
        return self.service


def test_transport_uses_documented_sampler_api_and_reports_token_counts() -> None:
    sampling = FakeSamplingClient()
    service = FakeServiceClient(sampling)
    module = FakePyTrio(service)
    transport = PyTrioSamplingTransport(pytrio_module=module)

    result = transport.sample(
        "one two three four",
        model="Qwen/Qwen3.5-4B",
        model_path="trio://saved",
        max_tokens=128,
        temperature=0.0,
        seed=20261106,
        timeout_seconds=7.5,
    )

    assert service.created == {
        "base_model": "Qwen/Qwen3.5-4B",
        "model_path": "trio://saved",
    }
    assert result.text == "{}"
    assert result.input_tokens == 4
    assert result.output_tokens == 3
    assert sampling.kwargs["num_samples"] == 1
    assert sampling.future.timeout == 7.5
    assert module.configured == {
        "request_timeout_seconds": 8,
        "retry_max_attempts": 1,
        "control_retry_timeout_seconds": 7.5,
        "sampling_retry_timeout_seconds": 7.5,
        "actor_capacity_wait_timeout_seconds": 7.5,
        "sampling_timeout_seconds": 8,
        "sampling_first_chunk_timeout_seconds": 7.5,
        "sampling_chunk_idle_timeout_seconds": 7.5,
    }
