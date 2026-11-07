"""Platform-neutral task initialization and compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike

from .modeling import CpuModelAdapter, ModelFamily, TaskKind


class TaskIncompatibleError(ValueError):
    """Raised when a stable model cannot legally serve a new task."""


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    task_kind: TaskKind
    n_features: int


@dataclass(frozen=True)
class TaskSignature:
    task_kind: TaskKind
    n_features: int
    label_space: tuple[object, ...] | None


@dataclass(frozen=True)
class BootstrapResult:
    model: CpuModelAdapter
    signature: TaskSignature


def _python_scalar(value: object) -> object:
    return value.item() if isinstance(value, np.generic) else value


class TaskBootstrap:
    def __init__(self, *, seed: int, initial_family: ModelFamily = "sgd") -> None:
        self.seed = seed
        self.initial_family = initial_family

    def initialize(
        self, definition: TaskDefinition, X: ArrayLike, y: ArrayLike
    ) -> BootstrapResult:
        X_array = np.asarray(X, dtype=np.float64)
        y_array = np.asarray(y)
        if X_array.ndim != 2 or X_array.shape[1] != definition.n_features:
            raise ValueError("training feature count does not match task definition")
        if y_array.ndim != 1 or len(y_array) != len(X_array) or len(y_array) == 0:
            raise ValueError("training targets must be a nonempty aligned vector")
        if not np.all(np.isfinite(X_array)) or not np.all(np.isfinite(y_array)):
            raise ValueError("training data contains non-finite values")
        label_space: tuple[object, ...] | None = None
        if definition.task_kind == "classification":
            labels = np.unique(y_array)
            if len(labels) < 2:
                raise ValueError("classification bootstrap requires at least two classes")
            label_space = tuple(_python_scalar(value) for value in labels)
        model = CpuModelAdapter(
            task_kind=definition.task_kind,
            family=self.initial_family,
            seed=self.seed,
        ).fit(X_array, y_array)
        return BootstrapResult(
            model=model,
            signature=TaskSignature(
                definition.task_kind, definition.n_features, label_space
            ),
        )

    def ensure_compatible(
        self,
        signature: TaskSignature,
        definition: TaskDefinition,
        *,
        observed_labels: Iterable[object] | None,
    ) -> None:
        if signature.task_kind != definition.task_kind:
            raise TaskIncompatibleError("task kind is incompatible with stable model")
        if signature.n_features != definition.n_features:
            raise TaskIncompatibleError("feature count is incompatible with stable model")
        if definition.task_kind == "classification":
            observed = {_python_scalar(value) for value in (observed_labels or ())}
            known = set(signature.label_space or ())
            if not observed.issubset(known):
                raise TaskIncompatibleError("label space is incompatible with stable model")
