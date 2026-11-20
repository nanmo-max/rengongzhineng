from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from brace_formal.model import FormalModel
from brace_formal.submission import predict, train
from tests.competition_core.support import make_round


@pytest.mark.parametrize("task", ["classification", "regression"])
def test_verified_round_trains_cites_and_predicts(task: str, monkeypatch, tmp_path: Path) -> None:
    """Catches loss of either host call, real continuation, state, finish references, or prediction schema."""

    rnd, parent_path = make_round(tmp_path, task=task)
    parent = FormalModel.load(parent_path)
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    train(rnd)

    assert rnd.call_ids == ["call-1", "call-2"]
    assert rnd.submitted is not None
    candidate_path = Path(rnd.submitted["directory"]) / "checkpoint.npz"
    candidate = FormalModel.load(candidate_path)
    assert candidate.meta["epochs"] > parent.meta["epochs"]
    assert candidate.meta["steps"] > parent.meta["steps"]
    assert rnd.saved_state is not None
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["rounds"][-1]["candidate_artifact_id"] == "candidate-1"
    assert rnd.finished is not None
    assert rnd.finished["model_call_ids"] == ["call-1", "call-2"]
    assert rnd.finished["history_ids"] == ["history-0"]

    sample = SimpleNamespace(task=task, inputs={"features": [1.5, 1.0]}, dataset_key="opaque-task")
    prediction = predict(sample, Path(rnd.submitted["directory"]))
    if task == "classification":
        assert {item["label"] for item in prediction} == {"cold", "hot"}
        assert all(0.0 <= item["score"] <= 1.0 for item in prediction)
        assert sum(item["score"] for item in prediction) == pytest.approx(1.0)
    else:
        assert set(prediction) == {"value"}
        assert isinstance(prediction["value"], float)
        assert prediction["value"] >= 0.0
