from dataclasses import fields
import inspect

import pytest

from brace_msi.modeling import ModelCapabilities
from brace_msi.policies import Action
from brace_msi.unified_policy import (
    MetricDescriptor,
    NormalizedEvidence,
    SharedPolicyConfig,
    UnifiedActionPolicy,
    normalized_metric_delta,
)


def _capabilities(*, partial_fit: bool = True) -> ModelCapabilities:
    return ModelCapabilities(
        task_kind="classification",
        supports_partial_fit=partial_fit,
        supports_predict_proba=True,
        supports_warm_start=False,
        supports_calibration=False,
        supports_serialization=True,
    )


def _evidence(**overrides: object) -> NormalizedEvidence:
    values = {
        "training_allowed": True,
        "relative_performance_drop": 0.10,
        "drift_score": 0.20,
        "drift_percentile": 0.60,
        "uncertainty_ratio": 0.05,
        "sample_support": 1.0,
        "failed_actions": 0,
        "remaining_budget_fraction": 1.0,
        "recent_relative_improvement": 0.0,
    }
    values.update(overrides)
    return NormalizedEvidence(**values)


def test_metric_normalization_is_scale_and_direction_invariant() -> None:
    f1_drop = normalized_metric_delta(
        reference=0.80,
        current=0.72,
        descriptor=MetricDescriptor(higher_is_better=True),
    )
    rmse_drop = normalized_metric_delta(
        reference=100.0,
        current=110.0,
        descriptor=MetricDescriptor(higher_is_better=False),
    )

    assert f1_drop == pytest.approx(0.10)
    assert rmse_drop == pytest.approx(0.10)


def test_policy_contract_cannot_receive_task_identity() -> None:
    forbidden = {"task_id", "dataset", "dataset_name", "profile", "batch_id"}
    evidence_fields = {field.name for field in fields(NormalizedEvidence)}
    config_fields = {field.name for field in fields(SharedPolicyConfig)}
    parameters = set(inspect.signature(UnifiedActionPolicy.select).parameters)

    assert forbidden.isdisjoint(evidence_fields)
    assert forbidden.isdisjoint(config_fields)
    assert forbidden.isdisjoint(parameters)


def test_shared_policy_escalates_using_only_evidence_and_capability() -> None:
    policy = UnifiedActionPolicy(
        SharedPolicyConfig(
            update_drop_threshold=0.05,
            refit_drop_threshold=0.20,
            drift_percentile_threshold=0.70,
            high_drift_percentile_threshold=0.90,
            hpo_failure_threshold=2,
            hpo_min_budget_fraction=0.25,
        )
    )

    assert policy.select(_evidence(), _capabilities()) is Action.INCREMENTAL_UPDATE
    assert policy.select(_evidence(), _capabilities(partial_fit=False)) is Action.REPLAY_REFIT
    assert policy.select(_evidence(failed_actions=1), _capabilities()) is Action.REPLAY_REFIT
    assert policy.select(
        _evidence(relative_performance_drop=0.30, failed_actions=2),
        _capabilities(),
    ) is Action.BOUNDED_HPO


def test_shared_policy_stops_for_weak_evidence_or_budget() -> None:
    policy = UnifiedActionPolicy(SharedPolicyConfig())

    assert policy.select(
        _evidence(relative_performance_drop=0.0, drift_percentile=0.0),
        _capabilities(),
    ) is Action.NOOP
    assert policy.select(
        _evidence(remaining_budget_fraction=0.0),
        _capabilities(),
    ) is Action.NOOP
    assert policy.select(
        _evidence(training_allowed=False),
        _capabilities(),
    ) is Action.NOOP


@pytest.mark.parametrize(
    "field,value",
    [
        ("relative_performance_drop", float("nan")),
        ("drift_percentile", 1.1),
        ("remaining_budget_fraction", -0.1),
        ("failed_actions", -1),
    ],
)
def test_normalized_evidence_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _evidence(**{field: value})
