import json
from pathlib import Path
import subprocess
import sys

import pytest

from brace_msi.unified_optimization import (
    EvaluationMetrics,
    run_development_search,
    validate_development_search,
)
from brace_msi.unified_policy import SharedPolicyConfig


class FakeEvaluator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def evaluate(
        self,
        *,
        task_key: str,
        policy_name: str,
        candidate_id: str | None,
        shared_config: SharedPolicyConfig | None,
    ) -> EvaluationMetrics:
        self.calls.append((task_key, policy_name, candidate_id))
        task_offset = {"task-1": 0.00, "task-2": 0.01, "task-3": 0.02}[task_key]
        if policy_name == "static":
            value, cpu, samples = 1.00, 0.0, 0
        elif policy_name == "fixed_low_cost":
            value, cpu, samples = 0.98, 0.5, 20
        elif policy_name == "performance_triggered":
            value, cpu, samples = 0.97, 0.8, 30
        else:
            assert shared_config is not None and candidate_id is not None
            value = (0.95 if candidate_id == "candidate-good" else 0.99) - task_offset
            cpu, samples = (1.0 if candidate_id == "candidate-good" else 0.6), 40
        return EvaluationMetrics(
            primary_metric=value,
            higher_is_better=False,
            cpu_seconds=cpu,
            wall_seconds=cpu + 0.1,
            peak_rss_bytes=1024,
            training_samples=samples,
            hard_constraints_passed=True,
            resource_within_budget=True,
            initial_state_sha256=(task_key[-1] * 64),
            phase_manifest_sha256=((str(int(task_key[-1]) + 3)) * 64),
        )


def _candidates() -> dict[str, SharedPolicyConfig]:
    return {
        "candidate-good": SharedPolicyConfig(update_drop_threshold=0.01),
        "candidate-weak": SharedPolicyConfig(update_drop_threshold=0.04),
    }


def test_development_search_runs_fair_baselines_and_shared_candidates(tmp_path: Path) -> None:
    evaluator = FakeEvaluator()

    state = run_development_search(
        runtime_root=tmp_path,
        task_keys=("task-1", "task-2", "task-3"),
        candidates=_candidates(),
        evaluator=evaluator,
        source_commit="abc1234",
        experiment_config_sha256="a" * 64,
        static_tolerance=0.005,
    )

    assert state["complete"] is True
    assert state["job_count"] == 15
    assert state["winner"] == "candidate-good"
    assert len(state["folds"]) == 3
    assert all(fold["held_out_task"] not in fold["development_tasks"] for fold in state["folds"])
    assert validate_development_search(tmp_path)["valid"] is True


def test_search_recovers_receipt_written_before_state_commit(tmp_path: Path) -> None:
    evaluator = FakeEvaluator()
    first = run_development_search(
        runtime_root=tmp_path,
        task_keys=("task-1", "task-2", "task-3"),
        candidates=_candidates(),
        evaluator=evaluator,
        source_commit="abc1234",
        experiment_config_sha256="a" * 64,
        static_tolerance=0.005,
        max_jobs=1,
    )
    assert first["complete"] is False
    assert len(evaluator.calls) == 1
    (tmp_path / "state.json").unlink()

    resumed = run_development_search(
        runtime_root=tmp_path,
        task_keys=("task-1", "task-2", "task-3"),
        candidates=_candidates(),
        evaluator=evaluator,
        source_commit="abc1234",
        experiment_config_sha256="a" * 64,
        static_tolerance=0.005,
    )

    assert resumed["complete"] is True
    assert len(evaluator.calls) == 15


def test_resume_rejects_source_or_candidate_config_drift(tmp_path: Path) -> None:
    evaluator = FakeEvaluator()
    run_development_search(
        runtime_root=tmp_path,
        task_keys=("task-1", "task-2", "task-3"),
        candidates=_candidates(),
        evaluator=evaluator,
        source_commit="abc1234",
        experiment_config_sha256="a" * 64,
        static_tolerance=0.005,
        max_jobs=1,
    )

    with pytest.raises(ValueError, match="execution manifest mismatch"):
        run_development_search(
            runtime_root=tmp_path,
            task_keys=("task-1", "task-2", "task-3"),
            candidates={"candidate-good": SharedPolicyConfig(update_drop_threshold=0.03)},
            evaluator=evaluator,
            source_commit="different",
            experiment_config_sha256="a" * 64,
            static_tolerance=0.005,
        )


def test_validator_reopens_receipts_and_rejects_tampering(tmp_path: Path) -> None:
    run_development_search(
        runtime_root=tmp_path,
        task_keys=("task-1", "task-2", "task-3"),
        candidates=_candidates(),
        evaluator=FakeEvaluator(),
        source_commit="abc1234",
        experiment_config_sha256="a" * 64,
        static_tolerance=0.005,
    )
    receipt = next((tmp_path / "jobs").rglob("receipt.json"))
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["metrics"]["primary_metric"] = -999.0
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="receipt hash mismatch"):
        validate_development_search(tmp_path)


def test_validator_rejects_unfair_initial_state_across_policies(tmp_path: Path) -> None:
    run_development_search(
        runtime_root=tmp_path,
        task_keys=("task-1", "task-2", "task-3"),
        candidates=_candidates(),
        evaluator=FakeEvaluator(),
        source_commit="abc1234",
        experiment_config_sha256="a" * 64,
        static_tolerance=0.005,
    )
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    summary["tasks"]["task-1"]["static"]["initial_state_sha256"] = "f" * 64
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(ValueError, match="summary mismatch"):
        validate_development_search(tmp_path)


def test_validate_only_cli_runs_from_clean_checkout(tmp_path: Path) -> None:
    run_development_search(
        runtime_root=tmp_path,
        task_keys=("task-1", "task-2", "task-3"),
        candidates=_candidates(),
        evaluator=FakeEvaluator(),
        source_commit="abc1234",
        experiment_config_sha256="a" * 64,
        static_tolerance=0.005,
    )
    repository = Path(__file__).parents[2]

    result = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "run_unified_policy_optimization.py"),
            "--runtime-root",
            str(tmp_path),
            "--validate-only",
        ],
        cwd=repository,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


def test_search_rejects_unfair_fixed_low_cost_initial_state(tmp_path: Path) -> None:
    class UnfairFixedEvaluator(FakeEvaluator):
        def evaluate(self, **kwargs: object) -> EvaluationMetrics:
            metrics = super().evaluate(**kwargs)
            if kwargs["policy_name"] == "fixed_low_cost":
                return EvaluationMetrics(
                    **{
                        **metrics.__dict__,
                        "initial_state_sha256": "f" * 64,
                    }
                )
            return metrics

    with pytest.raises(ValueError, match="unfair initial state"):
        run_development_search(
            runtime_root=tmp_path,
            task_keys=("task-1", "task-2", "task-3"),
            candidates=_candidates(),
            evaluator=UnfairFixedEvaluator(),
            source_commit="abc1234",
            experiment_config_sha256="a" * 64,
            static_tolerance=0.005,
        )
