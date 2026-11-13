from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brace_msi.online_data import (
    BufferRole,
    candidate_training_data,
    materialize_round_data,
    partition_feedback,
    partition_initial_data,
    promote_gate_to_replay,
)


def _classification_data(n: int = 30) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    X = np.arange(n * 3, dtype=np.float64).reshape(n, 3)
    y = np.asarray([index % 3 for index in range(n)], dtype=np.int64)
    sample_ids = tuple(f"sample-{index:03d}" for index in range(n))
    return X, y, sample_ids


def test_initial_and_feedback_roles_are_disjoint_and_read_only() -> None:
    X, y, sample_ids = _classification_data()

    update, anchor = partition_initial_data(
        X,
        y,
        sample_ids,
        task_kind="classification",
        batch_id="initial",
        anchor_fraction=0.1,
        seed=20261113,
    )
    feedback_update, gate = partition_feedback(
        X,
        y,
        sample_ids,
        task_kind="classification",
        batch_id="batch-1",
        round_index=1,
        gate_fraction=0.2,
        seed=20261113,
    )

    assert update.role is BufferRole.UPDATE
    assert anchor.role is BufferRole.ANCHOR
    assert feedback_update.role is BufferRole.UPDATE
    assert gate.role is BufferRole.GATE
    assert set(update.sample_ids).isdisjoint(anchor.sample_ids)
    assert set(feedback_update.sample_ids).isdisjoint(gate.sample_ids)
    assert set(update.sample_ids) | set(anchor.sample_ids) == set(sample_ids)
    assert set(feedback_update.sample_ids) | set(gate.sample_ids) == set(sample_ids)
    assert not update.X.flags.writeable
    assert not gate.y.flags.writeable


def test_gate_requires_one_complete_round_before_replay() -> None:
    X, y, sample_ids = _classification_data()
    _, gate = partition_feedback(
        X,
        y,
        sample_ids,
        task_kind="classification",
        batch_id="batch-2",
        round_index=2,
        seed=7,
    )

    assert gate.eligible_replay_round == 4
    with pytest.raises(ValueError, match="embargo"):
        promote_gate_to_replay(gate, current_round=3)

    replay = promote_gate_to_replay(gate, current_round=4)
    assert replay.role is BufferRole.REPLAY
    assert replay.sample_ids == gate.sample_ids
    assert replay.origin_role is BufferRole.GATE


def test_candidate_training_set_is_exactly_update_plus_eligible_replay() -> None:
    X, y, sample_ids = _classification_data()
    update, gate = partition_feedback(
        X,
        y,
        sample_ids,
        task_kind="classification",
        batch_id="batch-1",
        round_index=1,
        seed=11,
    )
    replay = promote_gate_to_replay(gate, current_round=3)

    train_X, train_y, train_ids = candidate_training_data(
        update,
        replay_buffers=[replay],
        current_round=3,
        include_replay=True,
    )

    assert train_X.shape[0] == len(update) + len(replay)
    assert train_y.shape[0] == train_X.shape[0]
    assert train_ids == update.sample_ids + replay.sample_ids
    assert set(train_ids).isdisjoint(set(sample_ids) - set(update.sample_ids) - set(replay.sample_ids))

    with pytest.raises(ValueError, match="ANCHOR"):
        candidate_training_data(
            update,
            replay_buffers=[update.with_role(BufferRole.ANCHOR)],
            current_round=3,
            include_replay=True,
        )


def test_worker_materialization_excludes_gate_anchor_and_future_decoy(tmp_path: Path) -> None:
    X, y, sample_ids = _classification_data()
    update, anchor = partition_initial_data(
        X,
        y,
        sample_ids,
        task_kind="classification",
        batch_id="initial",
        seed=3,
    )
    _, gate = partition_feedback(
        X,
        y,
        sample_ids,
        task_kind="classification",
        batch_id="batch-1",
        round_index=1,
        seed=5,
    )
    replay = promote_gate_to_replay(gate, current_round=3)

    source_root = tmp_path / "official-source"
    source_root.mkdir()
    future_decoy = source_root / "batch-4-FUTURE-SECRET.npz"
    np.savez(future_decoy, X=np.asarray([[999.0]]), y=np.asarray([999.0]))

    materialized = materialize_round_data(
        tmp_path / "round-3",
        round_index=3,
        update=update,
        replay_buffers=[replay],
        gate=gate,
        anchor=anchor,
    )

    worker_handle = materialized.training
    assert set(worker_handle.roles) == {BufferRole.UPDATE, BufferRole.REPLAY}
    assert all(not Path(entry.relative_path).is_absolute() for entry in worker_handle.manifest.entries)
    assert "official-source" not in worker_handle.manifest.to_json()
    assert "FUTURE-SECRET" not in worker_handle.manifest.to_json()
    assert future_decoy.exists()
    assert not any("FUTURE" in path.name for path in worker_handle.root.rglob("*"))
    with pytest.raises(ValueError, match="outside dataset handle"):
        worker_handle.resolve("../official-source/batch-4-FUTURE-SECRET.npz")

    assert set(materialized.evaluation.roles) == {BufferRole.GATE, BufferRole.ANCHOR}
    assert worker_handle.root != materialized.evaluation.root
