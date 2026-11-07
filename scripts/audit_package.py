"""Print a machine-readable Docker context audit."""

from __future__ import annotations

import json
from pathlib import Path

from brace_msi.packaging import audit_docker_context


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = audit_docker_context(root)
    payload = {
        "schema_version": 1,
        "included_file_count": len(result.included_files),
        "total_bytes": result.total_bytes,
        "under_2gb": result.total_bytes < 2_000_000_000,
        "forbidden_files": [path.as_posix() for path in result.forbidden_files],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["under_2gb"] and not payload["forbidden_files"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
