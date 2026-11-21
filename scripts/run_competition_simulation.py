"""Run the local official-protocol simulation from a frozen JSON config."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brace_msi.competition_simulator import load_and_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = load_and_run(args.config, args.output)
    print(
        json.dumps(
            {
                "valid": report["valid"],
                "label": report["label"],
                "report_json": str(args.output / "report.json"),
                "report_html": str(args.output / "report.html"),
                "task_count": len(report["tasks"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
