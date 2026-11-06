from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_load_config_requires_proxy_only_and_no_sealed_smoke(tmp_path: Path) -> None:
    from brace_msi.experiment import ExperimentConfigError, load_experiment_config

    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "experiment_id": "BAD",
                "proxy_only": False,
                "smoke": True,
                "include_sealed": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ExperimentConfigError):
        load_experiment_config(path)


def test_local_smoke_config_is_valid_and_reproducible() -> None:
    from brace_msi.experiment import load_experiment_config

    config = load_experiment_config(Path("configs/local_smoke.json"))

    assert config["experiment_id"] == "LOCAL-SMOKE-001"
    assert config["proxy_only"] is True
    assert config["seed"] == 20261106
    assert config["include_sealed"] is False
    assert config["data_hashes"]["gas"].startswith("91E8F4")


@pytest.mark.parametrize(
    ("policy_name", "expected_type"),
    [
        ("static", "StaticPolicy"),
        ("performance_triggered", "PerformanceTriggeredPolicy"),
        ("brace", "BracePolicy"),
    ],
)
def test_build_policy_creates_requested_control(
    policy_name: str, expected_type: str
) -> None:
    from brace_msi.experiment import build_policy, load_experiment_config

    config = load_experiment_config(Path("configs/local_smoke.json"))
    policy = build_policy(policy_name, task_kind="classification", config=config)

    assert type(policy).__name__ == expected_type


def test_build_policy_rejects_unknown_name() -> None:
    from brace_msi.experiment import ExperimentConfigError, build_policy

    with pytest.raises(ExperimentConfigError, match="unknown policy"):
        build_policy("mystery", task_kind="classification", config={})


def test_validate_smoke_output_requires_both_training_actions(tmp_path: Path) -> None:
    from brace_msi.experiment import ExperimentValidationError, validate_experiment_output

    summary = {
        "schema_version": 1,
        "experiment_id": "LOCAL-SMOKE-001",
        "proxy_only": True,
        "smoke": True,
        "include_sealed": False,
        "run_count": 6,
        "action_counts": {"incremental_update": 2},
        "runs": [],
    }
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    for index in range(6):
        (tmp_path / f"run-{index}.json").write_text("{}", encoding="utf-8")
        (tmp_path / f"run-{index}.jsonl").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "proxy_only": True,
                    "event": "batch_scored",
                    "batch_id": f"b-{index}",
                }
            )
            + "\n",
            encoding="utf-8",
        )

    with pytest.raises(ExperimentValidationError, match="replay_refit"):
        validate_experiment_output(tmp_path, expected_runs=6, smoke=True)

    summary["action_counts"]["replay_refit"] = 1
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    result = validate_experiment_output(tmp_path, expected_runs=6, smoke=True)

    assert result["valid"] is True
    assert result["jsonl_files"] == 6
