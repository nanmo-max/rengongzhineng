"""Bounded grouped-device search for the official B/C regression packages."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import psutil

from .official_package import PackageAudit, audit_package_root


@dataclass(frozen=True)
class MatrixCandidate:
    id: str
    epochs: int
    learning_rate_multiplier: float
    learning_rate: float


def candidate_grid(
    base_learning_rate: float,
    epochs: Iterable[int],
    learning_rate_multipliers: Iterable[float],
) -> list[MatrixCandidate]:
    """Return the fixed, bounded Cartesian matrix in deterministic order."""

    result: list[MatrixCandidate] = []
    for epoch in epochs:
        for multiplier in learning_rate_multipliers:
            label = str(multiplier).replace(".", "p")
            result.append(
                MatrixCandidate(
                    id=f"e{int(epoch)}-lr{label}",
                    epochs=int(epoch),
                    learning_rate_multiplier=float(multiplier),
                    learning_rate=float(base_learning_rate) * float(multiplier),
                )
            )
    if not result or len(result) > 18:
        raise ValueError("candidate matrix must contain 1..18 candidates")
    return result


def partition_name(profile: str, meta: Mapping[str, Any]) -> str:
    """Map whole devices to train/development/confirmation without row leakage."""

    if profile == "B":
        bearing = str(meta.get("bearing", ""))
        suffix = bearing.rsplit("_", 1)[-1]
        mapping = {"1": "train", "2": "development", "3": "confirmation"}
        if suffix in mapping:
            return mapping[suffix]
    elif profile == "C":
        subset = str(meta.get("source_subset", ""))
        mapping = {
            "FD001": "train",
            "FD002": "train",
            "FD003": "development",
            "FD004": "confirmation",
        }
        if subset in mapping:
            return mapping[subset]
    raise ValueError(f"unsupported {profile} group metadata for sprint partition")


def _group_name(profile: str, meta: Mapping[str, Any]) -> str:
    if profile == "B":
        return str(meta["bearing"])
    return f"{meta['source_subset']}:{meta['unit']}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def materialize_partitions(source: Path, output_dir: Path, profile: str) -> dict[str, Any]:
    """Write immutable, whole-device JSONL partitions outside the official package."""

    output_dir = Path(output_dir)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.is_file():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    if output_dir.exists():
        raise FileExistsError(f"incomplete partition directory: {output_dir}")
    output_dir.mkdir(parents=True)
    handles = {
        role: (output_dir / f"{role}.jsonl").open("x", encoding="utf-8", newline="\n")
        for role in ("train", "development", "confirmation")
    }
    rows = {role: 0 for role in handles}
    groups: dict[str, set[str]] = {role: set() for role in handles}
    identifiers: set[str] = set()
    try:
        with Path(source).open("r", encoding="utf-8") as stream:
            for number, raw in enumerate(stream, 1):
                if not raw.strip():
                    continue
                item = json.loads(raw)
                identity = item["id"]
                if identity in identifiers:
                    raise ValueError(f"duplicate sample identity at line {number}")
                identifiers.add(identity)
                role = partition_name(profile, item["meta"])
                groups[role].add(_group_name(profile, item["meta"]))
                handles[role].write(raw if raw.endswith("\n") else raw + "\n")
                rows[role] += 1
    finally:
        for handle in handles.values():
            handle.close()
    if any(not rows[role] or not groups[role] for role in rows):
        raise ValueError("every sprint partition must contain rows and groups")
    if any(groups[a] & groups[b] for a, b in (("train", "development"), ("train", "confirmation"), ("development", "confirmation"))):
        raise ValueError("device group overlap across sprint partitions")
    manifest = {
        "format": "brace-msi.regression-sprint-partitions.v1",
        "profile": profile,
        "source": str(Path(source).resolve()),
        "source_sha256": _sha256(Path(source)),
        "partitions": {
            role: {
                "path": str((output_dir / f"{role}.jsonl").resolve()),
                "rows": rows[role],
                "groups": sorted(groups[role]),
                "sha256": _sha256(output_dir / f"{role}.jsonl"),
            }
            for role in rows
        },
    }
    _atomic_json(manifest_path, manifest)
    return manifest


def _flatten(value: Any) -> tuple[list[str], list[float]]:
    paths: list[str] = []
    values: list[float] = []

    def visit(child: Any, path: list[list[Any]]) -> None:
        if isinstance(child, dict):
            for key in sorted(child):
                visit(child[key], path + [["key", key]])
        elif isinstance(child, list):
            for index, item in enumerate(child):
                visit(item, path + [["index", index]])
        elif isinstance(child, (int, float)) and not isinstance(child, bool) and math.isfinite(child):
            paths.append(json.dumps(path, ensure_ascii=False, separators=(",", ":")))
            values.append(float(child))
        else:
            raise ValueError("invalid numeric input structure")

    visit(value, [])
    return paths, values


def evaluate_checkpoint(checkpoint: Path, dataset: Path, profile: str) -> dict[str, Any]:
    """Independently evaluate a package checkpoint without importing trainer code."""

    with np.load(checkpoint, allow_pickle=False) as state:
        metadata = json.loads(str(state["metadata"].item()))
        mean = state["mean"].copy()
        scale = state["scale"].copy()
        w1 = state["w1"].copy()
        b1 = state["b1"].copy()
        w2 = state["w2"].copy()
        b2 = state["b2"].copy()
    expected_paths = metadata["paths"]
    total_squared = 0.0
    total_absolute = 0.0
    rows = 0
    group_totals: dict[str, list[float]] = {}
    features: list[list[float]] = []
    targets: list[float] = []
    group_names: list[str] = []

    def consume() -> None:
        nonlocal total_squared, total_absolute, rows
        if not features:
            return
        x = np.asarray(features, dtype=np.float64)
        normalized = np.clip((x - mean) / scale, -10.0, 10.0)
        hidden = np.tanh(normalized @ w1 + b1)
        prediction = np.maximum(
            0.0,
            (hidden @ w2 + b2)[:, 0] * float(metadata["target_scale"])
            + float(metadata["target_mean"]),
        )
        expected = np.asarray(targets, dtype=np.float64)
        error = prediction - expected
        total_squared += float(np.sum(error * error))
        total_absolute += float(np.sum(np.abs(error)))
        rows += len(expected)
        for name, difference in zip(group_names, error, strict=True):
            totals = group_totals.setdefault(name, [0.0, 0.0, 0.0])
            totals[0] += float(difference * difference)
            totals[1] += float(abs(difference))
            totals[2] += 1.0
        features.clear()
        targets.clear()
        group_names.clear()

    with Path(dataset).open("r", encoding="utf-8") as stream:
        for raw in stream:
            if not raw.strip():
                continue
            item = json.loads(raw)
            paths, values = _flatten(item["inputs"])
            if paths != expected_paths:
                raise ValueError("evaluation feature schema differs from checkpoint")
            features.append(values)
            targets.append(float(item["answer"]))
            group_names.append(_group_name(profile, item["meta"]))
            if len(features) >= 4096:
                consume()
    consume()
    if rows == 0:
        raise ValueError("evaluation dataset is empty")
    return {
        "rows": rows,
        "rmse": math.sqrt(total_squared / rows),
        "mae": total_absolute / rows,
        "groups": {
            name: {
                "rows": int(values[2]),
                "rmse": math.sqrt(values[0] / values[2]),
                "mae": values[1] / values[2],
            }
            for name, values in sorted(group_totals.items())
        },
    }


def select_candidate(
    candidates: list[dict[str, Any]],
    *,
    baseline_rmse: float,
    minimum_improvement_fraction: float,
) -> dict[str, Any]:
    """Select on development only, otherwise use the fixed one-epoch/1x fallback."""

    successful = [item for item in candidates if "development" in item]
    if not successful:
        raise ValueError("candidate matrix produced no successful candidate")
    best = min(successful, key=lambda item: (float(item["development"]["rmse"]), item["id"]))
    improvement = (baseline_rmse - float(best["development"]["rmse"])) / baseline_rmse
    if improvement >= minimum_improvement_fraction:
        return {**best, "selection_reason": "development_gate_passed"}
    fallback = next(
        (
            item
            for item in successful
            if item["epochs"] == 1 and math.isclose(item["learning_rate_multiplier"], 1.0)
        ),
        None,
    )
    if fallback is None:
        raise ValueError("fixed one-epoch/1x fallback is unavailable")
    return {**fallback, "selection_reason": "fixed_low_cost_fallback"}


def _run_training(
    package: PackageAudit,
    *,
    train_path: Path,
    validation_path: Path,
    output_dir: Path,
    stage_id: str,
    epochs: int,
    learning_rate: float,
    parent: Path | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    if output_dir.is_dir() and (output_dir / "training.json").is_file():
        return json.loads((output_dir / "training.json").read_text(encoding="utf-8"))
    if output_dir.exists():
        raise FileExistsError(f"incomplete training output: {output_dir}")
    command = [
        sys.executable,
        "-m",
        "baselines.train",
        "--profile",
        str(package.profile_path),
        "--train",
        str(train_path),
        "--validation",
        str(validation_path),
        "--output",
        str(output_dir),
        "--epochs",
        str(epochs),
        "--learning-rate",
        repr(learning_rate),
        "--batch-size",
        str(package.base_batch_size),
        "--stage-id",
        stage_id,
    ]
    if parent is not None:
        command.extend(["--resume", str(parent)])
    environment = os.environ.copy()
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        BASELINE_CPU_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=package.package_dir,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    observed = psutil.Process(process.pid)
    peak_rss = 0
    cpu_seconds = 0.0
    while process.poll() is None:
        if time.monotonic() - started > timeout_seconds:
            for child in observed.children(recursive=True):
                child.kill()
            process.kill()
            process.communicate()
            raise TimeoutError(f"training exceeded {timeout_seconds:g} seconds")
        try:
            family = [observed, *observed.children(recursive=True)]
            peak_rss = max(peak_rss, sum(member.memory_info().rss for member in family))
            cpu_seconds = max(
                cpu_seconds,
                sum(member.cpu_times().user + member.cpu_times().system for member in family),
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        time.sleep(0.01)
    stdout, stderr = process.communicate()
    if process.returncode:
        raise RuntimeError(f"trainer exited {process.returncode}: {stderr[-1000:]}")
    report = json.loads(stdout)
    if report.get("stage_id") != stage_id or report.get("final_epochs") != report.get("initial_epochs") + epochs:
        raise ValueError("trainer output does not prove requested stage")
    if not math.isclose(float(report["learning_rate"]), learning_rate, rel_tol=0.0, abs_tol=1e-15):
        raise ValueError("trainer did not apply requested learning rate")
    receipt = {
        "stage_id": stage_id,
        "wall_seconds": time.monotonic() - started,
        "cpu_seconds": cpu_seconds,
        "peak_rss_bytes": peak_rss,
        "checkpoint_sha256": _sha256(output_dir / "checkpoint.npz"),
        "train_sha256": _sha256(train_path),
        "validation_sha256": _sha256(validation_path),
    }
    _atomic_json(output_dir / "sprint-receipt.json", receipt)
    return report


def run_profile_matrix(
    package: PackageAudit,
    runtime_root: Path,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Run one bounded B/C matrix and one frozen full-train candidate."""

    profile_root = Path(runtime_root) / package.profile
    partitions = materialize_partitions(
        package.train_path,
        profile_root / "partitions",
        package.profile,
    )
    paths = {
        role: Path(partitions["partitions"][role]["path"])
        for role in ("train", "development", "confirmation")
    }
    timeout = float(config["resource_limits"]["candidate_timeout_seconds"])
    baseline_dir = profile_root / "baseline"
    _run_training(
        package,
        train_path=paths["train"],
        validation_path=paths["development"],
        output_dir=baseline_dir,
        stage_id=f"{package.profile}-sprint-baseline",
        epochs=int(config["baseline_epochs"]),
        learning_rate=package.base_learning_rate,
        parent=None,
        timeout_seconds=timeout,
    )
    baseline_checkpoint = baseline_dir / "checkpoint.npz"
    baseline_development = evaluate_checkpoint(baseline_checkpoint, paths["development"], package.profile)
    baseline_confirmation = evaluate_checkpoint(baseline_checkpoint, paths["confirmation"], package.profile)

    results: list[dict[str, Any]] = []
    grid = candidate_grid(
        package.base_learning_rate,
        config["epochs"],
        config["learning_rate_multipliers"],
    )
    for item in grid:
        output = profile_root / "candidates" / item.id
        row: dict[str, Any] = {
            "id": item.id,
            "epochs": item.epochs,
            "learning_rate_multiplier": item.learning_rate_multiplier,
            "learning_rate": item.learning_rate,
        }
        try:
            _run_training(
                package,
                train_path=paths["train"],
                validation_path=paths["development"],
                output_dir=output,
                stage_id=f"{package.profile}-{item.id}",
                epochs=item.epochs,
                learning_rate=item.learning_rate,
                parent=baseline_checkpoint,
                timeout_seconds=timeout,
            )
            row["development"] = evaluate_checkpoint(
                output / "checkpoint.npz", paths["development"], package.profile
            )
            row["status"] = "succeeded"
        except Exception as exc:
            row.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            _atomic_json(output.with_suffix(".failure.json"), row)
        results.append(row)
        _atomic_json(profile_root / "matrix-progress.json", {"candidates": results})

    selected = select_candidate(
        results,
        baseline_rmse=float(baseline_development["rmse"]),
        minimum_improvement_fraction=float(config["gates"]["minimum_development_improvement_fraction"]),
    )
    selected_checkpoint = profile_root / "candidates" / selected["id"] / "checkpoint.npz"
    selected_confirmation = evaluate_checkpoint(selected_checkpoint, paths["confirmation"], package.profile)
    confirmation_improvement = (
        float(baseline_confirmation["rmse"]) - float(selected_confirmation["rmse"])
    ) / float(baseline_confirmation["rmse"])
    if confirmation_improvement < float(config["gates"]["minimum_confirmation_improvement_fraction"]):
        fallback = next(
            item
            for item in results
            if item.get("status") == "succeeded"
            and item["epochs"] == 1
            and math.isclose(item["learning_rate_multiplier"], 1.0)
        )
        selected = {**fallback, "selection_reason": "confirmation_gate_fallback"}
        selected_checkpoint = profile_root / "candidates" / selected["id"] / "checkpoint.npz"
        selected_confirmation = evaluate_checkpoint(selected_checkpoint, paths["confirmation"], package.profile)

    final_dir = profile_root / "final" / selected["id"]
    final_report = _run_training(
        package,
        train_path=package.train_path,
        validation_path=package.validation_path,
        output_dir=final_dir,
        stage_id=f"{package.profile}-sprint-final-{selected['id']}",
        epochs=int(selected["epochs"]),
        learning_rate=float(selected["learning_rate"]),
        parent=package.checkpoint_path,
        timeout_seconds=timeout,
    )
    final_metrics = {key: float(value) for key, value in final_report["validation_after"].items()}
    baseline_metrics = dict(package.baseline_metrics)
    rmse_improvement = (baseline_metrics["rmse"] - final_metrics["rmse"]) / baseline_metrics["rmse"]
    mae_degradation = (final_metrics["mae"] - baseline_metrics["mae"]) / baseline_metrics["mae"]
    accepted = (
        rmse_improvement >= float(config["gates"]["minimum_final_rmse_improvement_fraction"])
        and mae_degradation <= float(config["gates"]["maximum_final_mae_degradation_fraction"])
    )
    summary = {
        "format": "brace-msi.regression-sprint-profile.v1",
        "experiment_id": config["experiment_id"],
        "profile": package.profile,
        "partition_manifest": partitions,
        "baseline_development": baseline_development,
        "baseline_confirmation": baseline_confirmation,
        "candidates": results,
        "selected": selected,
        "selected_confirmation": selected_confirmation,
        "final": {
            "metrics": final_metrics,
            "baseline_metrics": baseline_metrics,
            "rmse_improvement_fraction": rmse_improvement,
            "mae_degradation_fraction": mae_degradation,
            "accepted": accepted,
            "checkpoint": str((final_dir / "checkpoint.npz").resolve()) if accepted else str(package.checkpoint_path),
            "candidate_checkpoint": str((final_dir / "checkpoint.npz").resolve()),
        },
        "boundaries": {
            "official_test_opportunities": 0,
            "pytrio_calls": 0,
            "swanlab_calls": 0,
            "public_validation_historically_exposed": True,
            "confirmation_used_after_development_selection": True,
        },
    }
    _atomic_json(profile_root / "summary.json", summary)
    return summary


def run_regression_sprint(
    package_root: Path,
    runtime_root: Path,
    config: Mapping[str, Any],
    package_config: Mapping[str, Any],
    profiles: Iterable[str],
) -> dict[str, Any]:
    """Audit unchanged package inputs once, then execute requested profile matrices."""

    requested = list(profiles)
    if not requested or any(profile not in {"B", "C"} for profile in requested):
        raise ValueError("sprint profiles must be B and/or C")
    audits = audit_package_root(Path(package_root), package_config)
    new_summaries = {
        profile: run_profile_matrix(audits[profile], Path(runtime_root), config)
        for profile in requested
    }
    existing_path = Path(runtime_root) / "summary.json"
    existing_profiles: dict[str, Any] = {}
    if existing_path.is_file():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        if existing.get("experiment_id") != config["experiment_id"]:
            raise ValueError("existing sprint identity mismatch")
        existing_profiles = dict(existing.get("profiles", {}))
    summaries = {**existing_profiles, **new_summaries}
    result = {
        "format": "brace-msi.regression-sprint.v1",
        "experiment_id": config["experiment_id"],
        "profiles": summaries,
        "complete_profiles": sorted(summaries),
    }
    _atomic_json(Path(runtime_root) / "summary.json", result)
    return result


def validate_regression_sprint(runtime_root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    """Machine-check a completed sprint without retraining or rereading source data."""

    runtime_root = Path(runtime_root)
    summary_path = runtime_root / "summary.json"
    if not summary_path.is_file():
        raise ValueError("sprint summary is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("experiment_id") != config.get("experiment_id"):
        raise ValueError("sprint experiment identity mismatch")
    expected_count = len(config["epochs"]) * len(config["learning_rate_multipliers"])
    checks: dict[str, Any] = {}
    for profile, result in summary.get("profiles", {}).items():
        if profile not in {"B", "C"}:
            raise ValueError("unexpected sprint profile")
        candidates = result.get("candidates", [])
        if len(candidates) != expected_count:
            raise ValueError(f"{profile} candidate matrix is incomplete")
        successful = [row for row in candidates if row.get("status") == "succeeded"]
        if not successful or result.get("selected", {}).get("id") not in {row["id"] for row in successful}:
            raise ValueError(f"{profile} selected candidate is not a successful matrix member")
        partitions = result["partition_manifest"]["partitions"]
        group_sets = {role: set(partitions[role]["groups"]) for role in partitions}
        if any(
            group_sets[a] & group_sets[b]
            for a, b in (("train", "development"), ("train", "confirmation"), ("development", "confirmation"))
        ):
            raise ValueError(f"{profile} device groups overlap")
        boundary = result.get("boundaries", {})
        if any(boundary.get(field) != 0 for field in ("official_test_opportunities", "pytrio_calls", "swanlab_calls")):
            raise ValueError(f"{profile} external-use boundary is invalid")
        candidate_checkpoint = Path(result["final"]["candidate_checkpoint"])
        stable_checkpoint = Path(result["final"]["checkpoint"])
        if not candidate_checkpoint.is_file() or not stable_checkpoint.is_file():
            raise ValueError(f"{profile} final checkpoint evidence is missing")
        receipts = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (runtime_root / profile).rglob("sprint-receipt.json")
        ]
        if len(receipts) > int(config["resource_limits"]["maximum_candidates_per_profile"]):
            raise ValueError(f"{profile} exceeded candidate budget")
        total_wall = sum(float(item["wall_seconds"]) for item in receipts)
        peak_rss = max((int(item["peak_rss_bytes"]) for item in receipts), default=0)
        if total_wall > float(config["resource_limits"]["maximum_wall_seconds_per_profile"]):
            raise ValueError(f"{profile} exceeded wall budget")
        if peak_rss > int(config["resource_limits"]["maximum_peak_rss_bytes"]):
            raise ValueError(f"{profile} exceeded memory budget")
        checks[profile] = {
            "valid": True,
            "candidates": len(candidates),
            "successful_candidates": len(successful),
            "training_jobs": len(receipts),
            "total_wall_seconds": total_wall,
            "peak_rss_bytes": peak_rss,
            "accepted": bool(result["final"]["accepted"]),
        }
    if not checks:
        raise ValueError("sprint contains no completed profile")
    validation = {"valid": True, "experiment_id": config["experiment_id"], "profiles": checks}
    _atomic_json(runtime_root / "machine-validation.json", validation)
    return validation
