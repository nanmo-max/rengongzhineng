"""Evaluate official-schema recipes under a continuously inherited parent chain."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brace_msi.method_pilot import (  # noqa: E402
    _metrics,
    _native_prediction,
    _signed_gain,
    discover_transition_paths,
    fit_native_recipe,
)
from brace_msi.platform_runtime import _NativeModel, _read_rows  # noqa: E402


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}
RECIPES = (
    "current_e1",
    "current_e3_lr3",
    "cumulative_e1",
    "cumulative_e3",
    "cumulative_e3_lr0.3",
    "recent_e3",
    "soup_current_e3_alpha0.25",
    "soup_current_e3_alpha0.5",
    "soup_current_e3_alpha0.75",
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, float]:
    static_gains = np.asarray([row["gain_vs_static"] for row in rows], dtype=float)
    delayed_gains = np.asarray([row["gain_vs_direct_parent"] for row in rows], dtype=float)
    return {
        "transitions": float(len(rows)),
        "mean_gain_vs_static": float(np.mean(static_gains)),
        "median_gain_vs_static": float(np.median(static_gains)),
        "worst_gain_vs_static": float(np.min(static_gains)),
        "win_rate_vs_static": float(np.mean(static_gains > 0.0)),
        "mean_gain_vs_direct_parent": float(np.mean(delayed_gains)),
        "worst_gain_vs_direct_parent": float(np.min(delayed_gains)),
        "win_rate_vs_direct_parent": float(np.mean(delayed_gains > 0.0)),
        "cpu_seconds": float(sum(row["cpu_seconds"] for row in rows)),
    }


def _run_strategy(
    *,
    profile: str,
    recipe: str,
    stream_root: Path,
    checkpoint: Path,
    output_root: Path,
) -> dict[str, Any]:
    initial = _NativeModel.load(checkpoint)
    parent = initial.clone()
    task = str(initial.meta["task"])
    history_x: list[np.ndarray] = []
    history_y: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    for index, (current_path, next_path) in enumerate(
        discover_transition_paths(stream_root / profile), 1
    ):
        current = _read_rows(current_path, initial, require_answers=True)
        next_batch = _read_rows(next_path, initial, require_answers=True)
        prior_x = (
            np.concatenate(history_x, axis=0)
            if history_x
            else np.empty((0, len(initial.meta["paths"])), dtype=np.float64)
        )
        prior_y = (
            np.concatenate(history_y, axis=0)
            if history_y
            else np.empty(
                (0,),
                dtype=np.int64 if task == "classification" else np.float64,
            )
        )
        parent_metrics = _metrics(
            task, next_batch["y"], _native_prediction(parent, next_batch["x"])
        )
        static_metrics = _metrics(
            task, next_batch["y"], _native_prediction(initial, next_batch["x"])
        )
        previous_epochs = int(parent.meta["epochs"])
        started = time.process_time()
        candidate = fit_native_recipe(
            parent,
            recipe=recipe,
            history_x=prior_x,
            history_y=prior_y,
            current_x=current["x"],
            current_y=current["y"],
        )
        cpu_seconds = time.process_time() - started
        if int(candidate.meta["epochs"]) <= previous_epochs:
            raise RuntimeError("candidate epoch lineage did not advance")
        candidate_metrics = _metrics(
            task, next_batch["y"], _native_prediction(candidate, next_batch["x"])
        )
        rows.append(
            {
                "train_round": index,
                "eval_round": index + 1,
                "current_sha256": current["sha256"],
                "unseen_eval_sha256": next_batch["sha256"],
                "parent_epochs": previous_epochs,
                "candidate_epochs": int(candidate.meta["epochs"]),
                "static_metrics": static_metrics,
                "direct_parent_metrics": parent_metrics,
                "candidate_metrics": candidate_metrics,
                "gain_vs_static": _signed_gain(task, static_metrics, candidate_metrics),
                "gain_vs_direct_parent": _signed_gain(
                    task, parent_metrics, candidate_metrics
                ),
                "cpu_seconds": cpu_seconds,
            }
        )
        parent = candidate
        history_x.append(current["x"])
        history_y.append(current["y"])

    checkpoint_output = output_root / profile / recipe / "checkpoint.npz"
    checkpoint_output.parent.mkdir(parents=True, exist_ok=True)
    parent.save(checkpoint_output)
    reloaded = _NativeModel.load(checkpoint_output)
    if reloaded.meta["format"] != "contest.cpu-mlp.v1":
        raise RuntimeError("final checkpoint format changed")
    return {
        "profile": profile,
        "task": task,
        "recipe": recipe,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "final_checkpoint": str(checkpoint_output),
        "final_epochs": int(reloaded.meta["epochs"]),
        "final_steps": int(reloaded.meta["steps"]),
        "summary": _summarize(rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stream-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--experiment-id", default="METHOD-PORTFOLIO-PILOT-001-A3")
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    process = psutil.Process(os.getpid())
    results: list[dict[str, Any]] = []
    for profile, package in PACKAGES.items():
        checkpoint = args.package_root / package / "checkpoint.npz"
        for recipe in RECIPES:
            result = _run_strategy(
                profile=profile,
                recipe=recipe,
                stream_root=args.stream_root,
                checkpoint=checkpoint,
                output_root=args.output_root,
            )
            results.append(result)
            _write_json(
                args.output_root / profile / recipe / "result.json", result
            )
            print(f"{profile} {recipe} complete", flush=True)
    suite = {
        "experiment_id": args.experiment_id,
        "evidence_scope": "continuous-parent-adjacent-unseen-stream-proxy",
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "python": sys.version,
        "platform": platform.platform(),
        "wall_seconds": time.monotonic() - started,
        "rss_bytes": int(process.memory_info().rss),
        "results": [
            {
                key: value
                for key, value in result.items()
                if key != "rows"
            }
            for result in results
        ],
    }
    _write_json(args.output_root / "summary.json", suite)
    print(json.dumps(suite, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
