from __future__ import annotations

from pathlib import Path

import pytest

from brace_msi.policy_learning import (
    ActionObservation,
    ActionValueTable,
    EvidenceState,
    rank_actions,
)


def _evidence() -> EvidenceState:
    return EvidenceState(
        task_kind="classification",
        performance_drop=0.15,
        drift_score=0.4,
        failure_streak=1,
        remaining_budget_fraction=0.7,
        action_uncertainty=0.3,
    )


def _observation(
    action: str,
    reward: float,
    *,
    source: str = "delayed_shadow",
    confidence: str = "paired",
    cpu: float = 2.0,
) -> ActionObservation:
    return ActionObservation(
        action=action,
        primary_delta=reward,
        cpu_seconds=cpu,
        peak_memory_mb=100.0,
        token_count=0,
        model_bytes=1024,
        accepted=reward > 0,
        succeeded=True,
        reward_source=source,
        attribution_confidence=confidence,
        round_index=2,
    )


def test_action_statistics_are_isolated_per_task(tmp_path: Path) -> None:
    table = ActionValueTable(tmp_path / "values.json")
    evidence = _evidence()
    table.record("task-a", evidence, _observation("REPLAY_REFIT", 0.2))

    assert table.stats("task-a", evidence, "REPLAY_REFIT").reward_count == 1
    assert table.stats("task-b", evidence, "REPLAY_REFIT").reward_count == 0
    assert table.stats("task-b", evidence, "REPLAY_REFIT").attempt_count == 0

    reloaded = ActionValueTable(tmp_path / "values.json")
    assert reloaded.stats("task-a", evidence, "REPLAY_REFIT").mean_reward == pytest.approx(0.2)


def test_task_rename_does_not_change_algorithmic_ranking() -> None:
    evidence = _evidence()
    first = ActionValueTable()
    second = ActionValueTable()
    for table, task_id in ((first, "gas"), (second, "renamed-unknown-task")):
        table.record(task_id, evidence, _observation("INCREMENTAL_UPDATE", 0.08, cpu=1.0))
        table.record(task_id, evidence, _observation("REPLAY_REFIT", 0.12, cpu=4.0))

    costs = {
        "INCREMENTAL_UPDATE": {"cpu_seconds": 1.0, "peak_memory_mb": 50.0},
        "REPLAY_REFIT": {"cpu_seconds": 4.0, "peak_memory_mb": 100.0},
    }
    first_rank = rank_actions(first, "gas", evidence, tuple(costs), costs)
    second_rank = rank_actions(second, "renamed-unknown-task", evidence, tuple(costs), costs)

    assert [item.action for item in first_rank] == [item.action for item in second_rank]
    assert [item.expected_delta for item in first_rank] == pytest.approx(
        [item.expected_delta for item in second_rank]
    )


def test_weak_prior_is_overridden_by_real_delayed_evidence() -> None:
    table = ActionValueTable(
        weak_priors={"REPLAY_REFIT": {"mean_reward": 0.5, "pseudo_count": 0.25}}
    )
    evidence = _evidence()
    before = table.stats("new-task", evidence, "REPLAY_REFIT")
    assert before.reward_count == 0
    assert before.estimated_reward == pytest.approx(0.5)

    table.record("new-task", evidence, _observation("REPLAY_REFIT", -0.1))
    after = table.stats("new-task", evidence, "REPLAY_REFIT")
    assert after.mean_reward == pytest.approx(-0.1)
    assert after.estimated_reward < 0.05


def test_pareto_ranking_eliminates_strictly_dominated_actions() -> None:
    table = ActionValueTable()
    evidence = _evidence()
    table.record("task", evidence, _observation("INCREMENTAL_UPDATE", 0.10, cpu=1.0))
    table.record("task", evidence, _observation("REPLAY_REFIT", 0.08, cpu=3.0))
    table.record("task", evidence, _observation("FAMILY_SWITCH", 0.15, cpu=5.0))
    costs = {
        "INCREMENTAL_UPDATE": {"cpu_seconds": 1.0, "peak_memory_mb": 50.0},
        "REPLAY_REFIT": {"cpu_seconds": 3.0, "peak_memory_mb": 80.0},
        "FAMILY_SWITCH": {"cpu_seconds": 5.0, "peak_memory_mb": 120.0},
    }

    ranked = rank_actions(table, "task", evidence, tuple(costs), costs)
    actions = [item.action for item in ranked]

    assert "REPLAY_REFIT" not in actions
    assert set(actions) == {"INCREMENTAL_UPDATE", "FAMILY_SWITCH"}


def test_immediate_gate_evidence_does_not_update_delayed_action_value() -> None:
    table = ActionValueTable()
    evidence = _evidence()
    table.record(
        "task",
        evidence,
        _observation("INCREMENTAL_UPDATE", 0.5, source="immediate_gate", confidence="gate_low"),
    )
    immediate = table.stats("task", evidence, "INCREMENTAL_UPDATE")
    assert immediate.attempt_count == 1
    assert immediate.reward_count == 0
    assert immediate.mean_reward == pytest.approx(0.0)

    table.record(
        "task",
        evidence,
        _observation("INCREMENTAL_UPDATE", -0.2, source="delayed_shadow", confidence="paired"),
    )
    delayed = table.stats("task", evidence, "INCREMENTAL_UPDATE")
    assert delayed.attempt_count == 2
    assert delayed.reward_count == 1
    assert delayed.mean_reward == pytest.approx(-0.2)
    assert delayed.high_confidence_count == 1
