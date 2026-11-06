"""Allowlisted aggregate JSONL audit logging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOWED_FIELDS = frozenset(
    {
        "task_id",
        "policy",
        "phase",
        "batch_id",
        "batch_index",
        "sample_count",
        "primary_metric",
        "secondary_metric",
        "performance_drop",
        "drift_score",
        "action",
        "budget_allowed",
        "accepted",
        "reason",
        "validation_improvement",
        "anchor_degradation",
        "training_samples",
        "wall_seconds",
        "cpu_seconds",
        "peak_rss_bytes",
    }
)


class JsonlAuditLog:
    def __init__(self, path: Path, *, truncate: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if truncate:
            self.path.write_text("", encoding="utf-8")

    def write(self, event: str, payload: dict[str, Any]) -> None:
        safe_payload = {
            key: value for key, value in payload.items() if key in ALLOWED_FIELDS
        }
        record = {"schema_version": 1, "proxy_only": True, "event": event}
        record.update(safe_payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
