from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brace_msi.data.types import BatchData, TaskStream
from brace_msi.official_suite import run_official_development_suite, validate_official_development_suite


def _task(task_id: str, kind: str, features: int, parameter_count: int, metric: str) -> TaskStream:
    rng = np.random.default_rng(features)
    if kind == "classification":
        initial_y = np.tile(np.arange(1, 7), 10)
    else:
        initial_y = rng.normal(size=60)
    initial = BatchData(
        "initial",
        rng.normal(size=(60, features)),
        initial_y,
        tuple(f"{task_id}:initial:{i}" for i in range(60)),
    )
    development = []
    for index in range(10):
        y = np.tile(np.arange(1, 7), 3) if kind == "classification" else rng.normal(size=18)
        development.append(
            BatchData(
                f"opt-{index + 1:02d}",
                rng.normal(size=(18, features)),
                y,
                tuple(f"{task_id}:opt:{index}:{i}" for i in range(18)),
            )
        )
    return TaskStream(
        task_id,
        kind,
        initial,
        tuple(development),
        (),
        {
            "official_rules_aligned": True,
            "official_checkpoint": False,
            "primary_metric": metric,
            "published_parameter_count": parameter_count,
        },
    )


def _config() -> dict:
    task_config = {
        "budget": {
            "max_candidates": 20,
            "max_training_samples": 10000,
            "max_wall_seconds": 60.0,
            "max_cpu_seconds": 60.0,
        },
        "gate": {
            "min_validation_samples": 2,
            "min_primary_improvement": -1000000.0,
            "max_anchor_degradation": 1000000.0,
        },
        "minimum_candidate_events": 3,
        "replay_max_samples": 1000,
        "performance_drop_threshold": 0.0,
        "update_drop_threshold": 0.0,
        "refit_drop_threshold": 1000000.0,
        "drift_threshold": 1000000.0,
        "high_drift_threshold": 2000000.0,
        "mlp_max_iter": 2,
    }
    return {
        "experiment_id": "SUITE-TEST",
        "official_rules_aligned": True,
        "official_checkpoint": False,
        "seed": 20261111,
        "tasks": {name: task_config for name in ("gas", "bearing", "engine")},
    }


def test_suite_pauses_after_first_three_and_resumes_without_repeating(tmp_path: Path) -> None:
    streams = {
        "gas": _task("gas", "classification", 128, 4326, "macro_f1"),
        "bearing": _task("bearing", "regression", 25, 865, "rmse"),
        "engine": _task("engine", "regression", 24, 833, "rmse_nasa"),
    }
    root = tmp_path / "suite"

    paused = run_official_development_suite(streams, _config(), root, max_experiments=3)

    assert paused["status"] == "paused"
    assert paused["completed_experiments"] == 3
    assert (root / "first-three-health.json").exists()
    first_hashes = {
        path.parent.name: path.read_bytes()
        for path in (root / "experiments").glob("*/result.json")
    }

    completed = run_official_development_suite(streams, _config(), root)

    assert completed["status"] == "completed"
    assert completed["completed_experiments"] == 9
    assert first_hashes == {
        path.parent.name: path.read_bytes()
        for path in (root / "experiments").glob("*/result.json")
        if path.parent.name in {"01-gas-static", "02-bearing-static", "03-engine-static"}
    }
    validation = validate_official_development_suite(root, expected_experiments=9)
    assert validation["valid"] is True
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["official_score_computed"] is False
    assert set(summary["tasks"]) == {"gas", "bearing", "engine"}

