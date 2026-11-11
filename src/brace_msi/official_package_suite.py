"""Three-task local development suite for immutable official training packages."""

from __future__ import annotations

import html
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .official_package import PackageAudit, audit_package_root
from .official_rounds import PolicyResult, run_policy, validate_policy_result
from .official_trainer import CandidateConfig, CandidateReceipt, OfficialTrainer


@dataclass(frozen=True)
class SuiteState:
    complete: bool
    completed_jobs: list[str]
    total_jobs: int
    runtime_root: str
    official_package: bool = True
    official_scoring_ready: bool = False


_JOB_ORDER = [
    *(f"smoke:{profile}" for profile in "ABC"),
    *(f"performance_triggered:{profile}" for profile in "ABC"),
    *(f"brace:{profile}" for profile in "ABC"),
]


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _source_manifest(root: Path, audits: Mapping[str, PackageAudit]) -> dict[str, Any]:
    files = [path for path in root.rglob("*") if path.is_file()]
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    source_tree_dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
        ).stdout.strip()
    )
    return {
        "format": "brace-msi.official-source-manifest.v1",
        "source_commit": source_commit,
        "source_tree_dirty": source_tree_dirty,
        "source_root": str(root),
        "source_file_count": len(files),
        "source_total_bytes": sum(path.stat().st_size for path in files),
        "contains_python_cache": any(path.suffix == ".pyc" or "__pycache__" in path.parts for path in files),
        "packages": {
            profile: {
                "package_id": audit.package_id,
                "directory": audit.package_dir.name,
                "task": audit.task,
                "input_features": audit.input_features,
                "hidden": audit.hidden,
                "parameter_count": audit.parameter_count,
                "train_rows": audit.train_rows,
                "validation_rows": audit.validation_rows,
                "checkpoint_sha256": audit.checkpoint_sha256,
                "train_sha256": audit.train_sha256,
                "validation_sha256": audit.validation_sha256,
                "source_sha256": dict(audit.source_sha256),
                "baseline_metric": audit.baseline_metric,
                "primary_metric": audit.primary_metric,
                "official_package": True,
                "official_scoring_ready": False,
            }
            for profile, audit in audits.items()
        },
    }


def _within_limits(values: Mapping[str, float | int], limits: Mapping[str, Any]) -> bool:
    return (
        float(values["estimated_cpu_seconds"]) <= float(limits["estimated_cpu_seconds"])
        and float(values["estimated_wall_seconds"]) <= float(limits["estimated_wall_seconds"])
        and int(values["estimated_disk_bytes"]) <= int(limits["estimated_disk_bytes"])
    )


def _pre_smoke_estimate(audits: Mapping[str, PackageAudit], config: Mapping[str, Any]) -> dict[str, Any]:
    maximum_candidates = int(config.get("max_candidates_per_policy", 3))
    candidates_per_profile = 1 + 2 * maximum_candidates
    maximum_epochs_per_profile = 1 + 2 * maximum_candidates * 5
    total_candidates = len(audits) * candidates_per_profile
    pure_training = sum(
        audit.training_seconds / audit.base_epochs * maximum_epochs_per_profile
        for audit in audits.values()
    )
    checkpoint_bytes = sum(
        audit.checkpoint_path.stat().st_size * candidates_per_profile for audit in audits.values()
    )
    estimate: dict[str, Any] = {
        "basis": "package_training_history_with_4x_training_safety_and_1s_subprocess_overhead",
        "candidate_upper_bound": total_candidates,
        "epoch_upper_bound_per_profile": maximum_epochs_per_profile,
        "estimated_cpu_seconds": pure_training * 4.0 + total_candidates,
        "estimated_wall_seconds": pure_training * 4.0 + total_candidates,
        "estimated_disk_bytes": checkpoint_bytes * 4 + total_candidates * 65536,
    }
    estimate["within_limits"] = _within_limits(estimate, config["resource_limits"])
    return estimate


def _post_smoke_estimate(
    audits: Mapping[str, PackageAudit],
    config: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not all(f"smoke:{profile}" in state["completed_jobs"] for profile in audits):
        return None
    maximum_candidates = int(config.get("max_candidates_per_policy", 3))
    candidates_per_profile = 1 + 2 * maximum_candidates
    maximum_epochs_per_profile = 1 + 2 * maximum_candidates * 5
    cpu = 0.0
    wall = 0.0
    peak_rss = 0
    for profile in audits:
        receipt = state["jobs"][f"smoke:{profile}"]["receipt"]
        cpu += max(float(receipt["cpu_seconds"]), 0.001) * maximum_epochs_per_profile
        wall += max(float(receipt["wall_seconds"]), 0.001) * maximum_epochs_per_profile
        peak_rss = max(peak_rss, int(receipt["peak_rss_bytes"]))
    checkpoint_bytes = sum(
        audit.checkpoint_path.stat().st_size * candidates_per_profile for audit in audits.values()
    )
    estimate: dict[str, Any] = {
        "basis": "measured_one_epoch_smoke_scaled_to_candidate_and_epoch_upper_bounds",
        "candidate_upper_bound": len(audits) * candidates_per_profile,
        "epoch_upper_bound_per_profile": maximum_epochs_per_profile,
        "estimated_cpu_seconds": cpu * 1.5,
        "estimated_wall_seconds": wall * 1.5,
        "estimated_disk_bytes": checkpoint_bytes * 4 + len(audits) * candidates_per_profile * 65536,
        "measured_peak_rss_bytes": peak_rss,
    }
    estimate["within_limits"] = _within_limits(estimate, config["resource_limits"])
    return estimate


def _load_or_initialize_state(runtime_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    path = runtime_root / "suite-state.json"
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        expected = {profile: item["checkpoint_sha256"] for profile, item in manifest["packages"].items()}
        if state.get("source_checkpoint_sha256") != expected:
            raise ValueError("suite source manifest changed")
        return state
    return {
        "format": "brace-msi.official-package-suite-state.v1",
        "official_package": True,
        "official_scoring_ready": False,
        "round_semantics": "candidate_adaptation_decision",
        "real_drift_stream": False,
        "source_checkpoint_sha256": {
            profile: item["checkpoint_sha256"] for profile, item in manifest["packages"].items()
        },
        "completed_jobs": [],
        "jobs": {},
    }


def _collect_validation_rows(runtime_root: Path, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in "ABC":
        job = state["jobs"].get(f"smoke:{profile}")
        if job:
            receipt = job["receipt"]
            rows.append(
                {
                    "profile": profile,
                    "task": job["task"],
                    "policy": "smoke",
                    "round": 0,
                    "candidate": receipt["stage_id"],
                    "purpose": "smoke_validation",
                    "file_reads": receipt["validation_file_reads"],
                    "metric_evaluations": receipt["validation_metric_evaluations"],
                    "validation_sha256": job["validation_sha256"],
                    "used_for_training": False,
                    "used_for_preprocessing_fit": False,
                }
            )
    for policy in ("performance_triggered", "brace"):
        for profile in "ABC":
            if f"{policy}:{profile}" not in state["completed_jobs"]:
                continue
            path = runtime_root / "policies" / profile / policy / "validation-usage.jsonl"
            rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    cumulative_reads = 0
    cumulative_evaluations = 0
    for row in rows:
        cumulative_reads += int(row["file_reads"])
        cumulative_evaluations += int(row["metric_evaluations"])
        row["suite_cumulative_file_reads"] = cumulative_reads
        row["suite_cumulative_metric_evaluations"] = cumulative_evaluations
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    value = "".join(
        json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    _atomic_text(path, value)


def _summary(audits: Mapping[str, PackageAudit], state: Mapping[str, Any]) -> dict[str, Any]:
    tasks: dict[str, Any] = {}
    for profile, audit in audits.items():
        task: dict[str, Any] = {
            "task": audit.task,
            "primary_metric": audit.primary_metric,
            "higher_is_better": audit.higher_is_better,
            "static_metric": audit.baseline_metric,
        }
        for policy in ("performance_triggered", "brace"):
            job = state["jobs"].get(f"{policy}:{profile}")
            if job:
                task[policy] = job["result"]
        tasks[profile] = task
    return {
        "format": "brace-msi.official-package-summary.v1",
        "official_package": True,
        "official_scoring_ready": False,
        "round_semantics": "candidate_adaptation_decision",
        "real_drift_stream": False,
        "completed_jobs": list(state["completed_jobs"]),
        "tasks": tasks,
        "upstream_package_tests": {
            "A": {"passed": 9, "errors": 0},
            "B": {
                "core_passed": 10,
                "packaging_tool_errors": 2,
                "error_type": "missing scripts.package_baselines in delivered package",
                "training_failure": False,
            },
            "C": {"passed": 9, "errors": 0},
        },
        "interpretation": "Local development-reference results only; repeated public validation is exposed to selection and is not a real drift stream or official score.",
    }


def _write_reports(runtime_root: Path, config: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    title = str(config.get("report_title", "BRACE-MSI official package development"))
    markdown = [
        f"# {title}",
        "",
        "- Scope: local development-reference official packages",
        "- Official scoring ready: false",
        "- Round semantics: candidate adaptation decision; not a real drift stream",
        "- Public validation is repeatedly exposed to candidate selection and never used for training or preprocessing fit.",
        "",
        "| Profile | Static | Performance-triggered | BRACE |",
        "|---|---:|---:|---:|",
    ]
    for profile, task in summary["tasks"].items():
        simple = task.get("performance_triggered", {}).get("stable_metric", "pending")
        brace = task.get("brace", {}).get("stable_metric", "pending")
        markdown.append(f"| {profile} | {task['static_metric']} | {simple} | {brace} |")
    markdown.extend(
        [
            "",
            "B package upstream tests: 10 core tests passed; 2 packaging-tool tests error because the delivered package lacks scripts.package_baselines. This is not reported as a training failure or as an all-green package suite.",
            "",
        ]
    )
    _atomic_text(runtime_root / "report.md", "\n".join(markdown))
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(profile)}</td>"
        f"<td>{html.escape(str(task['static_metric']))}</td>"
        f"<td>{html.escape(str(task.get('performance_triggered', {}).get('stable_metric', 'pending')))}</td>"
        f"<td>{html.escape(str(task.get('brace', {}).get('stable_metric', 'pending')))}</td>"
        "</tr>"
        for profile, task in summary["tasks"].items()
    )
    page = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>"
        + html.escape(title)
        + "</title></head><body><h1>"
        + html.escape(title)
        + "</h1><p>Local development-reference only; official_scoring_ready=false.</p>"
        + "<p>Ten rounds mean candidate adaptation decisions, not a real drift stream. Public validation exposure can overfit selection.</p>"
        + "<table><thead><tr><th>Profile</th><th>Static</th><th>Performance-triggered</th><th>BRACE</th></tr></thead><tbody>"
        + rows
        + "</tbody></table><p>B upstream: 10 core passed; 2 packaging-tool errors from missing scripts.package_baselines.</p></body></html>"
    )
    _atomic_text(runtime_root / "report.html", page)


def _write_artifacts(
    runtime_root: Path,
    audits: Mapping[str, PackageAudit],
    state: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    rows = _collect_validation_rows(runtime_root, state)
    _write_jsonl(runtime_root / "validation-usage.jsonl", rows)
    summary = _summary(audits, state)
    _atomic_json(runtime_root / "summary.json", summary)
    _write_reports(runtime_root, config, summary)


def run_official_package_suite(
    package_root: Path,
    runtime_root: Path,
    config: Mapping[str, Any],
    max_jobs: int | None = None,
    *,
    trainer: Any | None = None,
) -> SuiteState:
    """Run or resume the fixed three-smoke plus six-policy local queue."""

    if max_jobs is not None and max_jobs < 1:
        raise ValueError("max_jobs must be positive")
    package_root = Path(package_root)
    runtime_root = Path(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    audits = audit_package_root(package_root, config)
    if set(audits) != {"A", "B", "C"}:
        raise ValueError("suite requires official packages A, B and C")
    manifest = _source_manifest(package_root, audits)
    if manifest["contains_python_cache"]:
        raise ValueError("official package root contains Python cache files")
    _atomic_json(runtime_root / "source-manifest.json", manifest)
    state = _load_or_initialize_state(runtime_root, manifest)

    pre = _pre_smoke_estimate(audits, config)
    estimates: dict[str, Any] = {"format": "brace-msi.official-resource-estimate.v1", "limits": config["resource_limits"], "pre_smoke": pre, "post_smoke": None}
    existing_estimate = runtime_root / "resource-estimate.json"
    if existing_estimate.exists():
        old = json.loads(existing_estimate.read_text(encoding="utf-8"))
        estimates["post_smoke"] = old.get("post_smoke")
    _atomic_json(existing_estimate, estimates)
    if not pre["within_limits"]:
        raise RuntimeError("resource estimate exceeds limits before smoke")

    if trainer is None:
        trainer = OfficialTrainer(sys.executable)
    new_jobs = 0
    for job_id in _JOB_ORDER:
        if job_id in state["completed_jobs"]:
            continue
        if max_jobs is not None and new_jobs >= max_jobs:
            break
        kind, profile = job_id.split(":", 1)
        package = audits[profile]
        if kind == "smoke":
            output = runtime_root / "smoke" / profile
            receipt = trainer.run_candidate(
                package,
                package.checkpoint_path,
                output,
                CandidateConfig(1, package.base_learning_rate, package.base_batch_size),
                f"{profile}-smoke",
            )
            state["jobs"][job_id] = {
                "task": package.task,
                "validation_sha256": package.validation_sha256,
                "receipt": asdict(receipt),
            }
        else:
            result: PolicyResult = run_policy(
                package,
                kind,
                runtime_root / "policies" / profile / kind,
                config,
                trainer,
            )
            if not result.complete:
                raise RuntimeError(f"policy job did not complete: {job_id}")
            state["jobs"][job_id] = {"task": package.task, "result": asdict(result)}
        state["completed_jobs"].append(job_id)
        _atomic_json(runtime_root / "suite-state.json", state)
        new_jobs += 1

        post = _post_smoke_estimate(audits, config, state)
        if post is not None:
            estimates["post_smoke"] = post
            _atomic_json(existing_estimate, estimates)
            if not post["within_limits"]:
                _write_artifacts(runtime_root, audits, state, config)
                raise RuntimeError("resource estimate exceeds limits after smoke")
        _write_artifacts(runtime_root, audits, state, config)

    if not (runtime_root / "suite-state.json").exists():
        _atomic_json(runtime_root / "suite-state.json", state)
    _write_artifacts(runtime_root, audits, state, config)
    return SuiteState(
        complete=state["completed_jobs"] == _JOB_ORDER,
        completed_jobs=list(state["completed_jobs"]),
        total_jobs=len(_JOB_ORDER),
        runtime_root=str(runtime_root),
    )


def validate_official_package_suite(runtime_root: Path) -> dict[str, Any]:
    """Validate the complete evidence package without running training."""

    runtime_root = Path(runtime_root)
    required = (
        "source-manifest.json",
        "resource-estimate.json",
        "suite-state.json",
        "summary.json",
        "validation-usage.jsonl",
        "report.md",
        "report.html",
    )
    missing = [name for name in required if not (runtime_root / name).is_file()]
    if missing:
        raise ValueError(f"suite evidence missing: {missing}")
    state = json.loads((runtime_root / "suite-state.json").read_text(encoding="utf-8"))
    if state.get("completed_jobs") != _JOB_ORDER:
        raise ValueError("suite job queue is incomplete or out of order")
    summary = json.loads((runtime_root / "summary.json").read_text(encoding="utf-8"))
    if summary.get("official_package") is not True or summary.get("official_scoring_ready") is not False:
        raise ValueError("suite result boundary is invalid")
    if summary.get("real_drift_stream") is not False or summary.get("round_semantics") != "candidate_adaptation_decision":
        raise ValueError("suite round semantics are invalid")
    profiles = sorted(summary.get("tasks", {}))
    if profiles != ["A", "B", "C"]:
        raise ValueError("suite task profiles are incomplete")
    policy_checks = []
    for profile in profiles:
        policy_checks.append(validate_policy_result(runtime_root / "policies" / profile / "performance_triggered", 10, 1))
        policy_checks.append(validate_policy_result(runtime_root / "policies" / profile / "brace", 10, 3))
    estimate = json.loads((runtime_root / "resource-estimate.json").read_text(encoding="utf-8"))
    if not estimate["pre_smoke"]["within_limits"] or not estimate["post_smoke"]["within_limits"]:
        raise ValueError("suite resource estimate is outside limits")
    rows = [json.loads(line) for line in (runtime_root / "validation-usage.jsonl").read_text(encoding="utf-8").splitlines() if line]
    expected_candidates = 3 + sum(item["candidates"] for item in policy_checks)
    if len(rows) != expected_candidates:
        raise ValueError("suite validation usage count does not match candidates")
    if any(row.get("used_for_training") or row.get("used_for_preprocessing_fit") for row in rows):
        raise ValueError("suite validation leakage recorded")
    validation = {
        "valid": True,
        "jobs": len(_JOB_ORDER),
        "profiles": profiles,
        "candidate_count": expected_candidates,
        "validation_file_reads": sum(int(row["file_reads"]) for row in rows),
        "official_package": True,
        "official_scoring_ready": False,
        "real_drift_stream": False,
    }
    _atomic_json(runtime_root / "validation.json", validation)
    return validation

