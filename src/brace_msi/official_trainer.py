"""Isolated adapter for the immutable official-package NumPy trainers."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from .official_package import PackageAudit, package_tree_sha256


class CandidateValidationError(ValueError):
    """Raised when trainer output does not prove a valid continuation."""


@dataclass(frozen=True)
class CandidateConfig:
    epochs: int
    learning_rate: float
    batch_size: int


@dataclass(frozen=True)
class CandidateReceipt:
    stage_id: str
    profile: str
    parent_sha256: str
    checkpoint_sha256: str
    metrics_before: dict[str, float]
    metrics_after: dict[str, float]
    initial_epochs: int
    final_epochs: int
    initial_steps: int
    final_steps: int
    model_state_changed: bool
    optimizer_state_changed: bool
    wall_seconds: float
    cpu_seconds: float
    peak_rss_bytes: int
    output_dir: str
    validation_file_reads: int
    validation_metric_evaluations: int
    validation_preflight_hash_reads: int = 1
    validation_trainer_dataset_loads: int = 1
    official_package: bool = True
    official_scoring_ready: bool = False


_PARAMETERS = ("w1", "b1", "w2", "b2")
_OPTIMIZER = tuple(
    f"adam_{moment}_{name}" for moment in ("first", "second") for name in _PARAMETERS
)
_STAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata(path: Path) -> dict[str, Any]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            raw = archive["metadata"]
            if raw.shape != () or raw.dtype.kind != "U":
                raise CandidateValidationError("checkpoint metadata schema is invalid")
            value = json.loads(str(raw.item()))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise CandidateValidationError(f"checkpoint cannot be safely loaded: {path}") from exc
    if not isinstance(value, dict):
        raise CandidateValidationError("checkpoint metadata must be an object")
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _metric_map(value: Any, field: str) -> dict[str, float]:
    if not isinstance(value, dict) or not value:
        raise CandidateValidationError(f"{field} must be a nonempty metric object")
    result: dict[str, float] = {}
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(float(raw)):
            raise CandidateValidationError(f"{field}.{key} must be finite")
        result[str(key)] = float(raw)
    return result


def validate_candidate_output(
    package: PackageAudit,
    parent: Path,
    output_dir: Path,
    config: CandidateConfig,
    stage_id: str,
) -> dict[str, Any]:
    """Validate a completed candidate against the actual parent and immutable inputs."""

    parent = Path(parent)
    output_dir = Path(output_dir)
    checkpoint = output_dir / "checkpoint.npz"
    report_path = output_dir / "training.json"
    history_path = output_dir / "history.jsonl"
    if not checkpoint.is_file() or not report_path.is_file() or not history_path.is_file():
        raise CandidateValidationError("candidate output is incomplete")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateValidationError("candidate training.json is invalid") from exc
    if not isinstance(report, dict):
        raise CandidateValidationError("candidate training.json must be an object")

    expected_parent = _sha256(parent)
    child_sha = _sha256(checkpoint)
    exact_fields = {
        "format": "contest.cpu-baseline-report.v1",
        "profile": package.profile,
        "task": package.task,
        "purpose": "development_reference",
        "official_scoring_ready": False,
        "stage_id": stage_id,
        "parameter_count": package.parameter_count,
        "input_features": package.input_features,
        "train_rows": package.train_rows,
        "validation_rows": package.validation_rows,
        "learning_rate": config.learning_rate,
        "batch_size": config.batch_size,
    }
    for field, expected in exact_fields.items():
        if report.get(field) != expected:
            raise CandidateValidationError(f"candidate report {field} mismatch")
    if str(report.get("parent_checkpoint_sha256", "")).split(":", 1)[-1].lower() != expected_parent:
        raise CandidateValidationError("candidate report parent checkpoint mismatch")
    if str(report.get("checkpoint_sha256", "")).split(":", 1)[-1].lower() != child_sha:
        raise CandidateValidationError("candidate report checkpoint mismatch")
    if str(report.get("train_sha256", "")).split(":", 1)[-1].lower() != package.train_sha256:
        raise CandidateValidationError("candidate report train data mismatch")
    if str(report.get("validation_sha256", "")).split(":", 1)[-1].lower() != package.validation_sha256:
        raise CandidateValidationError("candidate report validation data mismatch")

    parent_meta = _metadata(parent)
    child_meta = _metadata(checkpoint)
    initial_epochs = int(report.get("initial_epochs", -1))
    initial_steps = int(report.get("initial_steps", -1))
    final_epochs = int(report.get("final_epochs", -1))
    final_steps = int(report.get("final_steps", -1))
    if initial_epochs != int(parent_meta.get("epochs", -2)) or initial_steps != int(parent_meta.get("steps", -2)):
        raise CandidateValidationError("candidate initial epoch/step do not match parent state")
    if final_epochs != initial_epochs + config.epochs or child_meta.get("epochs") != final_epochs:
        raise CandidateValidationError("candidate final epoch does not prove requested continuation")
    if final_steps <= initial_steps or child_meta.get("steps") != final_steps:
        raise CandidateValidationError("candidate final step does not prove optimizer continuation")
    stable_metadata = ("format", "profile", "task", "paths", "classes", "hidden", "seed", "parameter_count", "target_mean", "target_scale")
    for field in stable_metadata:
        if child_meta.get(field) != parent_meta.get(field):
            raise CandidateValidationError(f"candidate changed inherited metadata: {field}")
    if child_meta.get("learning_rate") != config.learning_rate or child_meta.get("batch_size") != config.batch_size:
        raise CandidateValidationError("candidate did not apply requested optimizer configuration")

    try:
        with np.load(parent, allow_pickle=False) as old, np.load(checkpoint, allow_pickle=False) as new:
            if set(old.files) != set(new.files):
                raise CandidateValidationError("candidate checkpoint schema differs from parent")
            if not np.array_equal(old["mean"], new["mean"]) or not np.array_equal(old["scale"], new["scale"]):
                raise CandidateValidationError("candidate refit preprocessing state from validation or continuation data")
            model_changed = any(not np.array_equal(old[name], new[name]) for name in _PARAMETERS)
            optimizer_changed = any(not np.array_equal(old[name], new[name]) for name in _OPTIMIZER)
    except (OSError, ValueError, KeyError) as exc:
        if isinstance(exc, CandidateValidationError):
            raise
        raise CandidateValidationError("candidate arrays are invalid") from exc
    if not model_changed:
        raise CandidateValidationError("candidate model state did not change")
    if not optimizer_changed:
        raise CandidateValidationError("candidate optimizer state did not change")

    history_rows = [line for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(history_rows) != config.epochs:
        raise CandidateValidationError("candidate history epoch count mismatch")
    return {
        "parent_sha256": expected_parent,
        "checkpoint_sha256": child_sha,
        "metrics_before": _metric_map(report.get("validation_before"), "validation_before"),
        "metrics_after": _metric_map(report.get("validation_after"), "validation_after"),
        "initial_epochs": initial_epochs,
        "final_epochs": final_epochs,
        "initial_steps": initial_steps,
        "final_steps": final_steps,
        "model_state_changed": model_changed,
        "optimizer_state_changed": optimizer_changed,
    }


def recover_candidate_receipt(
    package: PackageAudit,
    parent: Path,
    output_dir: Path,
    config: CandidateConfig,
    stage_id: str,
) -> CandidateReceipt:
    """Recover a fully persisted candidate after interruption before parent state commit."""

    output_dir = Path(output_dir).resolve()
    receipt_path = output_dir / "candidate-receipt.json"
    if not receipt_path.is_file():
        raise FileExistsError(f"candidate output conflict without receipt: {output_dir}")
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt = CandidateReceipt(**payload)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise CandidateValidationError(f"candidate receipt is invalid: {receipt_path}") from exc
    if Path(receipt.output_dir).resolve() != output_dir or receipt.stage_id != stage_id or receipt.profile != package.profile:
        raise CandidateValidationError("recovered candidate identity mismatch")
    if (output_dir / "training.json").is_file():
        proof = validate_candidate_output(package, Path(parent), output_dir, config, stage_id)
        for field in (
            "parent_sha256",
            "checkpoint_sha256",
            "metrics_before",
            "metrics_after",
            "initial_epochs",
            "final_epochs",
            "initial_steps",
            "final_steps",
            "model_state_changed",
            "optimizer_state_changed",
        ):
            if getattr(receipt, field) != proof[field]:
                raise CandidateValidationError(f"recovered candidate proof mismatch: {field}")
    return receipt


class OfficialTrainer:
    """Run exactly one official-package trainer in an isolated subprocess."""

    def __init__(self, python_executable: Path | str, timeout_seconds: float = 600.0) -> None:
        self.python_executable = str(python_executable)
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @staticmethod
    def _validate_config(package: PackageAudit, config: CandidateConfig) -> None:
        if config.epochs not in {1, 2, 3, 5}:
            raise ValueError("epochs must be one of 1, 2, 3, 5")
        allowed_rates = {package.base_learning_rate * factor for factor in (0.25, 0.5, 1.0)}
        if not any(math.isclose(config.learning_rate, value, rel_tol=0.0, abs_tol=1e-15) for value in allowed_rates):
            raise ValueError("learning rate is outside the approved multipliers")
        if config.batch_size not in {package.base_batch_size, package.base_batch_size * 2}:
            raise ValueError("batch size is outside the approved choices")

    @staticmethod
    def _failure_path(output_dir: Path) -> Path:
        return output_dir.with_name(output_dir.name + ".failure.json")

    def _write_failure(self, output_dir: Path, stage_id: str, error: str, wall_seconds: float) -> None:
        failure = self._failure_path(output_dir)
        if failure.exists():
            raise FileExistsError(f"failure receipt already exists: {failure}")
        failure.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(
            failure,
            {
                "format": "brace-msi.official-candidate-failure.v1",
                "stage_id": stage_id,
                "status": "failed",
                "error": error,
                "wall_seconds": wall_seconds,
                "validation_exposure": {
                    "preflight_hash_reads": 1,
                    "trainer_dataset_loads_upper_bound": 1,
                    "metric_evaluations_unknown": True,
                },
                "official_package": True,
                "official_scoring_ready": False,
            },
        )

    def run_candidate(
        self,
        package: PackageAudit,
        parent: Path,
        output_dir: Path,
        config: CandidateConfig,
        stage_id: str,
    ) -> CandidateReceipt:
        parent = Path(parent).resolve()
        output_dir = Path(output_dir).resolve()
        package_dir = package.package_dir.resolve()
        if output_dir == package_dir or output_dir.is_relative_to(package_dir) or package_dir.is_relative_to(output_dir):
            raise ValueError("candidate output and official package paths overlap")
        if output_dir.exists() or output_dir.is_symlink():
            raise FileExistsError("output must be a new directory")
        if self._failure_path(output_dir).exists():
            raise FileExistsError("failure receipt already exists for output")
        if not _STAGE_PATTERN.fullmatch(stage_id):
            raise ValueError("stage_id must be nonempty, bounded and filesystem-safe")
        self._validate_config(package, config)
        if not parent.is_file() or parent.is_symlink():
            raise ValueError("parent checkpoint must be a regular file")
        if _sha256(package.checkpoint_path) != package.checkpoint_sha256:
            raise CandidateValidationError("official package checkpoint changed after audit")
        if _sha256(package.train_path) != package.train_sha256 or _sha256(package.validation_path) != package.validation_sha256:
            raise CandidateValidationError("official package public data changed after audit")
        if package_tree_sha256(package.package_dir) != package.package_tree_sha256:
            raise CandidateValidationError("official package tree changed after audit")
        for name, expected in package.source_sha256.items():
            if _sha256(package.package_dir / "baselines" / name) != expected:
                raise CandidateValidationError(f"official package source code changed after audit: {name}")

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.python_executable,
            "-m",
            "baselines.train",
            "--profile",
            package.profile,
            "--train",
            str(package.train_path),
            "--validation",
            str(package.validation_path),
            "--output",
            str(output_dir),
            "--epochs",
            str(config.epochs),
            "--learning-rate",
            repr(config.learning_rate),
            "--batch-size",
            str(config.batch_size),
            "--stage-id",
            stage_id,
        ]
        command.extend(
            ["--from-baseline" if _sha256(parent) == package.checkpoint_sha256 else "--resume", str(parent)]
        )
        provenance_path: Path | None = None
        if package.profile == "B":
            provenance_path = output_dir.parent / f".{stage_id}.label-provenance.json"
            if provenance_path.exists():
                raise FileExistsError(f"label provenance already exists: {provenance_path}")
            _atomic_json(
                provenance_path,
                {
                    "status": "approved",
                    "method": "official package remaining_time_from_lifecycle target definition",
                },
            )
            command.extend(["--label-provenance", str(provenance_path)])

        environment = os.environ.copy()
        environment.update(
            PYTHONDONTWRITEBYTECODE="1",
            BASELINE_CPU_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        started = time.monotonic()
        process: subprocess.Popen[str] | None = None
        cpu_seconds = 0.0
        peak_rss = 0
        try:
            process = subprocess.Popen(
                command,
                cwd=package.package_dir,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            observed = psutil.Process(process.pid)
            while process.poll() is None:
                elapsed = time.monotonic() - started
                if elapsed > self.timeout_seconds:
                    for child in observed.children(recursive=True):
                        child.kill()
                    process.kill()
                    process.communicate()
                    raise TimeoutError(f"candidate training timed out after {self.timeout_seconds:g} seconds")
                try:
                    family = [observed, *observed.children(recursive=True)]
                    cpu_seconds = max(
                        cpu_seconds,
                        sum(member.cpu_times().user + member.cpu_times().system for member in family),
                    )
                    peak_rss = max(peak_rss, sum(member.memory_info().rss for member in family))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                time.sleep(0.005)
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                message = f"candidate trainer exited {process.returncode}: {stderr.strip()[-1000:]}"
                raise RuntimeError(message)
            try:
                stdout_report = json.loads(stdout.strip())
            except json.JSONDecodeError as exc:
                raise CandidateValidationError("candidate trainer stdout is not one JSON report") from exc
            if stdout_report.get("stage_id") != stage_id:
                raise CandidateValidationError("candidate trainer stdout stage_id mismatch")
            proof = validate_candidate_output(package, parent, output_dir, config, stage_id)
        except Exception as exc:
            wall = time.monotonic() - started
            self._write_failure(output_dir, stage_id, str(exc), wall)
            raise
        finally:
            if provenance_path is not None and provenance_path.exists():
                provenance_path.unlink()

        receipt = CandidateReceipt(
            stage_id=stage_id,
            profile=package.profile,
            wall_seconds=time.monotonic() - started,
            cpu_seconds=cpu_seconds,
            peak_rss_bytes=peak_rss,
            output_dir=str(output_dir),
            validation_file_reads=1,
            validation_metric_evaluations=config.epochs + 1,
            **proof,
        )
        _atomic_json(output_dir / "candidate-receipt.json", asdict(receipt))
        return receipt

