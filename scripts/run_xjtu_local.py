"""Run the preregistered, resumable XJTU-SY local development queue."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
import psutil

from brace_msi.data.audit import file_sha256
from brace_msi.data.xjtu import (
    FROZEN_BEARING_SPLIT,
    extract_bearing_cache,
    load_xjtu_stream,
)
from brace_msi.xjtu_serial import run_serial_experiments, validate_serial_output


CONDITIONS = {
    "1": ("35Hz12kN", 2100.0, 12.0),
    "2": ("37.5Hz11kN", 2250.0, 11.0),
    "3": ("40Hz10kN", 2400.0, 10.0),
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--experiment-directory", default="experiments")
    parser.add_argument(
        "--rar-executable",
        type=Path,
        default=Path(r"C:\Program Files\WinRAR\Rar.exe"),
    )
    return parser.parse_args()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _status(root: Path, stage: str, **extra: Any) -> None:
    _atomic_json(
        root / "pipeline-status.json",
        {
            "schema_version": 1,
            "experiment_id": "XJTU-LOCAL-DEV-001",
            "local_development_only": True,
            "pid": os.getpid(),
            "stage": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        },
    )


def _limit_cpu() -> list[int]:
    process = psutil.Process()
    available = process.cpu_affinity()
    selected = available[: min(4, len(available))]
    if selected:
        process.cpu_affinity(selected)
    return selected


def _validate_archives(config: dict[str, Any], first_part: Path) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, expected in config["archive_sha256"].items():
        path = first_part.parent / name
        digest = file_sha256(path)
        if digest.upper() != str(expected).upper():
            raise RuntimeError(f"archive hash mismatch: {name}")
        observed[name] = digest.upper()
    return observed


def _source_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    worktree = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {"source_commit": commit, "source_tree_dirty": bool(worktree.strip())}


def _extract_archive(first_part: Path, raw_root: Path, rar_executable: Path) -> None:
    marker = raw_root / ".extraction-complete.json"
    if marker.exists():
        return
    raw_root.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(rar_executable), "x", "-idq", "-o+", "-y", str(first_part), str(raw_root) + os.sep],
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"RAR extraction failed with code {completed.returncode}")
    _atomic_json(
        marker,
        {"complete": True, "first_part": first_part.name, "return_code": 0},
    )


def _bearing_source(raw_root: Path, bearing_id: str) -> tuple[Path, str, float, float]:
    condition_index = bearing_id[len("Bearing") :].split("_", 1)[0]
    condition, speed_rpm, load_kn = CONDITIONS[condition_index]
    return (
        raw_root / "XJTU-SY_Bearing_Datasets" / condition / bearing_id,
        condition,
        speed_rpm,
        load_kn,
    )


def _build_feature_cache(runtime_root: Path) -> list[dict[str, Any]]:
    raw_root = runtime_root / "raw"
    cache_root = runtime_root / "features"
    summaries: list[dict[str, Any]] = []
    bearings = (*FROZEN_BEARING_SPLIT["initial"], *FROZEN_BEARING_SPLIT["development"])
    for index, bearing_id in enumerate(bearings, start=1):
        cache_path = cache_root / f"{bearing_id}.npz"
        if cache_path.exists():
            with np.load(cache_path, allow_pickle=False) as cache:
                summary = {
                    "bearing_id": bearing_id,
                    "sample_count": int(len(cache["y"])),
                    "feature_count": int(cache["X"].shape[1]),
                    "output_path": str(cache_path),
                    "resumed": True,
                }
        else:
            source, condition, speed_rpm, load_kn = _bearing_source(raw_root, bearing_id)
            result = extract_bearing_cache(
                source,
                cache_path,
                condition=condition,
                bearing_id=bearing_id,
                speed_rpm=speed_rpm,
                load_kn=load_kn,
            )
            summary = {
                "bearing_id": result.bearing_id,
                "sample_count": result.sample_count,
                "feature_count": result.feature_count,
                "output_path": result.output_path,
                "resumed": False,
            }
        summaries.append(summary)
        _status(
            runtime_root,
            "feature_cache",
            completed_bearings=index,
            total_bearings=len(bearings),
            last_bearing=bearing_id,
        )
    _atomic_json(cache_root / "manifest.json", {"bearings": summaries})
    return summaries


def main() -> int:
    args = _arguments()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    runtime_root = args.runtime_root
    if Path(args.experiment_directory).name != args.experiment_directory:
        raise ValueError("experiment directory must be a single relative name")
    experiment_root = runtime_root / args.experiment_directory
    runtime_root.mkdir(parents=True, exist_ok=True)
    selected_cpus = _limit_cpu()
    try:
        _status(runtime_root, "validating_archives", cpu_affinity=selected_cpus)
        hashes = _validate_archives(config, args.archive)
        _atomic_json(runtime_root / "archive-hashes.json", hashes)
        _atomic_json(
            runtime_root / f"run-metadata-{args.experiment_directory}.json",
            {
                "experiment_id": config["experiment_id"],
                "experiment_directory": args.experiment_directory,
                "local_development_only": True,
                **_source_state(),
            },
        )
        _status(runtime_root, "extracting", cpu_affinity=selected_cpus)
        _extract_archive(args.archive, runtime_root / "raw", args.rar_executable)
        _status(runtime_root, "feature_cache", completed_bearings=0, total_bearings=12)
        summaries = _build_feature_cache(runtime_root)
        stream = load_xjtu_stream(runtime_root / "features", include_sealed=False)
        _status(
            runtime_root,
            "serial_experiments",
            cached_bearings=len(summaries),
            initial_samples=len(stream.initial.y),
            development_samples=sum(len(batch.y) for batch in stream.development),
        )
        result = run_serial_experiments(stream, config, experiment_root)
        validation = validate_serial_output(
            experiment_root,
            expected_round_ids=tuple(item["id"] for item in config["rounds"]),
            minimum_real_candidates=3,
        )
        _atomic_json(runtime_root / f"validation-{args.experiment_directory}.json", validation)
        _status(
            runtime_root,
            "completed",
            experiment_directory=args.experiment_directory,
            serial_result=result,
            validation=validation,
        )
        return 0
    except Exception as exc:
        _status(
            runtime_root,
            "failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())

