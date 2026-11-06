"""Capability-declared lightweight CPU models for local proxy experiments."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, Self

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.linear_model import SGDClassifier, SGDRegressor
from sklearn.preprocessing import StandardScaler

TaskKind = Literal["classification", "regression"]


@dataclass(frozen=True)
class ModelCapabilities:
    task_kind: TaskKind
    supports_partial_fit: bool
    supports_predict_proba: bool
    supports_warm_start: bool
    supports_calibration: bool
    supports_serialization: bool


class SklearnModelAdapter:
    """SGD model with a scaler frozen between full refits."""

    def __init__(self, *, task_kind: TaskKind, seed: int) -> None:
        self.task_kind = task_kind
        self.seed = seed
        self.scaler = StandardScaler()
        self.estimator = self._new_estimator()
        self.is_fitted = False

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            task_kind=self.task_kind,
            supports_partial_fit=True,
            supports_predict_proba=self.task_kind == "classification",
            supports_warm_start=False,
            supports_calibration=False,
            supports_serialization=True,
        )

    def _new_estimator(self) -> SGDClassifier | SGDRegressor:
        if self.task_kind == "classification":
            return SGDClassifier(
                loss="log_loss", max_iter=1000, tol=1e-3, random_state=self.seed
            )
        if self.task_kind == "regression":
            return SGDRegressor(
                loss="huber",
                max_iter=2000,
                tol=1e-3,
                random_state=self.seed,
                learning_rate="adaptive",
                eta0=0.01,
            )
        raise ValueError(f"unsupported task kind: {self.task_kind}")

    def fit(self, X: ArrayLike, y: ArrayLike) -> Self:
        X_array = np.asarray(X, dtype=np.float64)
        y_array = np.asarray(y)
        transformed = self.scaler.fit_transform(X_array)
        self.estimator = self._new_estimator()
        self.estimator.fit(transformed, y_array)
        self.is_fitted = True
        return self

    def partial_fit(self, X: ArrayLike, y: ArrayLike) -> Self:
        self._require_fitted()
        transformed = self.scaler.transform(np.asarray(X, dtype=np.float64))
        self.estimator.partial_fit(transformed, np.asarray(y))
        return self

    def predict(self, X: ArrayLike) -> NDArray[np.float64] | NDArray[np.int64]:
        self._require_fitted()
        transformed = self.scaler.transform(np.asarray(X, dtype=np.float64))
        return np.asarray(self.estimator.predict(transformed))

    def predict_proba(self, X: ArrayLike) -> NDArray[np.float64]:
        self._require_fitted()
        if self.task_kind != "classification":
            raise TypeError("predict_proba is available only for classification")
        transformed = self.scaler.transform(np.asarray(X, dtype=np.float64))
        return np.asarray(self.estimator.predict_proba(transformed))

    def clone(self) -> Self:
        return deepcopy(self)

    def refit(self, X: ArrayLike, y: ArrayLike) -> Self:
        return type(self)(task_kind=self.task_kind, seed=self.seed).fit(X, y)

    def _require_fitted(self) -> None:
        if not self.is_fitted:
            raise RuntimeError("model must be fitted before this operation")
