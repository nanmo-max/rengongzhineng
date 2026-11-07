"""Atomic private checkpoints for bounded unattended execution."""

from __future__ import annotations

import os
import pickle
import tempfile
from pathlib import Path
from typing import Any


class CheckpointStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> dict[str, Any]:
        with self.path.open("rb") as handle:
            state = pickle.load(handle)
        if state.get("schema_version") != 1:
            raise RuntimeError("unsupported checkpoint schema")
        return state

    def save(self, state: dict[str, Any]) -> None:
        state = {"schema_version": 1, **state}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            pickle.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
