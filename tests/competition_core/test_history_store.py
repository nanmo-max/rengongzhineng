from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from brace_formal.data import DataBatch
from brace_formal.history import HistoryArtifactRef, HistoryStore
from brace_formal.model import FormalModel
from tests.competition_core.support import write_parent


def _model(tmp_path: Path, *, task: str = "regression", feature_count: int = 2) -> FormalModel:
    path = tmp_path / f"{task}-{feature_count}.npz"
    write_parent(path, task=task, feature_count=feature_count)
    return FormalModel.load(path)


def _batch(prefix: str, rows: int, *, feature_count: int = 2, offset: float = 0.0) -> DataBatch:
    x = np.arange(rows * feature_count, dtype=np.float64).reshape(rows, feature_count) + offset
    y = np.arange(rows, dtype=np.float64) + offset
    return DataBatch(
        ids=tuple(f"{prefix}-{index}" for index in range(rows)),
        x=x,
        y=y,
        sha256=(prefix[0].lower() * 64),
    )


def test_data_batch_select_and_concat_preserve_rows_and_source_fingerprints() -> None:
    first = _batch("A", 3)
    second = _batch("B", 2, offset=10.0)

    selected = first.select([2, 0])
    combined = DataBatch.concat([selected, second])

    assert selected.ids == ("A-2", "A-0")
    np.testing.assert_array_equal(selected.x, first.x[[2, 0]])
    np.testing.assert_array_equal(selected.y, first.y[[2, 0]])
    assert selected.sha256 != first.sha256
    assert combined.ids == ("A-2", "A-0", "B-0", "B-1")
    np.testing.assert_array_equal(combined.x, np.concatenate([selected.x, second.x]))
    assert combined.sha256 not in {selected.sha256, second.sha256}


def test_history_store_exact_round_trip_and_legal_replay(tmp_path: Path) -> None:
    model = _model(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    first = _batch("A", 3)
    second = _batch("B", 2, offset=10.0)
    current = _batch("C", 1, offset=20.0)
    store = HistoryStore.load(state, model)
    store.append(first, round_index=1)
    store.append(second, round_index=2)

    store.save(state)
    restored = HistoryStore.load(state, model)
    replay = restored.training_batch("current_plus_history", current)

    assert restored.round_indices == (1, 2)
    assert replay.ids == first.ids + second.ids + current.ids
    np.testing.assert_array_equal(replay.x, np.concatenate([first.x, second.x, current.x]))
    assert restored.audit_summaries == (
        {"round_index": 1, "sample_count": 3, "source_sha256": first.sha256, "retained": True},
        {"round_index": 2, "sample_count": 2, "source_sha256": second.sha256, "retained": True},
    )


def test_history_rejects_duplicate_ids_and_future_round(tmp_path: Path) -> None:
    model = _model(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    store = HistoryStore.load(state, model)
    store.append(_batch("A", 2), round_index=1)

    with pytest.raises(ValueError, match="duplicate sample ID"):
        store.append(_batch("A", 2, offset=10.0), round_index=2)
    with pytest.raises(ValueError, match="contiguous"):
        store.append(_batch("C", 2), round_index=3)


def test_history_rejects_changed_feature_schema_and_corrupt_npz(tmp_path: Path) -> None:
    model = _model(tmp_path, feature_count=2)
    state = tmp_path / "state"
    state.mkdir()
    store = HistoryStore.load(state, model)
    store.append(_batch("A", 2), round_index=1)
    store.save(state)

    changed = _model(tmp_path, feature_count=3)
    with pytest.raises(ValueError, match="feature schema"):
        HistoryStore.load(state, changed)

    (state / "history-data.npz").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="history data"):
        HistoryStore.load(state, model)


def test_history_rejects_symlinked_state_file(tmp_path: Path) -> None:
    model = _model(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = state / "history.json"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows host")

    with pytest.raises(ValueError, match="regular files"):
        HistoryStore.load(state, model)


def test_history_preserves_all_audits_and_newest_complete_batches_near_limit(monkeypatch, tmp_path: Path) -> None:
    import brace_formal.history as history_module

    model = _model(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    first = _batch("A", 100, offset=0.0)
    newest = _batch("B", 100, offset=1000.0)
    store = HistoryStore.load(state, model)
    store.append(first, round_index=1)
    store.append(newest, round_index=2)
    monkeypatch.setattr(history_module, "OFFICIAL_STATE_BYTE_LIMIT", 2_500)

    store.save(state)
    restored = HistoryStore.load(state, model)

    assert len(restored.audit_summaries) == 2
    assert restored.audit_summaries[0]["retained"] is False
    assert restored.audit_summaries[1]["retained"] is True
    assert restored.round_indices == (2,)
    assert restored.training_batch("history_only", _batch("C", 1)).ids == newest.ids
    assert sum(path.stat().st_size for path in state.iterdir()) <= 2_500


def test_history_artifact_reference_restores_only_through_round_api(tmp_path: Path) -> None:
    record = {
        "id": "history-7",
        "round_index": 7,
        "selected_artifact_id": "artifact-7",
        "raw_data_path": "C:/must-not-be-read/train.jsonl",
    }
    reference = HistoryArtifactRef.from_history_record(record)
    calls: list[tuple[str, Path]] = []

    def restore_artifact(artifact_id, directory):
        calls.append((artifact_id, Path(directory)))
        Path(directory).mkdir()
        return Path(directory)

    restored = reference.restore(SimpleNamespace(restore_artifact=restore_artifact), tmp_path / "restored")

    assert reference == HistoryArtifactRef("history-7", 7, "artifact-7")
    assert calls == [("artifact-7", tmp_path / "restored")]
    assert restored == tmp_path / "restored"


def test_history_artifact_reference_rejects_missing_official_artifact_id() -> None:
    with pytest.raises(ValueError, match="selected_artifact_id"):
        HistoryArtifactRef.from_history_record({"id": "history-1", "round_index": 1})
