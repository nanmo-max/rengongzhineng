from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

import scripts.run_generalization_matrix as matrix

from scripts.run_generalization_matrix import (
    _candidate_recipes,
    _experiment_id,
    _promotion_pass,
    _recovery_lags,
    _relative_signed_gain,
    _rollback_available,
    _round_root,
)


def test_candidate_recipes_depend_on_evidence_not_dataset_name() -> None:
    classification = _candidate_recipes(
        task_kind="classification",
        target_batch_means=(0.2, 0.4, 0.3),
        target_scale=1.0,
        previous_delayed_gain=0.01,
        failure_streak=0,
    )
    regression = _candidate_recipes(
        task_kind="regression",
        target_batch_means=(1400.0, 1250.0, 1100.0, 950.0),
        target_scale=780.0,
        previous_delayed_gain=20.0,
        failure_streak=0,
    )

    assert classification == ("soup_current_e3_alpha0.25", "recent_e3")
    assert regression == ("soup_current_e3_alpha0.25", "current_e3_lr3")


def test_candidate_recipes_always_include_real_training_fallback() -> None:
    assert _candidate_recipes(
        task_kind="regression",
        target_batch_means=(),
        target_scale=10.0,
        previous_delayed_gain=None,
        failure_streak=0,
    ) == ("soup_current_e3_alpha0.25",)


def test_high_scale_regression_heterogeneity_adds_forward_candidate() -> None:
    assert _candidate_recipes(
        task_kind="regression",
        target_batch_means=(1438.5, 34.5),
        target_scale=785.23,
        previous_delayed_gain=None,
        failure_streak=0,
    ) == ("soup_current_e3_alpha0.25", "current_e3_lr3")


def test_round_root_cannot_escape_to_confirmation_or_future_name(tmp_path) -> None:
    (tmp_path / "round-01").mkdir()
    (tmp_path / "round-10").mkdir()
    assert _round_root(tmp_path, 1) == tmp_path / "round-01"
    assert _round_root(tmp_path, 10) == tmp_path / "round-10"
    with pytest.raises(ValueError):
        _round_root(tmp_path, 0)
    with pytest.raises(ValueError):
        _round_root(tmp_path, 11)


def test_round_root_rejects_internal_directory_symlink(tmp_path) -> None:
    target = tmp_path / "materialized-round"
    target.mkdir()
    link = tmp_path / "round-01"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="symlink"):
        _round_root(tmp_path, 1)


def test_round_root_rejects_symlinked_runtime_root(tmp_path) -> None:
    target = tmp_path / "materialized-inputs"
    (target / "round-01").mkdir(parents=True)
    link = tmp_path / "runtime-inputs"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="root"):
        _round_root(link, 1)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_round_root_rejects_internal_junction(tmp_path) -> None:
    target = tmp_path / "materialized-round"
    target.mkdir()
    junction = tmp_path / "round-01"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")
    assert junction.is_junction()

    with pytest.raises(ValueError, match="junction"):
        _round_root(tmp_path, 1)


def test_last_round_cannot_claim_delayed_rollback() -> None:
    assert _rollback_available(round_index=9, parent_recoverable=True) is True
    assert _rollback_available(round_index=10, parent_recoverable=True) is False
    assert _rollback_available(round_index=9, parent_recoverable=False) is False


def test_recovery_lags_count_only_after_negative_stage() -> None:
    assert _recovery_lags((0.1, -0.2, -0.1, 0.0, 0.2, -0.3)) == (2,)
    assert _recovery_lags((0.1, 0.2)) == ()


def test_relative_signed_gain_is_scale_safe() -> None:
    assert _relative_signed_gain(5.0, 100.0) == pytest.approx(0.05)
    assert _relative_signed_gain(-0.5, 0.0) == pytest.approx(-0.5)


def test_promotion_requires_all_tasks_noncatastrophic_and_nonnegative() -> None:
    safe = [
        {"profile": "A", "mean_arrival_gain_vs_static": 0.2, "mean_relative_gain_vs_static": 0.2, "worst_relative_gain_vs_static": -0.01, "catastrophic_regression": False, "training_round_count": 10, "candidate_count": 10, "confirmation_files_read": 0, "final_selection_safe": True, "final_checkpoint_verified": True},
        {"profile": "B", "mean_arrival_gain_vs_static": 1.0, "mean_relative_gain_vs_static": 0.3, "worst_relative_gain_vs_static": 0.0, "catastrophic_regression": False, "training_round_count": 10, "candidate_count": 10, "confirmation_files_read": 0, "final_selection_safe": True, "final_checkpoint_verified": True},
        {"profile": "C", "mean_arrival_gain_vs_static": 0.1, "mean_relative_gain_vs_static": 0.1, "worst_relative_gain_vs_static": -0.01, "catastrophic_regression": False, "training_round_count": 10, "candidate_count": 10, "confirmation_files_read": 0, "final_selection_safe": True, "final_checkpoint_verified": True},
    ]
    baseline = [{**row, "mean_relative_gain_vs_static": row["mean_relative_gain_vs_static"] - 0.01, "worst_relative_gain_vs_static": row["worst_relative_gain_vs_static"] - 0.01} for row in safe]
    assert _promotion_pass(safe, baseline_rows=baseline, strategy="bounded_exploration") is True
    assert _promotion_pass([{**safe[0], "final_selection_safe": False}, *safe[1:]], baseline_rows=baseline, strategy="bounded_exploration") is False
    assert _promotion_pass([{**safe[0], "final_checkpoint_verified": False}, *safe[1:]], baseline_rows=baseline, strategy="bounded_exploration") is False
    assert _promotion_pass(safe, baseline_rows=baseline, strategy="conditional_champion") is False


def test_native_state_digest_binds_selected_model_state() -> None:
    selected = SimpleNamespace(
        meta={"format": "test", "epochs": 3},
        params={"w": np.asarray([[1.0, 2.0]], dtype=np.float64)},
        first={"w": np.asarray([[0.1, 0.2]], dtype=np.float64)},
        second={"w": np.asarray([[0.01, 0.02]], dtype=np.float64)},
        mean=np.asarray([0.5], dtype=np.float64),
        scale=np.asarray([2.0], dtype=np.float64),
    )
    loaded = SimpleNamespace(
        meta=dict(selected.meta),
        params={"w": selected.params["w"].copy()},
        first={"w": selected.first["w"].copy()},
        second={"w": selected.second["w"].copy()},
        mean=selected.mean.copy(),
        scale=selected.scale.copy(),
    )

    assert matrix._native_state_digest(selected) == matrix._native_state_digest(loaded)
    loaded.params["w"][0, 0] += 1.0
    assert matrix._native_state_digest(selected) != matrix._native_state_digest(loaded)


def test_experiment_id_comes_from_output_directory(tmp_path) -> None:
    assert _experiment_id(tmp_path / "GENERALIZATION-MATRIX-001-A4") == "GENERALIZATION-MATRIX-001-A4"

