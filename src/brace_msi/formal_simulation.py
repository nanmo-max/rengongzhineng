"""Preregistered three-task engineering simulation without consumed sealed data."""

from __future__ import annotations

import json
import math
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np
import psutil

from .budget import BudgetLimits
from .data.types import TaskStream
from .harness import HarnessConfig, HarnessResult, UnifiedHarness
from .packaging import audit_docker_context
from .protocol import ProtocolMode
from .reporting import render_html_report
from .safety import GateConfig


@dataclass(frozen=True)
class SimulationConfig:
    experiment_id: str
    seed: int
    protocol_mode: ProtocolMode
    minimum_candidate_events: int
    synthetic_failure_candidates: tuple[int, ...]
    budget: BudgetLimits
    gates: dict[str, GateConfig]
    max_logical_cpus: int
    max_rss_bytes: int
    max_docker_context_bytes: int
    data_hashes: dict[str, str]


def load_simulation_config(path: Path) -> SimulationConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("proxy_only") is not True:
        raise ValueError("formal simulation must remain proxy_only")
    if payload.get("include_consumed_sealed") is not False:
        raise ValueError("formal simulation must exclude consumed sealed data")
    resources = payload["resource_acceptance"]
    return SimulationConfig(
        experiment_id=str(payload["experiment_id"]),
        seed=int(payload["seed"]),
        protocol_mode=ProtocolMode(payload["protocol_mode"]),
        minimum_candidate_events=int(payload["minimum_candidate_events_per_task"]),
        synthetic_failure_candidates=tuple(
            int(item) for item in payload["synthetic_failure_candidates"]
        ),
        budget=BudgetLimits(**payload["budget_per_task"]),
        gates={key: GateConfig(**value) for key, value in payload["gate"].items()},
        max_logical_cpus=int(resources["max_logical_cpus"]),
        max_rss_bytes=int(resources["max_rss_bytes"]),
        max_docker_context_bytes=int(resources["max_docker_context_bytes"]),
        data_hashes={str(key): str(value) for key, value in payload["data_hashes"].items()},
    )


@contextmanager
def _limited_cpu_affinity(max_cpus: int) -> Iterator[int]:
    process = psutil.Process()
    if not hasattr(process, "cpu_affinity"):
        count = psutil.cpu_count(logical=True) or 1
        if count > max_cpus:
            raise RuntimeError("CPU affinity cannot be enforced on this platform")
        yield count
        return
    original = process.cpu_affinity()
    target = original[:max_cpus]
    if not target:
        raise RuntimeError("process has no available CPU affinity")
    process.cpu_affinity(target)
    try:
        yield len(process.cpu_affinity())
    finally:
        process.cpu_affinity(original)


def _aggregate_metrics(stream: TaskStream, result: HarnessResult) -> dict[str, float]:
    if not result.batch_metrics:
        return {}
    if stream.task_kind == "classification":
        accuracies = [float(item["accuracy"]) for item in result.batch_metrics]
        f1_values = [float(item["macro_f1"]) for item in result.batch_metrics]
        return {
            "mean_stage_accuracy": float(np.mean(accuracies)),
            "mean_stage_macro_f1": float(np.mean(f1_values)),
            "worst_stage_accuracy": float(min(accuracies)),
        }
    rmse = [float(item["rmse"]) for item in result.batch_metrics]
    mae = [float(item["mae"]) for item in result.batch_metrics]
    return {
        "mean_stage_rmse": float(np.mean(rmse)),
        "mean_stage_mae": float(np.mean(mae)),
        "worst_stage_rmse": float(max(rmse)),
    }


def _task_record(stream: TaskStream, result: HarnessResult) -> dict[str, Any]:
    usages = [candidate.usage for candidate in result.candidates]
    return {
        "task_id": stream.task_id,
        "task_kind": stream.task_kind,
        "synthetic": bool(stream.metadata.get("synthetic", False)),
        "evidence_scope": stream.metadata.get("evidence_scope", "proxy_development"),
        "status": result.status,
        "completed_batches": result.completed_batches,
        "candidate_count": result.candidate_count,
        "accepted_count": sum(candidate.accepted for candidate in result.candidates),
        "rejected_count": sum(not candidate.accepted for candidate in result.candidates),
        "rollback_count": result.rollback_count,
        "deployed_version": result.deployed_version,
        "metrics": _aggregate_metrics(stream, result),
        "resources": {
            "candidate_wall_seconds": float(sum(item.wall_seconds for item in usages)),
            "candidate_cpu_seconds": float(sum(item.cpu_seconds for item in usages)),
            "candidate_training_samples": int(
                sum(candidate.training_samples for candidate in result.candidates)
            ),
            "operation_boundary_peak_rss_bytes": int(
                max((item.peak_rss_bytes for item in usages), default=0)
            ),
        },
        "candidates": [
            {
                "batch_id": candidate.batch_id,
                "action": candidate.action,
                "accepted": candidate.accepted,
                "reason": candidate.reason,
                "validation_improvement": candidate.validation_improvement,
                "training_samples": candidate.training_samples,
            }
            for candidate in result.candidates
        ],
        "protocol_event_count": len(result.protocol_history),
    }


def _source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _assert_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise RuntimeError("simulation produced a non-finite value")
    if isinstance(value, dict):
        for child in value.values():
            _assert_finite(child)
    elif isinstance(value, list):
        for child in value:
            _assert_finite(child)


def run_simulation_suite(
    streams: Sequence[TaskStream], *, config: SimulationConfig, output_dir: Path
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("formal simulation output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    if len(streams) != 3:
        raise ValueError("formal simulation requires exactly three tasks")
    if any(stream.sealed for stream in streams):
        raise ValueError("formal simulation refuses streams exposing sealed batches")

    task_records: list[dict[str, Any]] = []
    process = psutil.Process()
    boundary_rss = [process.memory_info().rss]
    with _limited_cpu_affinity(config.max_logical_cpus) as affinity_count:
        for stream in streams:
            failures = (
                config.synthetic_failure_candidates
                if stream.task_id == "synthetic-bearing-protocol-only"
                else ()
            )
            harness_config = HarnessConfig(
                seed=config.seed,
                protocol_mode=config.protocol_mode,
                budget=config.budget,
                gate=config.gates[stream.task_kind],
                minimum_candidate_events=config.minimum_candidate_events,
                replay_max_samples=20_000,
                hpo_max_trials=3,
                fail_candidate_numbers=failures,
            )
            result = UnifiedHarness(
                output_dir / "tasks" / stream.task_id, harness_config
            ).run(stream)
            task_records.append(_task_record(stream, result))
            boundary_rss.append(process.memory_info().rss)

    package_audit = audit_docker_context(Path(__file__).resolve().parents[2])
    candidate_rss = max(
        (
            int(task["resources"]["operation_boundary_peak_rss_bytes"])
            for task in task_records
        ),
        default=0,
    )
    observed_rss = max([*boundary_rss, candidate_rss])
    resource_acceptance = {
        "cpu_affinity_count": affinity_count,
        "cpu_affinity_under_limit": affinity_count <= config.max_logical_cpus,
        "observed_boundary_rss_bytes": observed_rss,
        "rss_under_limit": observed_rss < config.max_rss_bytes,
        "memory_limit_enforced": False,
        "docker_context_bytes": package_audit.total_bytes,
        "docker_context_under_limit": package_audit.total_bytes
        < config.max_docker_context_bytes,
        "docker_context_forbidden_files": [
            path.as_posix() for path in package_audit.forbidden_files
        ],
    }
    status = "completed" if all(
        task["status"] == "completed"
        and task["candidate_count"] >= config.minimum_candidate_events
        for task in task_records
    ) else "failed"
    summary = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "proxy_only": True,
        "official_score": False,
        "source_commit": _source_commit(),
        "status": status,
        "task_count": len(task_records),
        "consumed_sealed_used": False,
        "tasks": task_records,
        "resource_acceptance": resource_acceptance,
        "swanlab": {
            "status": "local_spool_only",
            "official_sync_verified": False,
        },
    }
    _assert_finite(summary)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_payload = {
        "title": "BRACE-MSI full-system local simulation",
        "scope": "proxy development streams + synthetic protocol task; not official",
        "tasks": task_records,
    }
    (output_dir / "report.html").write_text(
        render_html_report(report_payload), encoding="utf-8"
    )
    return summary
