"""Parent-compatible task-adaptive training recipe registry."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

import numpy as np

from .data import DataBatch
from .model import FormalModel
from .profile import TaskProfile


@dataclass(frozen=True)
class TrainingRecipe:
    recipe_id: str
    task_types: tuple[str, ...]
    history_policy: str
    epochs: int
    learning_rate_multiplier: float = 1.0
    loss: str = "native"
    loss_parameters: tuple[tuple[str, float], ...] = ()
    class_weighting: bool = False
    balanced_sampling: bool = False
    parent_average_alpha: float | None = None

    def parameters_dict(self) -> dict[str, float]:
        return dict(self.loss_parameters)


@dataclass(frozen=True)
class CandidateResult:
    model: FormalModel
    losses: tuple[float, ...]
    receipt: dict[str, Any]


_RECIPES = (
    TrainingRecipe("native_current", ("classification", "regression"), "current", 1),
    TrainingRecipe("native_replay", ("classification", "regression"), "current_plus_history", 1),
    TrainingRecipe("class_weighted_ce", ("classification",), "current_plus_history", 2, loss="cross_entropy", class_weighting=True),
    TrainingRecipe("class_balanced_sample", ("classification",), "current", 2, loss="cross_entropy", balanced_sampling=True),
    TrainingRecipe("regression_mse", ("regression",), "current", 2, loss="mse"),
    TrainingRecipe("regression_huber", ("regression",), "current_plus_history", 2, loss="huber", loss_parameters=(("delta", 1.0),)),
    TrainingRecipe(
        "regression_asymmetric",
        ("regression",),
        "current_plus_history",
        2,
        loss="asymmetric",
        loss_parameters=(("overprediction_weight", 1.0), ("underprediction_weight", 2.0)),
    ),
    TrainingRecipe("averaged_native", ("classification", "regression"), "current_plus_history", 3, parent_average_alpha=0.25),
)


class RecipeRegistry:
    def __init__(self, recipes: tuple[TrainingRecipe, ...] = _RECIPES) -> None:
        if len({recipe.recipe_id for recipe in recipes}) != len(recipes):
            raise ValueError("recipe IDs must be unique")
        self._recipes = {recipe.recipe_id: recipe for recipe in recipes}

    def available(self, profile: TaskProfile) -> tuple[TrainingRecipe, ...]:
        return tuple(recipe for recipe in self._recipes.values() if profile.task in recipe.task_types)

    def fallback(self, profile: TaskProfile) -> TrainingRecipe:
        return self.resolve("native_current", profile, {})

    def resolve(
        self,
        recipe_id: str,
        profile: TaskProfile,
        parameters: Mapping[str, Any] | None,
    ) -> TrainingRecipe:
        recipe = self._recipes.get(recipe_id)
        if recipe is None:
            raise ValueError("unknown recipe")
        if profile.task not in recipe.task_types:
            raise ValueError("recipe is incompatible with the task")
        supplied = dict(parameters or {})
        allowed = {"epochs", "learning_rate_multiplier", "parent_average_alpha", "loss_parameters"}
        unknown = set(supplied) - allowed
        if unknown:
            raise ValueError(f"unsupported recipe parameter: {sorted(unknown)[0]}")
        epochs = supplied.get("epochs", recipe.epochs)
        multiplier = supplied.get("learning_rate_multiplier", recipe.learning_rate_multiplier)
        average = supplied.get("parent_average_alpha", recipe.parent_average_alpha)
        loss_parameters = supplied.get("loss_parameters", recipe.parameters_dict())
        if type(epochs) is not int or epochs < 1:
            raise ValueError("epochs must be a positive integer")
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or not math.isfinite(float(multiplier)) or float(multiplier) <= 0.0:
            raise ValueError("learning_rate_multiplier must be positive")
        if average is not None and (
            isinstance(average, bool)
            or not isinstance(average, (int, float))
            or not math.isfinite(float(average))
            or not 0.0 < float(average) <= 1.0
        ):
            raise ValueError("parent_average_alpha must be in (0, 1]")
        if not isinstance(loss_parameters, Mapping):
            raise ValueError("loss_parameters must be a mapping")
        normalized_loss_parameters: list[tuple[str, float]] = []
        for key, value in sorted(loss_parameters.items()):
            if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError("loss_parameters must contain finite numeric values")
            normalized_loss_parameters.append((key, float(value)))
        return replace(
            recipe,
            epochs=epochs,
            learning_rate_multiplier=float(multiplier),
            parent_average_alpha=None if average is None else float(average),
            loss_parameters=tuple(normalized_loss_parameters),
        )


def _class_weights(targets: np.ndarray, class_count: int) -> np.ndarray:
    counts = np.bincount(targets.astype(np.int64), minlength=class_count)
    if np.any(counts == 0):
        raise ValueError("class weighting requires every parent class in training data")
    inverse = len(targets) / (class_count * counts.astype(np.float64))
    return inverse[targets.astype(np.int64)]


def _balanced_rows(batch: DataBatch, class_count: int) -> tuple[np.ndarray, np.ndarray]:
    targets = batch.y.astype(np.int64)
    groups = [np.flatnonzero(targets == label) for label in range(class_count)]
    if any(len(indices) == 0 for indices in groups):
        raise ValueError("balanced sampling requires every parent class in training data")
    size = max(len(indices) for indices in groups)
    sampled = np.concatenate([np.resize(indices, size) for indices in groups])
    return batch.x[sampled], batch.y[sampled]


def execute_recipe(parent: FormalModel, recipe: TrainingRecipe, training_batch: DataBatch) -> CandidateResult:
    task = str(parent.meta["task"])
    if task not in recipe.task_types:
        raise ValueError("recipe is incompatible with the parent task")
    values = training_batch.x
    targets = training_batch.y
    sample_weights = None
    if recipe.class_weighting:
        sample_weights = _class_weights(targets, len(parent.meta["classes"]))
    if recipe.balanced_sampling:
        values, targets = _balanced_rows(training_batch, len(parent.meta["classes"]))
    candidate = parent.clone()
    parent_rate = float(parent.meta["learning_rate"])
    effective_rate = parent_rate * recipe.learning_rate_multiplier
    if not math.isfinite(effective_rate) or not 0.0 < effective_rate <= 1.0:
        raise ValueError("effective learning rate is outside the parent checkpoint contract")
    candidate.meta["learning_rate"] = effective_rate
    losses = candidate.fit(
        values,
        targets,
        recipe.epochs,
        sample_weights=sample_weights,
        loss=recipe.loss,
        loss_parameters=recipe.parameters_dict(),
    )
    candidate.meta["learning_rate"] = parent_rate
    if recipe.parent_average_alpha is not None:
        alpha = recipe.parent_average_alpha
        for name in candidate.params:
            candidate.params[name] = (1.0 - alpha) * parent.params[name] + alpha * candidate.params[name]
    candidate.validate()
    return CandidateResult(
        model=candidate,
        losses=tuple(float(value) for value in losses),
        receipt={
            "recipe_id": recipe.recipe_id,
            "task": task,
            "history_policy": recipe.history_policy,
            "epochs": recipe.epochs,
            "learning_rate_multiplier": recipe.learning_rate_multiplier,
            "effective_learning_rate": effective_rate,
            "loss": "cross_entropy" if task == "classification" and recipe.loss == "native" else "mse" if task == "regression" and recipe.loss == "native" else recipe.loss,
            "loss_parameters": recipe.parameters_dict(),
            "class_weighting": recipe.class_weighting,
            "balanced_sampling": recipe.balanced_sampling,
            "parent_average_alpha": recipe.parent_average_alpha,
            "training_samples": int(len(values)),
            "source_sha256": training_batch.sha256,
        },
    )
