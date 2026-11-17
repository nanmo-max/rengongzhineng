"""Small parent-compatible recipe portfolio selected only with train-internal folds."""

from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Any

import numpy as np

from .metrics import evaluate
from .model import FormalModel


RECIPES = ("retain", "e1_lr1", "e3_lr3", "soup_e3_alpha0.25")
_GROUP_SUFFIX = re.compile(r"^(.*)_(?:s|c)\d+$", re.IGNORECASE)


def _rank(value: str) -> bytes:
    return hashlib.sha256(("20261117\0" + value).encode("utf-8")).digest()


def fold_assignments(ids: tuple[str, ...], targets: np.ndarray, task: str) -> np.ndarray:
    if task not in {"classification", "regression"} or targets.shape != (len(ids),) or len(ids) < 6:
        raise ValueError("three-fold selection requires at least six aligned samples")
    groups: dict[str, list[int]] = {}
    for index, identity in enumerate(ids):
        match = _GROUP_SUFFIX.match(identity)
        if match:
            groups.setdefault(match.group(1), []).append(index)
    if 3 <= len(groups) <= 1000 and sum(len(value) for value in groups.values()) == len(ids):
        assignments = np.empty(len(ids), dtype=np.int64)
        for fold, group in enumerate(sorted(groups, key=_rank)):
            assignments[groups[group]] = fold % 3
        return assignments

    assignments = np.empty(len(ids), dtype=np.int64)
    strata: dict[str, list[int]] = {}
    if task == "classification":
        for index, target in enumerate(targets.tolist()):
            strata.setdefault(str(int(target)), []).append(index)
    else:
        strata["all"] = list(range(len(ids)))
    for indices in strata.values():
        for fold, index in enumerate(sorted(indices, key=lambda item: _rank(ids[item]))):
            assignments[index] = fold % 3
    if set(assignments.tolist()) != {0, 1, 2}:
        raise ValueError("could not construct three nonempty folds")
    return assignments


def fit_recipe(parent: FormalModel, recipe: str, values: np.ndarray, targets: np.ndarray) -> FormalModel:
    if recipe not in RECIPES:
        raise ValueError("unsupported formal recipe")
    candidate = parent.clone()
    if recipe == "retain":
        return candidate
    parent_rate = float(parent.meta["learning_rate"])
    epochs, multiplier = (1, 1.0) if recipe == "e1_lr1" else (3, 3.0 if recipe == "e3_lr3" else 1.0)
    candidate.meta["learning_rate"] = parent_rate * multiplier
    candidate.fit(values, targets, epochs)
    candidate.meta["learning_rate"] = parent_rate
    if recipe == "soup_e3_alpha0.25":
        for name in candidate.params:
            candidate.params[name] = 0.75 * parent.params[name] + 0.25 * candidate.params[name]
    candidate.validate()
    return candidate


def _metric_contract(model: FormalModel) -> tuple[str, str]:
    return ("macro_f1", "higher") if model.meta["task"] == "classification" else ("rmse", "lower")


def _gain(before: float, after: float, direction: str) -> float:
    return after - before if direction == "higher" else before - after


def cross_validate(parent: FormalModel, ids: tuple[str, ...], values: np.ndarray, targets: np.ndarray) -> dict[str, Any]:
    assignments = fold_assignments(ids, targets, str(parent.meta["task"]))
    metric, direction = _metric_contract(parent)
    records: dict[str, dict[str, Any]] = {recipe: {"folds": []} for recipe in RECIPES}
    for fold in range(3):
        train_mask = assignments != fold
        holdout_mask = assignments == fold
        baseline = evaluate(parent, values[holdout_mask], targets[holdout_mask])
        for recipe in RECIPES:
            started = time.process_time()
            candidate = fit_recipe(parent, recipe, values[train_mask], targets[train_mask])
            metrics = evaluate(candidate, values[holdout_mask], targets[holdout_mask])
            cpu_seconds = time.process_time() - started
            signed_gain = _gain(float(baseline[metric]), float(metrics[metric]), direction)
            relative_gain = signed_gain / max(abs(float(baseline[metric])), 1e-12)
            records[recipe]["folds"].append(
                {
                    "fold": fold,
                    "train_samples": int(train_mask.sum()),
                    "holdout_samples": int(holdout_mask.sum()),
                    "baseline_metrics": baseline,
                    "candidate_metrics": metrics,
                    "signed_gain": signed_gain,
                    "relative_gain": relative_gain,
                    "cpu_seconds": cpu_seconds,
                }
            )
    for recipe, record in records.items():
        gains = [float(item["signed_gain"]) for item in record["folds"]]
        relatives = [float(item["relative_gain"]) for item in record["folds"]]
        record["mean_signed_gain"] = float(np.mean(gains))
        record["positive_folds"] = int(sum(value >= 0.0 for value in gains))
        record["worst_relative_gain"] = min(relatives)
        record["cpu_seconds"] = sum(float(item["cpu_seconds"]) for item in record["folds"])
        record["eligible"] = recipe == "retain" or (
            record["mean_signed_gain"] > 0.0
            and record["positive_folds"] >= 2
            and record["worst_relative_gain"] >= -0.05
        )
        if not all(math.isfinite(float(record[key])) for key in ("mean_signed_gain", "worst_relative_gain", "cpu_seconds")):
            raise ValueError("portfolio produced nonfinite evidence")
    eligible = [recipe for recipe in RECIPES if records[recipe]["eligible"]]
    selected = max(eligible, key=lambda recipe: (records[recipe]["mean_signed_gain"], -records[recipe]["cpu_seconds"]))
    return {
        "metric": metric,
        "direction": direction,
        "fold_strategy": "group_suffix" if any(_GROUP_SUFFIX.match(identity) for identity in ids) else "stratified_or_hash",
        "selected_recipe": selected,
        "recipes": records,
    }
