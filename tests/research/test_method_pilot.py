from __future__ import annotations

import numpy as np

from brace_msi.method_pilot import (
    discover_transition_paths,
    fit_native_recipe,
    run_native_candidates,
    run_transition,
    summarize_transitions,
)
from brace_msi.platform_runtime import _NativeModel


def _parent(task: str) -> _NativeModel:
    input_width, hidden = 4, 3
    output_width = 2 if task == "classification" else 1
    shapes = {
        "w1": (input_width, hidden),
        "b1": (hidden,),
        "w2": (hidden, output_width),
        "b2": (output_width,),
    }
    arrays = {
        **{name: np.zeros(shape, dtype=np.float64) for name, shape in shapes.items()},
        **{
            f"adam_first_{name}": np.zeros(shape, dtype=np.float64)
            for name, shape in shapes.items()
        },
        **{
            f"adam_second_{name}": np.zeros(shape, dtype=np.float64)
            for name, shape in shapes.items()
        },
        "mean": np.zeros(input_width, dtype=np.float64),
        "scale": np.ones(input_width, dtype=np.float64),
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "task": task,
        "profile": "TEST",
        "paths": [f"f{index}" for index in range(input_width)],
        "classes": ["negative", "positive"] if task == "classification" else [],
        "hidden": hidden,
        "epochs": 0,
        "steps": 0,
        "seed": 7,
        "batch_size": 16,
        "parameter_count": int(sum(np.prod(shape) for shape in shapes.values())),
        "learning_rate": 0.01,
        "target_mean": 0.0,
        "target_scale": 1.0,
    }
    return _NativeModel(arrays, metadata)


def test_method_portfolio_produces_finite_classification_transfer_scores() -> None:
    rng = np.random.default_rng(11)
    history_x = rng.normal(size=(80, 4))
    history_y = (history_x[:, 0] + history_x[:, 1] > 0).astype(np.int64)
    current_x = rng.normal(loc=0.3, size=(50, 4))
    current_y = (current_x[:, 0] + current_x[:, 1] > 0).astype(np.int64)
    next_x = rng.normal(loc=0.6, size=(60, 4))
    next_y = (next_x[:, 0] + next_x[:, 1] > 0).astype(np.int64)
    parent = _parent("classification")
    original = {name: value.copy() for name, value in parent.params.items()}

    rows = run_transition(
        parent,
        history_x=history_x,
        history_y=history_y,
        current_x=current_x,
        current_y=current_y,
        next_x=next_x,
        next_y=next_y,
        seed=20261116,
        low_budget=True,
    )

    methods = {row["method"] for row in rows if row["available"]}
    assert {
        "static_parent",
        "native_current",
        "native_cumulative",
        "linear_cumulative",
        "hgb_cumulative",
        "extra_trees_cumulative",
        "tree_ensemble",
    } <= methods
    assert all(np.isfinite(row["signed_gain"]) for row in rows if row["available"])
    assert all(
        np.array_equal(parent.params[name], original[name]) for name in original
    )


def test_method_portfolio_supports_regression_and_summarizes_direction() -> None:
    rng = np.random.default_rng(19)
    history_x = rng.normal(size=(90, 4))
    history_y = 4.0 + 2.0 * history_x[:, 0] - history_x[:, 1]
    current_x = rng.normal(loc=0.2, size=(55, 4))
    current_y = 4.0 + 2.0 * current_x[:, 0] - current_x[:, 1]
    next_x = rng.normal(loc=0.4, size=(65, 4))
    next_y = 4.0 + 2.0 * next_x[:, 0] - next_x[:, 1]

    rows = run_transition(
        _parent("regression"),
        history_x=history_x,
        history_y=history_y,
        current_x=current_x,
        current_y=current_y,
        next_x=next_x,
        next_y=next_y,
        seed=20261116,
        low_budget=True,
    )
    summary = summarize_transitions(rows)

    assert summary["static_parent"]["mean_signed_gain"] == 0.0
    assert summary["linear_cumulative"]["win_rate"] > 0.0
    assert summary["linear_cumulative"]["mean_signed_gain"] > 0.0
    assert all(row["metrics"]["rmse"] >= 0.0 for row in rows if row["available"])


def test_transition_discovery_uses_only_ordered_feedback_rounds(tmp_path) -> None:
    inputs = tmp_path / "runtime-inputs"
    for index in range(1, 11):
        round_dir = inputs / f"round-{index:02d}"
        round_dir.mkdir(parents=True)
        (round_dir / "feedback.jsonl").write_text(
            '{"id":"sample","inputs":{"f0":0},"answer":0}\n',
            encoding="utf-8",
        )
    confirmation = inputs / "confirmation"
    confirmation.mkdir()
    (confirmation / "feedback.jsonl").write_text("forbidden\n", encoding="utf-8")

    transitions = discover_transition_paths(tmp_path)

    assert len(transitions) == 9
    assert transitions[0][0].parent.name == "round-01"
    assert transitions[-1][1].parent.name == "round-10"
    assert all("confirmation" not in str(path) for pair in transitions for path in pair)


def test_native_candidate_matrix_preserves_parent_and_emits_official_models() -> None:
    rng = np.random.default_rng(23)
    history_x = rng.normal(size=(100, 4))
    history_y = (history_x[:, 0] - 0.5 * history_x[:, 1] > 0).astype(np.int64)
    current_x = rng.normal(loc=0.2, size=(45, 4))
    current_y = (current_x[:, 0] - 0.5 * current_x[:, 1] > 0).astype(np.int64)
    next_x = rng.normal(loc=0.4, size=(50, 4))
    next_y = (next_x[:, 0] - 0.5 * next_x[:, 1] > 0).astype(np.int64)
    parent = _parent("classification")
    original = {name: value.copy() for name, value in parent.params.items()}

    rows = run_native_candidates(
        parent,
        history_x=history_x,
        history_y=history_y,
        current_x=current_x,
        current_y=current_y,
        next_x=next_x,
        next_y=next_y,
    )

    methods = {row["method"] for row in rows}
    assert "native_current_e3_lr0.3" in methods
    assert "native_cumulative_e3_reset" in methods
    assert "soup_cumulative_e3_alpha0.5" in methods
    assert all(row["checkpoint_format"] == "contest.cpu-mlp.v1" for row in rows)
    assert all(np.isfinite(row["signed_gain"]) for row in rows)
    assert all(
        np.array_equal(parent.params[name], original[name]) for name in original
    )


def test_native_recipe_returns_loadable_schema_without_mutating_parent(tmp_path) -> None:
    rng = np.random.default_rng(29)
    history_x = rng.normal(size=(70, 4))
    history_y = 3.0 + history_x[:, 0]
    current_x = rng.normal(loc=0.3, size=(40, 4))
    current_y = 3.0 + current_x[:, 0]
    parent = _parent("regression")
    original = {name: value.copy() for name, value in parent.params.items()}

    candidate = fit_native_recipe(
        parent,
        recipe="soup_current_e3_alpha0.25",
        history_x=history_x,
        history_y=history_y,
        current_x=current_x,
        current_y=current_y,
    )
    checkpoint = tmp_path / "checkpoint.npz"
    candidate.save(checkpoint)
    loaded = _NativeModel.load(checkpoint)

    assert loaded.meta["format"] == "contest.cpu-mlp.v1"
    assert all(
        np.array_equal(parent.params[name], original[name]) for name in original
    )


def test_learning_rate_multiplier_does_not_compound_across_parent_chain() -> None:
    rng = np.random.default_rng(31)
    current_x = rng.normal(size=(35, 4))
    current_y = (current_x[:, 0] > 0).astype(np.int64)
    parent = _parent("classification")
    original_rate = parent.meta["learning_rate"]

    for _ in range(10):
        parent = fit_native_recipe(
            parent,
            recipe="current_e3_lr3",
            history_x=np.empty((0, 4)),
            history_y=np.empty((0,), dtype=np.int64),
            current_x=current_x,
            current_y=current_y,
        )

    assert parent.meta["learning_rate"] == original_rate
