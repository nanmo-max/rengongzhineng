"""Private audit and offline-safe public aggregate record interfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PUBLIC_FIELDS = frozenset(
    {
        "task_id",
        "task_kind",
        "protocol_mode",
        "phase",
        "batch_id",
        "batch_index",
        "sample_count",
        "primary_metric",
        "secondary_metric",
        "diagnosis",
        "performance_drop",
        "drift_score",
        "action",
        "accepted",
        "reason",
        "validation_improvement",
        "training_samples",
        "wall_seconds",
        "cpu_seconds",
        "peak_rss_bytes",
        "candidate_count",
        "rollback_count",
        "deployed_version",
        "status",
        "training_started",
    }
)


class LocalPublicSpool:
    """Aggregate JSONL queue; it does not claim official SwanLab synchronization."""

    def __init__(self, path: Path, *, truncate: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if truncate:
            self.path.write_text("", encoding="utf-8")
        self._record_ids: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    record_id = json.loads(line).get("record_id")
                except json.JSONDecodeError:
                    continue
                if isinstance(record_id, str):
                    self._record_ids.add(record_id)

    def record(self, event: str, payload: dict[str, Any]) -> None:
        self._append(event, payload, record_id=None)

    def record_once(self, record_id: str, event: str, payload: dict[str, Any]) -> None:
        if record_id in self._record_ids:
            return
        self._append(event, payload, record_id=record_id)
        self._record_ids.add(record_id)

    def _append(
        self, event: str, payload: dict[str, Any], *, record_id: str | None
    ) -> None:
        safe = {key: value for key, value in payload.items() if key in PUBLIC_FIELDS}
        record = {
            "schema_version": 1,
            "proxy_only": True,
            "event": event,
            "sync_status": "pending",
            **safe,
        }
        if record_id is not None:
            record["record_id"] = record_id
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
