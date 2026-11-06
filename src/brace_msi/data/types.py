"""Common immutable containers used by proxy-data adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

TaskKind = Literal["classification", "regression"]


@dataclass(frozen=True)
class BatchData:
    """One legally visible batch with opaque sample identities."""

    batch_id: str
    X: NDArray[np.float64]
    y: NDArray[np.float64] | NDArray[np.int64]
    sample_ids: tuple[str, ...]
    group_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.X.ndim != 2 or self.y.ndim != 1:
            raise ValueError("X must be 2D and y must be 1D")
        if len(self.X) != len(self.y) or len(self.y) != len(self.sample_ids):
            raise ValueError("features, targets, and sample IDs must have equal length")
        if len(set(self.sample_ids)) != len(self.sample_ids):
            raise ValueError("sample IDs must be unique within a batch")
        if self.group_ids and len(self.group_ids) != len(self.y):
            raise ValueError("group IDs must be empty or match the sample count")


@dataclass(frozen=True)
class TaskStream:
    """Frozen local split: initial training, development stream, sealed stream."""

    task_id: str
    task_kind: TaskKind
    initial: BatchData
    development: tuple[BatchData, ...]
    sealed: tuple[BatchData, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def all_sample_ids_are_disjoint(self) -> bool:
        batches = (self.initial, *self.development, *self.sealed)
        sample_ids = [sample_id for batch in batches for sample_id in batch.sample_ids]
        return len(sample_ids) == len(set(sample_ids))
