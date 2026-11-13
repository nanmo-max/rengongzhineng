from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from brace_msi.model_gate import (
    ExternalCompatibilityReceipt,
    FormalArtifactGate,
    ModelGateError,
    ModelTier,
    ParentLineageProof,
    TieredCpuModelRegistry,
    predict_checkpoint,
)
from brace_msi.cli import main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkpoint(path: Path, *, task: str, epochs: int, steps: int) -> None:
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "profile": "test",
        "task": task,
        "paths": ["f0", "f1"],
        "classes": ["zero", "one"] if task == "classification" else None,
        "hidden": 2,
        "parameter_count": 12 if task == "classification" else 9,
        "epochs": epochs,
        "steps": steps,
        "target_mean": 10.0,
        "target_scale": 2.0,
    }
    output = 2 if task == "classification" else 1
    np.savez_compressed(
        path,
        w1=np.asarray([[1.0, 0.0], [0.0, 1.0]]),
        b1=np.zeros(2),
        w2=np.ones((2, output)),
        b2=np.asarray([0.0, 1.0]) if task == "classification" else np.zeros(1),
        mean=np.zeros(2),
        scale=np.ones(2),
        adam_first_w1=np.zeros((2, 2)),
        adam_first_b1=np.zeros(2),
        adam_first_w2=np.zeros((2, output)),
        adam_first_b2=np.zeros(output),
        adam_second_w1=np.zeros((2, 2)),
        adam_second_b1=np.zeros(2),
        adam_second_w2=np.zeros((2, output)),
        adam_second_b2=np.zeros(output),
        metadata=np.asarray(json.dumps(metadata)),
    )


def test_tiered_registry_declares_real_capabilities_without_dataset_names(tmp_path: Path) -> None:
    registry = TieredCpuModelRegistry(tmp_path / "registry")

    assert registry.spec("classification", "sgd").tier is ModelTier.TIER0
    assert registry.spec("regression", "linear").tier is ModelTier.TIER0
    assert registry.spec("classification", "hist_gradient_boosting").tier is ModelTier.TIER1
    assert registry.spec("regression", "extra_trees").tier is ModelTier.TIER1
    assert registry.spec("classification", "sgd").supports_incremental
    assert not registry.spec("classification", "linear").supports_incremental
    with pytest.raises(ModelGateError, match="family_not_registered"):
        registry.spec("classification", "mlp")


@pytest.mark.parametrize("family", ["sgd", "linear", "hist_gradient_boosting", "extra_trees"])
def test_tier0_and_tier1_train_save_load_same_predictions(tmp_path: Path, family: str) -> None:
    X = np.asarray([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
    y = np.asarray([0, 0, 1, 1])
    registry = TieredCpuModelRegistry(tmp_path / family)

    receipt = registry.certify_cpu_adapter(
        task_kind="classification",
        family=family,
        X_train=X,
        y_train=y,
        X_probe=X,
        seed=20261113,
    )

    assert receipt.predictions_identical
    assert receipt.artifact_bytes <= 64 * 1024 * 1024
    assert Path(receipt.artifact_path).is_file()
    assert receipt.formal_checkpoint_eligible is False


def test_tier2_requires_every_compatibility_gate(tmp_path: Path) -> None:
    registry = TieredCpuModelRegistry(tmp_path / "registry")
    incomplete = ExternalCompatibilityReceipt(
        family="catboost",
        dependency_bytes=10,
        artifact_bytes=10,
        runs_on_four_core_eight_gb=True,
        input_contract_ok=True,
        training_budget_ok=True,
        save_load_predictions_identical=False,
        prediction_protocol_ok=True,
        artifact_compatible=True,
    )
    with pytest.raises(ModelGateError, match="tier2_compatibility_failed"):
        registry.enable_tier2("regression", incomplete)


def test_formal_artifact_gate_proves_parent_lineage_prediction_and_size(tmp_path: Path) -> None:
    parent = tmp_path / "parent.npz"
    artifact = tmp_path / "candidate"
    artifact.mkdir()
    child = artifact / "checkpoint.npz"
    _checkpoint(parent, task="classification", epochs=1, steps=10)
    _checkpoint(child, task="classification", epochs=2, steps=20)
    proof = ParentLineageProof(
        parent_sha256=_sha256(parent),
        loaded_parent_sha256=_sha256(parent),
        child_sha256=_sha256(child),
        initial_epochs=1,
        final_epochs=2,
        initial_steps=10,
        final_steps=20,
    )

    receipt = FormalArtifactGate().validate(
        parent_checkpoint=parent,
        artifact_root=artifact,
        lineage=proof,
        prediction_probe=np.asarray([[0.0, 0.0], [1.0, 1.0]]),
    )

    assert receipt.checkpoint_name == "checkpoint.npz"
    assert receipt.parent_loaded
    assert receipt.prediction_entry_ok
    assert receipt.total_model_bytes <= 64 * 1024 * 1024


def test_formal_artifact_gate_rejects_fake_parent_and_oversized_models(tmp_path: Path) -> None:
    parent = tmp_path / "parent.npz"
    artifact = tmp_path / "candidate"
    artifact.mkdir()
    child = artifact / "checkpoint.npz"
    _checkpoint(parent, task="regression", epochs=1, steps=10)
    _checkpoint(child, task="regression", epochs=2, steps=20)
    bad = ParentLineageProof(
        parent_sha256=_sha256(parent),
        loaded_parent_sha256="0" * 64,
        child_sha256=_sha256(child),
        initial_epochs=1,
        final_epochs=2,
        initial_steps=10,
        final_steps=20,
    )
    with pytest.raises(ModelGateError, match="parent_not_actually_loaded"):
        FormalArtifactGate().validate(
            parent_checkpoint=parent,
            artifact_root=artifact,
            lineage=bad,
            prediction_probe=np.asarray([[0.0, 0.0]]),
        )

    (artifact / "extra-model.bin").write_bytes(b"x" * 256)
    good = ParentLineageProof(
        parent_sha256=_sha256(parent),
        loaded_parent_sha256=_sha256(parent),
        child_sha256=_sha256(child),
        initial_epochs=1,
        final_epochs=2,
        initial_steps=10,
        final_steps=20,
    )
    with pytest.raises(ModelGateError, match="model_artifacts_too_large"):
        FormalArtifactGate(max_model_bytes=128).validate(
            parent_checkpoint=parent,
            artifact_root=artifact,
            lineage=good,
            prediction_probe=np.asarray([[0.0, 0.0]]),
        )


def test_independent_prediction_entry_supports_classification_and_regression(tmp_path: Path) -> None:
    classification = tmp_path / "classification.npz"
    regression = tmp_path / "regression.npz"
    _checkpoint(classification, task="classification", epochs=1, steps=1)
    _checkpoint(regression, task="regression", epochs=1, steps=1)
    X = np.asarray([[0.0, 0.0], [1.0, 1.0]])

    class_predictions = predict_checkpoint(classification, X)
    regression_predictions = predict_checkpoint(regression, X)

    assert class_predictions.shape == (2,)
    assert set(class_predictions.tolist()) <= {"zero", "one"}
    assert regression_predictions.shape == (2,)
    assert np.all(np.isfinite(regression_predictions))

    input_path = tmp_path / "inputs.npy"
    output_path = tmp_path / "predictions.npy"
    np.save(input_path, X, allow_pickle=False)
    assert main(
        [
            "checkpoint-predict",
            "--checkpoint",
            str(regression),
            "--input-npy",
            str(input_path),
            "--output-npy",
            str(output_path),
        ]
    ) == 0
    assert np.array_equal(np.load(output_path, allow_pickle=False), regression_predictions)
