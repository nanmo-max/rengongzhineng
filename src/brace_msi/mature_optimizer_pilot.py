"""Research-only parent-compatible optimizer recipes.

This module is intentionally absent from the formal image allowlist.  A method
must pass the registered pilot before it can be proposed for the production
recipe registry.
"""

from __future__ import annotations

from dataclasses import dataclass

from brace_formal.data import DataBatch
from brace_formal.model import FormalModel
from brace_formal.recipes import CandidateResult


@dataclass(frozen=True)
class MaturePilotRecipe:
    recipe_id: str
    task_types: tuple[str, ...]
    history_policy: str
    optimizer: str
    optimizer_parameters: tuple[tuple[str, float], ...] = ()
    epochs: int = 1

    def parameters_dict(self) -> dict[str, float]:
        return dict(self.optimizer_parameters)


_TASKS = ("classification", "regression")
MATURE_PILOT_RECIPES = {
    recipe.recipe_id: recipe
    for recipe in (
        MaturePilotRecipe("native_current", _TASKS, "current", "adam"),
        MaturePilotRecipe("native_replay", _TASKS, "current_plus_history", "adam"),
        MaturePilotRecipe("l2sp_1e-4", _TASKS, "current", "l2sp", (("strength", 1e-4),)),
        MaturePilotRecipe("l2sp_1e-3", _TASKS, "current", "l2sp", (("strength", 1e-3),)),
        MaturePilotRecipe("sam_0.01", _TASKS, "current", "sam", (("rho", 0.01),)),
        MaturePilotRecipe("sam_0.05", _TASKS, "current", "sam", (("rho", 0.05),)),
        MaturePilotRecipe("adamw_1e-5", _TASKS, "current", "adamw", (("weight_decay", 1e-5),)),
        MaturePilotRecipe("adamw_1e-4", _TASKS, "current", "adamw", (("weight_decay", 1e-4),)),
    )
}


def fit_mature_recipe(
    parent: FormalModel,
    recipe: MaturePilotRecipe,
    training_batch: DataBatch,
) -> CandidateResult:
    task = str(parent.meta["task"])
    if task not in recipe.task_types:
        raise ValueError("pilot recipe is incompatible with the parent task")
    candidate = parent.clone()
    losses = candidate.fit(
        training_batch.x,
        training_batch.y,
        recipe.epochs,
        optimizer=recipe.optimizer,
        optimizer_parameters=recipe.parameters_dict(),
    )
    candidate.validate()
    return CandidateResult(
        model=candidate,
        losses=tuple(float(value) for value in losses),
        receipt={
            "recipe_id": recipe.recipe_id,
            "task": task,
            "history_policy": recipe.history_policy,
            "optimizer": recipe.optimizer,
            "optimizer_parameters": recipe.parameters_dict(),
            "epochs": recipe.epochs,
            "training_samples": len(training_batch.ids),
            "source_sha256": training_batch.sha256,
        },
    )
