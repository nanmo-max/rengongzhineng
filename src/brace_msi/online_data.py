"""Prefix-safe online data capabilities for the controlled dual loop.

This module deliberately has no knowledge of official SDK field names.  The
runtime adapter passes the current event payload as arrays; workers receive
only materialized files described by an immutable manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from sklearn.model_selection import train_test_split


class BufferRole(str, Enum):
    ANCHOR = "anchor"
    UPDATE = "update"
    GATE = "gate"
    REPLAY = "replay"


def _readonly_copy(array: np.ndarray) -> np.ndarray:
    copied = np.array(array, copy=True)
    copied.setflags(write=False)
    return copied


@dataclass(frozen=True)
class BufferSlice:
    role: BufferRole
    batch_id: str
    sample_ids: tuple[str, ...]
    X: np.ndarray
    y: np.ndarray
    created_round: int
    eligible_replay_round: int | None = None
    origin_role: BufferRole | None = None

    def __post_init__(self) -> None:
        X = np.asarray(self.X)
        y = np.asarray(self.y)
        if X.ndim != 2:
            raise ValueError("X must be a two-dimensional numeric table")
        if y.ndim not in (1, 2):
            raise ValueError("y must be one- or two-dimensional")
        if X.shape[0] != y.shape[0] or X.shape[0] != len(self.sample_ids):
            raise ValueError("X, y, and sample_ids must have identical lengths")
        if len(set(self.sample_ids)) != len(self.sample_ids):
            raise ValueError("sample_ids must be unique within a buffer")
        object.__setattr__(self, "X", _readonly_copy(X))
        object.__setattr__(self, "y", _readonly_copy(y))
        object.__setattr__(self, "sample_ids", tuple(str(value) for value in self.sample_ids))

    def __len__(self) -> int:
        return len(self.sample_ids)

    def with_role(self, role: BufferRole) -> "BufferSlice":
        return replace(self, role=role, origin_role=self.role)


@dataclass(frozen=True)
class ManifestEntry:
    role: BufferRole
    batch_id: str
    relative_path: str
    sha256: str
    sample_count: int
    feature_count: int
    sample_id_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "batch_id": self.batch_id,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "sample_count": self.sample_count,
            "feature_count": self.feature_count,
            "sample_id_digest": self.sample_id_digest,
        }


@dataclass(frozen=True)
class RoundDataManifest:
    round_index: int
    channel: str
    entries: tuple[ManifestEntry, ...]
    allowed_batch_ids: tuple[str, ...]
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "round_index": self.round_index,
            "channel": self.channel,
            "allowed_batch_ids": list(self.allowed_batch_ids),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class DatasetHandle:
    """Capability object limited to files enumerated by its manifest."""

    root: Path
    manifest: RoundDataManifest

    @property
    def roles(self) -> tuple[BufferRole, ...]:
        return tuple(dict.fromkeys(entry.role for entry in self.manifest.entries))

    def resolve(self, relative_path: str) -> Path:
        requested = Path(relative_path)
        if requested.is_absolute():
            raise ValueError("path is outside dataset handle")
        allowed = {entry.relative_path for entry in self.manifest.entries}
        if requested.as_posix() not in allowed:
            raise ValueError("path is outside dataset handle")
        root = self.root.resolve()
        resolved = (root / requested).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("path is outside dataset handle") from exc
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        return resolved

    def load(self, entry: ManifestEntry) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
        path = self.resolve(entry.relative_path)
        with np.load(path, allow_pickle=False) as payload:
            X = np.asarray(payload["X"])
            y = np.asarray(payload["y"])
            sample_ids = tuple(str(value) for value in payload["sample_ids"].tolist())
        return X, y, sample_ids


@dataclass(frozen=True)
class RoundMaterialization:
    training: DatasetHandle
    evaluation: DatasetHandle


def _validate_common(
    X: np.ndarray,
    y: np.ndarray,
    sample_ids: Sequence[str],
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    array_X = np.asarray(X)
    array_y = np.asarray(y)
    ids = tuple(str(value) for value in sample_ids)
    if array_X.ndim != 2 or array_y.ndim not in (1, 2):
        raise ValueError("invalid tabular data shape")
    if len(ids) != array_X.shape[0] or array_y.shape[0] != array_X.shape[0]:
        raise ValueError("X, y, and sample_ids must have identical lengths")
    if len(ids) < 2:
        raise ValueError("at least two samples are required for partitioning")
    if len(set(ids)) != len(ids):
        raise ValueError("sample_ids must be unique")
    return array_X, array_y, ids


def _split_indices(
    y: np.ndarray,
    *,
    holdout_fraction: float,
    task_kind: str,
    seed: int,
    groups: Sequence[str] | None,
) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout fraction must be between zero and one")
    n_samples = y.shape[0]
    holdout_size = max(1, int(round(n_samples * holdout_fraction)))
    holdout_size = min(holdout_size, n_samples - 1)
    indices = np.arange(n_samples)

    if groups is not None:
        group_values = np.asarray([str(value) for value in groups])
        if group_values.shape[0] != n_samples:
            raise ValueError("groups must match sample count")
        ordered_groups = tuple(dict.fromkeys(group_values.tolist()))
        held_groups: list[str] = []
        held_count = 0
        for group in reversed(ordered_groups):
            held_groups.append(group)
            held_count += int(np.count_nonzero(group_values == group))
            if held_count >= holdout_size:
                break
        holdout_mask = np.isin(group_values, held_groups)
        return indices[~holdout_mask], indices[holdout_mask]

    if task_kind == "classification":
        labels = y.reshape(-1)
        unique, counts = np.unique(labels, return_counts=True)
        can_stratify = (
            unique.size > 1
            and np.all(counts >= 2)
            and holdout_size >= unique.size
            and n_samples - holdout_size >= unique.size
        )
        train, holdout = train_test_split(
            indices,
            test_size=holdout_size,
            random_state=seed,
            shuffle=True,
            stratify=labels if can_stratify else None,
        )
        return np.sort(train), np.sort(holdout)

    if task_kind != "regression":
        raise ValueError("task_kind must be classification or regression")
    split_at = n_samples - holdout_size
    return indices[:split_at], indices[split_at:]


def _slice(
    role: BufferRole,
    batch_id: str,
    X: np.ndarray,
    y: np.ndarray,
    ids: tuple[str, ...],
    indices: np.ndarray,
    *,
    created_round: int,
    eligible_replay_round: int | None = None,
) -> BufferSlice:
    return BufferSlice(
        role=role,
        batch_id=batch_id,
        sample_ids=tuple(ids[index] for index in indices.tolist()),
        X=X[indices],
        y=y[indices],
        created_round=created_round,
        eligible_replay_round=eligible_replay_round,
    )


def partition_initial_data(
    X: np.ndarray,
    y: np.ndarray,
    sample_ids: Sequence[str],
    *,
    task_kind: str,
    batch_id: str,
    anchor_fraction: float = 0.1,
    groups: Sequence[str] | None = None,
    seed: int = 20261113,
) -> tuple[BufferSlice, BufferSlice]:
    array_X, array_y, ids = _validate_common(X, y, sample_ids)
    update_indices, anchor_indices = _split_indices(
        array_y,
        holdout_fraction=anchor_fraction,
        task_kind=task_kind,
        seed=seed,
        groups=groups,
    )
    return (
        _slice(BufferRole.UPDATE, batch_id, array_X, array_y, ids, update_indices, created_round=0),
        _slice(BufferRole.ANCHOR, batch_id, array_X, array_y, ids, anchor_indices, created_round=0),
    )


def partition_feedback(
    X: np.ndarray,
    y: np.ndarray,
    sample_ids: Sequence[str],
    *,
    task_kind: str,
    batch_id: str,
    round_index: int,
    gate_fraction: float = 0.2,
    groups: Sequence[str] | None = None,
    seed: int = 20261113,
) -> tuple[BufferSlice, BufferSlice]:
    if round_index < 1:
        raise ValueError("round_index must be positive")
    array_X, array_y, ids = _validate_common(X, y, sample_ids)
    update_indices, gate_indices = _split_indices(
        array_y,
        holdout_fraction=gate_fraction,
        task_kind=task_kind,
        seed=seed,
        groups=groups,
    )
    return (
        _slice(
            BufferRole.UPDATE,
            batch_id,
            array_X,
            array_y,
            ids,
            update_indices,
            created_round=round_index,
        ),
        _slice(
            BufferRole.GATE,
            batch_id,
            array_X,
            array_y,
            ids,
            gate_indices,
            created_round=round_index,
            eligible_replay_round=round_index + 2,
        ),
    )


def promote_gate_to_replay(gate: BufferSlice, *, current_round: int) -> BufferSlice:
    if gate.role is not BufferRole.GATE:
        raise ValueError("only GATE buffers can be promoted")
    if gate.eligible_replay_round is None or current_round < gate.eligible_replay_round:
        raise ValueError("gate buffer is still under one-round embargo")
    return BufferSlice(
        role=BufferRole.REPLAY,
        batch_id=gate.batch_id,
        sample_ids=gate.sample_ids,
        X=gate.X,
        y=gate.y,
        created_round=gate.created_round,
        eligible_replay_round=gate.eligible_replay_round,
        origin_role=BufferRole.GATE,
    )


def candidate_training_data(
    update: BufferSlice,
    *,
    replay_buffers: Iterable[BufferSlice] = (),
    current_round: int,
    include_replay: bool,
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    if update.role is not BufferRole.UPDATE:
        raise ValueError("candidate training requires an UPDATE buffer")
    selected = [update]
    if include_replay:
        for replay in replay_buffers:
            if replay.role is not BufferRole.REPLAY:
                raise ValueError(f"{replay.role.name} buffers cannot enter candidate training")
            if replay.eligible_replay_round is None or current_round < replay.eligible_replay_round:
                raise ValueError("REPLAY buffer is not yet eligible")
            selected.append(replay)
    X = np.concatenate([buffer.X for buffer in selected], axis=0)
    y = np.concatenate([buffer.y for buffer in selected], axis=0)
    ids = tuple(sample_id for buffer in selected for sample_id in buffer.sample_ids)
    if len(set(ids)) != len(ids):
        raise ValueError("candidate training buffers contain duplicate sample IDs")
    X.setflags(write=False)
    y.setflags(write=False)
    return X, y, ids


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _id_digest(sample_ids: Sequence[str]) -> str:
    payload = "\n".join(sample_ids).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _materialize_channel(
    root: Path,
    *,
    round_index: int,
    channel: str,
    buffers: Sequence[BufferSlice],
) -> DatasetHandle:
    root.mkdir(parents=True, exist_ok=False)
    entries: list[ManifestEntry] = []
    for index, buffer in enumerate(buffers):
        filename = f"{index:02d}-{buffer.role.value}-{buffer.batch_id}.npz"
        if Path(filename).name != filename:
            raise ValueError("batch_id produces an unsafe materialized filename")
        path = root / filename
        np.savez_compressed(
            path,
            X=np.asarray(buffer.X),
            y=np.asarray(buffer.y),
            sample_ids=np.asarray(buffer.sample_ids, dtype=np.str_),
        )
        entries.append(
            ManifestEntry(
                role=buffer.role,
                batch_id=buffer.batch_id,
                relative_path=filename,
                sha256=_sha256(path),
                sample_count=len(buffer),
                feature_count=int(buffer.X.shape[1]),
                sample_id_digest=_id_digest(buffer.sample_ids),
            )
        )
    manifest = RoundDataManifest(
        round_index=round_index,
        channel=channel,
        entries=tuple(entries),
        allowed_batch_ids=tuple(dict.fromkeys(buffer.batch_id for buffer in buffers)),
    )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(manifest.to_json() + "\n", encoding="utf-8")
    for path in [*root.glob("*.npz"), manifest_path]:
        try:
            os.chmod(path, 0o444)
        except OSError:
            pass
    return DatasetHandle(root=root, manifest=manifest)


def materialize_round_data(
    round_root: Path,
    *,
    round_index: int,
    update: BufferSlice,
    replay_buffers: Iterable[BufferSlice],
    gate: BufferSlice,
    anchor: BufferSlice,
) -> RoundMaterialization:
    if round_index < 1:
        raise ValueError("round_index must be positive")
    if update.role is not BufferRole.UPDATE:
        raise ValueError("training channel requires UPDATE")
    if gate.role is not BufferRole.GATE or anchor.role is not BufferRole.ANCHOR:
        raise ValueError("evaluation channel requires GATE and ANCHOR")
    replays = tuple(replay_buffers)
    for replay in replays:
        if replay.role is not BufferRole.REPLAY:
            raise ValueError("training channel accepts only REPLAY history")
        if replay.eligible_replay_round is None or round_index < replay.eligible_replay_round:
            raise ValueError("training channel received embargoed REPLAY history")
    base = Path(round_root)
    base.mkdir(parents=True, exist_ok=False)
    training = _materialize_channel(
        base / "training",
        round_index=round_index,
        channel="training",
        buffers=(update, *replays),
    )
    evaluation = _materialize_channel(
        base / "evaluation",
        round_index=round_index,
        channel="evaluation",
        buffers=(gate, anchor),
    )
    return RoundMaterialization(training=training, evaluation=evaluation)
