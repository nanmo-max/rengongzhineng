from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest


def _manifest() -> dict[str, object]:
    return {
        "format": "brace-msi.mature-optimizer-pilot.v1",
        "experiment_id": "TEST-MATURE-PILOT",
        "rounds": 3,
        "confirmation_read_policy": "never",
        "methods": [
            "native_current",
            "native_replay",
            "l2sp_1e-4",
            "l2sp_1e-3",
            "sam_0.01",
            "sam_0.05",
            "adamw_1e-5",
            "adamw_1e-4",
        ],
        "registered_surrogates": [
            {"key": "opaque-cls", "task": "classification", "feature_count": 3, "samples_per_round": 16, "confirmation_samples": 16, "seed": 9001},
            {"key": "opaque-reg", "task": "regression", "feature_count": 3, "samples_per_round": 16, "confirmation_samples": 16, "seed": 9002},
        ],
    }


def test_manifest_requires_three_rounds_never_reads_confirmation_and_known_methods(tmp_path: Path) -> None:
    """Catches a pilot silently becoming a confirmation-driven search."""

    from scripts.run_mature_optimizer_pilot import load_manifest

    path = tmp_path / "manifest.json"
    payload = _manifest()
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_manifest(path)["rounds"] == 3

    for field, value, message in (
        ("rounds", 10, "three rounds"),
        ("confirmation_read_policy", "once", "confirmation"),
        ("methods", ["mystery"], "method"),
    ):
        invalid = copy.deepcopy(payload)
        invalid[field] = value
        path.write_text(json.dumps(invalid), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_manifest(path)


def test_smoke_runs_all_methods_on_two_opaque_tasks_without_confirmation(tmp_path: Path) -> None:
    """Catches missing arms, confirmation access, or incomplete three-stage receipts."""

    from scripts.run_mature_optimizer_pilot import run_smoke

    manifest = _manifest()
    summary = run_smoke(manifest, tmp_path / "output")

    assert summary["valid"] is True
    assert summary["confirmation_reads"] == 0
    assert set(summary["tasks"]) == {"opaque-cls", "opaque-reg"}
    assert len(summary["arms"]) == 16
    assert all(len(arm["stages"]) == 3 for arm in summary["arms"])
    assert all(arm["parent_lineage_valid"] for arm in summary["arms"])
    assert all("confirmation" not in json.dumps(arm).lower() for arm in summary["arms"])
    assert (tmp_path / "output" / "summary.json").is_file()


def test_optimizer_mechanisms_use_current_batch_while_replay_is_separate_control() -> None:
    """Catches optimizer effects being confounded with historical replay."""

    from brace_msi.mature_optimizer_pilot import MATURE_PILOT_RECIPES

    assert MATURE_PILOT_RECIPES["native_replay"].history_policy == "current_plus_history"
    assert {
        recipe.history_policy
        for name, recipe in MATURE_PILOT_RECIPES.items()
        if name not in {"native_replay"}
    } == {"current"}


def test_pareto_front_prefers_gain_and_worst_stage_without_inventing_score() -> None:
    """Catches scalar score fabrication or a dominated method entering the frontier."""

    from scripts.run_mature_optimizer_pilot import pareto_front

    methods = [
        {"method": "balanced", "mean_relative_gain": 0.2, "worst_relative_gain": -0.1, "cpu_seconds": 2.0},
        {"method": "fast", "mean_relative_gain": 0.1, "worst_relative_gain": -0.2, "cpu_seconds": 0.5},
        {"method": "dominated", "mean_relative_gain": 0.05, "worst_relative_gain": -0.3, "cpu_seconds": 3.0},
    ]

    result = pareto_front(methods)

    assert result == ["balanced", "fast"]


def test_direct_cli_entry_can_import_sibling_runner(tmp_path: Path) -> None:
    """Catches pytest-only imports hiding a broken direct script entry."""

    config = tmp_path / "manifest.json"
    config.write_text(json.dumps(_manifest()), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_mature_optimizer_pilot.py",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "cli-output"),
            "--smoke",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads((tmp_path / "cli-output" / "summary.json").read_text(encoding="utf-8"))["valid"] is True
