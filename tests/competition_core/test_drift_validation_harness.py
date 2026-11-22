from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "p5_drift_statistical_validation.json"


def test_validation_config_freezes_disjoint_seed_sets_and_primary_budget() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    all_seeds: list[int] = []
    for spec in payload["seed_sets"].values():
        seeds = list(range(spec["start"], spec["start"] + spec["count"]))
        assert not set(seeds).intersection(all_seeds)
        all_seeds.extend(seeds)
    assert payload["monitor"]["permutations"] == 2047
    assert payload["monitor"]["alpha_run"] == 0.05
    assert payload["monitor"]["alpha_window"] == 0.005
    assert payload["statistics"]["independent_unit"] == "generated_stream_seed"


def test_validation_harness_exposes_reproducible_generator_and_wilson_interval() -> None:
    from scripts.run_p5_drift_statistical_validation import (
        generate_window,
        wilson_interval,
    )

    left = generate_window(seed=10, dimension=24, correlation="mixed_sign")
    right = generate_window(seed=10, dimension=24, correlation="mixed_sign")

    assert left.shape == (80, 24)
    assert (left == right).all()
    low, high = wilson_interval(successes=0, trials=40, confidence=0.95)
    assert low == 0.0
    assert 0.08 < high < 0.09


def test_validation_harness_builds_all_required_final_scenarios() -> None:
    from scripts.run_p5_drift_statistical_validation import build_final_jobs, load_config

    jobs = build_final_jobs(load_config(CONFIG))
    names = {job["scenario"] for job in jobs}

    assert {
        "no_drift",
        "mean_shift",
        "variance_shift",
        "joint_shift",
        "progressive_shift",
        "noise_increase",
        "outlier_burst",
        "composition_change",
        "transient_shift",
        "reverse_recovery",
        "correlation_check",
        "invalid_exchangeability",
        "by_comparison",
    }.issubset(names)
    assert {job["dimension"] for job in jobs} == {24, 34, 128}
    assert all(job["split"] == "final" for job in jobs)


def test_validation_harness_aggregates_by_stream_not_window() -> None:
    from scripts.run_p5_drift_statistical_validation import aggregate_no_drift

    records = [
        {
            "stream_id": "a",
            "window_warnings": 1,
            "windows": 10,
            "confirmed": False,
            "alpha_excess": 0.0,
        },
        {
            "stream_id": "b",
            "window_warnings": 0,
            "windows": 10,
            "confirmed": True,
            "alpha_excess": 0.0,
        },
    ]

    result = aggregate_no_drift(records)

    assert result["stream_count"] == 2
    assert result["single_window_fpr"] == 0.05
    assert result["run_level_false_alarm"] == 0.5
    assert result["run_level_trials"] == 2


def test_baseline_contamination_counts_only_truth_drift_windows() -> None:
    from scripts.run_p5_drift_statistical_validation import baseline_contamination_count

    assert baseline_contamination_count(
        active_ids=("reference", "stream-window-0", "stream-window-1"),
        truth_drift_ids=("stream-window-2",),
    ) == 0
    assert baseline_contamination_count(
        active_ids=("reference", "stream-window-0", "stream-window-2"),
        truth_drift_ids=("stream-window-2",),
    ) == 1


def test_group_composition_uses_reference_and_current_probabilities() -> None:
    import numpy as np

    from scripts.run_p5_drift_statistical_validation import apply_group_composition

    values = np.zeros((8, 3), dtype=np.float64)
    scale = np.ones(3, dtype=np.float64)
    unchanged = apply_group_composition(
        values, seed=1, probability=0.0, truth=(0, 1), shift=2.0, scale=scale
    )
    shifted = apply_group_composition(
        values, seed=1, probability=1.0, truth=(0, 1), shift=2.0, scale=scale
    )

    assert np.array_equal(unchanged, values)
    assert np.all(shifted[:, :2] == 2.0)
    assert np.all(shifted[:, 2] == 0.0)
