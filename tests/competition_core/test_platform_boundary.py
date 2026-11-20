from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from brace_formal import submission
from brace_formal.model import FormalModel
from contest_harness.errors import HarnessError
from contest_harness.round import Round
from tests.competition_core.support import make_round


def _frame(parent_digest: str) -> dict[str, object]:
    return {
        "protocol": "contest.harness.workspace.v2",
        "prompt": "official prompt",
        "prompt_version": "1",
        "dataset_key": "A",
        "round_index": 1,
        "task_contract": {"task": "classification", "metric": "macro_f1"},
        "model_name": "host-model",
        "max_output_tokens": 256,
        "parent_checkpoint_sha256": "sha256:" + parent_digest,
        "parent_artifact": {
            "artifact_id": "parent-1",
            "artifact": {"checkpoint_paths": ["checkpoint.npz"], "code_paths": [], "predict_argv": ["predict"]},
            "files": [{"path": "checkpoint.npz", "sha256": "sha256:" + parent_digest, "size_bytes": 1}],
        },
        "artifacts": [],
    }


def test_official_round_rejects_empty_model_receipt() -> None:
    """Catches silent acceptance of a host response that cannot be cited at finish."""

    response = {"type": "model_response", "id": 0, "call_id": "", "response": {}}
    rnd = Round(_frame("0" * 64), io.StringIO(json.dumps(response) + "\n"), io.StringIO())

    with pytest.raises(HarnessError, match="MODEL_RECEIPT_INVALID"):
        rnd.model([{"role": "user", "content": "propose an experiment"}])


def test_official_parent_view_rejects_wrong_digest(tmp_path: Path) -> None:
    """Catches training from bytes that do not match the official parent receipt."""

    checkpoint = tmp_path / "checkpoint.npz"
    checkpoint.write_bytes(b"real parent bytes")
    wrong_digest = hashlib.sha256(b"different bytes").hexdigest()
    rnd = Round(_frame(wrong_digest), io.StringIO(), io.StringIO())
    rnd.parent.root = tmp_path

    with pytest.raises(HarnessError) as exc_info:
        rnd.parent.path("checkpoint.npz")
    assert exc_info.value.code == "PARENT_DIGEST_MISMATCH"


def test_unloadable_candidate_is_not_submitted_and_parent_is_retained(monkeypatch, tmp_path: Path) -> None:
    """Catches an unloadable candidate escaping the hard artifact gate."""

    rnd, _ = make_round(tmp_path, task="classification")
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))
    original_save = FormalModel.save

    def save_invalid(_self, path):
        Path(path).write_bytes(b"not an npz checkpoint")

    monkeypatch.setattr(FormalModel, "save", save_invalid)
    try:
        submission.train(rnd)
    finally:
        monkeypatch.setattr(FormalModel, "save", original_save)

    assert rnd.call_ids == ["call-1", "call-2"]
    assert rnd.submitted is None
    assert rnd.finished is not None
    assert rnd.finished["selected_artifact_id"] == "parent-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["rounds"][-1]["outcome"] == "candidate_rejected_by_safety_gate"
    assert state["rounds"][-1]["safety_failures"] == ["checkpoint_unloadable:ValueError"]
