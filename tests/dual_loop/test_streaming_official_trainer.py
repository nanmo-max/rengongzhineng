from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from brace_msi.official_package import audit_package_root
from brace_msi.official_trainer import CandidateConfig, OfficialTrainer


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


@pytest.fixture(scope="module")
def audit_a():
    config = json.loads(
        (REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8")
    )
    return audit_package_root(PACKAGE_ROOT, config)["A"]


def _write_subset(source: Path, target: Path, start: int, stop: int) -> tuple[str, ...]:
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line]
    selected = lines[start:stop]
    target.write_text("\n".join(selected) + "\n", encoding="utf-8", newline="\n")
    return tuple(json.loads(line)["id"] for line in selected)


def test_stream_candidate_continues_official_parent_on_materialized_update_and_gate(
    tmp_path: Path, audit_a
) -> None:
    train_path = tmp_path / "update.jsonl"
    gate_path = tmp_path / "gate.jsonl"
    train_ids = _write_subset(audit_a.validation_path, train_path, 0, 96)
    gate_ids = _write_subset(audit_a.validation_path, gate_path, 96, 128)
    output = tmp_path / "candidate"

    receipt = OfficialTrainer(
        __import__("sys").executable,
        timeout_seconds=60,
        allowed_learning_rate_multipliers=(1.0,),
    ).run_stream_candidate(
        audit_a,
        audit_a.checkpoint_path,
        train_path,
        gate_path,
        output,
        CandidateConfig(1, audit_a.base_learning_rate, audit_a.base_batch_size),
        "stream-a-round-01",
        allowed_train_ids=frozenset(train_ids),
        allowed_gate_ids=frozenset(gate_ids),
    )

    assert receipt.parent_sha256 == audit_a.checkpoint_sha256
    assert receipt.checkpoint_sha256 == hashlib.sha256(
        (output / "checkpoint.npz").read_bytes()
    ).hexdigest()
    assert receipt.initial_epochs == audit_a.initial_epochs
    assert receipt.final_epochs == audit_a.initial_epochs + 1
    assert receipt.model_state_changed and receipt.optimizer_state_changed
    assert (output / "checkpoint.npz").stat().st_size < 64 * 1024 * 1024
    with np.load(audit_a.checkpoint_path, allow_pickle=False) as parent, np.load(
        output / "checkpoint.npz", allow_pickle=False
    ) as child:
        assert np.array_equal(parent["mean"], child["mean"])
        assert np.array_equal(parent["scale"], child["scale"])


def test_stream_candidate_rejects_manifest_identity_mismatch(tmp_path: Path, audit_a) -> None:
    train_path = tmp_path / "update.jsonl"
    gate_path = tmp_path / "gate.jsonl"
    train_ids = _write_subset(audit_a.validation_path, train_path, 0, 32)
    gate_ids = _write_subset(audit_a.validation_path, gate_path, 32, 48)

    with pytest.raises(ValueError, match="manifest IDs"):
        OfficialTrainer(
            __import__("sys").executable,
            allowed_learning_rate_multipliers=(1.0,),
        ).run_stream_candidate(
            audit_a,
            audit_a.checkpoint_path,
            train_path,
            gate_path,
            tmp_path / "candidate",
            CandidateConfig(1, audit_a.base_learning_rate, audit_a.base_batch_size),
            "stream-a-invalid",
            allowed_train_ids=frozenset((*train_ids, "future-decoy")),
            allowed_gate_ids=frozenset(gate_ids),
        )
