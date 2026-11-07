"""Optional, offline-first SwanLab export for aggregate public records."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

from .recording import PUBLIC_FIELDS


@dataclass(frozen=True)
class SwanLabOfflineConfig:
    project: str
    experiment_name: str
    logdir: Path
    public: bool = False


@dataclass(frozen=True)
class SwanLabExportResult:
    logdir: Path
    record_count: int


def _load_swanlab() -> ModuleType:
    try:
        return importlib.import_module("swanlab")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "SwanLab is optional; install the pinned requirements-swanlab.lock "
            "before exporting official offline logs"
        ) from exc


def _metric_payload(record: dict[str, Any], step: int) -> dict[str, float | int]:
    payload: dict[str, float | int] = {"brace/event_index": step}
    for key, value in record.items():
        if key not in PUBLIC_FIELDS:
            continue
        if isinstance(value, bool):
            payload[f"brace/{key}"] = int(value)
        elif isinstance(value, (int, float)):
            payload[f"brace/{key}"] = value
    return payload


def _ensure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        reconfigure = getattr(stream, "reconfigure", None)
        if isinstance(encoding, str) and encoding.lower().replace("-", "") != "utf8":
            if callable(reconfigure):
                reconfigure(encoding="utf-8")


def export_public_spool(
    spool_path: Path,
    config: SwanLabOfflineConfig,
    *,
    swanlab_module: Any | None = None,
) -> SwanLabExportResult:
    """Convert the aggregate JSONL spool into official SwanLab offline logs.

    This function never performs cloud synchronization. The user must inspect the
    generated run directory and explicitly execute the command returned by
    :func:`build_sync_command` after the competition policy is confirmed.
    """

    spool_path = Path(spool_path)
    records = [
        json.loads(line)
        for line in spool_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    _ensure_utf8_console()
    config.logdir.mkdir(parents=True, exist_ok=True)
    swanlab = swanlab_module if swanlab_module is not None else _load_swanlab()
    run = swanlab.init(
        project=config.project,
        experiment_name=config.experiment_name,
        description="BRACE-MSI aggregate training audit",
        logdir=str(config.logdir),
        mode="offline",
        public=config.public,
        config={
            "brace_schema_version": 1,
            "source": "aggregate_public_spool",
            "record_count": len(records),
        },
    )
    try:
        for step, record in enumerate(records):
            run.log(_metric_payload(record, step), step=step)
    finally:
        swanlab.finish()
    return SwanLabExportResult(config.logdir, len(records))


def build_sync_command(
    run_dir: Path,
    *,
    workspace: str | None = None,
    project: str | None = None,
) -> tuple[str, ...]:
    """Return, but never execute, the official explicit sync command."""

    command = ["swanlab", "sync", str(Path(run_dir))]
    if workspace:
        command.extend(("--workspace", workspace))
    if project:
        command.extend(("--project", project))
    return tuple(command)
