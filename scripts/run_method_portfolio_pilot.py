"""Run bounded method probes on adjacent unseen stream batches.

This research runner never reads the confirmation directory. It trains on legal
feedback through round t and evaluates the probe only on round t+1.
"""

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

from brace_msi.method_pilot import (
    discover_transition_paths,
    run_native_candidates,
    run_transition,
    summarize_transitions,
)
from brace_msi.platform_runtime import _NativeModel, _read_rows


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _profile_run(
    *,
    profile: str,
    stream_root: Path,
    package_root: Path,
    output_root: Path,
    seed: int,
    max_transitions: int,
    low_budget: bool,
    experiment_id: str,
    portfolio: str,
) -> dict[str, Any]:
    checkpoint = package_root / PACKAGES[profile] / "checkpoint.npz"
    parent = _NativeModel.load(checkpoint)
    transitions = discover_transition_paths(stream_root / profile)
    if max_transitions:
        transitions = transitions[:max_transitions]

    observed_x: list[np.ndarray] = []
    observed_y: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    started = time.monotonic()
    for transition_index, (current_path, next_path) in enumerate(transitions, 1):
        current = _read_rows(current_path, parent, require_answers=True)
        next_batch = _read_rows(next_path, parent, require_answers=True)
        history_x = (
            np.concatenate(observed_x, axis=0)
            if observed_x
            else np.empty((0, len(parent.meta["paths"])), dtype=np.float64)
        )
        history_y = (
            np.concatenate(observed_y, axis=0)
            if observed_y
            else np.empty(
                (0,),
                dtype=(
                    np.int64
                    if parent.meta["task"] == "classification"
                    else np.float64
                ),
            )
        )
        common = {
            "history_x": history_x,
            "history_y": history_y,
            "current_x": current["x"],
            "current_y": current["y"],
            "next_x": next_batch["x"],
            "next_y": next_batch["y"],
        }
        if portfolio == "teachers":
            transition_rows = run_transition(
                parent,
                **common,
                seed=seed + transition_index,
                low_budget=low_budget,
            )
        else:
            transition_rows = run_native_candidates(parent, **common)
        for row in transition_rows:
            rows.append(
                {
                    **row,
                    "profile": profile,
                    "train_round": transition_index,
                    "eval_round": transition_index + 1,
                    "history_samples": int(len(history_x)),
                    "current_samples": int(len(current["x"])),
                    "unseen_eval_samples": int(len(next_batch["x"])),
                }
            )
        manifests.append(
            {
                "train_round": transition_index,
                "eval_round": transition_index + 1,
                "train_feedback": str(current_path),
                "train_sha256": current["sha256"],
                "eval_feedback": str(next_path),
                "eval_sha256": next_batch["sha256"],
                "confirmation_files_read": 0,
            }
        )
        observed_x.append(current["x"])
        observed_y.append(current["y"])
        print(
            f"{profile} transition {transition_index}/{len(transitions)} complete",
            flush=True,
        )

    result = {
        "experiment_id": experiment_id,
        "profile": profile,
        "task": parent.meta["task"],
        "evidence_scope": "adjacent-unseen-stream-proxy",
        "selection_safe_for_confirmation": True,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "parent_checkpoint": str(checkpoint),
        "parent_epochs": int(parent.meta["epochs"]),
        "transitions": len(transitions),
        "wall_seconds": time.monotonic() - started,
        "summary": summarize_transitions(rows),
        "manifests": manifests,
        "rows": rows,
    }
    _write_json(output_root / f"profile-{profile}.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stream-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261116)
    parser.add_argument("--max-transitions", type=int, default=0)
    parser.add_argument("--low-budget", action="store_true")
    parser.add_argument("--experiment-id", default="METHOD-PORTFOLIO-PILOT-001-A1")
    parser.add_argument("--portfolio", choices=("teachers", "native"), default="teachers")
    args = parser.parse_args()
    if not 0 <= args.max_transitions <= 9:
        parser.error("--max-transitions must be between 0 and 9")
    if "confirmation" in str(args.output_root).lower():
        parser.error("output root cannot be a confirmation path")

    args.output_root.mkdir(parents=True, exist_ok=True)
    process = psutil.Process(os.getpid())
    started = time.monotonic()
    results = [
        _profile_run(
            profile=profile,
            stream_root=args.stream_root,
            package_root=args.package_root,
            output_root=args.output_root,
            seed=args.seed,
            max_transitions=args.max_transitions,
            low_budget=args.low_budget,
            experiment_id=args.experiment_id,
            portfolio=args.portfolio,
        )
        for profile in PACKAGES
    ]
    suite = {
        "experiment_id": args.experiment_id,
        "created_at_unix": time.time(),
        "python": sys.version,
        "platform": platform.platform(),
        "seed": args.seed,
        "low_budget": args.low_budget,
        "portfolio": args.portfolio,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "wall_seconds": time.monotonic() - started,
        "rss_bytes": int(process.memory_info().rss),
        "profiles": {
            result["profile"]: {
                "task": result["task"],
                "transitions": result["transitions"],
                "wall_seconds": result["wall_seconds"],
                "summary": result["summary"],
            }
            for result in results
        },
    }
    _write_json(args.output_root / "summary.json", suite)
    print(json.dumps(suite, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
