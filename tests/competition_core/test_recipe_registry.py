from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brace_formal.data import DataBatch
from brace_formal.model import FormalModel
from brace_formal.profile import build_task_profile
from brace_formal.recipes import RecipeRegistry, execute_recipe
from tests.competition_core.support import write_parent


def _model(tmp_path: Path, task: str) -> FormalModel:
    path = tmp_path / f"{task}.npz"
    write_parent(path, task=task)
    return FormalModel.load(path)


def _batch(task: str) -> DataBatch:
    x = np.asarray([[float(index), float(index % 3)] for index in range(12)], dtype=np.float64)
    y = (
        np.asarray([0] * 10 + [1] * 2, dtype=np.int64)
        if task == "classification"
        else np.asarray([float(index * index) for index in range(12)], dtype=np.float64)
    )
    return DataBatch(tuple(f"sample-{index}" for index in range(12)), x, y, task[0] * 64)


def _profile(model: FormalModel, batch: DataBatch):
    task = str(model.meta["task"])
    metric = "macro_f1" if task == "classification" else "rmse"
    return build_task_profile({"task": task, "metric": metric}, model, batch, batch)


def test_registry_exposes_task_compatible_weighting_losses_and_history_policies(tmp_path: Path) -> None:
    registry = RecipeRegistry()
    classification = _model(tmp_path, "classification")
    regression = _model(tmp_path, "regression")

    class_recipes = {recipe.recipe_id: recipe for recipe in registry.available(_profile(classification, _batch("classification")))}
    regression_recipes = {recipe.recipe_id: recipe for recipe in registry.available(_profile(regression, _batch("regression")))}

    assert {"native_current", "native_replay", "class_weighted_ce", "class_balanced_sample", "averaged_native"} <= set(class_recipes)
    assert {"native_current", "native_replay", "regression_mse", "regression_huber", "regression_asymmetric", "averaged_native"} <= set(regression_recipes)
    assert "regression_huber" not in class_recipes
    assert "class_weighted_ce" not in regression_recipes
    assert class_recipes["native_current"].history_policy == "current"
    assert class_recipes["native_replay"].history_policy == "current_plus_history"
    assert "retain" not in class_recipes
    assert registry.fallback(_profile(classification, _batch("classification"))).recipe_id == "native_current"


@pytest.mark.parametrize("recipe_id", ["class_weighted_ce", "class_balanced_sample"])
def test_classification_recipes_execute_real_balancing(tmp_path: Path, recipe_id: str) -> None:
    parent = _model(tmp_path, "classification")
    batch = _batch("classification")
    registry = RecipeRegistry()
    recipe = registry.resolve(recipe_id, _profile(parent, batch), {})

    result = execute_recipe(parent, recipe, batch)

    result.model.validate()
    assert result.model.meta["epochs"] > parent.meta["epochs"]
    assert result.receipt["recipe_id"] == recipe_id
    assert result.receipt["class_weighting"] is (recipe_id == "class_weighted_ce")
    assert result.receipt["balanced_sampling"] is (recipe_id == "class_balanced_sample")
    if recipe_id == "class_balanced_sample":
        assert result.receipt["training_samples"] > len(batch.ids)


@pytest.mark.parametrize("recipe_id,loss", [("regression_mse", "mse"), ("regression_huber", "huber"), ("regression_asymmetric", "asymmetric")])
def test_regression_recipes_execute_declared_loss(tmp_path: Path, recipe_id: str, loss: str) -> None:
    parent = _model(tmp_path, "regression")
    batch = _batch("regression")
    recipe = RecipeRegistry().resolve(recipe_id, _profile(parent, batch), {})

    result = execute_recipe(parent, recipe, batch)

    result.model.validate()
    assert result.receipt["loss"] == loss
    assert len(result.losses) == recipe.epochs
    assert all(np.isfinite(result.losses))


def test_recipe_overrides_learning_epoch_and_parent_candidate_averaging(tmp_path: Path) -> None:
    parent = _model(tmp_path, "regression")
    batch = _batch("regression")
    registry = RecipeRegistry()
    profile = _profile(parent, batch)
    recipe = registry.resolve(
        "averaged_native",
        profile,
        {"epochs": 2, "learning_rate_multiplier": 2.0, "parent_average_alpha": 0.5},
    )
    raw_recipe = registry.resolve(
        "native_current",
        profile,
        {"epochs": 2, "learning_rate_multiplier": 2.0},
    )

    averaged = execute_recipe(parent, recipe, batch)
    raw = execute_recipe(parent, raw_recipe, batch)

    assert averaged.receipt["epochs"] == 2
    assert averaged.receipt["effective_learning_rate"] == pytest.approx(0.02)
    assert averaged.model.meta["learning_rate"] == parent.meta["learning_rate"]
    for name in parent.params:
        np.testing.assert_allclose(
            averaged.model.params[name],
            0.5 * parent.params[name] + 0.5 * raw.model.params[name],
        )


def test_registry_rejects_task_incompatible_recipe_and_invalid_overrides(tmp_path: Path) -> None:
    parent = _model(tmp_path, "classification")
    profile = _profile(parent, _batch("classification"))
    registry = RecipeRegistry()

    with pytest.raises(ValueError, match="incompatible"):
        registry.resolve("regression_huber", profile, {})
    with pytest.raises(ValueError, match="epochs"):
        registry.resolve("native_current", profile, {"epochs": 0})
    with pytest.raises(ValueError, match="unsupported recipe parameter"):
        registry.resolve("native_current", profile, {"mystery": 1})
