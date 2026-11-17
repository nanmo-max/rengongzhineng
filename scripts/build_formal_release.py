"""Reproducibly build and export the allowlisted formal Docker image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping


def _run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=True, text=True, encoding="utf-8", **kwargs)


def validate_image_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("Os") != "linux" or payload.get("Architecture") != "amd64":
        raise ValueError("formal image must be linux/amd64")
    size = payload.get("Size")
    if type(size) is not int or not 0 < size < 2 * 1024**3:
        raise ValueError("formal image must remain below 2 GiB")
    config = payload.get("Config")
    user = config.get("User") if isinstance(config, Mapping) else None
    if not isinstance(user, str) or not user or user.split(":", 1)[0] in {"0", "root"}:
        raise ValueError("formal image must use a nonroot runtime user")
    return {"os": "linux", "architecture": "amd64", "size_bytes": size, "user": user}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(tag: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    _run([
        "docker", "build", "--platform", "linux/amd64", "--provenance=false",
        "-f", "Dockerfile.formal", "-t", tag, ".",
    ])
    inspected = json.loads(_run(["docker", "image", "inspect", tag], capture_output=True).stdout)[0]
    metadata = validate_image_metadata(inspected)
    describe = _run(
        ["docker", "run", "--rm", "--network", "none", "--read-only", "--cpus", "4", "--memory", "8g", tag, "describe"],
        capture_output=True,
    ).stdout.strip()
    descriptor = json.loads(describe)
    if descriptor.get("protocol") != "contest.harness.workspace.v2" or descriptor.get("sdk_version") != "1.0.2":
        raise ValueError("formal image does not expose the official SDK 1.0.2 contract")
    archive = output / "harness.tar"
    _run(["docker", "save", "-o", str(archive), tag])
    manifest = {
        "format": "brace-formal-release.v1",
        "tag": tag,
        "image_id": inspected["Id"],
        **metadata,
        "descriptor": descriptor,
        "archive": {"path": archive.name, "bytes": archive.stat().st_size, "sha256": _sha256(archive)},
    }
    (output / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="brace-msi:0.10.0rc1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.tag, args.output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
