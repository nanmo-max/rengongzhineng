"""Reproducibly build and export the allowlisted formal Docker image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Mapping


_ALLOWLIST = Path("configs/formal_runtime_allowlist.json")
_FORBIDDEN_PARTS = {"tests", "scripts", "docs", "dataji", "artifacts", "outputs", "tmp"}
_FORBIDDEN_NAMES = {"pytrio", "swanlab", "tokenizer", "sampler", "cache"}
_FORBIDDEN_SUFFIXES = {
    ".npz", ".pkl", ".pickle", ".joblib", ".pt", ".pth", ".onnx", ".key", ".pem"
}


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


def read_source_commit(
    repository_root: Path,
    *,
    runner: Any = _run,
) -> str:
    completed = runner(
        ["git", "rev-parse", "HEAD"], cwd=Path(repository_root), capture_output=True
    )
    commit = completed.stdout.strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit.lower()):
        raise ValueError("source commit is not a full Git SHA-1")
    return commit


def bind_release_metadata(
    manifest_path: Path,
    *,
    model_name: str,
    model_selection: str,
    swanlab_url: str,
    sft_evidence_sha256: str,
) -> dict[str, Any]:
    """Bind public provenance without embedding credentials or Sampler paths."""

    if model_name != "Qwen/Qwen3.5-4B":
        raise ValueError("formal release model must be the platform-validated base model")
    if model_selection != "platform_validated_base":
        raise ValueError("unadopted SFT candidates cannot be bound to the formal release")
    if not swanlab_url.startswith("https://swanlab.cn/"):
        raise ValueError("SwanLab evidence must be a public HTTPS SwanLab URL")
    if len(sft_evidence_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in sft_evidence_sha256.lower()
    ):
        raise ValueError("SFT evidence hash must be SHA-256")
    path = Path(manifest_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != "brace-formal-release.v1":
        raise ValueError("release manifest has an invalid format")
    payload["agent_model"] = {
        "name": model_name,
        "selection": model_selection,
        "sft_candidate": "evaluated_not_adopted",
        "sft_evidence_sha256": sft_evidence_sha256.lower(),
    }
    payload["swanlab"] = {
        "public_url": swanlab_url,
        "scope": "aggregate_public_no_private_rows_or_credentials",
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return payload


def load_formal_allowlist(config_path: Path, repository_root: Path) -> tuple[str, ...]:
    """Load and fail-closed validate the exact formal build-context file set."""

    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
    files = payload.get("files") if isinstance(payload, Mapping) else None
    if not isinstance(payload, Mapping) or payload.get("format") != "brace-formal-allowlist.v1" or not isinstance(files, list):
        raise ValueError("formal allowlist has an invalid format")
    if not files or any(not isinstance(item, str) or not item for item in files):
        raise ValueError("formal allowlist files must be nonempty strings")
    if len(files) != len(set(files)) or files != sorted(files):
        raise ValueError("formal allowlist must be unique and sorted")
    root = Path(repository_root).resolve()
    normalized: list[str] = []
    for relative in files:
        portable = Path(relative)
        if portable.is_absolute() or ".." in portable.parts or portable.as_posix() != relative:
            raise ValueError("formal allowlist paths must be normalized repository-relative paths")
        lowered = relative.lower()
        if (
            _FORBIDDEN_PARTS.intersection(portable.parts)
            or any(name in lowered for name in _FORBIDDEN_NAMES)
            or portable.suffix.lower() in _FORBIDDEN_SUFFIXES
            or portable.name.lower().startswith(".env")
        ):
            raise ValueError(f"forbidden formal context file: {relative}")
        source = root / portable
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"formal allowlist entry is not a regular file: {relative}")
        normalized.append(relative)
    return tuple(normalized)


def stage_explicit_context(
    repository_root: Path,
    destination: Path,
    files: tuple[str, ...],
    *,
    image_class: str,
    manifest_name: str,
) -> dict[str, Any]:
    """Copy only explicitly listed regular files into a new Docker context."""

    root = Path(repository_root).resolve()
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    for relative in files:
        source = root / Path(relative)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"context source is not a regular file: {relative}")
        copied = target / Path(relative)
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, copied)
        entries.append(
            {"path": relative, "bytes": copied.stat().st_size, "sha256": _sha256(copied)}
        )
    tree_digest = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        "format": "brace-image-context.v1",
        "image_class": image_class,
        "files": sorted(files),
        "entries": entries,
        "tree_sha256": tree_digest,
    }
    (target / manifest_name).write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def stage_formal_context(
    repository_root: Path,
    destination: Path,
    allowlist_path: Path = _ALLOWLIST,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    config = allowlist_path if allowlist_path.is_absolute() else root / allowlist_path
    files = load_formal_allowlist(config, root)
    return stage_explicit_context(
        root,
        destination,
        files,
        image_class="FORMAL_UPLOAD",
        manifest_name="FORMAL_CONTEXT_MANIFEST.json",
    )


def build(tag: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    repository_root = Path(__file__).resolve().parents[1]
    source_commit = read_source_commit(repository_root)
    with tempfile.TemporaryDirectory(prefix="brace-formal-context-") as temporary:
        context = Path(temporary) / "context"
        content_manifest = stage_formal_context(repository_root, context)
        _run([
            "docker", "build", "--platform", "linux/amd64", "--provenance=false",
            "-f", str(context / "Dockerfile.formal"), "-t", tag, str(context),
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
        "source_commit": source_commit,
        "image_id": inspected["Id"],
        **metadata,
        "content_manifest": content_manifest,
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--finalize-manifest", type=Path)
    parser.add_argument("--model-name", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--model-selection", default="platform_validated_base")
    parser.add_argument("--swanlab-url")
    parser.add_argument("--sft-evidence-sha256")
    args = parser.parse_args()
    if args.finalize_manifest is not None:
        if not args.swanlab_url or not args.sft_evidence_sha256:
            parser.error("--swanlab-url and --sft-evidence-sha256 are required when finalizing")
        result = bind_release_metadata(
            args.finalize_manifest,
            model_name=args.model_name,
            model_selection=args.model_selection,
            swanlab_url=args.swanlab_url,
            sft_evidence_sha256=args.sft_evidence_sha256,
        )
    else:
        if args.output is None:
            parser.error("--output is required when building")
        result = build(args.tag, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
