from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from brace_msi.official_package import audit_package_root
from brace_msi.official_rounds import run_policy, validate_policy_result
from brace_msi.official_trainer import CandidateReceipt


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


@pytest.fixture(scope="module")
def audit_a():
    config = json.loads((REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8"))
    return audit_package_root(PACKAGE_ROOT, config)["A"]


class DeterministicTrainer:
    def __init__(self, metric_values: list[float]) -> None:
        self.metric_values = iter(metric_values)
        self.calls: list[dict] = []

    def run_candidate(self, package, parent, output_dir, config, stage_id):
        output_dir = Path(output_dir)
        if output_dir.exists():
            raise FileExistsError("candidate output conflict")
        output_dir.mkdir(parents=True)
        checkpoint = output_dir / "checkpoint.npz"
        checkpoint.write_bytes(f"{stage_id}:{len(self.calls)}".encode())
        parent_sha = hashlib.sha256(Path(parent).read_bytes()).hexdigest()
        child_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        metric = next(self.metric_values)
        call = {
            "stage_id": stage_id,
            "parent": str(parent),
            "parent_sha256": parent_sha,
            "checkpoint_sha256": child_sha,
            "config": asdict(config),
        }
        self.calls.append(call)
        receipt = CandidateReceipt(
            stage_id=stage_id,
            profile=package.profile,
            parent_sha256=parent_sha,
            checkpoint_sha256=child_sha,
            metrics_before={package.primary_metric: package.baseline_metric},
            metrics_after={package.primary_metric: metric},
            initial_epochs=20 + len(self.calls) - 1,
            final_epochs=20 + len(self.calls),
            initial_steps=80 + len(self.calls) - 1,
            final_steps=80 + len(self.calls),
            model_state_changed=True,
            optimizer_state_changed=True,
            wall_seconds=0.1,
            cpu_seconds=0.05,
            peak_rss_bytes=1024,
            output_dir=str(output_dir),
            validation_file_reads=1,
            validation_metric_evaluations=config.epochs + 1,
        )
        (output_dir / "candidate-receipt.json").write_text(json.dumps(asdict(receipt)), encoding="utf-8")
        return receipt


def policy_config(**updates) -> dict:
    config = {
        "rounds": 10,
        "minimum_brace_candidates": 3,
        "max_candidates_per_policy": 3,
        "max_cpu_seconds_per_policy": 60.0,
        "max_wall_seconds_per_policy": 60.0,
    }
    config.update(updates)
    return config


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_brace_runs_ten_decision_rounds_and_rejected_candidate_never_becomes_parent(tmp_path: Path, audit_a) -> None:
    trainer = DeterministicTrainer([0.72, 0.70, 0.73])
    runtime = tmp_path / "brace"

    result = run_policy(audit_a, "brace", runtime, policy_config(), trainer)

    assert result.complete is True
    assert result.round_count == 10
    assert result.candidate_count == 3
    assert result.accepted_count == 2
    assert [row["kind"] for row in result.rounds] == ["candidate", "candidate", "candidate"] + ["noop"] * 7
    assert trainer.calls[0]["parent_sha256"] == audit_a.checkpoint_sha256
    assert trainer.calls[1]["parent_sha256"] == trainer.calls[0]["checkpoint_sha256"]
    assert trainer.calls[2]["parent_sha256"] == trainer.calls[0]["checkpoint_sha256"]
    assert trainer.calls[2]["parent_sha256"] != trainer.calls[1]["checkpoint_sha256"]
    validation = read_jsonl(runtime / "validation-usage.jsonl")
    assert len(validation) == 3
    assert [row["cumulative_file_reads"] for row in validation] == [1, 2, 3]
    assert all(row["purpose"] == "candidate_gate" for row in validation)
    assert result.round_semantics == "candidate_adaptation_decision"
    assert result.real_drift_stream is False
    assert validate_policy_result(runtime, expected_rounds=10, minimum_candidates=3)["valid"] is True


def test_performance_triggered_control_uses_one_candidate_then_noops(tmp_path: Path, audit_a) -> None:
    trainer = DeterministicTrainer([0.72])

    result = run_policy(audit_a, "performance_triggered", tmp_path / "simple", policy_config(), trainer)

    assert result.round_count == 10
    assert result.candidate_count == 1
    assert result.accepted_count == 1
    assert [row["kind"] for row in result.rounds[1:]] == ["noop"] * 9
    assert len(read_jsonl(tmp_path / "simple" / "validation-usage.jsonl")) == 1


def test_partial_execution_resumes_without_repeating_completed_candidates(tmp_path: Path, audit_a) -> None:
    trainer = DeterministicTrainer([0.72, 0.70, 0.73])
    runtime = tmp_path / "resume"
    partial = run_policy(audit_a, "brace", runtime, policy_config(max_rounds_this_call=5), trainer)
    state_after_five = (runtime / "state.json").read_bytes()

    completed = run_policy(audit_a, "brace", runtime, policy_config(), trainer)

    assert partial.complete is False
    assert partial.round_count == 5
    assert completed.complete is True
    assert completed.round_count == 10
    assert len(trainer.calls) == 3
    assert state_after_five != (runtime / "state.json").read_bytes()
    assert [row["round"] for row in read_jsonl(runtime / "audit.jsonl")] == list(range(1, 11))


def test_untracked_existing_candidate_directory_is_never_overwritten(tmp_path: Path, audit_a) -> None:
    runtime = tmp_path / "conflict"
    (runtime / "candidates" / "round-01-attempt-01").mkdir(parents=True)
    trainer = DeterministicTrainer([0.72, 0.70, 0.73])

    with pytest.raises(FileExistsError, match="conflict"):
        run_policy(audit_a, "brace", runtime, policy_config(), trainer)


def test_policy_validation_rejects_insufficient_brace_candidates(tmp_path: Path, audit_a) -> None:
    trainer = DeterministicTrainer([0.70, 0.69])
    runtime = tmp_path / "budget"
    result = run_policy(
        audit_a,
        "brace",
        runtime,
        policy_config(minimum_brace_candidates=2, max_candidates_per_policy=2),
        trainer,
    )
    assert result.candidate_count == 2

    with pytest.raises(ValueError, match="minimum candidates"):
        validate_policy_result(runtime, expected_rounds=10, minimum_candidates=3)

