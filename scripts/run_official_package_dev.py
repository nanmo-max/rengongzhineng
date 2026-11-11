"""Run the resumable official-package local development queue."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from brace_msi.official_package_suite import (
    run_official_package_suite,
    validate_official_package_suite,
    validate_runtime_boundary,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def _status(root: Path, stage: str, **extra: object) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "pipeline-status.json"
    if stage == "running" and path.is_file():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("stage") == "failed":
            history = root / "pipeline-status-history"
            history.mkdir(parents=True, exist_ok=True)
            attempt = 1
            while (history / f"attempt-{attempt:03d}.json").exists():
                attempt += 1
            archived = history / f"attempt-{attempt:03d}.json"
            archive_temporary = archived.with_name(archived.name + ".tmp")
            archive_temporary.write_text(
                json.dumps(previous, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(archive_temporary, archived)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "format": "brace-msi.official-package-pipeline-status.v1",
                "pid": os.getpid(),
                "stage": stage,
                "official_package": True,
                "official_scoring_ready": False,
                **extra,
            },
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    args = _arguments()
    try:
        package_root, runtime_root = validate_runtime_boundary(
            args.package_root, args.runtime_root
        )
        if args.validate_only:
            validation = validate_official_package_suite(runtime_root)
            _status(runtime_root, "validated", validation=validation)
            return 0
        config = json.loads(args.config.read_text(encoding="utf-8"))
        _status(runtime_root, "running")
        state = run_official_package_suite(
            package_root,
            runtime_root,
            config,
            max_jobs=args.max_jobs,
        )
        if state.complete:
            validation = validate_official_package_suite(runtime_root)
            _status(runtime_root, "completed", validation=validation)
        else:
            _status(runtime_root, "paused", completed_jobs=state.completed_jobs)
        return 0
    except Exception as exc:
        runtime = Path(args.runtime_root).resolve()
        package = Path(args.package_root).resolve()
        if not (
            runtime == package
            or runtime.is_relative_to(package)
            or package.is_relative_to(runtime)
        ):
            _status(runtime, "failed", error_type=type(exc).__name__, error=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())

