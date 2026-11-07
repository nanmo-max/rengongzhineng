"""Static Docker-context audit used when a local Docker daemon is unavailable."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

_FORBIDDEN_SUFFIXES = {".pkl", ".pickle", ".joblib", ".pt", ".pth", ".onnx", ".key", ".pem"}
_FORBIDDEN_PARTS = {"dataji", "artifacts", "outputs", ".git", ".env", "secrets"}


@dataclass(frozen=True)
class DockerContextAudit:
    included_files: tuple[Path, ...]
    total_bytes: int
    forbidden_files: tuple[Path, ...]


def _ignored(relative: Path, patterns: tuple[str, ...]) -> bool:
    value = relative.as_posix()
    for pattern in patterns:
        if pattern.endswith("/") and (
            value == pattern[:-1] or value.startswith(pattern)
        ):
            return True
        if fnmatch(value, pattern) or fnmatch(relative.name, pattern):
            return True
    return False


def audit_docker_context(root: Path) -> DockerContextAudit:
    root = Path(root)
    ignore_path = root / ".dockerignore"
    patterns = tuple(
        line.strip()
        for line in ignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    included: list[Path] = []
    forbidden: list[Path] = []
    total = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _ignored(relative, patterns):
            continue
        included.append(relative)
        total += path.stat().st_size
        if (
            path.suffix.lower() in _FORBIDDEN_SUFFIXES
            or any(part.lower() in _FORBIDDEN_PARTS for part in relative.parts)
        ):
            forbidden.append(relative)
    return DockerContextAudit(tuple(sorted(included)), total, tuple(sorted(forbidden)))
