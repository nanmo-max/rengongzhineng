"""Legal replay rows and historical artifact references persisted in official state."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .data import DataBatch
from .model import FormalModel
from .workspace import OFFICIAL_STATE_BYTE_LIMIT as _DEFAULT_STATE_BYTE_LIMIT


OFFICIAL_STATE_BYTE_LIMIT = _DEFAULT_STATE_BYTE_LIMIT
_FORMAT = "brace-formal-history.v1"
_METADATA = "history.json"
_DATA = "history-data.npz"


@dataclass(frozen=True)
class HistoryArtifactRef:
    history_id: str
    round_index: int
    artifact_id: str

    @classmethod
    def from_history_record(cls, record: Mapping[str, Any]) -> "HistoryArtifactRef":
        history_id = record.get("id")
        round_index = record.get("round_index")
        artifact_id = record.get("selected_artifact_id")
        if not isinstance(history_id, str) or not history_id:
            raise ValueError("history record id is required")
        if type(round_index) is not int or round_index < 1:
            raise ValueError("history round_index must be positive")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("history selected_artifact_id is required")
        return cls(history_id, round_index, artifact_id)

    def restore(self, rnd: Any, directory: Path | str) -> Path:
        return Path(rnd.restore_artifact(self.artifact_id, directory))


@dataclass(frozen=True)
class _Entry:
    round_index: int
    batch: DataBatch


class HistoryStore:
    def __init__(
        self,
        model: FormalModel,
        entries: list[_Entry] | None = None,
        audits: list[dict[str, Any]] | None = None,
    ) -> None:
        self._task = str(model.meta["task"])
        self._paths = tuple(str(path) for path in model.meta["paths"])
        self._entries = list(entries or [])
        self._audits = [dict(item) for item in audits or []]

    @property
    def round_indices(self) -> tuple[int, ...]:
        return tuple(entry.round_index for entry in self._entries)

    @property
    def audit_summaries(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self._audits)

    @classmethod
    def load(cls, state_root: Path | str, model: FormalModel) -> "HistoryStore":
        root = Path(state_root)
        metadata_path = root / _METADATA
        data_path = root / _DATA
        if not metadata_path.exists() and not data_path.exists():
            return cls(model)
        if (
            metadata_path.is_symlink()
            or data_path.is_symlink()
            or not metadata_path.is_file()
            or not data_path.is_file()
        ):
            raise ValueError("history state must contain regular files")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("history metadata is invalid") from exc
        if not isinstance(metadata, dict) or metadata.get("format") != _FORMAT:
            raise ValueError("history metadata is invalid")
        task = str(model.meta["task"])
        paths = list(model.meta["paths"])
        if metadata.get("task") != task:
            raise ValueError("history task differs from parent checkpoint")
        if metadata.get("feature_paths") != paths:
            raise ValueError("history feature schema differs from parent checkpoint")
        raw = data_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != metadata.get("data_sha256"):
            raise ValueError("history data digest is invalid")
        try:
            with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
                if set(archive.files) != {"ids", "x", "y", "rounds"}:
                    raise ValueError("history data schema is invalid")
                ids = tuple(str(value) for value in archive["ids"].tolist())
                x = archive["x"].copy()
                y = archive["y"].copy()
                rounds = archive["rounds"].copy()
        except (OSError, ValueError, KeyError) as exc:
            raise ValueError("history data could not be loaded") from exc
        if (
            x.ndim != 2
            or x.shape[1] != len(paths)
            or y.shape != (len(x),)
            or rounds.shape != (len(x),)
            or len(ids) != len(x)
            or len(ids) != len(set(ids))
            or not np.all(np.isfinite(x))
            or not np.all(np.isfinite(y))
        ):
            raise ValueError("history data is invalid")
        retained = metadata.get("retained_batches")
        audits = metadata.get("audit_summaries")
        if not isinstance(retained, list) or not isinstance(audits, list):
            raise ValueError("history metadata is invalid")
        entries: list[_Entry] = []
        offset = 0
        for item in retained:
            if not isinstance(item, dict):
                raise ValueError("history metadata is invalid")
            round_index = item.get("round_index")
            count = item.get("sample_count")
            source_sha256 = item.get("source_sha256")
            if type(round_index) is not int or round_index < 1 or type(count) is not int or count < 1:
                raise ValueError("history metadata is invalid")
            stop = offset + count
            if stop > len(ids) or not np.all(rounds[offset:stop] == round_index):
                raise ValueError("history data round mapping is invalid")
            entries.append(
                _Entry(
                    round_index,
                    DataBatch(ids[offset:stop], x[offset:stop], y[offset:stop], str(source_sha256)),
                )
            )
            offset = stop
        if offset != len(ids):
            raise ValueError("history data contains undeclared rows")
        return cls(model, entries, [dict(item) for item in audits if isinstance(item, dict)])

    def append(self, batch: DataBatch, round_index: int) -> None:
        if type(round_index) is not int or round_index < 1:
            raise ValueError("round index must be positive")
        previous_round = max((int(item["round_index"]) for item in self._audits), default=0)
        if round_index != previous_round + 1:
            raise ValueError("history rounds must be contiguous")
        if batch.x.ndim != 2 or batch.x.shape[1] != len(self._paths):
            raise ValueError("history feature schema differs from parent checkpoint")
        if batch.y.shape != (len(batch.x),) or len(batch.ids) != len(batch.x):
            raise ValueError("history batch shapes are inconsistent")
        if not np.all(np.isfinite(batch.x)) or not np.all(np.isfinite(batch.y)):
            raise ValueError("history rows must be finite")
        known = {identity for entry in self._entries for identity in entry.batch.ids}
        if known.intersection(batch.ids) or len(batch.ids) != len(set(batch.ids)):
            raise ValueError("duplicate sample ID in history")
        copied = DataBatch(tuple(batch.ids), batch.x.copy(), batch.y.copy(), str(batch.sha256))
        self._entries.append(_Entry(round_index, copied))
        self._audits.append(
            {
                "round_index": round_index,
                "sample_count": len(batch.ids),
                "source_sha256": str(batch.sha256),
                "retained": True,
            }
        )

    def training_batch(self, policy: str, current: DataBatch) -> DataBatch:
        if policy == "current":
            return current
        history = [entry.batch for entry in self._entries]
        if policy == "history_only":
            if not history:
                raise ValueError("history is empty")
            return DataBatch.concat(history)
        if policy == "current_plus_history":
            return DataBatch.concat([*history, current]) if history else current
        raise ValueError("unknown history policy")

    def monitoring_reference(
        self, *, minimum_windows: int = 3, maximum_windows: int = 3
    ) -> tuple[DataBatch, np.ndarray] | None:
        """Return a frozen legal-window reference and its real round blocks.

        This read-only view is separate from replay selection.  It never
        invents grouping from row order: every block identifier is the round
        in which the retained batch legally arrived.
        """

        if type(minimum_windows) is not int or minimum_windows < 1:
            raise ValueError("minimum_windows must be a positive integer")
        if type(maximum_windows) is not int or maximum_windows < minimum_windows:
            raise ValueError("maximum_windows must be at least minimum_windows")
        selected = self._entries[:maximum_windows]
        if len(selected) < minimum_windows:
            return None
        batch = DataBatch.concat(entry.batch for entry in selected)
        blocks = np.concatenate(
            [np.full(len(entry.batch.ids), entry.round_index, dtype=np.int64) for entry in selected]
        )
        return batch, blocks

    def _archive(self, entries: list[_Entry]) -> bytes:
        if entries:
            ids = np.asarray([identity for entry in entries for identity in entry.batch.ids], dtype=np.str_)
            x = np.concatenate([entry.batch.x for entry in entries], axis=0)
            y = np.concatenate([entry.batch.y for entry in entries], axis=0)
            rounds = np.concatenate(
                [np.full(len(entry.batch.ids), entry.round_index, dtype=np.int64) for entry in entries]
            )
        else:
            ids = np.asarray([], dtype=np.str_)
            x = np.empty((0, len(self._paths)), dtype=np.float64)
            y_dtype = np.int64 if self._task == "classification" else np.float64
            y = np.asarray([], dtype=y_dtype)
            rounds = np.asarray([], dtype=np.int64)
        stream = io.BytesIO()
        np.savez_compressed(stream, ids=ids, x=x, y=y, rounds=rounds)
        return stream.getvalue()

    def _metadata(self, retained: list[_Entry], archive: bytes) -> bytes:
        retained_rounds = {entry.round_index for entry in retained}
        audits = [
            {**item, "retained": int(item["round_index"]) in retained_rounds}
            for item in self._audits
        ]
        payload = {
            "format": _FORMAT,
            "task": self._task,
            "feature_paths": list(self._paths),
            "data_sha256": hashlib.sha256(archive).hexdigest(),
            "retained_batches": [
                {
                    "round_index": entry.round_index,
                    "sample_count": len(entry.batch.ids),
                    "source_sha256": entry.batch.sha256,
                }
                for entry in retained
            ],
            "audit_summaries": audits,
        }
        return (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")

    def save(self, state_root: Path | str) -> None:
        root = Path(state_root)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("state root must be a regular directory")
        selected: list[_Entry] = []
        selected_archive = self._archive(selected)
        selected_metadata = self._metadata(selected, selected_archive)
        for count in range(1, len(self._entries) + 1):
            candidate = self._entries[-count:]
            archive = self._archive(candidate)
            metadata = self._metadata(candidate, archive)
            if len(archive) + len(metadata) <= OFFICIAL_STATE_BYTE_LIMIT:
                selected, selected_archive, selected_metadata = candidate, archive, metadata
        if len(selected_archive) + len(selected_metadata) > OFFICIAL_STATE_BYTE_LIMIT:
            raise ValueError("history audit metadata exceeds official state limit")
        data_tmp = root / (_DATA + ".tmp")
        metadata_tmp = root / (_METADATA + ".tmp")
        data_tmp.write_bytes(selected_archive)
        metadata_tmp.write_bytes(selected_metadata)
        os.replace(data_tmp, root / _DATA)
        os.replace(metadata_tmp, root / _METADATA)
        self._entries = list(selected)
        self._audits = json.loads(selected_metadata)["audit_summaries"]
