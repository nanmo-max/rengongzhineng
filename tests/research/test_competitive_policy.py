from __future__ import annotations

from brace_msi.competitive_policy import PortfolioEvidence, build_candidate_plan
from scripts.run_portfolio_runtime_replay import _experiment_id


def test_classification_plan_uses_safe_primary_and_recent_secondary() -> None:
    plan = build_candidate_plan(
        PortfolioEvidence(
            task_kind="classification",
            target_batch_means=(0.2, 0.4, 0.3),
            target_scale=1.0,
            previous_delayed_gain=0.01,
            failure_streak=0,
        )
    )

    assert plan.primary_recipe == "soup_current_e3_alpha0.25"
    assert plan.secondary_recipe == "recent_e3"
    assert "dataset" not in plan.rationale.lower()


def test_monotonic_regression_plan_selects_local_high_step_candidate() -> None:
    plan = build_candidate_plan(
        PortfolioEvidence(
            task_kind="regression",
            target_batch_means=(1400.0, 1250.0, 1100.0, 950.0),
            target_scale=780.0,
            previous_delayed_gain=20.0,
            failure_streak=0,
        )
    )

    assert plan.secondary_recipe == "current_e3_lr3"
    assert plan.monotonic_trend_score > 0.8


def test_unstable_or_failed_regression_stays_conservative() -> None:
    plan = build_candidate_plan(
        PortfolioEvidence(
            task_kind="regression",
            target_batch_means=(106.0, 122.0, 126.0, 96.0),
            target_scale=84.0,
            previous_delayed_gain=-0.2,
            failure_streak=1,
        )
    )

    assert plan.primary_recipe == "soup_current_e3_alpha0.25"
    assert plan.secondary_recipe is None


def test_runtime_replay_uses_output_directory_as_experiment_id(tmp_path) -> None:
    assert _experiment_id(tmp_path / "COMPETITIVE-POLICY-002-A6") == (
        "COMPETITIVE-POLICY-002-A6"
    )


