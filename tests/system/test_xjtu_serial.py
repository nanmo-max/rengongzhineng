from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brace_msi.data.types import BatchData, TaskStream
from brace_msi.xjtu_serial import run_serial_experiments


def _stream() -> TaskStream:
    rng = np.random.default_rng(7)

    def batch(batch_id: str, start: int, count: int, group: str) -> BatchData:
        X = rng.normal(loc=float(start), scale=0.4, size=(count, 5))
        y = 40.0 - 3.0 * X[:, 0] + X[:, 1]
        return BatchData(
            batch_id=batch_id,
            X=X,
            y=y,
            sample_ids=tuple(f"{batch_id}:{i}" for i in range(count)),
            group_ids=tuple(group for _ in range(count)),
        )

    return TaskStream(
        task_id="xjtu-test",
        task_kind="regression",
        initial=batch("initial", 0, 72, "11"),
        development=(
            batch("dev-1", 1, 32, "14"),
            batch("dev-2", 2, 32, "24"),
            batch("dev-3", 3, 32, "34"),
        ),
        sealed=(),
        metadata={"local_development_only": True},
    )


def _config() -> dict:
    return {
        "experiment_id": "XJTU-TEST",
        "seed": 7,
        "local_development_only": True,
        "rounds": [
            {"id": "01-ridge", "kind": "static", "family": "linear"},
            {
                "id": "02-hist",
                "kind": "static",
                "family": "hist_gradient_boosting",
            },
            {"id": "03-extra", "kind": "static", "family": "extra_trees"},
            {"id": "04-trigger", "kind": "policy", "policy": "performance_triggered"},
            {"id": "05-brace", "kind": "policy", "policy": "brace"},
        ],
        "budget": {
            "max_candidates": 8,
            "max_training_samples": 2000,
            "max_wall_seconds": 60.0,
            "max_cpu_seconds": 60.0,
        },
        "gate": {
            "min_validation_samples": 4,
            "min_primary_improvement": 0.0,
            "max_anchor_degradation": 20.0,
        },
        "policies": {
            "performance_triggered": {"regression_drop_threshold": 0.0},
            "brace": {
                "regression": {
                    "update_drop_threshold": 0.0,
                    "refit_drop_threshold": 999.0,
                    "drift_threshold": 999.0,
                    "high_drift_threshold": 9999.0,
                }
            },
        },
    }


def test_serial_runner_checkpoints_each_round_and_resumes(tmp_path: Path) -> None:
    output = tmp_path / "run"
    first = run_serial_experiments(_stream(), _config(), output, max_rounds=3)

    assert first["status"] == "paused"
    assert first["completed_rounds"] == 3
    assert len(list((output / "rounds").glob("*.json"))) == 3
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    assert status["completed_rounds"] == 3
    assert status["health"]["finite_metrics"] is True

    complete = run_serial_experiments(_stream(), _config(), output)

    assert complete["status"] == "completed"
    assert complete["completed_rounds"] == 5
    assert len(list((output / "rounds").glob("*.json"))) == 5

