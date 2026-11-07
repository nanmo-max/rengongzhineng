"""Capability-declared CPU model adapters used by the deterministic Harness."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Self

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge, SGDClassifier, SGDRegressor
from sklearn.preprocessing import StandardScaler

TaskKind = Literal["classification", "regression"]
ModelFamily = Literal["sgd", "linear", "hist_gradient_boosting", "extra_trees"]


@dataclass(frozen=True)
class ModelCapabilities:
    task_kind: TaskKind
    supports_partial_fit: bool
    supports_predict_proba: bool
    supports_warm_start: bool
    supports_calibration: bool
    supports_serialization: bool


@dataclass(frozen=True)
class ModelSpec:
    family: ModelFamily
    task_kind: TaskKind
    capabilities: ModelCapabilities
    params: Mapping[str, Any] = field(default_factory=dict)

    def create(self, *, seed: int) -> "CpuModelAdapter":
        return CpuModelAdapter(
            task_kind=self.task_kind,
            family=self.family,
            seed=seed,
            params=self.params,
        )


def _capabilities(task_kind: TaskKind, family: ModelFamily) -> ModelCapabilities:
    return ModelCapabilities(
        task_kind=task_kind,
        supports_partial_fit=family == "sgd",
        supports_predict_proba=task_kind == "classification",
        supports_warm_start=family in {"hist_gradient_boosting", "extra_trees"},
        supports_calibration=False,
        supports_serialization=True,
    )


def cpu_model_pool(task_kind: TaskKind) -> tuple[ModelSpec, ...]:
    """Return the finite, auditable model families available to the Harness."""

    families: tuple[ModelFamily, ...] = (
        "sgd",
        "linear",
        "hist_gradient_boosting",
        "extra_trees",
    )
    return tuple(
        ModelSpec(family, task_kind, _capabilities(task_kind, family))
        for family in families
    )


class CpuModelAdapter:
    """Uniform adapter that never claims unsupported incremental behavior."""

    def __init__(
        self,
        *,
        task_kind: TaskKind,
        family: ModelFamily,
        seed: int,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        if family not in {spec.family for spec in cpu_model_pool(task_kind)}:
            raise ValueError(f"unsupported model family: {family}")
        self.task_kind = task_kind
        self.family = family
        self.seed = seed
        self.params = dict(params or {})
        self.scaler = StandardScaler() if family in {"sgd", "linear"} else None
        self.estimator = self._new_estimator()
        self.is_fitted = False

    @property
    def capabilities(self) -> ModelCapabilities:
        return _capabilities(self.task_kind, self.family)

    def _new_estimator(self):
        params = dict(self.params)
        if self.family == "sgd":
            if self.task_kind == "classification":
                defaults = dict(loss="log_loss", max_iter=1000, tol=1e-3)
                return SGDClassifier(random_state=self.seed, **(defaults | params))
            defaults = dict(
                loss="huber",
                max_iter=2000,
                tol=1e-3,
                learning_rate="adaptive",
                eta0=0.01,
            )
            return SGDRegressor(random_state=self.seed, **(defaults | params))
        if self.family == "linear":
            if self.task_kind == "classification":
                return LogisticRegression(
                    random_state=self.seed, max_iter=1000, **params
                )
            return Ridge(**params)
        if self.family == "hist_gradient_boosting":
            if self.task_kind == "classification":
                return HistGradientBoostingClassifier(random_state=self.seed, **params)
            return HistGradientBoostingRegressor(random_state=self.seed, **params)
        if self.family == "extra_trees":
            defaults = dict(n_estimators=100, n_jobs=1)
            if self.task_kind == "classification":
                return ExtraTreesClassifier(
                    random_state=self.seed, **(defaults | params)
                )
            return ExtraTreesRegressor(random_state=self.seed, **(defaults | params))
        raise ValueError(f"unsupported model family: {self.family}")

    def _transform_fit(self, X: NDArray[np.float64]) -> NDArray[np.float64]:
        return self.scaler.fit_transform(X) if self.scaler is not None else X

    def _transform(self, X: NDArray[np.float64]) -> NDArray[np.float64]:
        return self.scaler.transform(X) if self.scaler is not None else X

    def fit(self, X: ArrayLike, y: ArrayLike) -> Self:
        X_array = np.asarray(X, dtype=np.float64)
        y_array = np.asarray(y)
        transformed = self._transform_fit(X_array)
        self.estimator = self._new_estimator()
        self.estimator.fit(transformed, y_array)
        self.is_fitted = True
        return self

    def partial_fit(self, X: ArrayLike, y: ArrayLike) -> Self:
        self._require_fitted()
        if not self.capabilities.supports_partial_fit:
            raise TypeError(f"model family {self.family} does not support partial_fit")
        transformed = self._transform(np.asarray(X, dtype=np.float64))
        self.estimator.partial_fit(transformed, np.asarray(y))
        return self

    def predict(self, X: ArrayLike) -> NDArray[np.float64] | NDArray[np.int64]:
        self._require_fitted()
        transformed = self._transform(np.asarray(X, dtype=np.float64))
        return np.asarray(self.estimator.predict(transformed))

    def predict_proba(self, X: ArrayLike) -> NDArray[np.float64]:
        self._require_fitted()
        if not self.capabilities.supports_predict_proba:
            raise TypeError("predict_proba is available only for classification")
        transformed = self._transform(np.asarray(X, dtype=np.float64))
        return np.asarray(self.estimator.predict_proba(transformed))

    def clone(self) -> Self:
        return deepcopy(self)

    def refit(self, X: ArrayLike, y: ArrayLike) -> Self:
        return type(self)(
            task_kind=self.task_kind,
            family=self.family,
            seed=self.seed,
            params=self.params,
        ).fit(X, y)

    def _require_fitted(self) -> None:
        if not self.is_fitted:
            raise RuntimeError("model must be fitted before this operation")


class SklearnModelAdapter(CpuModelAdapter):
    """Backward-compatible default SGD adapter for existing proxy runs."""

    def __init__(self, *, task_kind: TaskKind, seed: int) -> None:
        super().__init__(task_kind=task_kind, family="sgd", seed=seed)

    def refit(self, X: ArrayLike, y: ArrayLike) -> Self:
        return type(self)(task_kind=self.task_kind, seed=self.seed).fit(X, y)
