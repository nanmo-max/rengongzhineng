"""Build a visibly local-only image from an explicit development context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

try:
    from scripts.build_formal_release import (
        _run,
        load_formal_allowlist,
        stage_explicit_context,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` invocation.
    from build_formal_release import (  # type: ignore[no-redef]
        _run,
        load_formal_allowlist,
        stage_explicit_context,
    )


_LOCAL_ONLY_FILES = (
    "Dockerfile.local-test",
    "configs/competition_simulation.json",
    "scripts/render_competition_report.py",
    "scripts/run_competition_simulation.py",
    "scripts/simulate_first_principles_runtime.py",
    "scripts/simulate_platform_report.py",
    "src/brace_msi/__init__.py",
    "src/brace_msi/competition_simulator.py",
)


def stage_local_test_context(repository_root: Path, destination: Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    formal = load_formal_allowlist(root / "configs/formal_runtime_allowlist.json", root)
    files = tuple(
        sorted(
            {
                *(item for item in formal if item != "Dockerfile.formal"),
                *_LOCAL_ONLY_FILES,
            }
        )
    )
    return stage_explicit_context(
        root,
        destination,
        files,
        image_class="LOCAL_TEST_ONLY",
        manifest_name="LOCAL_CONTEXT_MANIFEST.json",
    )


def build(tag: str) -> dict[str, Any]:
    if "local" not in tag.lower():
        raise ValueError("local-test image tag must visibly contain 'local'")
    repository_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="brace-local-context-") as temporary:
        context = Path(temporary) / "context"
        manifest = stage_local_test_context(repository_root, context)
        _run(
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "--provenance=false",
                "-f",
                str(context / "Dockerfile.local-test"),
                "-t",
                tag,
                str(context),
            ]
        )
    inspected = json.loads(
        _run(["docker", "image", "inspect", tag], capture_output=True).stdout
    )[0]
    environment = inspected.get("Config", {}).get("Env", [])
    if "BRACE_IMAGE_CLASS=LOCAL_TEST_ONLY" not in environment:
        raise ValueError("local-test image is missing the LOCAL_TEST_ONLY marker")
    return {"tag": tag, "image_id": inspected["Id"], "content_manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="brace-msi:local-test")
    args = parser.parse_args()
    print(json.dumps(build(args.tag), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
