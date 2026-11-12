"""Build a privacy-safe SwanLab spool from an immutable formal run."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FinalRecordResult:
    output_path: Path
    record_count: int


def build_swanlab_spool(
    runtime_dir: Path,
    output_path: Path,
    *,
    task_id: str,
    task_kind: str,
    primary_metric_name: str,
    secondary_metric_name: str | None,
    higher_is_better: bool,
) -> FinalRecordResult:
    """Convert a validated run audit into aggregate, non-reversible records."""

    runtime_dir = Path(runtime_dir)
    output_path = Path(output_path)
    state = json.loads((runtime_dir / "state.json").read_text(encoding="utf-8"))
    audit_rows = [
        json.loads(line)
        for line in (runtime_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rounds = state.get("rounds")
    if not isinstance(rounds, list) or audit_rows != rounds:
        raise ValueError("audit log does not match state")

    stable_primary = float(state["initial_metric"])
    initial_metrics = state.get("initial_metrics", {})
    stable_secondary = (
        float(initial_metrics[secondary_metric_name])
        if secondary_metric_name and secondary_metric_name in initial_metrics
        else None
    )
    candidate_count = 0
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rounds, start=1):
        kind = str(row.get("kind", "unknown"))
        training_started = kind == "candidate"
        accepted = bool(row.get("deployed", False)) if training_started else False
        improvement = 0.0
        if training_started:
            candidate_count += 1
            metric_before = float(row["metric_before"])
            metric_after = float(row["metric_after"])
            improvement = (
                metric_after - metric_before
                if higher_is_better
                else metric_before - metric_after
            )
            if accepted:
                stable_primary = metric_after
                metrics_after = row.get("metrics_after", {})
                if (
                    secondary_metric_name
                    and secondary_metric_name in metrics_after
                ):
                    stable_secondary = float(metrics_after[secondary_metric_name])

        status = "accepted" if accepted else "rejected" if training_started else "skipped"
        record: dict[str, Any] = {
            "schema_version": 1,
            "official_package": True,
            "official_scoring_ready": False,
            "event": "formal_training_round",
            "sync_status": "pending",
            "task_id": task_id,
            "task_kind": task_kind,
            "phase": kind,
            "batch_index": index,
            "primary_metric": stable_primary,
            "action": str(row.get("action", "unknown")),
            "accepted": accepted,
            "reason": str(row.get("gate_reason", row.get("reason", ""))),
            "validation_improvement": improvement,
            "wall_seconds": float(row.get("wall_seconds", 0.0)),
            "cpu_seconds": float(row.get("cpu_seconds", 0.0)),
            "peak_rss_bytes": int(row.get("peak_rss_bytes", 0)),
            "candidate_count": candidate_count,
            "rollback_count": 0,
            "status": status,
            "training_started": training_started,
        }
        if stable_secondary is not None:
            record["secondary_metric"] = stable_secondary
        records.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    return FinalRecordResult(output_path=output_path, record_count=len(records))

