from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brace_formal.data import DataBatch
from brace_formal.model import FormalModel
from tests.competition_core.support import write_parent


def _model(tmp_path: Path, task: str = "regression") -> FormalModel:
    path = tmp_path / f"{task}.npz"
    write_parent(path, task=task)
    return FormalModel.load(path)


def _batch(task: str = "regression") -> DataBatch:
    x = np.asarray([[float(index) / 4.0, float(index % 3)] for index in range(12)], dtype=np.float64)
    y = (
        np.asarray([0] * 6 + [1] * 6, dtype=np.int64)
        if task == "classification"
        else np.asarray([float(index * index) for index in range(12)], dtype=np.float64)
    )
    return DataBatch(tuple(f"row-{index}" for index in range(12)), x, y, "a" * 64)


def _distance_from(parent: FormalModel, candidate: FormalModel) -> float:
    return float(
        np.sqrt(
            sum(
                np.sum((candidate.params[name] - parent.params[name]) ** 2)
                for name in ("w1", "w2")
            )
        )
    )


def test_explicit_adam_optimizer_is_bitwise_equal_to_existing_fit(tmp_path: Path) -> None:
    """Catches an optimizer extension changing the verified native default."""

    parent = _model(tmp_path, "classification")
    batch = _batch("classification")
    implicit = parent.clone()
    explicit = parent.clone()

    implicit_losses = implicit.fit(batch.x, batch.y, 2)
    explicit_losses = explicit.fit(
        batch.x,
        batch.y,
        2,
        optimizer="adam",
        optimizer_parameters={},
    )

    assert implicit_losses == explicit_losses
    assert implicit.meta == explicit.meta
    for group_name in ("params", "first", "second"):
        implicit_group = getattr(implicit, group_name)
        explicit_group = getattr(explicit, group_name)
        for name in implicit_group:
            np.testing.assert_array_equal(implicit_group[name], explicit_group[name])


def test_l2sp_stays_closer_to_fit_entry_parent_than_adam(tmp_path: Path) -> None:
    """Catches L2-SP anchoring weights to zero or ignoring the fit-entry parent."""

    parent = _model(tmp_path)
    batch = _batch()
    adam = parent.clone()
    l2sp = parent.clone()

    adam.fit(batch.x, batch.y, 5, optimizer="adam")
    l2sp.fit(batch.x, batch.y, 5, optimizer="l2sp", optimizer_parameters={"strength": 0.1})

    assert _distance_from(parent, l2sp) < _distance_from(parent, adam)


def test_sam_uses_one_adam_step_per_minibatch_and_roundtrips(tmp_path: Path) -> None:
    """Catches SAM applying Adam twice or persisting an incompatible extra state."""

    parent = _model(tmp_path)
    batch = _batch()
    candidate = parent.clone()
    expected_steps = int(parent.meta["steps"]) + 3

    candidate.fit(batch.x, batch.y, 1, optimizer="sam", optimizer_parameters={"rho": 0.05})

    assert candidate.meta["steps"] == expected_steps
    assert all(np.all(np.isfinite(value)) for value in candidate.params.values())
    saved = tmp_path / "sam.npz"
    candidate.save(saved)
    restored = FormalModel.load(saved)
    np.testing.assert_array_equal(restored.predict_raw(batch.x), candidate.predict_raw(batch.x))


def test_adamw_decays_weights_only_after_the_adam_update(tmp_path: Path) -> None:
    """Catches AdamW shrinking biases, moments, or applying coupled L2 instead."""

    parent = _model(tmp_path)
    parent.meta["batch_size"] = 12
    batch = _batch()
    adam = parent.clone()
    adamw = parent.clone()
    decay = 0.1

    adam.fit(batch.x, batch.y, 1, optimizer="adam")
    adamw.fit(batch.x, batch.y, 1, optimizer="adamw", optimizer_parameters={"weight_decay": decay})

    factor = 1.0 - float(parent.meta["learning_rate"]) * decay
    for name in ("w1", "w2"):
        np.testing.assert_allclose(adamw.params[name], adam.params[name] * factor, rtol=0.0, atol=1e-15)
    for name in ("b1", "b2"):
        np.testing.assert_array_equal(adamw.params[name], adam.params[name])
    for name in parent.params:
        np.testing.assert_array_equal(adamw.first[name], adam.first[name])
        np.testing.assert_array_equal(adamw.second[name], adam.second[name])


@pytest.mark.parametrize(
    ("optimizer", "parameters", "message"),
    [
        ("mystery", {}, "unsupported optimizer"),
        ("l2sp", {"strength": -1.0}, "strength"),
        ("sam", {"rho": float("nan")}, "rho"),
        ("adamw", {"weight_decay": -0.1}, "weight_decay"),
        ("sam", {"rho": 0.1, "extra": 1.0}, "unsupported optimizer parameter"),
    ],
)
def test_optimizer_validation_fails_before_mutating_model(
    tmp_path: Path,
    optimizer: str,
    parameters: dict[str, float],
    message: str,
) -> None:
    """Catches invalid research configuration partially training a candidate."""

    model = _model(tmp_path)
    before = model.clone()
    batch = _batch()

    with pytest.raises(ValueError, match=message):
        model.fit(batch.x, batch.y, 1, optimizer=optimizer, optimizer_parameters=parameters)

    assert model.meta == before.meta
    for group_name in ("params", "first", "second"):
        group = getattr(model, group_name)
        expected = getattr(before, group_name)
        for name in group:
            np.testing.assert_array_equal(group[name], expected[name])


def test_mature_recipe_catalog_is_task_agnostic_and_parent_compatible(tmp_path: Path) -> None:
    """Catches the pilot silently routing mechanisms by A/B/C identity."""

    from brace_msi.mature_optimizer_pilot import MATURE_PILOT_RECIPES, fit_mature_recipe

    assert set(MATURE_PILOT_RECIPES) == {
        "native_current",
        "native_replay",
        "l2sp_1e-4",
        "l2sp_1e-3",
        "sam_0.01",
        "sam_0.05",
        "adamw_1e-5",
        "adamw_1e-4",
    }
    assert all(recipe.task_types == ("classification", "regression") for recipe in MATURE_PILOT_RECIPES.values())

    parent = _model(tmp_path)
    result = fit_mature_recipe(parent, MATURE_PILOT_RECIPES["l2sp_1e-4"], _batch())
    result.model.validate()
    assert result.receipt["optimizer"] == "l2sp"
    assert result.receipt["optimizer_parameters"] == {"strength": 1e-4}
    assert result.model.meta["parameter_count"] == parent.meta["parameter_count"]
