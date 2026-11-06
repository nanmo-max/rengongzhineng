from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np

from brace_msi.data.types import BatchData, TaskStream


def _batch(batch_id: str, center: float, start: int) -> BatchData:
    negative = np.linspace(center - 2.0, center - 0.5, 12)
    positive = np.linspace(center + 0.5, center + 2.0, 12)
    X = np.concatenate([negative, positive]).reshape(-1, 1)
    y = np.asarray([0] * 12 + [1] * 12)
    return BatchData(
        batch_id=batch_id,
        X=X,
        y=y,
        sample_ids=tuple(f"opaque-{start + index}" for index in range(24)),
    )


def _stream() -> TaskStream:
    return TaskStream(
        task_id="synthetic-classification",
        task_kind="classification",
        initial=_batch("initial", 0.0, 0),
        development=(
            _batch("dev-1", 1.0, 100),
            _batch("dev-2", 3.0, 200),
            _batch("dev-3", -2.0, 300),
        ),
        sealed=(_batch("sealed-1", 0.0, 400),),
        metadata={"proxy_only": True},
    )


@dataclass
class RecordingPolicy:
    actions: list
    contexts: list = field(default_factory=list)
    outcomes: list = field(default_factory=list)

    def choose(self, context):
        self.contexts.append(context)
        return self.actions[len(self.contexts) - 1]

    def observe(self, action, *, accepted: bool, improvement: float) -> None:
        self.outcomes.append((action, accepted, improvement))


def test_runner_executes_incremental_and_refit_candidates_in_protocol_order(
    tmp_path: Path,
) -> None:
    from brace_msi.budget import BudgetLimits
    from brace_msi.policies import Action
    from brace_msi.runner import RunConfig, run_stream
    from brace_msi.safety import GateConfig

    policy = RecordingPolicy(
        [Action.INCREMENTAL_UPDATE, Action.REPLAY_REFIT, Action.NOOP]
    )
    summary = run_stream(
        _stream(),
        policy=policy,
        config=RunConfig(
            seed=20261106,
            budget=BudgetLimits(5, 1000, 20.0, 20.0),
            gate=GateConfig(
                min_validation_samples=4,
                min_primary_improvement=-1.0,
                max_anchor_degradation=1.0,
            ),
        ),
        audit_path=tmp_path / "events.jsonl",
        include_sealed=False,
    )

    assert [event.action for event in summary.candidate_events] == [
        "incremental_update",
        "replay_refit",
    ]
    assert summary.candidate_count == 2
    assert summary.batch_results[-1].batch_id == "dev-3"
    assert summary.protocol_history.count("prediction_requested") == 3
    assert summary.protocol_history.count("prediction_submitted") == 3
    assert summary.protocol_history.count("feedback_available") == 3
    assert summary.protocol_history.count("batch_committed") == 3
    assert [context.batch_index for context in policy.contexts] == [1, 2, 3]
    assert len(policy.outcomes) == 2

    audit_events = [
        json.loads(line)["event"]
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    first_batch_events = audit_events[:5]
    assert first_batch_events[:3] == [
        "prediction_submitted",
        "feedback_received",
        "batch_scored",
    ]


def test_runner_static_policy_has_no_candidate_and_does_not_open_sealed(
    tmp_path: Path,
) -> None:
    from brace_msi.budget import BudgetLimits
    from brace_msi.policies import StaticPolicy
    from brace_msi.runner import RunConfig, run_stream
    from brace_msi.safety import GateConfig

    summary = run_stream(
        _stream(),
        policy=StaticPolicy(),
        config=RunConfig(
            seed=20261106,
            budget=BudgetLimits(2, 1000, 20.0, 20.0),
            gate=GateConfig(min_validation_samples=4),
        ),
        audit_path=tmp_path / "events.jsonl",
        include_sealed=False,
    )

    assert summary.candidate_count == 0
    assert all(result.phase == "development" for result in summary.batch_results)
    assert all(result.batch_id != "sealed-1" for result in summary.batch_results)


def test_runner_sealed_phase_predicts_without_training(tmp_path: Path) -> None:
    from brace_msi.budget import BudgetLimits
    from brace_msi.policies import StaticPolicy
    from brace_msi.runner import RunConfig, run_stream
    from brace_msi.safety import GateConfig

    summary = run_stream(
        _stream(),
        policy=StaticPolicy(),
        config=RunConfig(
            seed=20261106,
            budget=BudgetLimits(2, 1000, 20.0, 20.0),
            gate=GateConfig(min_validation_samples=4),
        ),
        audit_path=tmp_path / "events.jsonl",
        include_sealed=True,
    )

    assert summary.batch_results[-1].phase == "sealed"
    assert summary.batch_results[-1].batch_id == "sealed-1"
    assert summary.candidate_count == 0


def test_failed_training_consumes_candidate_budget_and_run_continues(
    tmp_path: Path,
) -> None:
    from brace_msi.budget import BudgetLimits
    from brace_msi.policies import Action
    from brace_msi.runner import RunConfig, run_stream
    from brace_msi.safety import GateConfig

    base = _stream()

    def unseen_batch(batch_id: str, start: int) -> BatchData:
        batch = _batch(batch_id, 0.0, start)
        return BatchData(
            batch_id=batch.batch_id,
            X=batch.X,
            y=np.asarray([2] * len(batch.y)),
            sample_ids=batch.sample_ids,
        )

    stream = TaskStream(
        task_id=base.task_id,
        task_kind=base.task_kind,
        initial=base.initial,
        development=(unseen_batch("dev-1", 500), unseen_batch("dev-2", 600)),
        sealed=(),
        metadata=base.metadata,
    )
    policy = RecordingPolicy([Action.INCREMENTAL_UPDATE, Action.INCREMENTAL_UPDATE])

    summary = run_stream(
        stream,
        policy=policy,
        config=RunConfig(
            seed=20261106,
            budget=BudgetLimits(1, 1000, 20.0, 20.0),
            gate=GateConfig(min_validation_samples=4),
        ),
        audit_path=tmp_path / "events.jsonl",
        include_sealed=False,
    )

    assert summary.candidate_count == 1
    assert summary.candidate_events[0].budget_allowed is True
    assert summary.candidate_events[0].accepted is False
    assert "candidate failure" in summary.candidate_events[0].reason
    assert summary.candidate_events[1].budget_allowed is False
    assert "candidate limit" in summary.candidate_events[1].reason
    assert len(summary.batch_results) == 2
