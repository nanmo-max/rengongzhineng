"""Validate or execute the preregistered unified-policy optimization workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brace_msi.data.audit import file_sha256
from brace_msi.formal_task_evaluator import FormalTaskEvaluator
from brace_msi.official_streams import build_official_development_streams
from brace_msi.unified_optimization import (
    candidate_configs_from_config,
    run_development_search,
    validate_development_search,
)
from brace_msi.unified_policy import SharedPolicyConfig


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--gas-root", type=Path)
    parser.add_argument("--gas-archive", type=Path)
    parser.add_argument("--cmapss-zip", type=Path)
    parser.add_argument("--xjtu-cache-root", type=Path)
    parser.add_argument("--maximum-candidates", type=int)
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--mlp-max-iter", type=int, default=80)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _require_execution_arguments(arguments: argparse.Namespace) -> None:
    required = {
        "config": arguments.config,
        "gas_root": arguments.gas_root,
        "gas_archive": arguments.gas_archive,
        "cmapss_zip": arguments.cmapss_zip,
        "xjtu_cache_root": arguments.xjtu_cache_root,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise SystemExit("missing execution arguments: " + ", ".join(missing))


def _verify_sources(config: dict[str, object], arguments: argparse.Namespace) -> None:
    expected = config["source_sha256"]
    paths = {
        "gas_archive": arguments.gas_archive,
        "cmapss_zip": arguments.cmapss_zip,
        "xjtu_manifest": arguments.xjtu_cache_root / "manifest.json",
    }
    for name, path in paths.items():
        if file_sha256(path).upper() != str(expected[name]).upper():
            raise RuntimeError(f"source hash mismatch: {name}")


def main() -> int:
    arguments = _arguments()
    if not arguments.validate_only:
        _require_execution_arguments(arguments)
        config = json.loads(arguments.config.read_text(encoding="utf-8"))
        if int(config.get("official_test_opportunities_allowed", -1)) != 0:
            raise RuntimeError("development config must forbid official test usage")
        _verify_sources(config, arguments)
        streams = build_official_development_streams(
            gas_root=str(arguments.gas_root),
            cmapss_zip=str(arguments.cmapss_zip),
            xjtu_cache_root=str(arguments.xjtu_cache_root),
        )
        baseline = SharedPolicyConfig(**config["shared_policy"])
        evaluator = FormalTaskEvaluator(
            streams=streams,
            runtime_root=arguments.runtime_root / "task-evaluations",
            seed=int(config["seed"]),
            baseline_shared_config=baseline,
            mlp_max_iter=arguments.mlp_max_iter,
        )
        result = run_development_search(
            runtime_root=arguments.runtime_root,
            task_keys=tuple(streams),
            candidates=candidate_configs_from_config(
                config, maximum_candidates=arguments.maximum_candidates
            ),
            evaluator=evaluator,
            source_commit=_source_commit(),
            experiment_config_sha256=_sha256(arguments.config),
            static_tolerance=float(config["selection"]["static_tolerance"]),
            max_jobs=arguments.max_jobs,
        )
    else:
        result = validate_development_search(arguments.runtime_root)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
