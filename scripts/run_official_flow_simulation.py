from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.official_flow_simulation import (
    build_bearing_stream_plan,
    build_engine_stream_plan,
    build_gas_stream_plan,
    run_official_flow_simulation,
    run_sequential_adaptation_simulation,
)
from brace_msi.platform_advisor import build_platform_advisor
from brace_msi.platform_runtime import PlatformRuntimeConfig


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}


def _plan(profile: str, package_root: Path, gas_raw_root: Path):
    package = package_root / PACKAGES[profile]
    train = package / "public" / "train.jsonl"
    if profile == "A":
        return build_gas_stream_plan(train, gas_raw_root)
    unseen = package / "public" / "validation.jsonl"
    if profile == "B":
        return build_bearing_stream_plan(train, unseen)
    return build_engine_stream_plan(train, unseen)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run prediction-first BRACE-MSI local platform simulation")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--gas-raw-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", choices=sorted(PACKAGES), default=sorted(PACKAGES))
    parser.add_argument("--max-training-rounds", type=int, default=10)
    parser.add_argument(
        "--flow-mode", choices=("sequential", "external-only"), default="sequential"
    )
    parser.add_argument("--arrival-drop-trigger", type=float, default=0.02)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate-multiplier", type=float, default=1.0)
    parser.add_argument("--advisor", choices=("deterministic", "pytrio"), default="deterministic")
    parser.add_argument("--pytrio-timeout", type=float, default=60.0)
    parser.add_argument("--no-swanlab", action="store_true")
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise FileExistsError("output root must be new")
    output_root.mkdir(parents=True)
    tasks = {}
    config = PlatformRuntimeConfig(
        policy_mode="sequential" if args.flow_mode == "sequential" else "competitive",
        max_training_rounds=args.max_training_rounds,
        arrival_drop_trigger=args.arrival_drop_trigger,
        epochs=args.epochs,
        learning_rate_multiplier=args.learning_rate_multiplier,
    )
    advisor = (
        build_platform_advisor(timeout_seconds=args.pytrio_timeout)
        if args.advisor == "pytrio"
        else None
    )
    for profile in args.profiles:
        package = args.package_root.resolve() / PACKAGES[profile]
        plan = _plan(profile, args.package_root.resolve(), args.gas_raw_root.resolve())
        runner = (
            run_sequential_adaptation_simulation
            if args.flow_mode == "sequential"
            else run_official_flow_simulation
        )
        tasks[profile] = runner(
            plan,
            package / "checkpoint.npz",
            output_root / profile,
            config=config,
            advisor=advisor,
            export_swanlab=not args.no_swanlab,
        )
    aggregate = {
        "format": (
            "brace-msi.sequential-adaptation-suite.v1"
            if args.flow_mode == "sequential"
            else "brace-msi.official-flow-suite.v1"
        ),
        "status": "completed",
        "evidence_scope": "local_protocol_and_task_stream_simulation_not_official_hidden_score",
        "profiles": list(args.profiles),
        "advisor": args.advisor,
        "flow_mode": args.flow_mode,
        "tasks": {
            profile: {
                "round_count": task["round_count"],
                "parent_chain_valid": task["parent_chain_valid"],
                "confirmation_read_count": task["confirmation_read_count"],
                "local_final_confirmation": task["local_final_confirmation"],
                "input_tokens": task["input_tokens"],
                "output_tokens": task["output_tokens"],
            }
            for profile, task in tasks.items()
        },
    }
    (output_root / "suite-summary.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
