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


def test_reference_status_replay_recovers_after_confirmed_reverse_shift() -> None:
    from scripts.run_p5_drift_statistical_validation import (
        load_config,
        replay_reference_statuses,
    )

    trajectory = replay_reference_statuses(
        ["stable", "warning", "warning", "warning", "stable", "stable"],
        load_config(),
    )

    assert "confirmed" in trajectory
    assert trajectory[-2:] == ["recovery", "stable"]


def test_aggregate_records_reports_confidence_intervals_for_required_metrics() -> None:
    from scripts.run_p5_drift_statistical_validation import aggregate_records, load_config

    records = []
    for seed, detected, delay, recall in (
        (1, True, 1, 1.0),
        (2, True, 2, 0.5),
        (3, False, None, None),
    ):
        records.append(
            {
                "scenario": "mean_shift",
                "dimension": 24,
                "effect": "medium",
                "correlation": "block_positive",
                "method": "block_permutation_maxT",
                "variant": "primary",
                "stream_id": str(seed),
                "confirmed": detected,
                "detection_delay": delay,
                "recall_at_k": recall,
                "baseline_contamination_count": 0,
                "alpha_excess": 0.0,
                "cpu_seconds": 1.0,
                "wall_seconds": 1.0,
                "statuses": ["warning"],
            }
        )

    result = aggregate_records(records, load_config())[0]

    assert len(result["event_recall_wilson_95"]) == 2
    assert len(result["miss_rate_wilson_95"]) == 2
    assert len(result["median_detection_delay_bootstrap_95"]) == 2
    assert len(result["mean_recall_at_k_bootstrap_95"]) == 2


def test_aggregate_with_no_detections_is_strict_json_serializable() -> None:
    from scripts.run_p5_drift_statistical_validation import aggregate_records, load_config

    result = aggregate_records(
        [
            {
                "scenario": "variance_shift",
                "dimension": 128,
                "effect": "medium",
                "correlation": "block_positive",
                "method": "block_permutation_maxT",
                "variant": "primary",
                "confirmed": False,
                "detection_delay": None,
                "recall_at_k": None,
                "baseline_contamination_count": 0,
                "alpha_excess": 0.0,
                "cpu_seconds": 1.0,
                "wall_seconds": 1.0,
                "statuses": ["stable"],
            }
        ],
        load_config(),
    )

    json.dumps(result, allow_nan=False)
    assert result[0]["median_detection_delay_bootstrap_95"] == [None, None]


def test_acceptance_evaluator_keeps_one_second_target_non_gating() -> None:
    from scripts.run_p5_drift_statistical_validation import evaluate_acceptance, load_config

    config = load_config()
    aggregate = {
        "scenario": "variance_shift",
        "dimension": 24,
        "effect": "medium",
        "correlation": "block_positive",
        "method": "block_permutation_maxT",
        "variant": "primary",
        "event_recall": 0.5,
        "event_recall_wilson_95": [0.1, 0.9],
        "median_detection_delay": 3.0,
        "median_detection_delay_bootstrap_95": [2.0, 4.0],
        "mean_recall_at_k": 1.0,
        "mean_recall_at_k_bootstrap_95": [1.0, 1.0],
        "baseline_contamination_rate": 0.0,
        "alpha_excess_rate": 0.0,
    }
    resources = [
        {
            "logical_cpu_limit": 4,
            "per_window_cpu_seconds": 5.0,
            "per_window_wall_seconds": 5.0,
            "rss_delta_bytes": 10_000_000,
        }
    ]

    result = evaluate_acceptance([aggregate], resources, config, require_coverage=False)

    assert result["overall_pass"] is False
    assert any("event_recall" in item["check_id"] and not item["passed"] for item in result["checks"])
    aspirational = next(item for item in result["checks"] if "aspirational" in item["check_id"])
    assert aspirational["gating"] is False
    assert aspirational["passed"] is False


def test_acceptance_requires_by_behavior_under_invalid_exchangeability() -> None:
    from scripts.run_p5_drift_statistical_validation import evaluate_acceptance, load_config

    result = evaluate_acceptance([], [], load_config(), require_coverage=True)
    check = next(
        item
        for item in result["checks"]
        if item["check_id"] == "coverage.by_invalid_exchangeability"
    )

    assert check["passed"] is False
    assert check["gating"] is True
