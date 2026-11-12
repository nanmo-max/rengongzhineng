"""Read-only validation of the development-reference training packages."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np


class PackageAuditError(ValueError):
    """Raised before training when an immutable package does not match its manifest."""


@dataclass(frozen=True)
class PackageSpec:
    profile: str
    directory: str
    task: str
    primary_metric: str
    higher_is_better: bool
    package_tree_sha256: str
    checkpoint_sha256: str
    train_sha256: str
    validation_sha256: str


@dataclass(frozen=True)
class PackageAudit:
    profile: str
    package_id: str
    package_dir: Path
    task: str
    primary_metric: str
    higher_is_better: bool
    input_features: int
    hidden: int
    parameter_count: int
    train_rows: int
    validation_rows: int
    train_ids: frozenset[str]
    validation_ids: frozenset[str]
    train_groups: frozenset[str]
    validation_groups: frozenset[str]
    baseline_metric: float
    baseline_metrics: Mapping[str, float]
    checkpoint_sha256: str
    package_tree_sha256: str
    train_sha256: str
    validation_sha256: str
    checkpoint_path: Path
    train_path: Path
    validation_path: Path
    profile_path: Path
    base_learning_rate: float
    base_batch_size: int
    base_epochs: int
    training_seconds: float
    initial_epochs: int
    initial_steps: int
    source_sha256: Mapping[str, str]
    official_package: bool = True
    official_scoring_ready: bool = False


_REQUIRED_FILES = (
    "baseline-info.json",
    "checkpoint.npz",
    "training.json",
    "baselines/train.py",
    "baselines/model.py",
    "baselines/data.py",
    "baselines/predict.py",
    "public/train.jsonl",
    "public/validation.jsonl",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _without_prefix(value: str) -> str:
    return value.split(":", 1)[-1].lower()


def package_tree_sha256(package_dir: Path) -> str:
    """Hash every delivered file name and digest against the repository-pinned manifest."""

    digest = hashlib.sha256()
    files = sorted(
        (
            path
            for path in package_dir.rglob("*")
            if path.is_file()
            and path.suffix != ".pyc"
            and "__pycache__" not in path.parts
        ),
        key=lambda path: path.relative_to(package_dir).as_posix(),
    )
    for path in files:
        relative = path.relative_to(package_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageAuditError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PackageAuditError(f"JSON object required: {path}")
    return value


def _dataset_summary(path: Path, profile: str) -> tuple[int, frozenset[str], frozenset[str]]:
    identifiers: set[str] = set()
    groups: set[str] = set()
    rows = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                item = json.loads(line)
                identifier = item["id"]
                meta = item["meta"]
                if not isinstance(identifier, str) or not isinstance(meta, dict):
                    raise TypeError
                if identifier in identifiers:
                    raise PackageAuditError(f"duplicate id in {path}: {identifier}")
                identifiers.add(identifier)
                if profile == "A":
                    group = f"batch:{meta['source_batch']}"
                elif profile == "B":
                    group = f"bearing:{meta['bearing']}"
                else:
                    group = f"unit:{meta['source_subset']}:{meta['unit']}"
                groups.add(group)
                rows += 1
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PackageAuditError(f"invalid dataset row in {path} at line {line_number}") from exc
    return rows, frozenset(identifiers), frozenset(groups)


def _specs(config: Mapping[str, Any]) -> dict[str, PackageSpec]:
    raw = config.get("packages")
    if not isinstance(raw, Mapping) or not raw:
        raise PackageAuditError("config packages mapping is required")
    specs: dict[str, PackageSpec] = {}
    for profile, item in raw.items():
        if profile not in {"A", "B", "C"} or not isinstance(item, Mapping):
            raise PackageAuditError(f"unsupported package profile: {profile}")
        try:
            specs[profile] = PackageSpec(
                profile=profile,
                directory=str(item["directory"]),
                task=str(item["task"]),
                primary_metric=str(item["primary_metric"]),
                higher_is_better=bool(item["higher_is_better"]),
                package_tree_sha256=str(item["package_tree_sha256"]).lower(),
                checkpoint_sha256=str(item["checkpoint_sha256"]).lower(),
                train_sha256=str(item["train_sha256"]).lower(),
                validation_sha256=str(item["validation_sha256"]).lower(),
            )
        except KeyError as exc:
            raise PackageAuditError(f"missing config field for profile {profile}: {exc.args[0]}") from exc
    return specs


def _audit_one(root: Path, spec: PackageSpec) -> PackageAudit:
    package_dir = root / spec.directory
    if not package_dir.is_dir():
        raise PackageAuditError(f"missing package directory: {package_dir}")
    for relative in _REQUIRED_FILES:
        if not (package_dir / relative).is_file():
            raise PackageAuditError(f"missing required file: {relative}")

    checkpoint_path = package_dir / "checkpoint.npz"
    train_path = package_dir / "public" / "train.jsonl"
    validation_path = package_dir / "public" / "validation.jsonl"
    actual_hashes = {
        "checkpoint.npz": _sha256(checkpoint_path),
        "public/train.jsonl": _sha256(train_path),
        "public/validation.jsonl": _sha256(validation_path),
    }
    expected_hashes = {
        "checkpoint.npz": spec.checkpoint_sha256,
        "public/train.jsonl": spec.train_sha256,
        "public/validation.jsonl": spec.validation_sha256,
    }
    for name, expected in expected_hashes.items():
        if actual_hashes[name] != expected:
            raise PackageAuditError(f"{name} SHA-256 mismatch")
    actual_tree_sha256 = package_tree_sha256(package_dir)
    if actual_tree_sha256 != spec.package_tree_sha256:
        raise PackageAuditError(f"package tree SHA-256 mismatch for {spec.profile}")

    info = _load_json(package_dir / "baseline-info.json")
    report = _load_json(package_dir / "training.json")
    profile_path = package_dir / "baselines" / "configs" / f"{spec.profile}.json"
    profile_config = _load_json(profile_path)
    if info.get("dataset_key") != spec.profile or report.get("profile") != spec.profile:
        raise PackageAuditError(f"profile mismatch for {spec.profile}")
    if info.get("task") != spec.task or report.get("task") != spec.task:
        raise PackageAuditError(f"task mismatch for {spec.profile}")
    if report.get("purpose") != "development_reference" or report.get("official_scoring_ready") is not False:
        raise PackageAuditError(f"invalid result boundary for {spec.profile}")
    for name, expected in expected_hashes.items():
        report_key = {
            "checkpoint.npz": "checkpoint_sha256",
            "public/train.jsonl": "train_sha256",
            "public/validation.jsonl": "validation_sha256",
        }[name]
        if _without_prefix(str(report.get(report_key, ""))) != expected:
            raise PackageAuditError(f"training report {report_key} mismatch")

    try:
        with np.load(checkpoint_path, allow_pickle=False) as archive:
            metadata_array = archive["metadata"]
            if metadata_array.shape != () or metadata_array.dtype.kind != "U":
                raise PackageAuditError("checkpoint metadata must be scalar Unicode JSON")
            metadata = json.loads(str(metadata_array.item()))
            w1_shape = archive["w1"].shape
            w2_shape = archive["w2"].shape
            required_arrays = {
                "w1", "b1", "w2", "b2", "mean", "scale", "metadata",
                "adam_first_w1", "adam_first_b1", "adam_first_w2", "adam_first_b2",
                "adam_second_w1", "adam_second_b1", "adam_second_w2", "adam_second_b2",
            }
            if not required_arrays.issubset(archive.files):
                raise PackageAuditError("checkpoint missing model or Adam state")
            if any(archive[name].dtype.kind == "O" for name in archive.files):
                raise PackageAuditError("checkpoint contains object arrays")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise PackageAuditError(f"invalid checkpoint schema for {spec.profile}") from exc

    input_features = int(report["input_features"])
    hidden = int(report["configuration"]["hidden"])
    parameter_count = int(report["parameter_count"])
    output_features = 6 if spec.task == "classification" else 1
    calculated_parameters = input_features * hidden + hidden + hidden * output_features + output_features
    if (
        metadata.get("format") != "contest.cpu-mlp.v1"
        or metadata.get("profile") != spec.profile
        or metadata.get("task") != spec.task
        or len(metadata.get("paths", [])) != input_features
        or int(metadata.get("hidden", -1)) != hidden
        or int(metadata.get("parameter_count", -1)) != parameter_count
        or w1_shape != (input_features, hidden)
        or w2_shape != (hidden, output_features)
        or calculated_parameters != parameter_count
        or int(info.get("parameter_count", -1)) != parameter_count
    ):
        raise PackageAuditError(f"checkpoint topology mismatch for {spec.profile}")

    train_rows, train_ids, train_groups = _dataset_summary(train_path, spec.profile)
    validation_rows, validation_ids, validation_groups = _dataset_summary(validation_path, spec.profile)
    if train_ids & validation_ids:
        raise PackageAuditError(f"train/validation ID overlap for {spec.profile}")
    if train_groups & validation_groups:
        raise PackageAuditError(f"train/validation group overlap for {spec.profile}")
    if train_rows != int(report["train_rows"]) or validation_rows != int(report["validation_rows"]):
        raise PackageAuditError(f"dataset row count mismatch for {spec.profile}")

    baseline_metrics = {key: float(value) for key, value in report["validation_after"].items()}
    reported_source = report.get("source_sha256")
    if not isinstance(reported_source, dict):
        raise PackageAuditError(f"missing source hashes for {spec.profile}")
    source_sha256: dict[str, str] = {}
    for name in ("model.py", "data.py", "train.py", "predict.py"):
        path = package_dir / "baselines" / name
        actual = _sha256(path)
        if _without_prefix(str(reported_source.get(name, ""))) != actual:
            raise PackageAuditError(f"source code SHA-256 mismatch: {name}")
        source_sha256[name] = actual
    return PackageAudit(
        profile=spec.profile,
        package_id=str(info["id"]),
        package_dir=package_dir,
        task=spec.task,
        primary_metric=spec.primary_metric,
        higher_is_better=spec.higher_is_better,
        input_features=input_features,
        hidden=hidden,
        parameter_count=parameter_count,
        train_rows=train_rows,
        validation_rows=validation_rows,
        train_ids=train_ids,
        validation_ids=validation_ids,
        train_groups=train_groups,
        validation_groups=validation_groups,
        baseline_metric=baseline_metrics[spec.primary_metric],
        baseline_metrics=baseline_metrics,
        checkpoint_sha256=actual_hashes["checkpoint.npz"],
        package_tree_sha256=actual_tree_sha256,
        train_sha256=actual_hashes["public/train.jsonl"],
        validation_sha256=actual_hashes["public/validation.jsonl"],
        checkpoint_path=checkpoint_path,
        train_path=train_path,
        validation_path=validation_path,
        profile_path=profile_path,
        base_learning_rate=float(report["learning_rate"]),
        base_batch_size=int(report["batch_size"]),
        base_epochs=int(report["final_epochs"]),
        training_seconds=float(report["training_seconds"]),
        initial_epochs=int(metadata["epochs"]),
        initial_steps=int(metadata["steps"]),
        source_sha256=source_sha256,
    )


def audit_package_root(root: Path, config: Mapping[str, Any]) -> dict[str, PackageAudit]:
    """Audit configured packages without importing package code or writing to the source tree."""

    root = Path(root)
    return {profile: _audit_one(root, spec) for profile, spec in _specs(config).items()}

