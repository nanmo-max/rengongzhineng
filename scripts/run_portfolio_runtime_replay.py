"""Replay the portfolio policy through the real native platform start entry."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_msi.method_pilot import _metrics, _native_prediction, _signed_gain  # noqa: E402
from brace_msi.platform_runtime import (  # noqa: E402
    ArrivalEvidence,
    PlatformRuntimeConfig,
    _NativeModel,
    _read_rows,
    start_round,
)


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _profile(profile: str, stream: Path, packages: Path, output: Path) -> dict[str, Any]:
    initial_path = packages / PACKAGES[profile] / "checkpoint.npz"
    initial = _NativeModel.load(initial_path)
    parent_path = initial_path
    workspace = output / profile / "workspace"
    rows: list[dict[str, Any]] = []
    rollback_path: Path | None = None
    previous_arrival: dict[str, float] | None = None
    config = PlatformRuntimeConfig(policy_mode="portfolio", max_training_rounds=9)
    for index in range(1, 11):
        round_root = stream / profile / "runtime-inputs" / f"round-{index:02d}"
        feedback = _read_rows(round_root / "feedback.jsonl", initial, require_answers=True)
        parent = _NativeModel.load(parent_path)
        arrival = _metrics(
            initial.meta["task"],
            feedback["y"],
            _native_prediction(parent, feedback["x"]),
        )
        static = _metrics(
            initial.meta["task"],
            feedback["y"],
            _native_prediction(initial, feedback["x"]),
        )
        delayed_gain = None
        predecessor_metrics = None
        if rollback_path is not None:
            predecessor = _NativeModel.load(rollback_path)
            predecessor_metrics = _metrics(
                initial.meta["task"],
                feedback["y"],
                _native_prediction(predecessor, feedback["x"]),
            )
            delayed_gain = _signed_gain(
                initial.meta["task"], predecessor_metrics, arrival
            )
        round_output = output / profile / f"round-{index:02d}"
        receipt = start_round(
            round_root / "update.jsonl",
            parent_path,
            workspace,
            round_output,
            config,
            gate_data_path=round_root / "gate.jsonl",
            arrival_evidence=ArrivalEvidence(
                metrics=arrival,
                previous_metrics=previous_arrival,
                sample_count=len(feedback["ids"]),
                delayed_gain=delayed_gain,
            ),
            rollback_checkpoint=rollback_path,
        )
        rows.append(
            {
                "round_index": index,
                "arrival_metrics": arrival,
                "static_metrics": static,
                "arrival_gain_vs_static": _signed_gain(
                    initial.meta["task"], static, arrival
                ),
                "predecessor_metrics": predecessor_metrics,
                "delayed_gain": delayed_gain,
                "receipt": receipt,
            }
        )
        previous_parent = parent_path
        parent_path = round_output / "checkpoint.npz"
        rollback_path = previous_parent if receipt["deployed"] else None
        previous_arrival = arrival
    final_path = output / profile / "checkpoint.npz"
    shutil.copy2(parent_path, final_path)
    gains = np.asarray([row["arrival_gain_vs_static"] for row in rows], dtype=float)
    return {
        "profile": profile,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "mean_arrival_gain_vs_static": float(np.mean(gains)),
        "worst_arrival_gain_vs_static": float(np.min(gains)),
        "win_rate_vs_static": float(np.mean(gains > 0.0)),
        "candidate_count": sum(row["receipt"]["candidate_trained"] for row in rows),
        "accepted_count": sum(row["receipt"]["deployed"] for row in rows),
        "rollback_count": sum(
            row["receipt"]["decision"]["outcome"] == "rollback" for row in rows
        ),
        "final_checkpoint": str(final_path),
        "final_checkpoint_bytes": final_path.stat().st_size,
        "rounds": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stream-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.output_root.exists():
        raise FileExistsError("output root must be new")
    args.output_root.mkdir(parents=True)
    results = [
        _profile(profile, args.stream_root, args.package_root, args.output_root)
        for profile in PACKAGES
    ]
    for result in results:
        _atomic_json(args.output_root / result["profile"] / "result.json", result)
    summary = {
        "experiment_id": "COMPETITIVE-POLICY-002-A4",
        "entry": "brace_msi.platform_runtime.start_round",
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "results": [
            {key: value for key, value in result.items() if key != "rounds"}
            for result in results
        ],
    }
    _atomic_json(args.output_root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
