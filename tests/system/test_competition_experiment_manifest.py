from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "competition_core_experiments.json"


def test_manifest_has_no_task_name_recipe_routing_or_confirmation_feedback() -> None:
    from scripts.run_competition_core_experiments import load_manifest

    manifest = load_manifest(CONFIG)

    assert manifest["confirmation_feedback"] is False
    assert manifest["confirmation_read_policy"] == "once_after_development_freeze"
    for strategy in manifest["strategies"].values():
        recipes = strategy.get("recipes", {})
        assert set(recipes) <= {"classification", "regression"}
        assert not ({"A", "B", "C"} & set(recipes))


def test_manifest_verifies_all_official_source_hashes() -> None:
    from scripts.run_competition_core_experiments import validate_sources

    manifest = json.loads(CONFIG.read_text(encoding="utf-8"))
    result = validate_sources(manifest)

    assert set(result) == {"A", "B", "C"}
    assert all(item["valid"] for item in result.values())
    for item in result.values():
        assert item["checkpoint_sha256"] == item["expected_checkpoint_sha256"]
        assert item["train_sha256"] == item["expected_train_sha256"]
        assert item["confirmation_sha256"] == item["expected_confirmation_sha256"]


def test_output_root_is_unique_and_resumable_only_for_same_manifest(tmp_path: Path) -> None:
    from scripts.run_competition_core_experiments import prepare_output

    manifest = json.loads(CONFIG.read_text(encoding="utf-8"))
    first = prepare_output(manifest, tmp_path / "run")
    second = prepare_output(manifest, tmp_path / "run")
    assert first == second

    changed = {**manifest, "seed": manifest["seed"] + 1}
    with pytest.raises(ValueError, match="manifest"):
        prepare_output(changed, tmp_path / "run")


def test_parent_lineage_validator_rejects_noncontiguous_chain() -> None:
    from scripts.run_competition_core_experiments import validate_parent_lineage

    valid = [
        {"round_index": 1, "parent_sha256": "a", "selected_sha256": "b"},
        {"round_index": 2, "parent_sha256": "b", "selected_sha256": "c"},
    ]
    assert validate_parent_lineage(valid) is True

    invalid = [valid[0], {**valid[1], "parent_sha256": "invented"}]
    assert validate_parent_lineage(invalid) is False


def test_source_files_remain_immutable_during_a_smoke_job(tmp_path: Path) -> None:
    from scripts.run_competition_core_experiments import run_smoke

    manifest = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = validate = Path(manifest["official_package_root"]) / manifest["packages"]["A"]["directory"] / "checkpoint.npz"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = run_smoke(manifest, tmp_path / "smoke")
    after = hashlib.sha256(validate.read_bytes()).hexdigest()

    assert result["valid"] is True
    assert result["tasks"] == {"classification": 1, "regression": 1}
    assert before == after


def test_winner_prefers_cross_task_worst_stage_before_mean_gain() -> None:
    from scripts.run_competition_core_experiments import choose_winner

    strategies = {
        "mean-heavy": {"kind": "competition_core"},
        "risk-stable": {"kind": "competition_core"},
    }
    results = [
        {"strategy": "mean-heavy", "mean_relative_gain_vs_static": 0.30, "worst_relative_gain_vs_static": -0.80, "cpu_seconds": 1.0},
        {"strategy": "mean-heavy", "mean_relative_gain_vs_static": 0.20, "worst_relative_gain_vs_static": -0.40, "cpu_seconds": 1.0},
        {"strategy": "risk-stable", "mean_relative_gain_vs_static": 0.15, "worst_relative_gain_vs_static": -0.10, "cpu_seconds": 1.0},
        {"strategy": "risk-stable", "mean_relative_gain_vs_static": 0.14, "worst_relative_gain_vs_static": -0.05, "cpu_seconds": 1.0},
    ]

    assert choose_winner(results, strategies) == "risk-stable"

