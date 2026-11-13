from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.paper_fusion_runner import (
    run_paper_fusion_sprint,
    validate_paper_fusion_output,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--open-validation", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    result = (
        validate_paper_fusion_output(args.output)
        if args.validate_only
        else run_paper_fusion_sprint(
            args.config, args.output, open_validation=args.open_validation
        )
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0 if result.get("valid", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
