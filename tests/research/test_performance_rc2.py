from __future__ import annotations

from pathlib import Path

import numpy as np

from brace_formal.data import DataBatch
from brace_formal.metrics import resolve_metric_contract
from brace_formal.model import FormalModel
from tests.competition_core.support import write_parent


def _model(tmp_path: Path, task: str, feature_count: int = 4) -> FormalModel:
    path = tmp_path / f"{task}.npz"
    write_parent(path, task=task, feature_count=feature_count)
    return FormalModel.load(path)


def _batch(task: str, prefix: str, offset: float = 0.0, count: int = 24) -> DataBatch:
    x = np.asarray(
        [[offset + index / 10.0, float(index % 3), float((index * 2) % 5), 1.0] for index in range(count)],
        dtype=np.float64,
    )
    y = (
        np.asarray([index % 2 for index in range(count)], dtype=np.int64)
        if task == "classification"
        else np.asarray([offset + index * 0.7 for index in range(count)], dtype=np.float64)
    )
    return DataBatch(tuple(f"{prefix}-{index}" for index in range(count)), x, y, prefix * 64)


def test_adaptive_normalizer_preserves_predictions_before_training(tmp_path: Path) -> None:
    from brace_msi.performance_rc2 import reparameterize_normalizer

    model = _model(tmp_path, "regression")
    batch = _batch("regression", "a", offset=3.0)
    before = model.predict_raw(batch.x)

    receipt = reparameterize_normalizer(model, batch.x, blend=0.5)

    np.testing.assert_allclose(model.predict_raw(batch.x), before, rtol=0.0, atol=1e-10)
    assert receipt["updated_features"] > 0
    assert receipt["max_prediction_delta"] <= 1e-10
    assert all(np.count_nonzero(model.first[name]) == 0 for name in ("w1", "b1"))
    assert all(np.count_nonzero(model.second[name]) == 0 for name in ("w1", "b1"))


def test_recent_weighted_training_uses_updates_only_and_current_has_highest_weight() -> None:
    from brace_msi.performance_rc2 import recent_weighted_training

    old = _batch("regression", "a", 0.0, 4)
    recent = _batch("regression", "b", 1.0, 4)
    current = _batch("regression", "c", 2.0, 4)

    combined, weights = recent_weighted_training([old, recent], current, limit=2, decay=0.5)

    assert combined.ids == (*old.ids, *recent.ids, *current.ids)
    np.testing.assert_array_equal(weights, np.asarray([0.25] * 4 + [0.5] * 4 + [1.0] * 4))


def test_rc2_recipe_catalog_routes_only_by_task_contract() -> None:
    from brace_msi.performance_rc2 import recipes_for_task

    classification = recipes_for_task("classification")
    regression = recipes_for_task("regression")

    assert {item.recipe_id for item in classification} == {
        "native_current_e3",
        "balanced_current_e3",
        "adaptive_balanced_e3",
        "adaptive_recent_e3",
    }
    assert {item.recipe_id for item in regression} == {
        "mse_current_e3_lr3",
        "huber_recent_e3",
        "asymmetric_recent_e3",
        "adaptive_recent_mse_e3_lr3",
    }
    assert all("gas" not in item.recipe_id and "bearing" not in item.recipe_id and "engine" not in item.recipe_id for item in (*classification, *regression))


def test_robust_selector_requires_positive_median_and_mean(tmp_path: Path) -> None:
    from brace_msi.performance_rc2 import CandidateEvidence, select_robust_candidate

    contract = resolve_metric_contract(None, "regression")
    candidates = [
        CandidateEvidence("unstable", object(), (3.0, 2.0, -8.0), 1.0, 0.2, 0.0, {}),
        CandidateEvidence("stable", object(), (1.0, 1.0, 0.5), 1.0, 0.2, 0.0, {}),
    ]

    selected = select_robust_candidate(contract, candidates)

    assert selected is not None
    assert selected.candidate_id == "stable"


def test_robust_selector_keeps_parent_when_candidates_lack_positive_evidence() -> None:
    from brace_msi.performance_rc2 import CandidateEvidence, select_robust_candidate

    contract = resolve_metric_contract(None, "classification")
    candidates = [CandidateEvidence("flat", object(), (0.0, 0.0, 0.0), 0.1, 0.1, 0.0, {})]

    assert select_robust_candidate(contract, candidates) is None


def test_fit_research_candidate_keeps_parent_schema_and_records_method(tmp_path: Path) -> None:
    from brace_msi.performance_rc2 import fit_research_candidate, recipes_for_task

    parent = _model(tmp_path, "classification")
    current = _batch("classification", "c")
    recipe = next(item for item in recipes_for_task("classification") if item.recipe_id == "adaptive_balanced_e3")

    result = fit_research_candidate(parent, recipe, current, [])

    result.model.validate()
    assert result.model.meta["parameter_count"] == parent.meta["parameter_count"]
    assert result.receipt["recipe_id"] == "adaptive_balanced_e3"
    assert result.receipt["normalizer"]["updated_features"] > 0
