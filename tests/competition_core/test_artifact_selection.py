from __future__ import annotations

import pytest


def _contract(task: str = "classification"):
    from brace_formal.metrics import resolve_metric_contract

    if task == "classification":
        return resolve_metric_contract(
            {"task": task, "metric": "macro_f1", "metric_direction": "higher"}, task
        )
    return resolve_metric_contract(
        {"task": task, "metric": "rmse", "metric_direction": "lower"}, task
    )


def _evaluation(
    artifact_id: str,
    role: str,
    metrics: dict[str, float],
    *,
    scope: str = "sha256:current-scope",
    resources: dict[str, float] | None = None,
    hard_failures: tuple[str, ...] = (),
):
    from brace_formal.selection import ArtifactEvaluation

    return ArtifactEvaluation(
        artifact_id=artifact_id,
        role=role,
        metrics=metrics,
        validation_sha256=scope,
        resource_evidence=resources or {},
        hard_failures=hard_failures,
    )


def test_higher_is_better_and_wrong_qwen_arithmetic_cannot_deploy_regression() -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract(),
        [
            _evaluation("parent", "parent", {"macro_f1": 0.9213, "accuracy": 0.93}),
            _evaluation("candidate", "candidate", {"macro_f1": 0.8805, "accuracy": 0.90}),
        ],
        requested_artifact_id="candidate",
    )

    assert result.requested_artifact_id == "candidate"
    assert result.applied_artifact_id == "parent"
    assert result.relation_to_parent == "unchanged"
    assert result.request_honored is False
    assert "worse" in result.reason


@pytest.mark.parametrize(
    ("task", "parent_value", "candidate_value"),
    [
        ("regression", 660.81, 675.55),
        ("regression", 52.71, 52.94),
        ("regression", 52.868573, 55.629944),
    ],
)
def test_frozen_official_and_rc_counterexamples_never_apply_worse_candidate(
    task: str, parent_value: float, candidate_value: float
) -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract(task),
        [
            _evaluation("parent", "parent", {"rmse": parent_value, "mae": parent_value / 2}),
            _evaluation("candidate", "candidate", {"rmse": candidate_value, "mae": candidate_value / 2}),
        ],
        requested_artifact_id="candidate",
    )

    assert result.applied_artifact_id == "parent"
    assert result.request_honored is False


def test_lower_is_better_for_regression() -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract("regression"),
        [
            _evaluation("parent", "parent", {"rmse": 42.0, "mae": 30.0}),
            _evaluation("candidate", "candidate", {"rmse": 35.0, "mae": 25.0}),
        ],
        requested_artifact_id="candidate",
    )

    assert result.applied_artifact_id == "candidate"
    assert result.relation_to_parent == "improved"
    assert result.request_honored is True


def test_equal_primary_uses_declared_auxiliary_then_measured_cost() -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract(),
        [
            _evaluation(
                "parent",
                "parent",
                {"macro_f1": 0.8, "accuracy": 0.84},
                resources={"cpu_seconds": 1.0},
            ),
            _evaluation(
                "candidate-aux",
                "candidate",
                {"macro_f1": 0.8, "accuracy": 0.86},
                resources={"cpu_seconds": 9.0},
            ),
            _evaluation(
                "candidate-cheap",
                "candidate",
                {"macro_f1": 0.8, "accuracy": 0.86},
                resources={"cpu_seconds": 2.0},
            ),
        ],
        requested_artifact_id="candidate-aux",
    )

    assert result.applied_artifact_id == "candidate-cheap"
    assert result.relation_to_parent == "improved_auxiliary"
    assert result.request_honored is False


def test_changed_validation_fingerprint_excludes_historical_artifact() -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract(),
        [
            _evaluation("parent", "parent", {"macro_f1": 0.8, "accuracy": 0.8}),
            _evaluation(
                "history-old",
                "history",
                {"macro_f1": 0.99, "accuracy": 0.99},
                scope="sha256:old-scope",
            ),
        ],
        requested_artifact_id="history-old",
    )

    assert result.applied_artifact_id == "parent"
    assert result.comparable_artifact_ids == ("parent",)
    assert result.excluded_artifacts["history-old"] == "validation_scope_mismatch"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_primary_metric_is_excluded(value: float) -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract(),
        [
            _evaluation("parent", "parent", {"macro_f1": 0.7, "accuracy": 0.7}),
            _evaluation("candidate", "candidate", {"macro_f1": value, "accuracy": 0.9}),
        ],
        requested_artifact_id="candidate",
    )

    assert result.applied_artifact_id == "parent"
    assert result.excluded_artifacts["candidate"] == "primary_metric_not_finite"


def test_unloadable_artifact_is_excluded_by_official_hard_failure() -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract(),
        [
            _evaluation("parent", "parent", {"macro_f1": 0.7, "accuracy": 0.7}),
            _evaluation(
                "candidate",
                "candidate",
                {"macro_f1": 0.99, "accuracy": 0.99},
                hard_failures=("artifact_unloadable",),
            ),
        ],
        requested_artifact_id="candidate",
    )

    assert result.applied_artifact_id == "parent"
    assert result.excluded_artifacts["candidate"] == "hard_failure:artifact_unloadable"


def test_valid_same_scope_historical_artifact_can_be_selected_as_rollback() -> None:
    from brace_formal.selection import select_artifact

    result = select_artifact(
        _contract("regression"),
        [
            _evaluation("parent", "parent", {"rmse": 45.0, "mae": 30.0}),
            _evaluation("candidate", "candidate", {"rmse": 46.0, "mae": 31.0}),
            _evaluation("history", "history", {"rmse": 40.0, "mae": 28.0}),
        ],
        requested_artifact_id="history",
    )

    assert result.applied_artifact_id == "history"
    assert result.applied_role == "history"
    assert result.relation_to_parent == "improved"
    assert result.request_honored is True


def test_requires_exactly_one_valid_parent_reference() -> None:
    from brace_formal.selection import select_artifact

    with pytest.raises(ValueError, match="parent"):
        select_artifact(
            _contract(),
            [_evaluation("candidate", "candidate", {"macro_f1": 0.8, "accuracy": 0.8})],
            requested_artifact_id="candidate",
        )

