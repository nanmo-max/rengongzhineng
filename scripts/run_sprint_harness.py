"""Run and machine-validate the frozen three-profile ten-round sprint Harness."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from brace_msi.official_agent_harness import (
    FrozenScheduleOfficialProposalProvider,
    official_agent_config_from_mapping,
    run_official_agent_harness,
    validate_official_agent_harness,
)
from brace_msi.official_package import audit_package_root
from brace_msi.official_trainer import OfficialTrainer


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _config_sha256(config: dict) -> str:
    raw = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    raw_config = json.loads(args.config.read_text(encoding="utf-8"))
    fingerprint = _config_sha256(raw_config)
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    source_dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    )
    manifest_path = args.runtime_root / "execution-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("configuration_sha256") != fingerprint:
            raise ValueError("sprint Harness configuration changed after start")
        if manifest.get("source_commit") != source_commit:
            raise ValueError("sprint Harness source commit changed after start")
    elif args.validate_only:
        raise ValueError("execution manifest is missing")
    else:
        _atomic_json(
            manifest_path,
            {
                "format": "brace-msi.sprint-harness-manifest.v1",
                "experiment_id": raw_config["experiment_id"],
                "configuration_sha256": fingerprint,
                "source_commit": source_commit,
                "source_tree_dirty": source_dirty,
                "official_test_opportunities": 0,
                "pytrio_calls": 0,
                "swanlab_calls": 0,
            },
        )

    audits = audit_package_root(args.package_root, raw_config)
    harness_config = official_agent_config_from_mapping(raw_config)
    validations: dict[str, dict] = {}
    results: dict[str, dict] = {}
    for profile in ("A", "B", "C"):
        package = audits[profile]
        runtime = args.runtime_root / "profiles" / profile
        if not args.validate_only:
            provider = FrozenScheduleOfficialProposalProvider(
                package, tuple(raw_config["deterministic_schedules"][profile])
            )
            result = run_official_agent_harness(
                package,
                runtime,
                harness_config,
                OfficialTrainer(
                    sys.executable,
                    timeout_seconds=args.timeout_seconds,
                    allowed_learning_rate_multipliers=(
                        harness_config.allowed_learning_rate_multipliers
                    ),
                ),
                provider,
                fallback_provider=provider,
            )
            results[profile] = asdict(result)
        validations[profile] = validate_official_agent_harness(
            runtime, package, harness_config
        )
    if not all(item["valid"] and item["complete"] for item in validations.values()):
        raise ValueError("one or more sprint Harness profiles are incomplete")
    previous_results: dict[str, dict] = {}
    summary_path = args.runtime_root / "summary.json"
    if args.validate_only and summary_path.is_file():
        previous_results = json.loads(summary_path.read_text(encoding="utf-8")).get(
            "results", {}
        )
    summary = {
        "format": "brace-msi.sprint-harness-summary.v1",
        "experiment_id": raw_config["experiment_id"],
        "configuration_sha256": fingerprint,
        "source_commit": source_commit,
        "source_tree_dirty_at_validation": source_dirty,
        "results": results or previous_results,
        "validation": validations,
        "boundaries": {
            "official_test_opportunities": 0,
            "pytrio_calls": 0,
            "swanlab_calls": 0,
            "real_drift_stream": False,
            "round_semantics": "candidate_adaptation_decision"
        }
    }
    _atomic_json(summary_path, summary)
    print(json.dumps({"status": "validated", "profiles": validations}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
