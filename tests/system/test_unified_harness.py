import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from brace_msi.budget import BudgetLimits
from brace_msi.data.types import BatchData, TaskStream
from brace_msi.harness import HarnessConfig, UnifiedHarness
from brace_msi.protocol import ProtocolMode, SimulatedSdkAdapter
from brace_msi.recording import LocalPublicSpool
from brace_msi.safety import GateConfig


def _batch(batch_id: str, offset: float, *, count: int = 24) -> BatchData:
    negative = np.linspace(-2.0 + offset, -0.2 + offset, count // 2)
    positive = np.linspace(0.2 + offset, 2.0 + offset, count // 2)
    values = np.concatenate([negative, positive])
    X = np.column_stack([values, values**2])
    y = (values > offset).astype(int)
    return BatchData(
        batch_id,
        X,
        y,
        tuple(f"{batch_id}-{index}" for index in range(count)),
    )


def _stream() -> TaskStream:
    return TaskStream(
        task_id="synthetic-bearing",
        task_kind="classification",
        initial=_batch("initial", 0.0, count=40),
        development=tuple(_batch(f"dev-{index}", index * 0.8) for index in range(4)),
        sealed=(),
        metadata={"synthetic": True},
    )


def _config(mode: ProtocolMode) -> HarnessConfig:
    return HarnessConfig(
        seed=20261107,
        protocol_mode=mode,
        budget=BudgetLimits(8, 5000, 30.0, 30.0),
        gate=GateConfig(
            min_validation_samples=2,
            min_primary_improvement=-1.0,
            max_anchor_degradation=1.0,
        ),
        minimum_candidate_events=3,
        replay_max_samples=200,
        hpo_max_trials=2,
    )


@pytest.mark.parametrize(
    "mode,owned_event",
    [
        (ProtocolMode.PREDICT_THEN_FEEDBACK, "feedback_available"),
        (ProtocolMode.LABELED_TRAIN_THEN_PREDICT, "training_available"),
    ],
)
def test_unified_harness_runs_both_protocols_with_three_real_candidates(
    tmp_path: Path, mode: ProtocolMode, owned_event: str
) -> None:
    result = UnifiedHarness(tmp_path / mode.value, _config(mode)).run(_stream())

    assert result.status == "completed"
    assert result.completed_batches == 4
    assert result.candidate_count >= 3
    assert owned_event in result.protocol_history
    assert result.protocol_history[-1] == "run_finished"
    assert (tmp_path / mode.value / "registry" / "synthetic-bearing" / "manifest.json").exists()


def test_harness_resumes_from_committed_checkpoint_without_repeating_training(
    tmp_path: Path,
) -> None:
    root = tmp_path / "resume"
    harness = UnifiedHarness(root, _config(ProtocolMode.PREDICT_THEN_FEEDBACK))
    partial = harness.run(_stream(), max_batches=1)
    assert partial.status == "paused"
    first_candidate_count = partial.candidate_count

    completed = UnifiedHarness(
        root, _config(ProtocolMode.PREDICT_THEN_FEEDBACK)
    ).run(_stream())

    assert completed.status == "completed"
    assert completed.completed_batches == 4
    assert completed.candidate_count >= first_candidate_count
    records = [json.loads(line) for line in (root / "private-audit.jsonl").read_text().splitlines()]
    committed = [record["batch_id"] for record in records if record["event"] == "batch_committed"]
    assert committed == ["dev-0", "dev-1", "dev-2", "dev-3"]


def test_resume_reconciles_checkpointed_batch_when_audit_append_was_interrupted(
    tmp_path: Path,
) -> None:
    root = tmp_path / "audit-reconcile"
    harness = UnifiedHarness(root, _config(ProtocolMode.PREDICT_THEN_FEEDBACK))
    harness.run(_stream(), max_batches=1)
    for filename in ("private-audit.jsonl", "public-spool.jsonl"):
        path = root / filename
        records = [json.loads(line) for line in path.read_text().splitlines()]
        records = [record for record in records if record["event"] != "batch_committed"]
        path.write_text("".join(json.dumps(record) + "\n" for record in records))

    UnifiedHarness(root, _config(ProtocolMode.PREDICT_THEN_FEEDBACK)).run(_stream())

    private_records = [
        json.loads(line) for line in (root / "private-audit.jsonl").read_text().splitlines()
    ]
    committed = [record["batch_id"] for record in private_records if record["event"] == "batch_committed"]
    assert committed == ["dev-0", "dev-1", "dev-2", "dev-3"]


def test_budget_rejected_attempts_do_not_count_as_real_candidates(tmp_path: Path) -> None:
    config = _config(ProtocolMode.PREDICT_THEN_FEEDBACK)
    config = HarnessConfig(
        **{
            **config.__dict__,
            "budget": BudgetLimits(8, 1, 30.0, 30.0),
        }
    )

    result = UnifiedHarness(tmp_path / "budget-rejected", config).run(_stream())

    assert result.candidate_count == 0
    assert result.candidates
    assert all(event.training_started is False for event in result.candidates)


def test_failed_candidate_is_rejected_and_stable_registry_remains_loadable(
    tmp_path: Path,
) -> None:
    config = _config(ProtocolMode.PREDICT_THEN_FEEDBACK)
    config = HarnessConfig(**{**config.__dict__, "fail_candidate_numbers": (1,)})
    result = UnifiedHarness(tmp_path / "failure", config).run(_stream())

    assert result.status == "completed"
    assert any(event.reason == "injected_candidate_failure" for event in result.candidates)
    assert result.deployed_version is not None
    assert result.rollback_count >= 1


def test_public_spool_keeps_only_aggregate_allowlisted_fields(tmp_path: Path) -> None:
    spool = LocalPublicSpool(tmp_path / "public.jsonl")
    spool.record(
        "candidate",
        {
            "task_id": "task",
            "batch_id": "batch",
            "primary_metric": 0.8,
            "raw_features": [[1.0, 2.0]],
            "targets": [1],
            "api_key": "secret",
        },
    )

    record = json.loads((tmp_path / "public.jsonl").read_text())
    assert record["sync_status"] == "pending"
    assert record["task_id"] == "task"
    assert "raw_features" not in record
    assert "targets" not in record
    assert "api_key" not in record


def test_harness_uses_replaceable_protocol_adapter_factory(tmp_path: Path) -> None:
    created: list[ProtocolMode] = []

    def factory(mode: ProtocolMode) -> SimulatedSdkAdapter:
        created.append(mode)
        return SimulatedSdkAdapter(mode)

    result = UnifiedHarness(
        tmp_path / "replaceable",
        _config(ProtocolMode.PREDICT_THEN_FEEDBACK),
        adapter_factory=factory,
    ).run(_stream(), max_batches=1)

    assert result.status == "paused"
    assert created == [ProtocolMode.PREDICT_THEN_FEEDBACK]


def test_cli_runs_noninteractive_synthetic_smoke(tmp_path: Path) -> None:
    output = tmp_path / "cli-run"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "brace_msi",
            "synthetic-smoke",
            "--output",
            str(output),
            "--protocol",
            "predict_then_feedback",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["candidate_count"] >= 3
    assert summary["synthetic"] is True
