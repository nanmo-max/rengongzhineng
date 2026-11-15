from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).parents[2] / "scripts" / "run_unseen_simulation.py"
SPEC = importlib.util.spec_from_file_location("run_unseen_simulation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_series_and_matrix_statistics_are_consistent() -> None:
    values = np.asarray([1.0, 2.0, 4.0, 8.0])
    series = np.asarray(MODULE._series_stats(values))
    matrix = MODULE._matrix_stats(values[None, :])[0]
    np.testing.assert_allclose(series, matrix)
    assert len(series) == len(MODULE.SENSOR_STATS)


def test_empty_or_nonfinite_target_is_rejected_without_coercion() -> None:
    assert MODULE._finite_scalar(np.asarray([], dtype=np.float64)) is None
    assert MODULE._finite_scalar(np.asarray([1.0, 2.0])) is None
    assert MODULE._finite_scalar(np.asarray([np.nan])) is None
    assert MODULE._finite_scalar(np.asarray([1.25])) == 1.25


def test_partition_rows_never_overlap_groups() -> None:
    rows = []
    for case in range(1, 17):
        for run in range(10):
            rows.append(
                {
                    "id": f"{case}-{run}",
                    "group": f"case-{case:02d}",
                    "order": run,
                    "features": [float(run)],
                    "answer": float(run),
                }
            )
    partitions = MODULE._partition_rows("mill", rows)
    groups = [{row["group"] for row in partition} for partition in partitions.values()]
    assert not groups[0] & groups[1]
    assert not groups[0] & groups[2]
    assert not groups[1] & groups[2]
    assert len(partitions["adaptation"]) >= 50


def test_simulated_parent_is_loadable_and_marked(tmp_path: Path) -> None:
    rows = [
        {
            "id": f"sample-{index}",
            "group": "bootstrap",
            "order": index,
            "features": [float(index), float(index % 3)],
            "answer": float(index) / 10.0,
        }
        for index in range(40)
    ]
    checkpoint = tmp_path / "checkpoint.npz"
    result = MODULE._build_parent(
        checkpoint,
        rows,
        ["sensor.mean", "sensor.std"],
        task_kind="regression",
        profile="UNSEEN-REGRESSION",
    )
    model = MODULE._NativeModel.load(checkpoint)
    assert model.meta["simulated_parent"] is True
    assert model.meta["epochs"] == 30
    assert result["checkpoint_bytes"] < 64 * 1024 * 1024
