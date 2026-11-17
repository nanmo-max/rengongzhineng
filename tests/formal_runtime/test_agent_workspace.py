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
    """Catches fixed token limits or comparisons with a hard-coded model name."""

    from brace_formal.agent import request_proposal

    rnd = FakeRound(
        max_output_tokens=16,
        response_text=json.dumps(
            {"action": "train", "epochs": 3, "learning_rate_multiplier": 0.3}
        ),
    )

    decision = request_proposal(rnd, {"round_index": 2, "task": "regression"})

    assert decision.action == "train"
    assert decision.epochs == 3
    assert decision.learning_rate_multiplier == 0.3
    assert decision.call_id == "call-1"
    assert rnd.calls[0][1]["max_tokens"] == 16
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
