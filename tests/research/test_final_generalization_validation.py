from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brace_msi.final_validation import (
    FinalValidationError,
    assert_sealed_not_cached,
    build_progress_rounds,
    claim_one_time_holdout,
    load_cache_batch,
    promotion_decision,
    run_one_time_validation,
)


def test_progress_rounds_preserve_each_bearing_order_and_keep_gate_out_of_update() -> None:
    batches = []
    for bearing_index in range(3):
        x = np.column_stack(
            [np.arange(100, dtype=np.float64), np.full(100, bearing_index)]
        )
        y = np.arange(99, -1, -1, dtype=np.float64)
        ids = tuple(f"b{bearing_index}:{index}" for index in range(100))
        batches.append((x, y, ids))

    rounds = build_progress_rounds(tuple(batches), round_count=10, update_fraction=0.8)

    assert len(rounds) == 10
    all_ids: list[str] = []
    for round_index, round_data in enumerate(rounds):
        assert set(round_data.update_ids).isdisjoint(round_data.gate_ids)
        assert len(round_data.update_ids) == 24
        assert len(round_data.gate_ids) == 6
        expected = {
            f"b{bearing}:{offset}"
            for bearing in range(3)
            for offset in range(round_index * 10, (round_index + 1) * 10)
        }
        assert set(round_data.update_ids + round_data.gate_ids) == expected
        all_ids.extend(round_data.update_ids + round_data.gate_ids)
    assert len(all_ids) == len(set(all_ids)) == 300


def test_one_time_holdout_claim_fails_closed_after_first_claim(tmp_path: Path) -> None:
    claim = tmp_path / "sealed-opened.json"

    claim_one_time_holdout(claim, experiment_id="FINAL-GENERALIZATION-VALIDATION-001-A1")

    assert claim.is_file()
    with pytest.raises(FinalValidationError, match="already claimed"):
        claim_one_time_holdout(
            claim, experiment_id="FINAL-GENERALIZATION-VALIDATION-001-A1"
        )


def test_promotion_requires_average_worst_and_each_resource_gate() -> None:
    passing = {
        "development_mean_gain": 1.0,
        "development_worst_relative_gain": -0.01,
        "sealed_global_rmse_gain": 2.0,
        "sealed_global_mae_gain": 1.0,
        "sealed_worst_bearing_relative_gain": -0.01,
        "sealed_improved_bearings": 2,
        "cpu_seconds": 10.0,
        "wall_seconds": 11.0,
        "peak_rss_bytes": 1000,
        "checkpoint_bytes": 1000,
        "leakage_free": True,
        "checkpoint_verified": True,
    }
    gate = {
        "development_mean_gain_min": 0.0,
        "development_worst_relative_gain_min": -0.05,
        "sealed_global_rmse_gain_min": 0.0,
        "sealed_global_mae_gain_min": 0.0,
        "sealed_worst_bearing_relative_gain_min": -0.05,
        "sealed_minimum_improved_bearings": 2,
        "max_cpu_seconds": 600.0,
        "max_wall_seconds": 900.0,
        "max_rss_bytes": 8589934592,
        "max_checkpoint_bytes": 67108864,
    }

    assert promotion_decision(passing, gate)["passed"] is True
    failing = dict(passing, sealed_improved_bearings=1)
    result = promotion_decision(failing, gate)
    assert result["passed"] is False
    assert result["failed_gates"] == ["sealed_minimum_improved_bearings"]


def test_one_time_validation_opens_sealed_only_after_ten_development_rounds(
    tmp_path: Path,
) -> None:
    def batch(name: str, offset: float, count: int = 40):
        elapsed = np.arange(count, dtype=np.float64)
        x = np.column_stack((elapsed, np.sin(elapsed / 5.0) + offset))
        y = np.maximum(0.0, count - 1 - elapsed + offset)
        ids = tuple(f"{name}:{index}" for index in range(count))
        return x, y, ids

    initial = tuple(batch(f"initial-{index}", float(index)) for index in range(3))
    development = tuple(batch(f"development-{index}", float(index) + 0.5) for index in range(3))
    events: list[str] = []

    def open_sealed():
        events.append("sealed-opened")
        assert (tmp_path / "result" / "development-complete.json").is_file()
        return tuple(batch(f"sealed-{index}", float(index) + 0.25) for index in range(3))

    config = {
        "experiment_id": "FINAL-GENERALIZATION-VALIDATION-TEST",
        "seed": 7,
        "parent": {"hidden": 4, "epochs": 2, "learning_rate": 0.003, "batch_size": 16},
        "adaptation": {
            "rounds": 10,
            "update_fraction": 0.8,
            "strategy": "bounded_exploration",
            "exploration_budget": 2,
            "relative_regression_tolerance": 0.01,
            "method_portfolio": False,
            "classification_balance_only": False,
        },
        "promotion_gate": {
            "development_mean_gain_min": -1e9,
            "development_worst_relative_gain_min": -1e9,
            "sealed_global_rmse_gain_min": -1e9,
            "sealed_global_mae_gain_min": -1e9,
            "sealed_worst_bearing_relative_gain_min": -1e9,
            "sealed_minimum_improved_bearings": 0,
            "max_cpu_seconds": 600.0,
            "max_wall_seconds": 900.0,
            "max_rss_bytes": 8589934592,
            "max_checkpoint_bytes": 67108864,
        },
    }

    summary = run_one_time_validation(
        initial_batches=initial,
        development_batches=development,
        open_sealed=open_sealed,
        output_root=tmp_path / "result",
        config=config,
    )

    assert events == ["sealed-opened"]
    assert summary["development"]["round_count"] == 10
    assert summary["development"]["candidate_count"] >= 10
    assert summary["sealed"]["bearing_count"] == 3
    assert summary["data_integrity"]["sample_id_overlap_count"] == 0
    assert summary["checkpoint_verified"] is True
    assert (tmp_path / "result" / "summary.json").is_file()


def test_cache_loader_and_virgin_guard_fail_closed(tmp_path: Path) -> None:
    cache = tmp_path / "Bearing1_1.npz"
    np.savez_compressed(
        cache,
        X=np.asarray([[1.0, 2.0], [3.0, 4.0]]),
        y=np.asarray([1.0, 0.0]),
        sample_ids=np.asarray(["one", "two"]),
        bearing_id=np.asarray("Bearing1_1"),
    )

    x, y, ids = load_cache_batch(cache, expected_bearing="Bearing1_1")

    assert x.shape == (2, 2)
    assert y.tolist() == [1.0, 0.0]
    assert ids == ("one", "two")
    assert_sealed_not_cached(tmp_path, ("Bearing1_5",))
    (tmp_path / "Bearing1_5.npz").write_bytes(b"opened")
    with pytest.raises(FinalValidationError, match="already cached"):
        assert_sealed_not_cached(tmp_path, ("Bearing1_5",))
