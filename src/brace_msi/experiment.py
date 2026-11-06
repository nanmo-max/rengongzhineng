"""Configuration and orchestration for local proxy experiments."""

from __future__ import annotations

import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from .audit import ALLOWED_FIELDS
from .budget import BudgetLimits
from .data.audit import file_sha256
from .data.cmapss import load_cmapss_fd001_stream
from .data.gas import load_gas_stream
from .policies import BracePolicy, PerformanceTriggeredPolicy, StaticPolicy
from .runner import RunConfig, RunSummary, run_stream
from .safety import GateConfig


class ExperimentConfigError(ValueError):
    """Raised when an experiment configuration violates evidence boundaries."""


class ExperimentValidationError(ValueError):
    """Raised when saved experiment evidence is incomplete or unsafe."""


def load_experiment_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentConfigError(f"cannot read experiment config: {path}") from exc
    required = {"experiment_id", "proxy_only", "seed", "smoke", "include_sealed"}
    missing = required.difference(config)
    if missing:
        raise ExperimentConfigError(f"missing config fields: {sorted(missing)}")
    if config["proxy_only"] is not True:
        raise ExperimentConfigError("local experiments must set proxy_only=true")
    if config["smoke"] and config["include_sealed"]:
        raise ExperimentConfigError("smoke runs must not open the sealed stream")
    return config


def build_policy(
    policy_name: str,
    *,
    task_kind: Literal["classification", "regression"],
    config: dict[str, Any],
):
    if policy_name == "static":
        return StaticPolicy()
    if policy_name == "performance_triggered":
        policy_config = config["policies"]["performance_triggered"]
        key = f"{task_kind}_drop_threshold"
        return PerformanceTriggeredPolicy(
            performance_drop_threshold=float(policy_config[key])
        )
    if policy_name == "brace":
        policy_config = config["policies"]["brace"][task_kind]
        return BracePolicy(**{key: float(value) for key, value in policy_config.items()})
    raise ExperimentConfigError(f"unknown policy: {policy_name}")


def _source_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _assert_finite(value: Any, *, path: str = "result") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise RuntimeError(f"non-finite value at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_finite(child, path=f"{path}[{index}]")


def validate_experiment_output(
    output_dir: Path, *, expected_runs: int, smoke: bool
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    try:
        summary = json.loads(
            (output_dir / "summary.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentValidationError("missing or invalid summary.json") from exc
    if summary.get("proxy_only") is not True:
        raise ExperimentValidationError("proxy_only must be true")
    if summary.get("run_count") != expected_runs:
        raise ExperimentValidationError("unexpected run count")
    if smoke and summary.get("include_sealed") is not False:
        raise ExperimentValidationError("smoke output opened the sealed stream")
    _assert_finite(summary)
    action_counts = summary.get("action_counts", {})
    for required_action in ("incremental_update", "replay_refit"):
        if int(action_counts.get(required_action, 0)) < 1:
            raise ExperimentValidationError(
                f"missing required action: {required_action}"
            )

    jsonl_files = sorted(output_dir.glob("*.jsonl"))
    run_json_files = sorted(
        path for path in output_dir.glob("*.json") if path.name != "summary.json"
    )
    if len(jsonl_files) != expected_runs or len(run_json_files) != expected_runs:
        raise ExperimentValidationError("incomplete per-run evidence files")
    standard_fields = {"schema_version", "proxy_only", "event"}
    for path in jsonl_files:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise ExperimentValidationError(f"empty audit log: {path.name}")
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ExperimentValidationError(
                    f"invalid JSONL record: {path.name}"
                ) from exc
            if record.get("proxy_only") is not True:
                raise ExperimentValidationError(
                    f"unsafe proxy marker in {path.name}"
                )
            unexpected = set(record).difference(standard_fields | ALLOWED_FIELDS)
            if unexpected:
                raise ExperimentValidationError(
                    f"non-allowlisted audit fields in {path.name}: {sorted(unexpected)}"
                )
    return {
        "valid": True,
        "run_count": expected_runs,
        "jsonl_files": len(jsonl_files),
        "run_json_files": len(run_json_files),
        "action_counts": action_counts,
    }


def _resource_summary(summary: RunSummary) -> dict[str, float | int]:
    usages = [event.usage for event in summary.candidate_events if event.usage]
    return {
        "candidate_count": summary.candidate_count,
        "training_samples": sum(
            event.training_samples
            for event in summary.candidate_events
            if event.budget_allowed
        ),
        "wall_seconds": float(sum(usage.wall_seconds for usage in usages)),
        "cpu_seconds": float(sum(usage.cpu_seconds for usage in usages)),
        "peak_rss_bytes": int(max((usage.peak_rss_bytes for usage in usages), default=0)),
    }


def run_local_experiment(
    *,
    config_path: Path,
    gas_root: Path,
    gas_archive: Path,
    cmapss_zip: Path,
    cmapss_archive: Path,
    output_dir: Path,
) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    observed_hashes = {
        "gas": file_sha256(gas_archive),
        "cmapss": file_sha256(cmapss_archive),
    }
    if observed_hashes != config["data_hashes"]:
        raise ExperimentConfigError("proxy archive hash does not match preregistration")

    streams = (
        load_gas_stream(gas_root, smoke=bool(config["smoke"])),
        load_cmapss_fd001_stream(cmapss_zip, smoke=bool(config["smoke"])),
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_records: list[dict[str, Any]] = []
    actions: Counter[str] = Counter()
    for stream in streams:
        task_gate = config["gate"][stream.task_kind]
        for policy_name in ("static", "performance_triggered", "brace"):
            policy = build_policy(
                policy_name, task_kind=stream.task_kind, config=config
            )
            run_config = RunConfig(
                seed=int(config["seed"]),
                budget=BudgetLimits(**config["budget"]),
                gate=GateConfig(**task_gate),
            )
            stem = f"{stream.task_id}__{policy_name}"
            summary = run_stream(
                stream,
                policy=policy,
                config=run_config,
                audit_path=output_dir / f"{stem}.jsonl",
                include_sealed=bool(config["include_sealed"]),
            )
            summary_payload = summary.to_dict()
            _assert_finite(summary_payload)
            for event in summary.candidate_events:
                actions[event.action] += 1
            record = {
                "task_id": stream.task_id,
                "task_kind": stream.task_kind,
                "policy": policy_name,
                "metrics": {
                    "development": summary.development_metrics,
                    "sealed": summary.sealed_metrics,
                },
                "resources": _resource_summary(summary),
                "candidate_events": summary_payload["candidate_events"],
                "batch_results": summary_payload["batch_results"],
                "audit_file": f"{stem}.jsonl",
            }
            (output_dir / f"{stem}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            run_records.append(record)

    result = {
        "schema_version": 1,
        "experiment_id": config["experiment_id"],
        "proxy_only": True,
        "source_commit": _source_commit(),
        "seed": config["seed"],
        "smoke": config["smoke"],
        "include_sealed": config["include_sealed"],
        "data_hashes": observed_hashes,
        "run_count": len(run_records),
        "action_counts": dict(sorted(actions.items())),
        "runs": run_records,
        "swanlab": {
            "status": "not_available",
            "reason": "package absent and official offline synchronization unresolved",
        },
    }
    _assert_finite(result)
    (output_dir / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
