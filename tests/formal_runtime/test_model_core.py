from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _write_checkpoint(path: Path, *, task: str) -> None:
    feature_paths = [
        '[["key","features"],["index",0]]',
        '[["key","features"],["index",1]]',
    ]
    classes = ["cold", "hot"] if task == "classification" else []
    outputs = len(classes) if classes else 1
    params = {
        "w1": np.asarray([[0.5, -0.2], [0.1, 0.3]], dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.full((2, outputs), 0.2, dtype=np.float64),
        "b2": np.arange(outputs, dtype=np.float64) * 0.01,
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": "test-profile",
        "task": task,
        "paths": feature_paths,
        "classes": classes,
        "hidden": 2,
        "seed": 42,
        "epochs": 1,
        "steps": 1,
        "learning_rate": 0.01,
        "batch_size": 4,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 5.0 if task == "regression" else 0.0,
        "target_scale": 5.0 if task == "regression" else 1.0,
    }
    np.savez(
        path,
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        mean=np.zeros(2, dtype=np.float64),
        scale=np.ones(2, dtype=np.float64),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


def test_formal_model_matches_verified_native_one_epoch(tmp_path: Path) -> None:
    """Catches optimizer, shuffle, target-scaling or state drift from the verified trainer."""

    from brace_formal.model import FormalModel
    from brace_msi.platform_runtime import _NativeModel

    checkpoint = tmp_path / "checkpoint.npz"
    _write_checkpoint(checkpoint, task="classification")
    formal = FormalModel.load(checkpoint)
    native = _NativeModel.load(checkpoint)
    x = np.asarray([[i / 10.0, float(i % 2)] for i in range(12)], dtype=np.float64)
    y = np.asarray([0] * 6 + [1] * 6, dtype=np.int64)

    formal_losses = formal.fit(x, y, 1)
    native_losses = native.fit(x, y, 1)

    np.testing.assert_array_equal(formal_losses, native_losses)
    assert formal.meta == native.meta
    for name in ("w1", "b1", "w2", "b2"):
        np.testing.assert_array_equal(formal.params[name], native.params[name])
        np.testing.assert_array_equal(formal.first[name], native.first[name])
        np.testing.assert_array_equal(formal.second[name], native.second[name])
    np.testing.assert_array_equal(formal.predict_raw(x), native.predict_raw(x))


def test_formal_model_save_reload_preserves_regression_predictions(tmp_path: Path) -> None:
    """Catches non-deterministic or incomplete checkpoint serialization."""

    from brace_formal.model import FormalModel

    source = tmp_path / "parent.npz"
    saved = tmp_path / "candidate.npz"
    _write_checkpoint(source, task="regression")
    model = FormalModel.load(source)
    x = np.asarray([[i / 5.0, float(i % 3)] for i in range(15)], dtype=np.float64)
    y = np.asarray([float(i) for i in range(15)], dtype=np.float64)
    model.fit(x, y, 2)
    expected = model.predict_raw(x)

    model.save(saved)
    restored = FormalModel.load(saved)

    np.testing.assert_array_equal(restored.predict_raw(x), expected)
    assert saved.stat().st_size < 64 * 1024 * 1024


def test_data_loader_and_metrics_follow_parent_contract(tmp_path: Path) -> None:
    """Catches schema drift, target leakage or wrong official metric direction."""

    from brace_formal.data import load_rows
    from brace_formal.metrics import evaluate
    from brace_formal.model import FormalModel

    checkpoint = tmp_path / "checkpoint.npz"
    dataset = tmp_path / "train.jsonl"
    _write_checkpoint(checkpoint, task="classification")
    rows = [
        {
            "id": f"sample-{index}",
            "inputs": {"features": [float(index), float(index % 2)]},
            "answer": "hot" if index >= 3 else "cold",
        }
        for index in range(6)
    ]
    dataset.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    model = FormalModel.load(checkpoint)

    batch = load_rows(dataset, model, require_answers=True)
    metrics = evaluate(model, batch.x, batch.y)

    assert batch.ids == tuple(f"sample-{index}" for index in range(6))
    assert batch.x.shape == (6, 2)
    assert batch.y.tolist() == [0, 0, 0, 1, 1, 1]
    assert set(metrics) == {"accuracy", "macro_f1"}
    assert all(0.0 <= value <= 1.0 for value in metrics.values())


def test_extended_fit_without_options_is_exactly_native(tmp_path: Path) -> None:
    from brace_formal.model import FormalModel

    checkpoint = tmp_path / "classification.npz"
    _write_checkpoint(checkpoint, task="classification")
    parent = FormalModel.load(checkpoint)
    values = np.asarray([[float(index), float(index % 2)] for index in range(12)], dtype=np.float64)
    targets = np.asarray([0] * 6 + [1] * 6, dtype=np.int64)
    implicit = parent.clone()
    explicit = parent.clone()

    implicit_losses = implicit.fit(values, targets, 2)
    explicit_losses = explicit.fit(
        values,
        targets,
        2,
        sample_weights=None,
        loss="native",
        loss_parameters=None,
    )

    assert implicit_losses == explicit_losses
    assert implicit.meta == explicit.meta
    for group_name in ("params", "first", "second"):
        implicit_group = getattr(implicit, group_name)
        explicit_group = getattr(explicit, group_name)
        for name in implicit_group:
            np.testing.assert_array_equal(implicit_group[name], explicit_group[name])


def test_weighted_classification_and_regression_losses_change_training_deterministically(tmp_path: Path) -> None:
    from brace_formal.model import FormalModel

    class_checkpoint = tmp_path / "classification.npz"
    _write_checkpoint(class_checkpoint, task="classification")
    classification = FormalModel.load(class_checkpoint)
    class_values = np.asarray([[float(index), float(index % 2)] for index in range(10)], dtype=np.float64)
    class_targets = np.asarray([0] * 9 + [1], dtype=np.int64)
    weighted = classification.clone()
    weighted_again = classification.clone()
    weights = np.asarray([1.0] * 9 + [9.0], dtype=np.float64)
    weighted.fit(class_values, class_targets, 1, sample_weights=weights, loss="cross_entropy")
    weighted_again.fit(class_values, class_targets, 1, sample_weights=weights, loss="cross_entropy")
    for name in weighted.params:
        np.testing.assert_array_equal(weighted.params[name], weighted_again.params[name])

    regression_checkpoint = tmp_path / "regression.npz"
    _write_checkpoint(regression_checkpoint, task="regression")
    regression = FormalModel.load(regression_checkpoint)
    regression_values = np.asarray([[float(index), float(index % 2)] for index in range(8)], dtype=np.float64)
    regression_targets = np.asarray([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 100.0])
    mse = regression.clone()
    huber = regression.clone()
    asymmetric = regression.clone()
    mse.fit(regression_values, regression_targets, 1, loss="mse")
    huber.fit(regression_values, regression_targets, 1, loss="huber", loss_parameters={"delta": 1.0})
    asymmetric.fit(
        regression_values,
        regression_targets,
        1,
        loss="asymmetric",
        loss_parameters={"underprediction_weight": 2.0, "overprediction_weight": 1.0},
    )
    assert any(not np.array_equal(mse.params[name], huber.params[name]) for name in mse.params)
    assert any(not np.array_equal(mse.params[name], asymmetric.params[name]) for name in mse.params)
