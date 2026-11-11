"""Run the preregistered local development queue for the three published tasks."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import psutil

from brace_msi.data.audit import file_sha256
from brace_msi.official_streams import build_official_development_streams
from brace_msi.official_suite import (
    run_official_development_suite,
    validate_official_development_suite,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--gas-root", type=Path, required=True)
    parser.add_argument("--gas-archive", type=Path, required=True)
    parser.add_argument("--cmapss-zip", type=Path, required=True)
    parser.add_argument("--xjtu-cache-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--max-experiments", type=int)
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
            "experiment_id": "OFFICIAL-RULES-ALIGNED-DEV-001",
            "official_rules_aligned": True,
            "official_checkpoint": False,
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


def _source_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"source_commit": commit, "source_tree_dirty": bool(dirty)}


def _verify_sources(
    config: dict[str, Any],
    *,
    gas_archive: Path,
    cmapss_zip: Path,
    xjtu_cache_root: Path,
) -> dict[str, Any]:
    expected = config["source_sha256"]
    paths = {
        "gas_archive": gas_archive,
        "cmapss_zip": cmapss_zip,
        "xjtu_manifest": xjtu_cache_root / "manifest.json",
    }
    observed: dict[str, Any] = {}
    for name, path in paths.items():
        digest = file_sha256(path).upper()
        if digest != str(expected[name]).upper():
            raise RuntimeError(f"source hash mismatch: {name}")
        observed[name] = digest
    cache_hashes: dict[str, str] = {}
    for name, expected_digest in config["xjtu_cache_sha256"].items():
        digest = file_sha256(xjtu_cache_root / name).upper()
        if digest != str(expected_digest).upper():
            raise RuntimeError(f"XJTU cache hash mismatch: {name}")
        cache_hashes[name] = digest
    observed["xjtu_cache_sha256"] = cache_hashes
    return observed


def main() -> int:
    args = _arguments()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    root = args.runtime_root
    root.mkdir(parents=True, exist_ok=True)
    cpus = _limit_cpu()
    try:
        _status(root, "validating_sources", cpu_affinity=cpus)
        hashes = _verify_sources(
            config,
            gas_archive=args.gas_archive,
            cmapss_zip=args.cmapss_zip,
            xjtu_cache_root=args.xjtu_cache_root,
        )
        _atomic_json(root / "source-hashes.json", hashes)
        metadata_path = root / "run-metadata.json"
        if not metadata_path.exists():
            _atomic_json(
                metadata_path,
                {
                    "experiment_id": config["experiment_id"],
                    "official_rules_aligned": True,
                    "official_checkpoint": False,
                    **_source_state(),
                },
            )
        _status(root, "loading_unsealed_streams", cpu_affinity=cpus)
        streams = build_official_development_streams(
            gas_root=str(args.gas_root),
            cmapss_zip=str(args.cmapss_zip),
            xjtu_cache_root=str(args.xjtu_cache_root),
        )
        _atomic_json(
            root / "stream-audit.json",
            {
                name: {
                    "task_kind": stream.task_kind,
                    "initial_samples": len(stream.initial.y),
                    "development_samples": sum(len(batch.y) for batch in stream.development),
                    "development_rounds": len(stream.development),
                    "feature_count": int(stream.initial.X.shape[1]),
                    "sealed_batches_loaded": len(stream.sealed),
                    "metadata": stream.metadata,
                }
                for name, stream in streams.items()
            },
        )
        _status(root, "serial_experiments", cpu_affinity=cpus)
        state = run_official_development_suite(
            streams,
            config,
            root,
            max_experiments=args.max_experiments,
        )
        if state["status"] == "completed":
            validation = validate_official_development_suite(root)
            _atomic_json(root / "validation.json", validation)
            _status(root, "completed", suite_state=state, validation=validation)
        else:
            _status(root, "paused", suite_state=state)
        return 0
    except Exception as exc:
        _status(
            root,
            "failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
