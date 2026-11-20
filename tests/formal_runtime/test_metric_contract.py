from __future__ import annotations

import pytest
import numpy as np


def test_metric_contract_rejects_incompatible_direction() -> None:
    from brace_formal.metrics import resolve_metric_contract

    with pytest.raises(ValueError, match="direction"):
        resolve_metric_contract(
            {"task": "classification", "metric": "macro_f1", "metric_direction": "lower"},
            "classification",
        )
    with pytest.raises(ValueError, match="direction"):
        resolve_metric_contract(
            {"task": "regression", "metric": "rmse", "metric_direction": "higher"},
            "regression",
        )


def test_metric_contract_rejects_unknown_metric_without_silent_fallback() -> None:
    from brace_formal.metrics import resolve_metric_contract

    with pytest.raises(ValueError, match="unsupported"):
        resolve_metric_contract(
            {"task": "regression", "metric": "mystery", "metric_direction": "lower"},
            "regression",
        )


def test_primary_evidence_uses_metric_direction_and_scope() -> None:
    from brace_formal.metrics import primary_evidence, resolve_metric_contract

    higher = resolve_metric_contract(
        {"task": "classification", "metric": "macro_f1", "metric_direction": "higher"},
        "classification",
    )
    evidence = primary_evidence(
        higher,
        {"macro_f1": 0.80},
        {"macro_f1": 0.75},
        parent_validation_sha256="sha256:scope-a",
        candidate_validation_sha256="sha256:scope-a",
    )
    assert evidence["signed_gain"] == pytest.approx(-0.05)
    assert evidence["relation"] == "regressed"
    assert evidence["validation_sha256"] == "sha256:scope-a"

    lower = resolve_metric_contract(
        {"task": "regression", "metric": "rmse", "metric_direction": "lower"},
        "regression",
    )
    evidence = primary_evidence(
        lower,
        {"rmse": 680.0},
        {"rmse": 350.0},
        parent_validation_sha256="sha256:scope-b",
        candidate_validation_sha256="sha256:scope-b",
    )
    assert evidence["signed_gain"] == pytest.approx(330.0)
    assert evidence["relation"] == "improved"


@pytest.mark.parametrize(
    ("task", "metric", "direction", "parent", "candidate"),
    [
        ("classification", "macro_f1", "higher", 0.9213, 0.8805),
        ("regression", "rmse", "lower", 660.81, 675.55),
        ("regression", "rmse", "lower", 52.71, 52.94),
    ],
)
def test_official_report_regression_examples_are_machine_classified(
    task: str,
    metric: str,
    direction: str,
    parent: float,
    candidate: float,
) -> None:
    from brace_formal.metrics import primary_evidence, resolve_metric_contract

    contract = resolve_metric_contract(
        {"task": task, "metric": metric, "metric_direction": direction},
        task,
    )
    evidence = primary_evidence(
        contract,
        {metric: parent},
        {metric: candidate},
        parent_validation_sha256="sha256:official-report-same-round",
        candidate_validation_sha256="sha256:official-report-same-round",
    )

    assert evidence["relation"] == "regressed"
    assert evidence["signed_gain"] < 0.0


def test_primary_evidence_rejects_different_validation_scopes() -> None:
    from brace_formal.metrics import primary_evidence, resolve_metric_contract

    contract = resolve_metric_contract(
        {"task": "regression", "metric": "rmse", "metric_direction": "lower"},
        "regression",
    )
    with pytest.raises(ValueError, match="scope"):
        primary_evidence(
            contract,
            {"rmse": 10.0},
            {"rmse": 9.0},
            parent_validation_sha256="sha256:old",
            candidate_validation_sha256="sha256:new",
        )


def test_explicit_rmse_nasa_contract_adds_directional_auxiliary_metrics(tmp_path) -> None:
    from brace_formal.metrics import evaluate, resolve_metric_contract
    from brace_formal.model import FormalModel
    from test_submission import _write_parent

    checkpoint = tmp_path / "checkpoint.npz"
    _write_parent(checkpoint, task="regression")
    model = FormalModel.load(checkpoint)
    contract = resolve_metric_contract(
        {"task": "regression", "metric": "rmse_nasa", "metric_direction": "lower"},
        "regression",
    )
    values = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=np.float64)
    targets = np.asarray([10.0, 20.0], dtype=np.float64)

    metrics = evaluate(model, values, targets, metric_contract=contract)

    assert contract.name == "rmse"
    assert contract.metric_directions == {
        "rmse": "lower",
        "mae": "lower",
        "nasa_score": "lower",
        "nasa_score_mean": "lower",
    }
    assert set(metrics) == set(contract.metric_directions)
    assert all(np.isfinite(value) for value in metrics.values())

