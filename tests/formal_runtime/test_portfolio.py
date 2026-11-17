from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _model():
    from brace_formal.model import FormalModel

    params = {
        "w1": np.asarray([[0.1, -0.1], [0.05, 0.2]], dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.asarray([[0.1, -0.1], [-0.1, 0.1]], dtype=np.float64),
        "b2": np.zeros(2, dtype=np.float64),
    }
    arrays = {
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        "mean": np.zeros(2), "scale": np.ones(2),
    }
    meta = {
        "format": "contest.cpu-mlp.v1", "device": "cpu", "profile": "test",
        "task": "classification",
        "paths": ['[["key","features"],["index",0]]', '[["key","features"],["index",1]]'],
        "classes": ["no", "yes"], "hidden": 2, "seed": 11, "epochs": 0, "steps": 0,
        "learning_rate": 0.01, "batch_size": 8,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 0.0, "target_scale": 1.0,
    }
    return FormalModel(arrays, meta)


def test_group_folds_never_split_one_trajectory() -> None:
    from brace_formal.portfolio import fold_assignments

    ids = tuple(f"bearing_{group}_s{index:06d}" for group in range(1, 5) for index in range(6))
    targets = np.arange(len(ids), dtype=np.float64)
    assignments = fold_assignments(ids, targets, "regression")

    assert set(assignments.tolist()) == {0, 1, 2}
    for group in range(1, 5):
        members = [assignments[index] for index, identity in enumerate(ids) if identity.startswith(f"bearing_{group}_")]
        assert len(set(members)) == 1


def test_recipes_preserve_parent_and_checkpoint_schema() -> None:
    from brace_formal.portfolio import fit_recipe

    parent = _model()
    original = {name: value.copy() for name, value in parent.params.items()}
    x = np.asarray([[float(i), float(i % 2)] for i in range(20)], dtype=np.float64)
    y = np.asarray([0] * 10 + [1] * 10, dtype=np.int64)

    for recipe in ("retain", "e1_lr1", "e3_lr3", "soup_e3_alpha0.25"):
        candidate = fit_recipe(parent, recipe, x, y)
        candidate.validate()
        assert candidate.meta["format"] == "contest.cpu-mlp.v1"
        assert candidate.meta["learning_rate"] == parent.meta["learning_rate"]
    for name in parent.params:
        np.testing.assert_array_equal(parent.params[name], original[name])


def test_cross_validation_records_all_recipes_without_public_validation() -> None:
    from brace_formal.portfolio import cross_validate

    parent = _model()
    rng = np.random.default_rng(7)
    x = rng.normal(size=(90, 2))
    y = (x[:, 0] + x[:, 1] > 0).astype(np.int64)
    ids = tuple(f"row-{index}" for index in range(len(x)))

    result = cross_validate(parent, ids, x, y)

    assert result["selected_recipe"] in {"retain", "e1_lr1", "e3_lr3", "soup_e3_alpha0.25"}
    assert set(result["recipes"]) == {"retain", "e1_lr1", "e3_lr3", "soup_e3_alpha0.25"}
    assert all(len(record["folds"]) == 3 for record in result["recipes"].values())
    assert all(np.isfinite(record["mean_signed_gain"]) for record in result["recipes"].values())
