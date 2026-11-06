"""Run a preregistered local proxy experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.experiment import run_local_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--gas-root", type=Path, required=True)
    parser.add_argument("--gas-archive", type=Path, required=True)
    parser.add_argument("--cmapss-zip", type=Path, required=True)
    parser.add_argument("--cmapss-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_local_experiment(
            config_path=args.config,
            gas_root=args.gas_root,
            gas_archive=args.gas_archive,
            cmapss_zip=args.cmapss_zip,
            cmapss_archive=args.cmapss_archive,
            output_dir=args.output,
        )
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema_version": 1,
            "proxy_only": True,
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        (args.output / "failure.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "run_count": result["run_count"],
                "action_counts": result["action_counts"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
