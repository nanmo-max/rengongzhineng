"""Resumable, evidence-preserving search for one shared cross-task policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
from typing import Any, Mapping, Protocol

from .cross_task_validation import (
    CandidateEvaluation,
    TaskOutcome,
    rank_shared_candidates,
)
from .unified_policy import MetricDescriptor, SharedPolicyConfig, normalized_metric_delta


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BASELINES = ("static", "fixed_low_cost", "performance_triggered")


def candidate_configs_from_config(
    config: Mapping[str, Any], *, maximum_candidates: int | None = None
) -> dict[str, SharedPolicyConfig]:
    """Expand one deterministic bounded search space without task-specific overrides."""

    if "task_overrides" in config:
        raise ValueError("task-specific policy overrides are forbidden")
    base_payload = dict(config["shared_policy"])
    base = SharedPolicyConfig(**base_payload)
    search_space = config.get("search_space", {})
    if not isinstance(search_space, Mapping):
        raise ValueError("search_space must be a mapping")
    keys = tuple(sorted(search_space))
    values = [tuple(search_space[key]) for key in keys]
    if any(not options for options in values):
        raise ValueError("search dimensions cannot be empty")
    variants: dict[str, SharedPolicyConfig] = {}

    def add(candidate: SharedPolicyConfig) -> None:
        payload = asdict(candidate)
        identifier = "shared-" + _payload_sha256(payload)[:12]
        variants[identifier] = candidate

    add(base)
    expanded: list[SharedPolicyConfig] = []
    for combination in itertools.product(*values) if keys else [()]:
        payload = dict(base_payload)
        payload.update(dict(zip(keys, combination)))
        try:
            candidate = SharedPolicyConfig(**payload)
        except (TypeError, ValueError):
            continue
        if candidate != base:
            expanded.append(candidate)
    rng = random.Random(int(config.get("seed", 0)))
    rng.shuffle(expanded)
    for candidate in expanded:
        add(candidate)
    limit = (
        int(maximum_candidates)
        if maximum_candidates is not None
        else int(config["selection"]["maximum_shared_candidates"])
    )
    if limit < 1:
        raise ValueError("maximum candidate count must be positive")
    return dict(list(variants.items())[:limit])


@dataclass(frozen=True)
class EvaluationMetrics:
    primary_metric: float
    higher_is_better: bool
    cpu_seconds: float
    wall_seconds: float
    peak_rss_bytes: int
    training_samples: int
    hard_constraints_passed: bool
    resource_within_budget: bool
    initial_state_sha256: str
    phase_manifest_sha256: str

    def __post_init__(self) -> None:
        numeric = (self.primary_metric, self.cpu_seconds, self.wall_seconds)
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError("evaluation metrics must be finite")
        if self.cpu_seconds < 0.0 or self.wall_seconds < 0.0:
            raise ValueError("resource time cannot be negative")
        if self.peak_rss_bytes < 0 or self.training_samples < 0:
            raise ValueError("resource counts cannot be negative")
        for value in (self.initial_state_sha256, self.phase_manifest_sha256):
            if not _SHA256.fullmatch(value.lower()):
                raise ValueError("evaluation identities must be SHA-256 values")


class DevelopmentEvaluator(Protocol):
    def evaluate(
        self,
        *,
        task_key: str,
        policy_name: str,
        candidate_id: str | None,
        shared_config: SharedPolicyConfig | None,
    ) -> EvaluationMetrics: ...


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _payload_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _config_payload(config: SharedPolicyConfig) -> dict[str, Any]:
    return asdict(config)


def _build_jobs(
    tasks: tuple[str, ...], candidates: Mapping[str, SharedPolicyConfig]
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for task in tasks:
        for policy in _BASELINES:
            jobs.append(
                {
                    "task_key": task,
                    "policy_name": policy,
                    "candidate_id": None,
                    "shared_config": None,
                }
            )
    for candidate_id in sorted(candidates):
        for task in tasks:
            jobs.append(
                {
                    "task_key": task,
                    "policy_name": "brace",
                    "candidate_id": candidate_id,
                    "shared_config": _config_payload(candidates[candidate_id]),
                }
            )
    for index, job in enumerate(jobs, 1):
        job["job_id"] = f"job-{index:03d}"
    return jobs


def _execution_manifest(
    *,
    tasks: tuple[str, ...],
    candidates: Mapping[str, SharedPolicyConfig],
    source_commit: str,
    experiment_config_sha256: str,
    static_tolerance: float,
) -> dict[str, Any]:
    if not source_commit:
        raise ValueError("source_commit is required")
    if not _SHA256.fullmatch(experiment_config_sha256.lower()):
        raise ValueError("experiment_config_sha256 must be a SHA-256")
    payload = {
        "format": "brace-msi.unified-development-manifest.v1",
        "source_commit": source_commit,
        "experiment_config_sha256": experiment_config_sha256.lower(),
        "task_keys": list(tasks),
        "candidate_configs": {
            candidate_id: _config_payload(candidates[candidate_id])
            for candidate_id in sorted(candidates)
        },
        "static_tolerance": static_tolerance,
        "official_test_opportunities_used": 0,
    }
    payload["manifest_sha256"] = _payload_sha256(payload)
    return payload


def _load_receipt(runtime_root: Path, job: Mapping[str, Any]) -> dict[str, Any] | None:
    job_root = runtime_root / "jobs" / str(job["job_id"])
    receipt_path = job_root / "receipt.json"
    hash_path = job_root / "receipt.sha256"
    if not receipt_path.exists() and not hash_path.exists():
        return None
    if not receipt_path.is_file() or not hash_path.is_file():
        raise ValueError(f"incomplete receipt: {job['job_id']}")
    expected = hash_path.read_text(encoding="ascii").strip().lower()
    if _file_sha256(receipt_path) != expected:
        raise ValueError(f"receipt hash mismatch: {job['job_id']}")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid receipt: {job['job_id']}") from exc
    identity = {key: job[key] for key in ("job_id", "task_key", "policy_name", "candidate_id")}
    if any(receipt.get(key) != value for key, value in identity.items()):
        raise ValueError(f"receipt identity mismatch: {job['job_id']}")
    if receipt.get("shared_config") != job.get("shared_config"):
        raise ValueError(f"receipt config mismatch: {job['job_id']}")
    EvaluationMetrics(**receipt["metrics"])
    return receipt


def _write_receipt(runtime_root: Path, job: Mapping[str, Any], metrics: EvaluationMetrics) -> dict[str, Any]:
    receipt = {
        "format": "brace-msi.unified-development-receipt.v1",
        "job_id": job["job_id"],
        "task_key": job["task_key"],
        "policy_name": job["policy_name"],
        "candidate_id": job["candidate_id"],
        "shared_config": job["shared_config"],
        "metrics": asdict(metrics),
    }
    job_root = runtime_root / "jobs" / str(job["job_id"])
    receipt_path = job_root / "receipt.json"
    _atomic_json(receipt_path, receipt)
    hash_path = job_root / "receipt.sha256"
    temporary = hash_path.with_name(hash_path.name + ".tmp")
    temporary.write_text(_file_sha256(receipt_path) + "\n", encoding="ascii")
    os.replace(temporary, hash_path)
    return receipt


def _metric(receipt: Mapping[str, Any]) -> EvaluationMetrics:
    return EvaluationMetrics(**receipt["metrics"])


def _relative_gain(reference: EvaluationMetrics, current: EvaluationMetrics) -> float:
    if reference.higher_is_better != current.higher_is_better:
        raise ValueError("metric directions differ within a task")
    return -normalized_metric_delta(
        reference=reference.primary_metric,
        current=current.primary_metric,
        descriptor=MetricDescriptor(higher_is_better=reference.higher_is_better),
    )


def _build_summary(
    tasks: tuple[str, ...],
    candidates: Mapping[str, SharedPolicyConfig],
    receipts: Mapping[str, dict[str, Any]],
    jobs: list[dict[str, Any]],
    *,
    static_tolerance: float,
) -> dict[str, Any]:
    by_key = {
        (job["task_key"], job["policy_name"], job["candidate_id"]): receipts[job["job_id"]]
        for job in jobs
    }
    tasks_payload: dict[str, Any] = {}
    evaluations: list[CandidateEvaluation] = []
    for task in tasks:
        baseline_payload: dict[str, Any] = {}
        for policy in _BASELINES:
            baseline_payload[policy] = _metric(by_key[(task, policy, None)]).__dict__
        brace_payload: dict[str, Any] = {}
        for candidate_id in sorted(candidates):
            brace_payload[candidate_id] = _metric(
                by_key[(task, "brace", candidate_id)]
            ).__dict__
        tasks_payload[task] = {**baseline_payload, "brace_candidates": brace_payload}

    for candidate_id in sorted(candidates):
        outcomes: list[TaskOutcome] = []
        for task in tasks:
            static = _metric(by_key[(task, "static", None)])
            fixed = _metric(by_key[(task, "fixed_low_cost", None)])
            simple = _metric(by_key[(task, "performance_triggered", None)])
            brace = _metric(by_key[(task, "brace", candidate_id)])
            compared = (static, fixed, simple, brace)
            if len({item.initial_state_sha256 for item in compared}) != 1 or len(
                {item.phase_manifest_sha256 for item in compared}
            ) != 1:
                raise ValueError(f"unfair initial state or phase manifest: {task}")
            outcomes.append(
                TaskOutcome(
                    task_key=task,
                    relative_gain_vs_static=_relative_gain(static, brace),
                    relative_gain_vs_simple=_relative_gain(simple, brace),
                    cpu_seconds=brace.cpu_seconds,
                    simple_cpu_seconds=simple.cpu_seconds,
                    training_samples=brace.training_samples,
                    hard_constraints_passed=brace.hard_constraints_passed,
                    resource_within_budget=brace.resource_within_budget,
                )
            )
        evaluations.append(CandidateEvaluation(candidate_id, tuple(outcomes)))

    global_ranking = rank_shared_candidates(
        evaluations, static_tolerance=static_tolerance
    )
    folds: list[dict[str, Any]] = []
    for held_out in tasks:
        development = tuple(task for task in tasks if task != held_out)
        fold_candidates = tuple(
            CandidateEvaluation(
                evaluation.config_id,
                tuple(
                    outcome
                    for outcome in evaluation.outcomes
                    if outcome.task_key in development
                ),
            )
            for evaluation in evaluations
        )
        ranking = rank_shared_candidates(
            fold_candidates, static_tolerance=static_tolerance
        )
        outcome = None
        if ranking.winner is not None:
            selected = next(
                evaluation
                for evaluation in evaluations
                if evaluation.config_id == ranking.winner
            )
            outcome = asdict(
                next(item for item in selected.outcomes if item.task_key == held_out)
            )
        folds.append(
            {
                "held_out_task": held_out,
                "development_tasks": list(development),
                "selected_config_id": ranking.winner,
                "held_out_outcome": outcome,
            }
        )
    return {
        "format": "brace-msi.unified-development-summary.v1",
        "complete": True,
        "job_count": len(jobs),
        "winner": global_ranking.winner,
        "ordered_candidate_ids": list(global_ranking.ordered_candidate_ids),
        "eliminated": global_ranking.eliminated,
        "folds": folds,
        "tasks": tasks_payload,
        "official_test_opportunities_used": 0,
    }


def run_development_search(
    *,
    runtime_root: Path,
    task_keys: tuple[str, ...],
    candidates: Mapping[str, SharedPolicyConfig],
    evaluator: DevelopmentEvaluator,
    source_commit: str,
    experiment_config_sha256: str,
    static_tolerance: float,
    max_jobs: int | None = None,
) -> dict[str, Any]:
    """Run or resume all baseline and shared-candidate development jobs."""

    runtime_root = Path(runtime_root).resolve()
    tasks = tuple(sorted(task_keys))
    if len(tasks) != 3 or len(set(tasks)) != 3:
        raise ValueError("unified optimization requires exactly three unique tasks")
    if not candidates:
        raise ValueError("at least one shared candidate is required")
    if max_jobs is not None and max_jobs < 1:
        raise ValueError("max_jobs must be positive")
    manifest = _execution_manifest(
        tasks=tasks,
        candidates=candidates,
        source_commit=source_commit,
        experiment_config_sha256=experiment_config_sha256,
        static_tolerance=static_tolerance,
    )
    manifest_path = runtime_root / "execution-manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise ValueError("execution manifest mismatch")
    else:
        _atomic_json(manifest_path, manifest)

    jobs = _build_jobs(tasks, candidates)
    receipts: dict[str, dict[str, Any]] = {}
    for job in jobs:
        recovered = _load_receipt(runtime_root, job)
        if recovered is not None:
            receipts[str(job["job_id"])] = recovered
    newly_run = 0
    for job in jobs:
        job_id = str(job["job_id"])
        if job_id in receipts:
            continue
        if max_jobs is not None and newly_run >= max_jobs:
            break
        candidate_id = job["candidate_id"]
        shared_config = candidates[candidate_id] if candidate_id is not None else None
        metrics = evaluator.evaluate(
            task_key=str(job["task_key"]),
            policy_name=str(job["policy_name"]),
            candidate_id=candidate_id,
            shared_config=shared_config,
        )
        receipts[job_id] = _write_receipt(runtime_root, job, metrics)
        newly_run += 1
        _atomic_json(
            runtime_root / "state.json",
            {
                "format": "brace-msi.unified-development-state.v1",
                "manifest_sha256": manifest["manifest_sha256"],
                "completed_jobs": sorted(receipts),
                "complete": len(receipts) == len(jobs),
            },
        )
    complete = len(receipts) == len(jobs)
    state: dict[str, Any] = {
        "format": "brace-msi.unified-development-state.v1",
        "manifest_sha256": manifest["manifest_sha256"],
        "completed_jobs": sorted(receipts),
        "complete": complete,
        "job_count": len(jobs),
    }
    if complete:
        summary = _build_summary(
            tasks,
            candidates,
            receipts,
            jobs,
            static_tolerance=static_tolerance,
        )
        _atomic_json(runtime_root / "summary.json", summary)
        state.update(
            {
                "winner": summary["winner"],
                "folds": summary["folds"],
            }
        )
    _atomic_json(runtime_root / "state.json", state)
    return state


def validate_development_search(runtime_root: Path) -> dict[str, Any]:
    """Reopen every receipt and recompute the complete development summary."""

    runtime_root = Path(runtime_root).resolve()
    manifest = json.loads(
        (runtime_root / "execution-manifest.json").read_text(encoding="utf-8")
    )
    recorded_manifest_sha = manifest.pop("manifest_sha256", None)
    if recorded_manifest_sha != _payload_sha256(manifest):
        raise ValueError("execution manifest hash mismatch")
    manifest["manifest_sha256"] = recorded_manifest_sha
    candidates = {
        candidate_id: SharedPolicyConfig(**payload)
        for candidate_id, payload in manifest["candidate_configs"].items()
    }
    tasks = tuple(manifest["task_keys"])
    jobs = _build_jobs(tasks, candidates)
    receipts: dict[str, dict[str, Any]] = {}
    for job in jobs:
        receipt = _load_receipt(runtime_root, job)
        if receipt is None:
            raise ValueError(f"missing receipt: {job['job_id']}")
        receipts[str(job["job_id"])] = receipt
    recomputed = _build_summary(
        tasks,
        candidates,
        receipts,
        jobs,
        static_tolerance=float(manifest["static_tolerance"]),
    )
    recorded = json.loads((runtime_root / "summary.json").read_text(encoding="utf-8"))
    if recorded != recomputed:
        raise ValueError("summary mismatch")
    return {
        "valid": True,
        "job_count": len(jobs),
        "winner": recomputed["winner"],
        "fold_count": len(recomputed["folds"]),
        "official_test_opportunities_used": 0,
    }
