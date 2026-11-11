"""Immutable three-phase manifests and one-shot terminal access locks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ExposureClass(str, Enum):
    VIRGIN_TERMINAL = "virgin_terminal"
    HISTORICALLY_EXPOSED_TERMINAL = "historically_exposed_terminal"
    DEVELOPMENT_ONLY = "development_only"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


@dataclass(frozen=True)
class PhaseManifest:
    task_key: str
    bootstrap_sample_ids: tuple[str, ...]
    development_sample_ids: tuple[str, ...]
    terminal_sample_ids: tuple[str, ...]
    bootstrap_group_ids: tuple[str, ...]
    development_group_ids: tuple[str, ...]
    terminal_group_ids: tuple[str, ...]
    terminal_exposure: ExposureClass
    source_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["terminal_exposure"] = self.terminal_exposure.value
        return payload

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _duplicates(values: tuple[str, ...]) -> bool:
    return len(values) != len(set(values))


def validate_phase_manifest(manifest: PhaseManifest) -> dict[str, Any]:
    if not manifest.task_key or not manifest.task_key.strip():
        raise ValueError("task_key is required")
    phases = {
        "bootstrap_train": manifest.bootstrap_sample_ids,
        "policy_development": manifest.development_sample_ids,
        "terminal_test": manifest.terminal_sample_ids,
    }
    if any(not values for values in phases.values()):
        raise ValueError("all three phases require samples")
    if any(_duplicates(values) for values in phases.values()):
        raise ValueError("duplicate sample ID within a phase")
    phase_sets = [set(values) for values in phases.values()]
    if any(
        phase_sets[left] & phase_sets[right]
        for left in range(len(phase_sets))
        for right in range(left + 1, len(phase_sets))
    ):
        raise ValueError("sample IDs overlap across phases")

    groups = (
        set(manifest.bootstrap_group_ids),
        set(manifest.development_group_ids),
        set(manifest.terminal_group_ids),
    )
    if any(
        groups[left] & groups[right]
        for left in range(len(groups))
        for right in range(left + 1, len(groups))
    ):
        raise ValueError("group IDs overlap across phases")
    if not manifest.source_sha256 or any(
        not _SHA256.fullmatch(value.lower()) for value in manifest.source_sha256
    ):
        raise ValueError("source_sha256 must contain valid SHA-256 values")
    return {
        "valid": True,
        "manifest_sha256": manifest.sha256,
        "phase_counts": {name: len(values) for name, values in phases.items()},
        "terminal_exposure": manifest.terminal_exposure.value,
    }


class TerminalLock:
    """Persist a frozen development identity and permit one terminal opening."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @staticmethod
    def _identity(
        *, manifest_sha256: str, config_sha256: str, source_commit: str
    ) -> dict[str, str]:
        if not _SHA256.fullmatch(manifest_sha256.lower()):
            raise ValueError("manifest_sha256 must be a SHA-256")
        if not _SHA256.fullmatch(config_sha256.lower()):
            raise ValueError("config_sha256 must be a SHA-256")
        if not source_commit or not source_commit.strip():
            raise ValueError("source_commit is required")
        return {
            "manifest_sha256": manifest_sha256.lower(),
            "config_sha256": config_sha256.lower(),
            "source_commit": source_commit,
        }

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise PermissionError("terminal is not frozen") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("terminal lock is invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("terminal lock must be an object")
        return payload

    def freeze(
        self, *, manifest_sha256: str, config_sha256: str, source_commit: str
    ) -> dict[str, Any]:
        identity = self._identity(
            manifest_sha256=manifest_sha256,
            config_sha256=config_sha256,
            source_commit=source_commit,
        )
        if self.path.exists():
            payload = self._read()
            if any(payload.get(key) != value for key, value in identity.items()):
                raise ValueError("frozen identity mismatch")
            return payload
        payload: dict[str, Any] = {
            "format": "brace-msi.terminal-lock.v1",
            **identity,
            "frozen": True,
            "terminal_open_count": 0,
        }
        _atomic_json(self.path, payload)
        return payload

    def open_terminal(
        self, *, manifest_sha256: str, config_sha256: str, source_commit: str
    ) -> dict[str, Any]:
        identity = self._identity(
            manifest_sha256=manifest_sha256,
            config_sha256=config_sha256,
            source_commit=source_commit,
        )
        payload = self._read()
        if not payload.get("frozen"):
            raise PermissionError("terminal is not frozen")
        if any(payload.get(key) != value for key, value in identity.items()):
            raise ValueError("frozen identity mismatch")
        if int(payload.get("terminal_open_count", 0)) != 0:
            raise PermissionError("terminal was already opened")
        payload["terminal_open_count"] = 1
        _atomic_json(self.path, payload)
        return payload
