"""Run the bounded grouped-device regression sprint matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from brace_msi.regression_sprint import run_regression_sprint, validate_regression_sprint


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--package-config", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", choices=("B", "C"), required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    package_config = json.loads(args.package_config.read_text(encoding="utf-8"))
    if args.validate_only:
        validate_regression_sprint(args.runtime_root, config)
    else:
        run_regression_sprint(
            args.package_root,
            args.runtime_root,
            config,
            package_config,
            args.profiles,
        )
        validate_regression_sprint(args.runtime_root, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
