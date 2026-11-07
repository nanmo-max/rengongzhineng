"""Atomic local model registry with explicit rollback history."""

from __future__ import annotations

import json
import os
import pickle
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .bootstrap import TaskSignature
from .modeling import CpuModelAdapter

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class RegistryRecord:
    version: str
    model: CpuModelAdapter
    signature: TaskSignature


def _validated_identifier(value: str) -> str:
    if not value or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError("identifier contains unsafe characters")
    return value


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class ModelRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _task_root(self, task_id: str) -> Path:
        return self.root / _validated_identifier(task_id)

    def _manifest_path(self, task_id: str) -> Path:
        return self._task_root(task_id) / "manifest.json"

    def _manifest(self, task_id: str) -> dict[str, object]:
        path = self._manifest_path(task_id)
        if not path.exists():
            return {"schema_version": 1, "current": None, "history": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def deploy(
        self,
        *,
        task_id: str,
        version: str,
        model: CpuModelAdapter,
        signature: TaskSignature,
    ) -> None:
        task_root = self._task_root(task_id)
        version = _validated_identifier(version)
        manifest = self._manifest(task_id)
        history = list(manifest["history"])
        if version in history:
            raise ValueError(f"model version already exists: {version}")
        payload = {"model": model, "signature": signature}
        _atomic_bytes(task_root / f"{version}.pkl", pickle.dumps(payload))
        history.append(version)
        updated = {"schema_version": 1, "current": version, "history": history}
        _atomic_bytes(
            task_root / "manifest.json",
            (json.dumps(updated, sort_keys=True) + "\n").encode("utf-8"),
        )

    def current_version(self, task_id: str) -> str:
        current = self._manifest(task_id).get("current")
        if not isinstance(current, str):
            raise KeyError(f"task has no deployed model: {task_id}")
        return current

    def load_stable(self, task_id: str) -> RegistryRecord:
        version = self.current_version(task_id)
        path = self._task_root(task_id) / f"{version}.pkl"
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        return RegistryRecord(version, payload["model"], payload["signature"])

    def rollback(self, task_id: str) -> str:
        manifest = self._manifest(task_id)
        history = list(manifest["history"])
        if len(history) < 2:
            raise RuntimeError("no previous deployed model is available")
        history.pop()
        previous = history[-1]
        updated = {"schema_version": 1, "current": previous, "history": history}
        _atomic_bytes(
            self._manifest_path(task_id),
            (json.dumps(updated, sort_keys=True) + "\n").encode("utf-8"),
        )
        return previous
