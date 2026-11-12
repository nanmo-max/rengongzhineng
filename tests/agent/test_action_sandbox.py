from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from brace_msi.action_sandbox import (
    ActionSandboxError,
    BudgetSnapshot,
    PluginRegistry,
    PluginSpec,
    assert_isolated_output_path,
    default_official_tool_registry,
)
from brace_msi.official_package import PackageAudit
from brace_msi.policies import Action
from brace_msi.pytrio_agent import ExperimentProposal


def package(tmp_path: Path, *, task: str = "classification") -> PackageAudit:
    package_dir = tmp_path / "immutable-package"
    package_dir.mkdir()
    checkpoint = package_dir / "checkpoint.npz"
    checkpoint.write_bytes(b"checkpoint")
    empty = frozenset()
    return PackageAudit(
        profile="A",
        package_id="test",
        package_dir=package_dir,
        task=task,
        primary_metric="macro_f1" if task == "classification" else "rmse",
        higher_is_better=task == "classification",
        input_features=4,
        hidden=2,
        parameter_count=10,
        train_rows=100,
        validation_rows=20,
        train_ids=empty,
        validation_ids=empty,
        train_groups=empty,
        validation_groups=empty,
        baseline_metric=0.5,
        baseline_metrics={},
        checkpoint_sha256=hashlib.sha256(b"checkpoint").hexdigest(),
        package_tree_sha256="a" * 64,
        train_sha256="b" * 64,
        validation_sha256="c" * 64,
        checkpoint_path=checkpoint,
        train_path=package_dir / "train.jsonl",
        validation_path=package_dir / "validation.jsonl",
        profile_path=package_dir / "A.json",
        base_learning_rate=0.01,
        base_batch_size=16,
        base_epochs=10,
        training_seconds=20.0,
        initial_epochs=10,
        initial_steps=100,
        source_sha256={},
    )


def proposal(action: Action, tool: str, **parameters) -> ExperimentProposal:
    return ExperimentProposal(
        schema_version="brace-msi.experiment-proposal.v1",
        action=action,
        tool=tool,
        rationale="bounded experiment",
        parameters=parameters,
        max_cpu_seconds=10.0,
        max_candidates=1,
        stop_conditions=("budget_exhausted",),
    )


def budget(**updates) -> BudgetSnapshot:
    values = {
        "candidate_slots_remaining": 2,
        "cpu_seconds_remaining": 30.0,
        "wall_seconds_remaining": 30.0,
    }
    values.update(updates)
    return BudgetSnapshot(**values)


def test_builtin_registry_is_versioned_and_builds_an_estimated_plan(tmp_path: Path) -> None:
    registry = default_official_tool_registry()

    plan = registry.build_plan(
        proposal(Action.INCREMENTAL_UPDATE, "train_incremental", epochs=1),
        package(tmp_path),
        budget(),
        allowed_epochs=(1, 2),
        allowed_learning_rate_multipliers=(0.5, 1.0),
    )

    assert len(registry.sha256) == 64
    assert plan.tool_id == "train_incremental"
    assert plan.tool_version == "1"
    assert plan.candidate_config.epochs == 1
    assert plan.estimated_training_sample_visits == 100
    assert plan.estimated_cpu_seconds == pytest.approx(2.0)


def test_incremental_and_full_replay_parameters_fail_closed(tmp_path: Path) -> None:
    registry = default_official_tool_registry()
    pkg = package(tmp_path)

    with pytest.raises(ActionSandboxError, match="incremental_epochs_not_allowed"):
        registry.build_plan(
            proposal(Action.INCREMENTAL_UPDATE, "train_incremental", epochs=2),
            pkg,
            budget(),
            allowed_epochs=(1, 2),
            allowed_learning_rate_multipliers=(1.0,),
        )
    with pytest.raises(ActionSandboxError, match="replay_fraction_not_executable"):
        registry.build_plan(
            proposal(
                Action.REPLAY_REFIT,
                "train_replay_refit",
                epochs=1,
                replay_fraction=0.5,
            ),
            pkg,
            budget(),
            allowed_epochs=(1,),
            allowed_learning_rate_multipliers=(1.0,),
        )


def test_training_estimate_and_proposal_budget_are_checked_before_execution(tmp_path: Path) -> None:
    registry = default_official_tool_registry()

    with pytest.raises(ActionSandboxError, match="estimated_cpu_budget_exceeded"):
        registry.build_plan(
            proposal(Action.REPLAY_REFIT, "train_replay_refit", epochs=2, replay_fraction=1.0),
            package(tmp_path),
            budget(cpu_seconds_remaining=3.0),
            allowed_epochs=(1, 2),
            allowed_learning_rate_multipliers=(1.0,),
        )


def test_output_path_must_stay_in_runtime_and_outside_package(tmp_path: Path) -> None:
    pkg = package(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    assert_isolated_output_path(pkg.package_dir, runtime, runtime / "candidate")
    with pytest.raises(ActionSandboxError, match="output_outside_runtime"):
        assert_isolated_output_path(pkg.package_dir, runtime, tmp_path / "escape")
    with pytest.raises(ActionSandboxError, match="runtime_overlaps_package"):
        assert_isolated_output_path(
            pkg.package_dir, pkg.package_dir / "runtime", pkg.package_dir / "runtime" / "candidate"
        )


def test_registered_plugin_is_fixed_by_root_hash_and_license(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    root.mkdir()
    entry = root / "method.py"
    entry.write_text("VALUE = 1\n", encoding="utf-8")
    digest = hashlib.sha256(entry.read_bytes()).hexdigest()
    registry = PluginRegistry(root)
    spec = PluginSpec(
        plugin_id="paper-method",
        version="1.0",
        entry_path=entry,
        sha256=digest,
        license_id="MIT",
        supported_tasks=("classification",),
    )

    registry.register(spec)
    assert registry.resolve("paper-method", task="classification") == spec
    entry.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(ActionSandboxError, match="plugin_hash_mismatch"):
        registry.resolve("paper-method", task="classification")
