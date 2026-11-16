"""Run the evidence-routed two-candidate policy without confirmation access."""

from __future__ import annotations

import argparse
import json
import os
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

from brace_msi.competitive_policy import (  # noqa: E402
    PortfolioEvidence,
    build_candidate_plan,
)
from brace_msi.method_pilot import (  # noqa: E402
    _metrics,
    _native_prediction,
    _signed_gain,
    fit_native_recipe,
)
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
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _run_profile(
    profile: str,
    stream_root: Path,
    package_root: Path,
    output_root: Path,
    *,
    enhanced_routing: bool,
) -> dict[str, Any]:
    initial_path = package_root / PACKAGES[profile] / "checkpoint.npz"
    initial = _NativeModel.load(initial_path)
    parent = initial.clone()
    task = str(parent.meta["task"])
    history_x: list[np.ndarray] = []
    history_y: list[np.ndarray] = []
    batch_means: list[float] = []
    rounds: list[dict[str, Any]] = []
    direct_predecessor: _NativeModel | None = None
    previous_delayed_gain: float | None = None
    failure_streak = 0
    candidate_count = accepted_count = rollback_count = 0
    consecutive_aggressive = 0
    cpu_total = 0.0

    for index in range(1, 11):
        round_root = stream_root / profile / "runtime-inputs" / f"round-{index:02d}"
        feedback = _read_rows(round_root / "feedback.jsonl", initial, require_answers=True)
        update = _read_rows(round_root / "update.jsonl", initial, require_answers=True)
        gate = _read_rows(round_root / "gate.jsonl", initial, require_answers=True)
        arrival_metrics = _metrics(
            task, feedback["y"], _native_prediction(parent, feedback["x"])
        )
        static_metrics = _metrics(
            task, feedback["y"], _native_prediction(initial, feedback["x"])
        )
        arrival_gain = _signed_gain(task, static_metrics, arrival_metrics)
        rollback = False
        if direct_predecessor is not None:
            predecessor_metrics = _metrics(
                task,
                feedback["y"],
                _native_prediction(direct_predecessor, feedback["x"]),
            )
            previous_delayed_gain = _signed_gain(
                task, predecessor_metrics, arrival_metrics
            )
            if previous_delayed_gain < 0.0:
                parent = direct_predecessor
                rollback = True
                rollback_count += 1
                failure_streak += 1
            else:
                failure_streak = 0
            direct_predecessor = None

        batch_means.append(float(np.mean(feedback["y"])))
        plan = build_candidate_plan(
            PortfolioEvidence(
                task_kind=task,
                target_batch_means=tuple(batch_means),
                target_scale=float(parent.meta["target_scale"]),
                previous_delayed_gain=previous_delayed_gain,
                failure_streak=failure_streak,
                consecutive_aggressive=consecutive_aggressive,
            )
        )
        action = "rollback" if rollback else "retain"
        selected_recipe: str | None = None
        candidate_receipts: list[dict[str, Any]] = []
        deployed_parent: _NativeModel | None = None
        if not rollback and index < 10:
            prior_x = (
                np.concatenate(history_x, axis=0)
                if history_x
                else np.empty((0, len(parent.meta["paths"])), dtype=np.float64)
            )
            prior_y = (
                np.concatenate(history_y, axis=0)
                if history_y
                else np.empty(
                    (0,), dtype=np.int64 if task == "classification" else np.float64
                )
            )
            parent_gate = _metrics(
                task, gate["y"], _native_prediction(parent, gate["x"])
            )
            candidate_models: list[tuple[str, float, _NativeModel]] = []
            high_confidence_forward = bool(
                enhanced_routing
                and plan.secondary_recipe == "current_e3_lr3"
                and plan.monotonic_trend_score >= 0.95
                and plan.normalized_trend_slope >= 0.10
            )
            compare_classification = bool(
                enhanced_routing
                and task == "classification"
                and plan.secondary_recipe is not None
            )
            for slot, recipe in enumerate(
                filter(None, (plan.primary_recipe, plan.secondary_recipe)), 1
            ):
                if (
                    slot == 2
                    and candidate_receipts[-1]["gain"] > 0.0
                    and not high_confidence_forward
                    and not compare_classification
                ):
                    break
                started = time.process_time()
                candidate = fit_native_recipe(
                    parent,
                    recipe=recipe,
                    history_x=prior_x,
                    history_y=prior_y,
                    current_x=update["x"],
                    current_y=update["y"],
                )
                elapsed = time.process_time() - started
                cpu_total += elapsed
                candidate_count += 1
                candidate_gate = _metrics(
                    task, gate["y"], _native_prediction(candidate, gate["x"])
                )
                gain = _signed_gain(task, parent_gate, candidate_gate)
                candidate_receipts.append(
                    {
                        "slot": slot,
                        "recipe": recipe,
                        "gate_parent": parent_gate,
                        "gate_candidate": candidate_gate,
                        "gain": gain,
                        "cpu_seconds": elapsed,
                    }
                )
                candidate_models.append((recipe, gain, candidate))
            chosen: tuple[str, float, _NativeModel] | None = None
            if high_confidence_forward and len(candidate_models) >= 2:
                chosen = candidate_models[-1]
            elif compare_classification and candidate_models:
                chosen = max(candidate_models, key=lambda item: item[1])
                if chosen[1] <= 0.0:
                    chosen = None
            else:
                chosen = next(
                    (item for item in candidate_models if item[1] > 0.0), None
                )
            if chosen is not None:
                selected_recipe, _, selected_candidate = chosen
                deployed_parent = parent.clone()
                parent = selected_candidate
                direct_predecessor = deployed_parent
                accepted_count += 1
                action = "deploy"
                failure_streak = 0
                consecutive_aggressive = (
                    consecutive_aggressive + 1
                    if selected_recipe == "current_e3_lr3"
                    else 0
                )
            else:
                consecutive_aggressive = 0
            if selected_recipe is None:
                failure_streak += 1

        rounds.append(
            {
                "round_index": index,
                "feedback_sha256": feedback["sha256"],
                "update_sha256": update["sha256"],
                "gate_sha256": gate["sha256"],
                "arrival_metrics": arrival_metrics,
                "static_metrics": static_metrics,
                "arrival_gain_vs_static": arrival_gain,
                "previous_delayed_gain": previous_delayed_gain,
                "action": action,
                "selected_recipe": selected_recipe,
                "plan": {
                    "primary": plan.primary_recipe,
                    "secondary": plan.secondary_recipe,
                    "trend_score": plan.monotonic_trend_score,
                    "normalized_slope": plan.normalized_trend_slope,
                    "rationale": plan.rationale,
                },
                "candidates": candidate_receipts,
            }
        )
        history_x.append(feedback["x"])
        history_y.append(feedback["y"])

    gains = np.asarray([row["arrival_gain_vs_static"] for row in rounds], dtype=float)
    checkpoint = output_root / profile / "checkpoint.npz"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    parent.save(checkpoint)
    loaded = _NativeModel.load(checkpoint)
    return {
        "profile": profile,
        "task": task,
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "candidate_count": candidate_count,
        "accepted_count": accepted_count,
        "rollback_count": rollback_count,
        "mean_arrival_gain_vs_static": float(np.mean(gains)),
        "median_arrival_gain_vs_static": float(np.median(gains)),
        "worst_arrival_gain_vs_static": float(np.min(gains)),
        "win_rate_vs_static": float(np.mean(gains > 0.0)),
        "cpu_seconds": cpu_total,
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "final_epochs": int(loaded.meta["epochs"]),
        "final_steps": int(loaded.meta["steps"]),
        "rounds": rounds,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stream-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--experiment-id", default="COMPETITIVE-POLICY-002-A1")
    parser.add_argument("--enhanced-routing", action="store_true")
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    results = [
        _run_profile(
            profile,
            args.stream_root,
            args.package_root,
            args.output_root,
            enhanced_routing=args.enhanced_routing,
        )
        for profile in PACKAGES
    ]
    for result in results:
        _write_json(args.output_root / result["profile"] / "result.json", result)
    suite = {
        "experiment_id": args.experiment_id,
        "enhanced_routing": args.enhanced_routing,
        "evidence_scope": "ten-round-prequential-proxy-no-confirmation",
        "confirmation_files_read": 0,
        "official_trial_count": 0,
        "wall_seconds": time.monotonic() - started,
        "rss_bytes": int(psutil.Process(os.getpid()).memory_info().rss),
        "results": [
            {key: value for key, value in result.items() if key != "rounds"}
            for result in results
        ],
    }
    _write_json(args.output_root / "summary.json", suite)
    print(json.dumps(suite, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
