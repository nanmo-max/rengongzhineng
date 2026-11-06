from __future__ import annotations


def _evidence(*, drop: float, drift: float):
    from brace_msi.evidence import Evidence

    return Evidence(
        current_metric=0.5,
        reference_metric=0.8,
        performance_drop=drop,
        drift_score=drift,
        sample_count=100,
    )


def test_static_policy_never_trains() -> None:
    from brace_msi.policies import Action, PolicyContext, StaticPolicy

    action = StaticPolicy().choose(
        PolicyContext(batch_index=1, evidence=_evidence(drop=1.0, drift=1.0))
    )

    assert action is Action.NOOP


def test_performance_triggered_policy_uses_one_low_cost_action() -> None:
    from brace_msi.policies import Action, PerformanceTriggeredPolicy, PolicyContext

    policy = PerformanceTriggeredPolicy(performance_drop_threshold=0.2)

    assert policy.choose(PolicyContext(1, _evidence(drop=0.1, drift=1.0))) is Action.NOOP
    assert (
        policy.choose(PolicyContext(2, _evidence(drop=0.3, drift=0.0)))
        is Action.INCREMENTAL_UPDATE
    )


def test_brace_policy_selects_action_from_evidence_and_feedback() -> None:
    from brace_msi.policies import Action, BracePolicy, PolicyContext

    policy = BracePolicy(
        update_drop_threshold=0.1,
        refit_drop_threshold=0.5,
        drift_threshold=0.2,
        high_drift_threshold=0.8,
    )

    assert policy.choose(PolicyContext(1, _evidence(drop=0.0, drift=0.0))) is Action.NOOP
    assert (
        policy.choose(PolicyContext(2, _evidence(drop=0.2, drift=0.1)))
        is Action.INCREMENTAL_UPDATE
    )
    policy.observe(Action.INCREMENTAL_UPDATE, accepted=False, improvement=-0.1)
    assert (
        policy.choose(PolicyContext(3, _evidence(drop=0.2, drift=0.1)))
        is Action.REPLAY_REFIT
    )
    policy.observe(Action.REPLAY_REFIT, accepted=True, improvement=0.2)
    assert (
        policy.choose(PolicyContext(4, _evidence(drop=0.6, drift=0.1)))
        is Action.REPLAY_REFIT
    )
