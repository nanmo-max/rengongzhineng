from __future__ import annotations

import json
from pathlib import Path


def test_audit_log_writes_only_allowlisted_aggregate_fields(tmp_path: Path) -> None:
    from brace_msi.audit import JsonlAuditLog

    path = tmp_path / "events.jsonl"
    logger = JsonlAuditLog(path)
    logger.write(
        "batch_scored",
        {
            "batch_id": "dev-1",
            "sample_count": 8,
            "primary_metric": 0.75,
            "raw_features": [[999.0]],
            "targets": [1, 0],
            "sample_ids": ["secret-id"],
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["proxy_only"] is True
    assert payload["event"] == "batch_scored"
    assert payload["batch_id"] == "dev-1"
    assert "raw_features" not in payload
    assert "targets" not in payload
    assert "sample_ids" not in payload
    assert "secret-id" not in path.read_text(encoding="utf-8")
