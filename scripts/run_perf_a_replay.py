"""Run or resume the preregistered PERF-A-REPLAY-001 experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_msi.gas_replay import run_gas_replay_experiment
from brace_msi.official_package import audit_package_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    package_config = json.loads(
        (ROOT / "configs" / "formal_agent_dev.json").read_text(encoding="utf-8")
    )
    package = audit_package_root(args.package_root, package_config)["A"]
    state = run_gas_replay_experiment(
        package,
        args.raw_root,
        args.runtime_root,
        config,
        python_executable=Path(sys.executable),
    )
    print(
        json.dumps(
            {
                "status": state["status"],
                "selected_strategy": state["selected_strategy"],
                "selection_reason": state["selection_reason"],
                "development_summary": state["development_summary"],
                "confirmation_summary": state["confirmation_summary"],
                "official_test_opportunities_used": state["official_test_opportunities_used"],
            },
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
