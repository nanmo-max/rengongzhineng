from __future__ import annotations

import numpy as np


def test_classifier_declares_capabilities_and_supports_incremental_update() -> None:
    from brace_msi.modeling import SklearnModelAdapter

    X = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
    y = np.asarray([0, 0, 1, 1])
    model = SklearnModelAdapter(task_kind="classification", seed=20261106)

    model.fit(X, y)
    before = model.predict(np.asarray([[0.25]]))[0]
    model.partial_fit(np.asarray([[0.2], [0.3]]), np.asarray([0, 0]))
    after = model.predict(np.asarray([[0.25]]))[0]

    assert model.capabilities.task_kind == "classification"
    assert model.capabilities.supports_partial_fit is True
    assert model.capabilities.supports_predict_proba is True
    assert model.is_fitted is True
    assert before in {0, 1}
    assert after in {0, 1}


def test_regressor_refit_returns_independent_fitted_candidate() -> None:
    from brace_msi.modeling import SklearnModelAdapter

    X = np.arange(12, dtype=float).reshape(-1, 1)
    y = 2 * X[:, 0] + 1
    stable = SklearnModelAdapter(task_kind="regression", seed=20261106).fit(X, y)

    candidate = stable.refit(X, y + 10)

    assert stable.capabilities.task_kind == "regression"
    assert stable.capabilities.supports_partial_fit is True
    assert stable.capabilities.supports_predict_proba is False
    assert candidate is not stable
    assert candidate.is_fitted is True
    assert not np.allclose(candidate.predict(X), stable.predict(X))


def test_clone_preserves_stable_model_when_candidate_is_updated() -> None:
    from brace_msi.modeling import SklearnModelAdapter

    X = np.asarray([[-1.0], [0.0], [1.0], [2.0]])
    y = np.asarray([0, 0, 1, 1])
    stable = SklearnModelAdapter(task_kind="classification", seed=20261106).fit(X, y)
    stable_predictions = stable.predict(X).copy()

    candidate = stable.clone()
    candidate.partial_fit(np.asarray([[3.0], [4.0]]), np.asarray([0, 0]))

    np.testing.assert_array_equal(stable.predict(X), stable_predictions)
    assert candidate is not stable
