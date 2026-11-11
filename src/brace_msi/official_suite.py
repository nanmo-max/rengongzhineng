"""Resumable three-task development queue aligned with published platform rules."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Any

import numpy as np

from .budget import BudgetLimits
from .data.types import TaskStream
from .formal_development import (
    FormalRunConfig,
    create_local_checkpoint,
    run_formal_development_experiment,
    validate_formal_development_output,
)
from .official_metrics import higher_is_better
from .safety import GateConfig


QUEUE: tuple[tuple[str, str], ...] = (
    ("gas", "static"),
    ("bearing", "static"),
    ("engine", "static"),
    ("gas", "performance_triggered"),
    ("bearing", "performance_triggered"),
    ("engine", "performance_triggered"),
    ("gas", "brace"),
    ("bearing", "brace"),
    ("engine", "brace"),
)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def _config_digest(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(canonical).hexdigest().upper()


def _run_config(config: dict[str, Any], task_name: str) -> FormalRunConfig:
    task = config["tasks"][task_name]
    return FormalRunConfig(
        seed=int(config["seed"]),
        budget=BudgetLimits(**task["budget"]),
        gate=GateConfig(**task["gate"]),
        minimum_candidate_events=int(task["minimum_candidate_events"]),
        replay_max_samples=int(task["replay_max_samples"]),
        performance_drop_threshold=float(task["performance_drop_threshold"]),
        update_drop_threshold=float(task["update_drop_threshold"]),
        refit_drop_threshold=float(task["refit_drop_threshold"]),
        drift_threshold=float(task["drift_threshold"]),
        high_drift_threshold=float(task["high_drift_threshold"]),
        mlp_max_iter=int(task.get("mlp_max_iter", 120)),
        validation_fraction=float(task.get("validation_fraction", 0.25)),
    )


def _queue_id(index: int, task_name: str, policy: str) -> str:
    return f"{index:02d}-{task_name}-{policy.replace('_', '-')}"


def _read_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_first_three_health(root: Path) -> None:
    results = []
    for index, (task_name, policy) in enumerate(QUEUE[:3], start=1):
        directory = root / "experiments" / _queue_id(index, task_name, policy)
        validation = validate_formal_development_output(
            directory, expected_batches=10, minimum_candidates=0
        )
        result = _read_result(directory / "result.json")
        results.append(
            {
                "queue_id": directory.name,
                "task": task_name,
                "policy": policy,
                "validation": validation,
                "primary_metric": result["primary_metric_name"],
                "primary_value": result["metrics"][
                    "macro_f1"
                    if result["primary_metric_name"] == "macro_f1"
                    else "rmse"
                ],
            }
        )
    _atomic_json(
        root / "first-three-health.json",
        {
            "valid": True,
            "scope": "local_rules_aligned_static_health_check",
            "official_score": False,
            "experiments": results,
        },
    )


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    metric = result["primary_metric_name"]
    values = np.asarray(
        [record["primary_metric"] for record in result["batch_records"]],
        dtype=np.float64,
    )
    if higher_is_better(metric):
        worst_index = int(np.argmin(values))
        best_after = int(worst_index + np.argmax(values[worst_index:]))
    else:
        worst_index = int(np.argmax(values))
        best_after = int(worst_index + np.argmin(values[worst_index:]))
    primary_key = "macro_f1" if metric == "macro_f1" else "rmse"
    return {
        "primary_metric": metric,
        "aggregate_primary": float(result["metrics"][primary_key]),
        "final_stage_primary": float(values[-1]),
        "worst_stage_primary": float(values[worst_index]),
        "stage_standard_deviation": float(np.std(values)),
        "worst_stage_index": worst_index + 1,
        "proxy_recovery_rounds_to_best_observed": best_after - worst_index,
        "real_candidate_count": int(result["real_candidate_count"]),
        "accepted_candidate_count": int(result["accepted_candidate_count"]),
        "resources": result["resources"],
    }


def _write_summary(root: Path) -> dict[str, Any]:
    by_task: dict[str, dict[str, Any]] = {}
    for index, (task_name, policy) in enumerate(QUEUE, start=1):
        result = _read_result(
            root
            / "experiments"
            / _queue_id(index, task_name, policy)
            / "result.json"
        )
        by_task.setdefault(task_name, {})[policy] = _result_summary(result)

    for task_name, policies in by_task.items():
        static_value = policies["static"]["aggregate_primary"]
        metric = policies["static"]["primary_metric"]
        for policy in policies.values():
            value = policy["aggregate_primary"]
            policy["improvement_over_static"] = float(
                value - static_value if higher_is_better(metric) else static_value - value
            )
        candidates = ("static", "performance_triggered", "brace")
        by_task[task_name]["best_observed_policy"] = (
            max(candidates, key=lambda name: policies[name]["aggregate_primary"])
            if higher_is_better(metric)
            else min(candidates, key=lambda name: policies[name]["aggregate_primary"])
        )

    summary = {
        "schema_version": 1,
        "status": "completed",
        "scope": "local_official_rules_aligned_development",
        "official_checkpoint": False,
        "official_score_computed": False,
        "tasks": by_task,
    }
    _atomic_json(root / "summary.json", summary)
    _write_reports(root, summary)
    return summary


def _write_reports(root: Path, summary: dict[str, Any]) -> None:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for task_name, task in summary["tasks"].items():
        for policy in ("static", "performance_triggered", "brace"):
            rows.append((task_name, policy, task[policy]))

    markdown = [
        "# OFFICIAL-RULES-ALIGNED-DEV-001",
        "",
        "> Local public-data development evidence; this is not an official score. "
        "The initial checkpoints are locally reconstructed (`official_checkpoint=false`).",
        "",
        "| Task | Policy | Primary | Improvement vs static | Candidates | Accepted | CPU seconds | Training samples |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for task_name, policy, item in rows:
        markdown.append(
            "| {task} | {policy} | {primary:.6f} | {delta:.6f} | {candidates} | "
            "{accepted} | {cpu:.6f} | {samples} |".format(
                task=task_name,
                policy=policy,
                primary=item["aggregate_primary"],
                delta=item["improvement_over_static"],
                candidates=item["real_candidate_count"],
                accepted=item["accepted_candidate_count"],
                cpu=item["resources"]["candidate_cpu_seconds"],
                samples=item["resources"]["candidate_training_samples"],
            )
        )
    markdown.extend(
        [
            "",
            "The table reports performance, stability proxies and resources separately. "
            "No unpublished competition weighting or composite score is inferred.",
            "",
        ]
    )
    _atomic_text(root / "report.md", "\n".join(markdown))

    html_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{:.6f}</td><td>{:.6f}</td>"
        "<td>{}</td><td>{}</td><td>{:.6f}</td><td>{}</td></tr>".format(
            escape(task_name),
            escape(policy),
            item["aggregate_primary"],
            item["improvement_over_static"],
            item["real_candidate_count"],
            item["accepted_candidate_count"],
            item["resources"]["candidate_cpu_seconds"],
            item["resources"]["candidate_training_samples"],
        )
        for task_name, policy, item in rows
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>BRACE-MSI development report</title>
<style>body{{font:15px system-ui;margin:2rem;color:#17202a}}table{{border-collapse:collapse}}
th,td{{border:1px solid #ccd1d1;padding:.45rem;text-align:right}}th:first-child,td:first-child,
th:nth-child(2),td:nth-child(2){{text-align:left}}.notice{{padding:1rem;background:#fff3cd}}</style></head>
<body><h1>OFFICIAL-RULES-ALIGNED-DEV-001</h1>
<p class="notice">Local public-data development evidence; this is not an official score.
Initial checkpoints are locally reconstructed (official_checkpoint=false).</p>
<table><thead><tr><th>Task</th><th>Policy</th><th>Primary</th><th>Improvement vs static</th>
<th>Candidates</th><th>Accepted</th><th>CPU seconds</th><th>Training samples</th></tr></thead>
<tbody>{html_rows}</tbody></table>
<p>Performance and resources are reported separately; no unpublished scoring formula is inferred.</p>
</body></html>"""
    _atomic_text(root / "report.html", html)


def run_official_development_suite(
    streams: dict[str, TaskStream],
    config: dict[str, Any],
    root: Path,
    *,
    max_experiments: int | None = None,
) -> dict[str, Any]:
    """Run or resume the nine serial experiments without rewriting completed evidence."""

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    required = {"gas", "bearing", "engine"}
    if set(streams) != required:
        raise ValueError(f"expected streams {sorted(required)}")
    if config.get("official_rules_aligned") is not True:
        raise ValueError("suite configuration lacks the rules-aligned marker")
    if config.get("official_checkpoint") is not False:
        raise ValueError("local suite cannot claim an official checkpoint")
    digest = _config_digest(config)
    status_path = root / "status.json"
    if status_path.exists():
        previous = _read_result(status_path)
        if previous.get("config_sha256") != digest:
            raise RuntimeError("refusing to resume with a different configuration")

    checkpoints: dict[str, Path] = {}
    for task_name in ("gas", "bearing", "engine"):
        checkpoint = root / "checkpoints" / f"{task_name}.pkl"
        if not checkpoint.exists():
            create_local_checkpoint(
                streams[task_name], checkpoint, _run_config(config, task_name)
            )
        checkpoints[task_name] = checkpoint

    target = len(QUEUE) if max_experiments is None else min(len(QUEUE), max_experiments)
    completed = 0
    for index, (task_name, policy) in enumerate(QUEUE, start=1):
        result_dir = root / "experiments" / _queue_id(index, task_name, policy)
        if (result_dir / "result.json").exists():
            completed += 1
        elif completed < target:
            run_formal_development_experiment(
                streams[task_name],
                policy_name=policy,
                checkpoint_path=checkpoints[task_name],
                output_dir=result_dir,
                config=_run_config(config, task_name),
            )
            validate_formal_development_output(
                result_dir,
                expected_batches=10,
                minimum_candidates=(
                    _run_config(config, task_name).minimum_candidate_events
                    if policy == "brace"
                    else 0
                ),
            )
            completed += 1
        if completed >= 3 and not (root / "first-three-health.json").exists():
            _write_first_three_health(root)
        state = {
            "schema_version": 1,
            "status": "completed" if completed == len(QUEUE) else "running",
            "config_sha256": digest,
            "completed_experiments": completed,
            "total_experiments": len(QUEUE),
            "current_or_next_queue_index": min(completed + 1, len(QUEUE)),
            "official_checkpoint": False,
        }
        _atomic_json(status_path, state)
        if completed >= target:
            break

    if completed == len(QUEUE):
        _write_summary(root)
        state["status"] = "completed"
    else:
        state["status"] = "paused"
    _atomic_json(status_path, state)
    return state


def validate_official_development_suite(
    root: Path, *, expected_experiments: int = 9
) -> dict[str, Any]:
    root = Path(root)
    status = _read_result(root / "status.json")
    if status.get("status") != "completed":
        raise RuntimeError("development suite is not completed")
    results = sorted((root / "experiments").glob("*/result.json"))
    if len(results) != expected_experiments:
        raise RuntimeError("unexpected completed experiment count")
    if not (root / "first-three-health.json").exists() or not (
        root / "summary.json"
    ).exists():
        raise RuntimeError("suite-level evidence is incomplete")
    for result_path in results:
        result = _read_result(result_path)
        validate_formal_development_output(
            result_path.parent,
            expected_batches=10,
            minimum_candidates=(3 if result["policy"] == "brace" else 0),
        )
    return {
        "valid": True,
        "completed_experiments": len(results),
        "official_checkpoint": False,
        "official_score_computed": False,
    }
