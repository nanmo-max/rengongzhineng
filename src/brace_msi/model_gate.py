"""Tiered CPU model admission and formal checkpoint delivery gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import hashlib
import json
import os
from pathlib import Path
import pickle
import tempfile
from typing import Any

import numpy as np

from .modeling import CpuModelAdapter, TaskKind


MAX_FORMAL_MODEL_BYTES = 64 * 1024 * 1024


class ModelGateError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ModelTier(IntEnum):
    TIER0 = 0
    TIER1 = 1
    TIER2 = 2


@dataclass(frozen=True)
class RegisteredModelSpec:
    task_kind: TaskKind
    family: str
    tier: ModelTier
    supports_incremental: bool
    formal_checkpoint_eligible: bool


@dataclass(frozen=True)
class CpuAdapterReceipt:
    task_kind: TaskKind
    family: str
    tier: ModelTier
    artifact_path: str
    artifact_bytes: int
    predictions_identical: bool
    supports_incremental: bool
    formal_checkpoint_eligible: bool


@dataclass(frozen=True)
class ExternalCompatibilityReceipt:
    family: str
    dependency_bytes: int
    artifact_bytes: int
    runs_on_four_core_eight_gb: bool
    input_contract_ok: bool
    training_budget_ok: bool
    save_load_predictions_identical: bool
    prediction_protocol_ok: bool
    artifact_compatible: bool


@dataclass(frozen=True)
class ParentLineageProof:
    parent_sha256: str
    loaded_parent_sha256: str
    child_sha256: str
    initial_epochs: int
    final_epochs: int
    initial_steps: int
    final_steps: int


@dataclass(frozen=True)
class FormalArtifactReceipt:
    checkpoint_name: str
    checkpoint_sha256: str
    parent_sha256: str
    parent_loaded: bool
    prediction_entry_ok: bool
    total_model_bytes: int
    task_kind: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_pickle(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class TieredCpuModelRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._specs: dict[tuple[str, str], RegisteredModelSpec] = {}
        for task_kind in ("classification", "regression"):
            self._specs[(task_kind, "official_initial")] = RegisteredModelSpec(
                task_kind=task_kind,
                family="official_initial",
                tier=ModelTier.TIER0,
                supports_incremental=True,
                formal_checkpoint_eligible=True,
            )
            for family in ("sgd", "linear"):
                self._specs[(task_kind, family)] = RegisteredModelSpec(
                    task_kind=task_kind,
                    family=family,
                    tier=ModelTier.TIER0,
                    supports_incremental=family == "sgd",
                    formal_checkpoint_eligible=False,
                )
            for family in ("hist_gradient_boosting", "extra_trees"):
                self._specs[(task_kind, family)] = RegisteredModelSpec(
                    task_kind=task_kind,
                    family=family,
                    tier=ModelTier.TIER1,
                    supports_incremental=False,
                    formal_checkpoint_eligible=False,
                )

    def spec(self, task_kind: TaskKind, family: str) -> RegisteredModelSpec:
        try:
            return self._specs[(task_kind, family)]
        except KeyError as exc:
            raise ModelGateError("family_not_registered") from exc

    def certify_cpu_adapter(
        self,
        *,
        task_kind: TaskKind,
        family: str,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_probe: np.ndarray,
        seed: int,
    ) -> CpuAdapterReceipt:
        spec = self.spec(task_kind, family)
        if family == "official_initial" or spec.tier is ModelTier.TIER2:
            raise ModelGateError("adapter_certification_not_applicable")
        model = CpuModelAdapter(task_kind=task_kind, family=family, seed=seed).fit(X_train, y_train)
        if model.capabilities.supports_partial_fit != spec.supports_incremental:
            raise ModelGateError("incremental_capability_mismatch")
        before = np.asarray(model.predict(X_probe))
        artifact = self.root / task_kind / f"{family}.pkl"
        _atomic_pickle(artifact, model)
        with artifact.open("rb") as stream:
            restored = pickle.load(stream)
        after = np.asarray(restored.predict(X_probe))
        if before.shape != after.shape or not np.array_equal(before, after):
            raise ModelGateError("save_load_prediction_mismatch")
        size = artifact.stat().st_size
        if size > MAX_FORMAL_MODEL_BYTES:
            raise ModelGateError("model_artifacts_too_large")
        return CpuAdapterReceipt(
            task_kind=task_kind,
            family=family,
            tier=spec.tier,
            artifact_path=str(artifact),
            artifact_bytes=size,
            predictions_identical=True,
            supports_incremental=spec.supports_incremental,
            formal_checkpoint_eligible=False,
        )

    def enable_tier2(
        self,
        task_kind: TaskKind,
        receipt: ExternalCompatibilityReceipt,
    ) -> RegisteredModelSpec:
        checks = (
            receipt.dependency_bytes >= 0,
            0 <= receipt.artifact_bytes <= MAX_FORMAL_MODEL_BYTES,
            receipt.runs_on_four_core_eight_gb,
            receipt.input_contract_ok,
            receipt.training_budget_ok,
            receipt.save_load_predictions_identical,
            receipt.prediction_protocol_ok,
            receipt.artifact_compatible,
        )
        if not all(checks):
            raise ModelGateError("tier2_compatibility_failed")
        spec = RegisteredModelSpec(
            task_kind=task_kind,
            family=receipt.family,
            tier=ModelTier.TIER2,
            supports_incremental=False,
            formal_checkpoint_eligible=receipt.artifact_compatible,
        )
        self._specs[(task_kind, receipt.family)] = spec
        return spec


def _load_checkpoint(path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    required = {"w1", "b1", "w2", "b2", "mean", "scale", "metadata"}
    try:
        with np.load(path, allow_pickle=False) as archive:
            if not required.issubset(archive.files):
                raise ModelGateError("checkpoint_schema_invalid")
            if any(archive[name].dtype.kind == "O" for name in archive.files):
                raise ModelGateError("checkpoint_object_array_forbidden")
            raw_metadata = archive["metadata"]
            if raw_metadata.shape != () or raw_metadata.dtype.kind != "U":
                raise ModelGateError("checkpoint_metadata_invalid")
            metadata = json.loads(str(raw_metadata.item()))
            arrays = {name: np.asarray(archive[name]) for name in required - {"metadata"}}
    except ModelGateError:
        raise
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ModelGateError("checkpoint_load_failed") from exc
    if not isinstance(metadata, dict):
        raise ModelGateError("checkpoint_metadata_invalid")
    if any(not np.all(np.isfinite(array)) for array in arrays.values()):
        raise ModelGateError("checkpoint_non_finite")
    return arrays, metadata


def predict_checkpoint(checkpoint: Path, inputs: np.ndarray) -> np.ndarray:
    """Independent, platform-neutral prediction entry for official NumPy MLPs."""
    arrays, metadata = _load_checkpoint(Path(checkpoint))
    X = np.asarray(inputs, dtype=np.float64)
    if X.ndim != 2 or X.shape[1] != arrays["w1"].shape[0]:
        raise ModelGateError("prediction_input_shape_invalid")
    scale = np.asarray(arrays["scale"], dtype=np.float64)
    safe_scale = np.where(np.abs(scale) < 1e-12, 1.0, scale)
    normalized = (X - arrays["mean"]) / safe_scale
    hidden = np.tanh(normalized @ arrays["w1"] + arrays["b1"])
    output = hidden @ arrays["w2"] + arrays["b2"]
    task = metadata.get("task")
    if task == "classification":
        indices = np.argmax(output, axis=1)
        classes = metadata.get("classes")
        return np.asarray(classes, dtype=np.str_)[indices] if classes else indices
    if task == "regression":
        predictions = output.reshape(-1)
        return predictions * float(metadata.get("target_scale", 1.0)) + float(
            metadata.get("target_mean", 0.0)
        )
    raise ModelGateError("checkpoint_task_invalid")


class FormalArtifactGate:
    MODEL_SUFFIXES = {".npz", ".pkl", ".joblib", ".onnx", ".bin"}

    def __init__(self, *, max_model_bytes: int = MAX_FORMAL_MODEL_BYTES) -> None:
        self.max_model_bytes = int(max_model_bytes)

    def validate(
        self,
        *,
        parent_checkpoint: Path,
        artifact_root: Path,
        lineage: ParentLineageProof,
        prediction_probe: np.ndarray,
    ) -> FormalArtifactReceipt:
        parent = Path(parent_checkpoint)
        root = Path(artifact_root)
        child = root / "checkpoint.npz"
        if not parent.is_file() or not child.is_file():
            raise ModelGateError("checkpoint_missing")
        actual_parent = _sha256(parent)
        actual_child = _sha256(child)
        if lineage.parent_sha256 != actual_parent or lineage.loaded_parent_sha256 != actual_parent:
            raise ModelGateError("parent_not_actually_loaded")
        if lineage.child_sha256 != actual_child or actual_child == actual_parent:
            raise ModelGateError("child_checkpoint_invalid")
        if lineage.final_epochs <= lineage.initial_epochs or lineage.final_steps <= lineage.initial_steps:
            raise ModelGateError("continuation_not_proven")
        _, parent_metadata = _load_checkpoint(parent)
        _, child_metadata = _load_checkpoint(child)
        for field in ("format", "profile", "task", "paths", "hidden", "parameter_count"):
            if child_metadata.get(field) != parent_metadata.get(field):
                raise ModelGateError("inherited_metadata_changed")
        if (
            int(parent_metadata.get("epochs", -1)) != lineage.initial_epochs
            or int(parent_metadata.get("steps", -1)) != lineage.initial_steps
            or int(child_metadata.get("epochs", -1)) != lineage.final_epochs
            or int(child_metadata.get("steps", -1)) != lineage.final_steps
        ):
            raise ModelGateError("lineage_state_mismatch")
        model_files = [
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in self.MODEL_SUFFIXES
        ]
        total_model_bytes = sum(path.stat().st_size for path in model_files)
        if total_model_bytes > self.max_model_bytes:
            raise ModelGateError("model_artifacts_too_large")
        predictions = np.asarray(predict_checkpoint(child, prediction_probe))
        if predictions.shape != (len(prediction_probe),):
            raise ModelGateError("independent_prediction_failed")
        return FormalArtifactReceipt(
            checkpoint_name=child.name,
            checkpoint_sha256=actual_child,
            parent_sha256=actual_parent,
            parent_loaded=True,
            prediction_entry_ok=True,
            total_model_bytes=total_model_bytes,
            task_kind=str(child_metadata["task"]),
        )
