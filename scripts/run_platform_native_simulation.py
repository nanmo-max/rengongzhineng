from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.platform_runtime import PlatformRuntimeConfig
from brace_msi.platform_simulation import run_ten_round_simulation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-swanlab", action="store_true")
    args = parser.parse_args()
    raw = json.loads(args.config.read_text(encoding="utf-8"))
    if args.output.exists():
        raise FileExistsError("output must be a new directory")
    args.output.mkdir(parents=True)
    runtime = PlatformRuntimeConfig(
        policy_mode=str(raw.get("policy_mode", "protocol")),
        epochs=int(raw["epochs_per_round"]),
        learning_rate_multiplier=float(raw["learning_rate_multiplier"]),
        gate_fraction=float(raw["gate_fraction"]),
        min_primary_improvement=float(raw["min_primary_improvement"]),
        min_relative_improvement=float(raw.get("min_relative_improvement", 0.05)),
        max_training_rounds=int(raw["max_training_rounds"]),
        max_anchor_degradation=float(raw.get("max_anchor_degradation", 0.0)),
        max_replay_samples=int(raw.get("max_replay_samples", 4096)),
    )
    profiles = {}
    for profile, directory in raw["profiles"].items():
        package = args.package_root / directory
        profiles[profile] = run_ten_round_simulation(
            package / raw["data_file"],
            package / raw["parent_checkpoint"],
            args.output / profile,
            prediction_data_path=package / raw.get("prediction_file", raw["data_file"]),
            config=runtime,
            export_swanlab=not args.no_swanlab,
            swanlab_project="brace-msi-platform-native",
            experiment_name=f"{raw['experiment_id']}-{profile}",
        )
    summary = {
        "format": "brace-msi.platform-suite.v1",
        "experiment_id": raw["experiment_id"],
        "status": "completed",
        "official_test_opportunities_used": 0,
        "profiles": profiles,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "profiles": sorted(profiles),
                "rounds": sum(value["round_count"] for value in profiles.values()),
                "candidates": sum(value["candidate_count"] for value in profiles.values()),
            },
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

