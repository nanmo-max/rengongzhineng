from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.formal_observation import build_formal_observation


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind existing formal acceptance rounds to SwanLab-safe records")
    parser.add_argument("acceptance", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-rounds", type=int, default=10)
    arguments = parser.parse_args()
    result = build_formal_observation(
        arguments.acceptance,
        arguments.output,
        expected_rounds=arguments.expected_rounds,
    )
    print(json.dumps({
        "manifest": str(result.manifest_path),
        "spool": str(result.spool_path),
        "source_sha256": result.source_sha256,
        "record_count": result.record_count,
        "task_counts": result.task_counts,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
