"""Run preregistered native objective pilots on adjacent unseen stages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_msi.method_pilot import (  # noqa: E402
    _metrics,
    _native_prediction,
    _signed_gain,
    discover_transition_paths,
    fit_performance_method,
    performance_method_names,
)
from brace_msi.official_metrics import nasa_asymmetric_score  # noqa: E402
from brace_msi.platform_runtime import _NativeModel, _read_rows  # noqa: E402


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _empty_history(model: _NativeModel) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.empty((0, len(model.meta["paths"])), dtype=np.float64),
        np.empty(
            (0,),
            dtype=np.int64 if model.meta["task"] == "classification" else np.float64,
        ),
    )


def _run_method(
    *,
    profile: str,
    method: str,
    initial: _NativeModel,
    transitions: list[tuple[Path, Path]],
    output_root: Path,
) -> dict[str, Any]:
    parent = initial.clone()
    task = str(initial.meta["task"])
    history_x: list[np.ndarray] = []
    history_y: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    cpu_total = 0.0
    for transition_index, (current_path, next_path) in enumerate(transitions, 1):
        current = _read_rows(current_path, initial, require_answers=True)
        next_batch = _read_rows(next_path, initial, require_answers=True)
        prior_x, prior_y = _empty_history(initial)
        if history_x:
            prior_x = np.concatenate(history_x, axis=0)
            prior_y = np.concatenate(history_y, axis=0)
        direct_parent_metrics = _metrics(
            task, next_batch["y"], _native_prediction(parent, next_batch["x"])
        )
        static_metrics = _metrics(
            task, next_batch["y"], _native_prediction(initial, next_batch["x"])
        )
        started = time.process_time()
        candidate = fit_performance_method(
            parent,
            method=method,
            history_x=prior_x,
            history_y=prior_y,
            current_x=current["x"],
            current_y=current["y"],
        )
        cpu_seconds = time.process_time() - started
        cpu_total += cpu_seconds
        prediction = _native_prediction(candidate, next_batch["x"])
        candidate_metrics = _metrics(task, next_batch["y"], prediction)
        row: dict[str, Any] = {
            "train_round": transition_index,
            "eval_round": transition_index + 1,
            "train_sha256": current["sha256"],
            "eval_sha256": next_batch["sha256"],
            "static_metrics": static_metrics,
            "direct_parent_metrics": direct_parent_metrics,
            "candidate_metrics": candidate_metrics,
            "gain_vs_static": _signed_gain(task, static_metrics, candidate_metrics),
            "gain_vs_direct_parent": _signed_gain(
                task, direct_parent_metrics, candidate_metrics
            ),
            "cpu_seconds": cpu_seconds,
        }
        if task == "regression":
            row["nasa_score"] = nasa_asymmetric_score(next_batch["y"], prediction)
            row["static_nasa_score"] = nasa_asymmetric_score(
                next_batch["y"], _native_prediction(initial, next_batch["x"])
            )
        rows.append(row)
        parent = candidate
        history_x.append(current["x"])
        history_y.append(current["y"])

    checkpoint = output_root / profile / method / "checkpoint.npz"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    parent.save(checkpoint)
    loaded = _NativeModel.load(checkpoint)
    gains = np.asarray([row["gain_vs_static"] for row in rows], dtype=np.float64)
    direct = np.asarray(
        [row["gain_vs_direct_parent"] for row in rows], dtype=np.float64
    )
    summary: dict[str, Any] = {
        "transitions": len(rows),
        "mean_gain_vs_static": float(np.mean(gains)),
        "worst_gain_vs_static": float(np.min(gains)),
        "win_rate_vs_static": float(np.mean(gains > 0.0)),
        "mean_gain_vs_direct_parent": float(np.mean(direct)),
        "worst_gain_vs_direct_parent": float(np.min(direct)),
        "cpu_seconds": cpu_total,
    }
    if task == "regression":
        nasa = np.asarray([row["nasa_score"] for row in rows], dtype=np.float64)
        static_nasa = np.asarray(
            [row["static_nasa_score"] for row in rows], dtype=np.float64
        )
        summary.update(
            mean_nasa_score=float(np.mean(nasa)),
            mean_static_nasa_score=float(np.mean(static_nasa)),
            nasa_improvement_ratio=float(
                (np.mean(static_nasa) - np.mean(nasa))
                / max(float(np.mean(static_nasa)), 1e-12)
            ),
        )
    result = {
        "profile": profile,
        "task": task,
        "method": method,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "final_epochs": int(loaded.meta["epochs"]),
        "final_steps": int(loaded.meta["steps"]),
        "summary": summary,
        "rows": rows,
    }
    _write_json(output_root / profile / method / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stream-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--experiment-id", default="PERFORMANCE-METHOD-PILOT-001-A1"
    )
    parser.add_argument("--profiles", nargs="+", choices=tuple(PACKAGES), default=None)
    parser.add_argument(
        "--portfolio",
        choices=("a1", "bias_followup", "intensity_followup", "stability_followup"),
        default="a1",
    )
    args = parser.parse_args()
    if args.output_root.name != args.experiment_id:
        parser.error("output directory name must equal the experiment ID")
    if "confirmation" in str(args.output_root).lower():
        parser.error("output root cannot be a confirmation path")
    args.output_root.mkdir(parents=True, exist_ok=False)

    process = psutil.Process(os.getpid())
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    selected_profiles = args.profiles or list(PACKAGES)
    for profile in selected_profiles:
        package = PACKAGES[profile]
        initial = _NativeModel.load(args.package_root / package / "checkpoint.npz")
        transitions = discover_transition_paths(args.stream_root / profile)
        for method in performance_method_names(
            str(initial.meta["task"]), args.portfolio
        ):
            result = _run_method(
                profile=profile,
                method=method,
                initial=initial,
                transitions=transitions,
                output_root=args.output_root,
            )
            results.append(result)
            print(f"{profile} {method} complete", flush=True)

    suite = {
        "experiment_id": args.experiment_id,
        "evidence_scope": "continuous-parent-adjacent-unseen-stream-proxy",
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "pytrio_calls": 0,
        "swanlab_syncs": 0,
        "wall_seconds": time.monotonic() - started,
        "rss_bytes": int(process.memory_info().rss),
        "results": [
            {key: value for key, value in result.items() if key != "rows"}
            for result in results
        ],
    }
    _write_json(args.output_root / "summary.json", suite)
    print(json.dumps(suite, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
