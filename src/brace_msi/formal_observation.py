"""Bind existing formal acceptance rounds to privacy-safe observation records."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .recording import LocalPublicSpool


@dataclass(frozen=True)
class FormalObservationResult:
    manifest_path: Path
    spool_path: Path
    source_sha256: str
    record_count: int
    task_counts: dict[str, int]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_resources(root: Path, task_id: str, round_index: int) -> tuple[dict[str, Any], int]:
    ledger_path = root / task_id / f"round-{round_index:02d}-state" / "round-ledger.json"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    rounds = payload.get("rounds") if isinstance(payload, Mapping) else None
    if not isinstance(rounds, list) or not rounds:
        raise ValueError(f"missing round ledger entry: {task_id}/{round_index}")
    entry = rounds[-1]
    if not isinstance(entry, Mapping) or entry.get("round_index") != round_index:
        raise ValueError(f"round ledger mismatch: {task_id}/{round_index}")
    evaluations = entry.get("artifact_evaluations")
    candidate = next(
        (
            item
            for item in evaluations if isinstance(item, Mapping) and item.get("role") == "candidate"
        ),
        None,
    ) if isinstance(evaluations, list) else None
    resources = candidate.get("resource_evidence", {}) if isinstance(candidate, Mapping) else {}
    execution = entry.get("candidate_execution", {})
    training_samples = execution.get("training_samples", 0) if isinstance(execution, Mapping) else 0
    return dict(resources) if isinstance(resources, Mapping) else {}, int(training_samples)


def _metric_contract(parent_metrics: Mapping[str, Any]) -> tuple[str, str, str]:
    if "macro_f1" in parent_metrics:
        return "classification", "macro_f1", "accuracy"
    if "rmse" in parent_metrics:
        return "regression", "rmse", "mae"
    raise ValueError("unsupported acceptance metric contract")


def build_formal_observation(
    acceptance_path: Path,
    output_dir: Path,
    *,
    expected_rounds: int = 10,
) -> FormalObservationResult:
    """Create exact-round public records without rerunning training or exposing rows."""

    acceptance_path = Path(acceptance_path)
    root = acceptance_path.parent
    payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
    if payload.get("format") != "brace-msi.workspace-v2-acceptance.v1" or payload.get("valid") is not True:
        raise ValueError("acceptance summary is not a valid workspace-v2 acceptance")
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping) or set(profiles) != {"A", "B", "C"}:
        raise ValueError("acceptance summary must contain exactly A/B/C profiles")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    spool_path = output / "formal-observation.jsonl"
    spool = LocalPublicSpool(spool_path)
    task_counts: dict[str, int] = {}
    for task_id in ("A", "B", "C"):
        profile = profiles[task_id]
        rounds = profile.get("rounds") if isinstance(profile, Mapping) else None
        if not isinstance(rounds, list) or len(rounds) != expected_rounds:
            raise ValueError(f"unexpected round count for task {task_id}")
        indices = [item.get("round_index") for item in rounds if isinstance(item, Mapping)]
        if indices != list(range(1, expected_rounds + 1)):
            raise ValueError(f"non-contiguous rounds for task {task_id}")
        for item in rounds:
            assert isinstance(item, Mapping)
            index = int(item["round_index"])
            parent = item.get("parent_metrics")
            candidate = item.get("candidate_metrics")
            if not isinstance(parent, Mapping) or not isinstance(candidate, Mapping):
                raise ValueError(f"missing metrics for task {task_id} round {index}")
            task_kind, primary_name, secondary_name = _metric_contract(parent)
            deployed_candidate = item.get("applied_role") == "candidate"
            selected = candidate if deployed_candidate else parent
            resources, training_samples = _candidate_resources(root, task_id, index)
            record = {
                "task_id": task_id,
                "task_kind": task_kind,
                "protocol_mode": "workspace_v2_exact_image_local_acceptance",
                "phase": str(item.get("executed_recipe_id", "unknown")),
                "batch_index": index,
                "primary_metric": float(selected[primary_name]),
                "secondary_metric": float(selected[secondary_name]),
                "action": str(item.get("executed_recipe_id", "unknown")),
                "accepted": deployed_candidate,
                "reason": str(item.get("selection_reason", "")),
                "training_samples": training_samples,
                "cpu_seconds": float(resources.get("cpu_seconds", 0.0)),
                "wall_seconds": float(resources.get("wall_seconds", 0.0)),
                "peak_rss_bytes": int(resources.get("peak_rss_bytes", 0)),
                "candidate_count": index,
                "status": str(item.get("applied_role", "unknown")),
                "training_started": True,
            }
            spool.record_once(f"formal-observation:{task_id}:{index}", "round_complete", record)
        task_counts[task_id] = len(rounds)
    source_sha256 = _sha256(acceptance_path)
    manifest_path = output / "manifest.json"
    manifest = {
        "format": "brace-msi.formal-observation.v1",
        "scope": "existing_exact_image_local_acceptance_no_retraining",
        "image": payload["image"],
        "source_acceptance_sha256": source_sha256,
        "record_count": sum(task_counts.values()),
        "task_counts": task_counts,
        "spool_sha256": _sha256(spool_path),
        "limitations": [
            "local protocol acceptance, not an official score",
            "model call identifiers are intentionally excluded from public metrics",
            "does not prove current source commit is contained in the frozen image",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return FormalObservationResult(
        manifest_path=manifest_path,
        spool_path=spool_path,
        source_sha256=source_sha256,
        record_count=sum(task_counts.values()),
        task_counts=task_counts,
    )
