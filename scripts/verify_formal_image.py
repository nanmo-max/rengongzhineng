"""Container acceptance for the frozen Competition Core formal image.

The official-SDK host simulator answers the current two-call Agent schema and
drives the exact image.  Results are local protocol evidence, never official
scores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import verify_workspace_v2_image as base


def run(image: str, package_root: Path, output: Path) -> dict[str, object]:
    report = base.run(image, package_root, output)
    report["scope"] = "local_formal_container_protocol_only_not_official_score"
    report["proposal_schema"] = "competition-core-two-call-v1"
    (output / "acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.image, args.package_root, args.output)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
