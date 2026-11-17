"""Container acceptance for the first-principles formal image.

It reuses the official-SDK host simulator while supplying only the new bounded
proposal schema. Results are local protocol evidence, never official scores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import verify_workspace_v2_image as base


def _proposal() -> dict[str, object]:
    content = json.dumps(
        {
            "action": "train",
            "epochs": 1,
            "learning_rate_multiplier": 1.0,
            "rationale": "bounded parent-compatible continuation",
        },
        separators=(",", ":"),
    )
    return {
        "id": "chatcmpl-local-formal-protocol",
        "model": "host-selected-alias",
        "object": "chat.completion",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 64, "completion_tokens": 24, "total_tokens": 88},
    }


def run(image: str, package_root: Path, output: Path) -> dict[str, object]:
    original = base._proposal
    base._proposal = _proposal
    try:
        report = base.run(image, package_root, output)
    finally:
        base._proposal = original
    report["scope"] = "local_formal_container_protocol_only_not_official_score"
    report["proposal_schema"] = "brace-formal-bounded-v1"
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
