"""Run the registered three-stage mature-optimizer development probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import numpy as np
import psutil


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brace_formal.data import DataBatch  # noqa: E402
from brace_formal.metrics import evaluate, resolve_metric_contract  # noqa: E402
from brace_formal.model import FormalModel  # noqa: E402
from brace_msi.mature_optimizer_pilot import MATURE_PILOT_RECIPES, fit_mature_recipe  # noqa: E402
from scripts.run_competition_core_experiments import _prepare_surrogate, _task_rounds  # noqa: E402


FORMAT = "brace-msi.mature-optimizer-pilot.v1"
SUMMARY_FORMAT = "brace-msi.mature-optimizer-pilot-result.v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_manifest(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise ValueError("mature optimizer pilot manifest is invalid")
    if payload.get("rounds") != 3:
        raise ValueError("pilot must use exactly three rounds")
    if payload.get("confirmation_read_policy") != "never":
        raise ValueError("confirmation must never be read by the pilot")
    methods = payload.get("methods")
    if (
        not isinstance(methods, list)
        or not methods
        or len(methods) != len(set(methods))
        or any(method not in MATURE_PILOT_RECIPES for method in methods)
    ):
        raise ValueError("method list contains an unknown or duplicate method")
    return payload


def _prepare_output(manifest: Mapping[str, Any], output: Path) -> str:
    fingerprint = hashlib.sha256(_canonical(manifest)).hexdigest()
    marker = output / "manifest-lock.json"
    if output.exists():
        if not marker.is_file():
            raise ValueError("existing output has no manifest lock")
        locked = json.loads(marker.read_text(encoding="utf-8"))
        if locked.get("manifest_sha256") != fingerprint:
            raise ValueError("existing output belongs to a different manifest")
        return fingerprint
    output.mkdir(parents=True)
    _write_json(marker, {"format": FORMAT, "experiment_id": manifest["experiment_id"], "manifest_sha256": fingerprint})
    return fingerprint


def _metric_gain(direction: str, candidate: float, parent: float) -> float:
    return candidate - parent if direction == "higher" else parent - candidate


def _lineage_valid(stages: list[Mapping[str, Any]], initial_sha256: str) -> bool:
    expected = initial_sha256
    for index, stage in enumerate(stages, 1):
        if stage.get("stage_index") != index or stage.get("parent_sha256") != expected:
            return False
        expected = str(stage.get("selected_sha256"))
    return True


def _run_arm(
    task_key: str,
    parent_path: Path,
    rounds: list[tuple[DataBatch, DataBatch]],
    method: str,
    output: Path,
    manifest_sha256: str,
) -> dict[str, Any]:
    root = output / task_key / method
    result_path = root / "result.json"
    final_path = root / "checkpoint.npz"
    if result_path.is_file() and final_path.is_file():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("manifest_sha256") != manifest_sha256:
            raise ValueError("resumed arm manifest mismatch")
        return result
    root.mkdir(parents=True, exist_ok=True)
    recipe = MATURE_PILOT_RECIPES[method]
    current = FormalModel.load(parent_path)
    contract = resolve_metric_contract(None, str(current.meta["task"]))
    history: list[DataBatch] = []
    stages: list[dict[str, Any]] = []
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    cpu_total = 0.0
    wall_total = 0.0
    initial_sha256 = _sha(parent_path)
    selected_sha256 = initial_sha256

    for stage_index, (update, gate) in enumerate(rounds, 1):
        parent_sha256 = selected_sha256
        parent_metrics = evaluate(current, gate.x, gate.y, contract)
        training = (
            DataBatch.concat([*history, update])
            if recipe.history_policy == "current_plus_history" and history
            else update
        )
        started_cpu = time.process_time()
        started_wall = time.perf_counter()
        candidate = fit_mature_recipe(current, recipe, training)
        candidate_metrics = evaluate(candidate.model, gate.x, gate.y, contract)
        cpu_seconds = time.process_time() - started_cpu
        wall_seconds = time.perf_counter() - started_wall
        peak_rss = max(peak_rss, process.memory_info().rss)
        cpu_total += cpu_seconds
        wall_total += wall_seconds
        candidate_path = root / f"candidate-{stage_index:02d}.npz"
        candidate.model.save(candidate_path)
        candidate_sha256 = _sha(candidate_path)
        primary = contract.name
        gain = _metric_gain(
            contract.direction,
            float(candidate_metrics[primary]),
            float(parent_metrics[primary]),
        )
        selected_role = "candidate" if gain > 0.0 else "parent"
        if selected_role == "candidate":
            current = candidate.model
            selected_sha256 = candidate_sha256
        candidate_path.unlink()
        stages.append(
            {
                "stage_index": stage_index,
                "parent_sha256": parent_sha256,
                "candidate_sha256": candidate_sha256,
                "selected_sha256": selected_sha256,
                "selected_role": selected_role,
                "training_sha256": training.sha256,
                "validation_sha256": gate.sha256,
                "training_samples": len(training.ids),
                "validation_samples": len(gate.ids),
                "parent_metrics": parent_metrics,
                "candidate_metrics": candidate_metrics,
                "candidate_signed_gain": gain,
                "candidate_relative_gain": gain / max(1.0, abs(float(parent_metrics[primary]))),
                "cpu_seconds": cpu_seconds,
                "wall_seconds": wall_seconds,
                "receipt": candidate.receipt,
            }
        )
        history.append(DataBatch.concat([update, gate]))

    current.save(final_path)
    relative = [float(stage["candidate_relative_gain"]) for stage in stages]
    result = {
        "format": "brace-msi.mature-optimizer-pilot-arm.v1",
        "manifest_sha256": manifest_sha256,
        "task_key": task_key,
        "task": current.meta["task"],
        "method": method,
        "primary_metric": contract.name,
        "direction": contract.direction,
        "initial_checkpoint_sha256": initial_sha256,
        "final_checkpoint_sha256": _sha(final_path),
        "final_checkpoint_bytes": final_path.stat().st_size,
        "parent_lineage_valid": _lineage_valid(stages, initial_sha256),
        "stages": stages,
        "mean_relative_gain": float(np.mean(relative)),
        "worst_relative_gain": float(min(relative)),
        "improved_stages": sum(value > 0.0 for value in relative),
        "degraded_stages": sum(value < 0.0 for value in relative),
        "selected_candidates": sum(stage["selected_role"] == "candidate" for stage in stages),
        "cpu_seconds": cpu_total,
        "wall_seconds": wall_total,
        "peak_rss_bytes": int(peak_rss),
    }
    _write_json(result_path, result)
    return result


def _method_summaries(arms: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    methods = sorted({str(arm["method"]) for arm in arms})
    summaries = []
    for method in methods:
        rows = [arm for arm in arms if arm["method"] == method]
        summaries.append(
            {
                "method": method,
                "mean_relative_gain": float(np.mean([row["mean_relative_gain"] for row in rows])),
                "worst_relative_gain": float(min(row["worst_relative_gain"] for row in rows)),
                "improved_tasks": sum(float(row["mean_relative_gain"]) > 0.0 for row in rows),
                "degraded_tasks": sum(float(row["mean_relative_gain"]) < 0.0 for row in rows),
                "cpu_seconds": float(sum(row["cpu_seconds"] for row in rows)),
                "wall_seconds": float(sum(row["wall_seconds"] for row in rows)),
                "peak_rss_bytes": int(max(row["peak_rss_bytes"] for row in rows)),
                "checkpoint_bytes_max": int(max(row["final_checkpoint_bytes"] for row in rows)),
            }
        )
    return summaries


def pareto_front(methods: list[Mapping[str, Any]]) -> list[str]:
    frontier = []
    for candidate in methods:
        dominated = any(
            other is not candidate
            and float(other["mean_relative_gain"]) >= float(candidate["mean_relative_gain"])
            and float(other["worst_relative_gain"]) >= float(candidate["worst_relative_gain"])
            and float(other["cpu_seconds"]) <= float(candidate["cpu_seconds"])
            and (
                float(other["mean_relative_gain"]) > float(candidate["mean_relative_gain"])
                or float(other["worst_relative_gain"]) > float(candidate["worst_relative_gain"])
                or float(other["cpu_seconds"]) < float(candidate["cpu_seconds"])
            )
            for other in methods
        )
        if not dominated:
            frontier.append(str(candidate["method"]))
    return sorted(frontier)


def _summary(manifest: Mapping[str, Any], fingerprint: str, arms: list[dict[str, Any]]) -> dict[str, Any]:
    methods = _method_summaries(arms)
    return {
        "format": SUMMARY_FORMAT,
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": fingerprint,
        "valid": (
            all(len(arm["stages"]) == 3 for arm in arms)
            and all(arm["parent_lineage_valid"] for arm in arms)
        ),
        "tasks": sorted({str(arm["task_key"]) for arm in arms}),
        "arms": arms,
        "methods": methods,
        "pareto_front": pareto_front(methods),
        "confirmation_reads": 0,
        "official_hidden_score": None,
    }


def run_smoke(manifest: Mapping[str, Any], output: Path | str) -> dict[str, Any]:
    output = Path(output)
    fingerprint = _prepare_output(manifest, output)
    arms: list[dict[str, Any]] = []
    for spec in manifest["registered_surrogates"]:
        parent_path, _, rounds = _prepare_surrogate(spec, output / "surrogate-sources")
        for method in manifest["methods"]:
            arms.append(_run_arm(str(spec["key"]), parent_path, rounds[:3], str(method), output / "arms", fingerprint))
    summary = _summary(manifest, fingerprint, arms)
    _write_json(output / "summary.json", summary)
    return summary


def _validate_training_sources(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    package_root = Path(str(manifest["official_package_root"]))
    result = {}
    for key, spec in manifest["packages"].items():
        package = package_root / spec["directory"]
        observed = {
            "checkpoint_sha256": _sha(package / "checkpoint.npz"),
            "train_sha256": _sha(package / "public" / "train.jsonl"),
        }
        expected = {
            "checkpoint_sha256": spec["checkpoint_sha256"],
            "train_sha256": spec["train_sha256"],
        }
        result[str(key)] = {**observed, "valid": observed == expected}
    if not all(item["valid"] for item in result.values()):
        raise ValueError("official training source hash mismatch")
    return result


def run_full(manifest: Mapping[str, Any], output: Path | str) -> dict[str, Any]:
    output = Path(output)
    fingerprint = _prepare_output(manifest, output)
    sources_before = _validate_training_sources(manifest)
    package_root = Path(str(manifest["official_package_root"]))
    arms: list[dict[str, Any]] = []
    for key, spec in manifest["packages"].items():
        package = package_root / spec["directory"]
        parent_path = package / "checkpoint.npz"
        rounds, _ = _task_rounds(package / "public" / "train.jsonl", FormalModel.load(parent_path))
        for method in manifest["methods"]:
            arms.append(_run_arm(str(key), parent_path, rounds[:3], str(method), output / "arms", fingerprint))
    summary = _summary(manifest, fingerprint, arms)
    sources_after = _validate_training_sources(manifest)
    summary["source_audit_before"] = sources_before
    summary["source_audit_after"] = sources_after
    summary["valid"] = bool(summary["valid"] and sources_before == sources_after)
    _write_json(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest(args.config)
    result = run_smoke(manifest, args.output) if args.smoke else run_full(manifest, args.output)
    print(json.dumps({"valid": result["valid"], "output": str(args.output)}, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
