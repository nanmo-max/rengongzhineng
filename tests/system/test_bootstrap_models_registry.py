from pathlib import Path

import numpy as np
import pytest

from brace_msi.bootstrap import TaskBootstrap, TaskDefinition, TaskIncompatibleError
from brace_msi.modeling import CpuModelAdapter, cpu_model_pool
from brace_msi.registry import ModelRegistry


def _classification_data() -> tuple[np.ndarray, np.ndarray]:
    X = np.asarray(
        [[-2.0, 0.0], [-1.0, 0.2], [-0.5, -0.1], [0.5, 0.1], [1.0, 0.2], [2.0, 0.0]]
    )
    y = np.asarray([0, 0, 0, 1, 1, 1])
    return X, y


def test_cpu_pool_declares_real_capabilities_and_rejects_illegal_incremental_call() -> None:
    X, y = _classification_data()
    pool = {spec.family: spec for spec in cpu_model_pool("classification")}

    assert set(pool) == {"sgd", "linear", "hist_gradient_boosting", "extra_trees"}
    assert pool["sgd"].capabilities.supports_partial_fit is True
    assert pool["linear"].capabilities.supports_partial_fit is False
    assert pool["extra_trees"].capabilities.supports_partial_fit is False

    batch_model = CpuModelAdapter(
        task_kind="classification", family="linear", seed=20261107
    ).fit(X, y)
    with pytest.raises(TypeError, match="does not support partial_fit"):
        batch_model.partial_fit(X, y)


@pytest.mark.parametrize("task_kind", ["classification", "regression"])
def test_every_cpu_pool_spec_constructs_and_predicts_its_declared_task(task_kind: str) -> None:
    X, classification_y = _classification_data()
    y = classification_y if task_kind == "classification" else np.arange(6, dtype=float)

    for spec in cpu_model_pool(task_kind):
        model = spec.create(seed=20261107).fit(X, y)
        assert model.capabilities == spec.capabilities
        assert model.predict(X).shape == (6,)


def test_task_bootstrap_initializes_unknown_task_and_blocks_incompatible_reuse() -> None:
    X, y = _classification_data()
    bootstrap = TaskBootstrap(seed=20261107)
    first = bootstrap.initialize(
        TaskDefinition("unknown-bearing-a", "classification", 2), X, y
    )

    assert first.signature.task_kind == "classification"
    assert first.signature.n_features == 2
    assert first.signature.label_space == (0, 1)
    assert first.model.predict(X).shape == (6,)

    compatible = TaskDefinition("unknown-bearing-b", "classification", 2)
    bootstrap.ensure_compatible(first.signature, compatible, observed_labels=[0, 1])

    with pytest.raises(TaskIncompatibleError, match="feature count"):
        bootstrap.ensure_compatible(
            first.signature,
            TaskDefinition("unknown-bearing-c", "classification", 3),
            observed_labels=[0, 1],
        )
    with pytest.raises(TaskIncompatibleError, match="label space"):
        bootstrap.ensure_compatible(first.signature, compatible, observed_labels=[0, 2])
    with pytest.raises(TaskIncompatibleError, match="task kind"):
        bootstrap.ensure_compatible(
            first.signature,
            TaskDefinition("unknown-rul", "regression", 2),
            observed_labels=None,
        )


def test_model_registry_loads_exact_prediction_and_rolls_back(tmp_path: Path) -> None:
    X, y = _classification_data()
    bootstrap = TaskBootstrap(seed=20261107)
    result = bootstrap.initialize(
        TaskDefinition("bearing", "classification", 2), X, y
    )
    registry = ModelRegistry(tmp_path / "registry")
    registry.deploy(
        task_id="bearing",
        version="v1",
        model=result.model,
        signature=result.signature,
    )
    original = registry.load_stable("bearing")
    original_predictions = original.model.predict(X)

    updated = result.model.clone().partial_fit(
        np.asarray([[3.0, 0.0], [4.0, 0.1]]), np.asarray([0, 0])
    )
    registry.deploy(
        task_id="bearing",
        version="v2",
        model=updated,
        signature=result.signature,
    )
    assert registry.current_version("bearing") == "v2"

    rolled_back = registry.rollback("bearing")
    assert rolled_back == "v1"
    assert registry.current_version("bearing") == "v1"
    np.testing.assert_array_equal(
        registry.load_stable("bearing").model.predict(X), original_predictions
    )


def test_registry_rejects_unsafe_identifiers(tmp_path: Path) -> None:
    X, y = _classification_data()
    result = TaskBootstrap(seed=1).initialize(
        TaskDefinition("bearing", "classification", 2), X, y
    )
    registry = ModelRegistry(tmp_path / "registry")

    with pytest.raises(ValueError, match="identifier"):
        registry.deploy(
            task_id="../escape",
            version="v1",
            model=result.model,
            signature=result.signature,
        )
