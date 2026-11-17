"""Collision-free per-round paths inside a persistent workspace mount."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RoundPaths:
    root: Path
    state: Path
    candidate: Path


def _slug(value: str) -> str:
    result = "".join(character if character.isalnum() or character in "-_" else "-" for character in value)
    return result.strip("-")[:48] or "default"


def create_round_paths(
    workspace_root: Path | str,
    round_index: int,
    stage_id: str,
    dataset_key: str,
) -> RoundPaths:
    if type(round_index) is not int or not 1 <= round_index <= 10:
        raise ValueError("round index must be in 1..10")
    root = (
        Path(workspace_root).resolve()
        / f"dataset-{_slug(str(dataset_key))}"
        / f"round-{round_index:04d}-{_slug(str(stage_id))}"
    )
    if root.exists() or root.is_symlink():
        raise FileExistsError(f"round workspace already exists: {root}")
    return RoundPaths(root=root, state=root / "state", candidate=root / "candidate")
