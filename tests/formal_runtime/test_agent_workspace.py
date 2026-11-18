from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


class FakeRound:
    def __init__(self, *, max_output_tokens: int, response_text: str) -> None:
        self.max_output_tokens = max_output_tokens
        self.model_name = "platform/sampler-alias"
        self.call_ids: list[str] = []
        self.calls: list[tuple[list[dict[str, str]], dict[str, object]]] = []
        self._response_text = response_text

    def model(self, messages, **options):
        self.calls.append((messages, options))
        call_id = f"call-{len(self.calls)}"
        self.call_ids.append(call_id)
        return SimpleNamespace(
            call_id=call_id,
            response={"choices": [{"message": {"content": self._response_text}}]},
            text=self._response_text,
        )


def test_agent_call_respects_host_token_limit_and_model_alias() -> None:
    """Catches overriding the official SDK's host-authorized token budget."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(
        max_output_tokens=16,
        response_text=json.dumps({"action": "train", "rationale": "adapt"}),
    )

    decision = request_proposal(rnd, {"round_index": 2, "task": "regression"})

    assert decision.action == "train"
    assert decision.epochs == 1
    assert decision.learning_rate_multiplier == 1.0
    assert decision.call_id == "call-1"
    assert "max_tokens" not in rnd.calls[0][1]
    assert "model" not in rnd.calls[0][1]


def test_agent_accepts_host_response_without_usage() -> None:
    """Catches treating optional response usage as required proposal data."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(
        max_output_tokens=512,
        response_text='```json\n{"action":"retain","epochs":1,"learning_rate_multiplier":1}\n```',
    )

    decision = request_proposal(rnd, {"round_index": 4, "task": "classification"})

    assert decision.action == "retain"
    assert decision.call_id == "call-1"
    assert rnd.call_ids == ["call-1"]


def test_agent_uses_structured_non_thinking_response_without_a_local_token_cap() -> None:
    """Catches replacing the platform's authorized budget with any participant cap."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(
        max_output_tokens=2048,
        response_text='{"action":"retain","epochs":1,"learning_rate_multiplier":1}',
    )

    request_proposal(rnd, {"round_index": 1, "task": "classification"})

    options = rnd.calls[0][1]
    assert "max_tokens" not in options
    assert options["enable_thinking"] is False
    assert options["response_format"] == {"type": "json_object"}


def test_agent_accepts_one_bounded_json_object_surrounded_by_host_text() -> None:
    """Catches rejecting a valid bounded decision solely because the host added prose."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(
        max_output_tokens=1024,
        response_text=(
            "Decision follows.\n"
            '{"action":"train","epochs":3,"learning_rate_multiplier":3,'
            '"rationale":"bounded continuation"}\nDone.'
        ),
    )

    decision = request_proposal(rnd, {"round_index": 6, "task": "regression"})

    assert decision.action == "train"
    assert decision.epochs == 1
    assert decision.learning_rate_multiplier == 1.0
    assert decision.parse_error is None


def test_agent_rejects_ambiguous_multiple_json_proposals() -> None:
    """Catches silently selecting one of two conflicting model decisions."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(
        max_output_tokens=1024,
        response_text=(
            '{"action":"retain","epochs":1,"learning_rate_multiplier":1}\n'
            '{"action":"train","epochs":3,"learning_rate_multiplier":3}'
        ),
    )

    decision = request_proposal(rnd, {"round_index": 7, "task": "regression"})

    assert decision.action == "retain"
    assert decision.parse_error is not None
    assert "exactly one JSON object" in decision.parse_error


def test_agent_ignores_unused_training_parameters_and_keeps_execution_defaults() -> None:
    """Catches rejecting safe intent because of parameters the executor never uses."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(
        max_output_tokens=2048,
        response_text=(
            '{"action":"train","epochs":99,"learning_rate_multiplier":17,'
            '"rationale":"adapt to the observed degradation"}'
        ),
    )

    decision = request_proposal(rnd, {"round_index": 8, "task": "regression"})

    assert decision.action == "train"
    assert decision.epochs == 1
    assert decision.learning_rate_multiplier == 1.0
    assert decision.parse_error is None


def test_invalid_agent_text_retains_after_a_real_call() -> None:
    """Catches fallback paths that skip the mandatory host model call."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(max_output_tokens=32, response_text="not valid json")

    decision = request_proposal(rnd, {"round_index": 10, "task": "regression"})

    assert decision.action == "retain"
    assert decision.call_id == "call-1"
    assert decision.parse_error is not None
    assert len(rnd.calls) == 1


def test_round_paths_remain_unique_in_a_persistent_workspace(tmp_path: Path) -> None:
    """Catches reuse of fixed state/candidate directories across host rounds."""

    from brace_formal.workspace import create_round_paths

    seen: set[Path] = set()
    for round_index in range(1, 11):
        paths = create_round_paths(tmp_path, round_index, "stage-A", "A")
        assert paths.root not in seen
        assert not paths.state.exists()
        assert not paths.candidate.exists()
        paths.root.mkdir(parents=True)
        paths.state.mkdir()
        paths.candidate.mkdir()
        seen.add(paths.root)

    assert len(seen) == 10


def test_round_paths_reject_an_existing_round_directory(tmp_path: Path) -> None:
    """Catches silently overwriting a prior round after retry or restart."""

    import pytest

    from brace_formal.workspace import create_round_paths

    occupied = tmp_path / "dataset-A" / "round-0003-stage-A"
    occupied.parent.mkdir()
    occupied.mkdir()

    with pytest.raises(FileExistsError, match="round workspace already exists"):
        create_round_paths(tmp_path, 3, "stage-A", "A")


def test_round_paths_are_isolated_by_dataset(tmp_path: Path) -> None:
    from brace_formal.workspace import create_round_paths

    a = create_round_paths(tmp_path, 1, "shared-stage", "A")
    b = create_round_paths(tmp_path, 1, "shared-stage", "B")

    assert a.root != b.root
    assert a.root.parent.name == "dataset-A"
    assert b.root.parent.name == "dataset-B"
