"""Run the preregistered local full-system simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.data.audit import file_sha256
from brace_msi.data.cmapss import load_cmapss_fd001_stream
from brace_msi.data.gas import load_gas_stream
from brace_msi.formal_simulation import load_simulation_config, run_simulation_suite
from brace_msi.simulation import synthetic_bearing_stream


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--gas-root", type=Path, required=True)
    parser.add_argument("--gas-archive", type=Path, required=True)
    parser.add_argument("--cmapss-zip", type=Path, required=True)
    parser.add_argument("--cmapss-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    config = load_simulation_config(args.config)
    observed = {
        "gas": file_sha256(args.gas_archive),
        "cmapss": file_sha256(args.cmapss_archive),
    }
    if observed != config.data_hashes:
        raise RuntimeError("proxy archive hash does not match preregistration")
    streams = (
        load_gas_stream(args.gas_root, include_sealed=False),
        load_cmapss_fd001_stream(args.cmapss_zip, include_sealed=False),
        synthetic_bearing_stream(seed=config.seed),
    )
    result = run_simulation_suite(streams, config=config, output_dir=args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "task_count": result["task_count"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
