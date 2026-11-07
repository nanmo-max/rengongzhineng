"""Bounded replay and finite CPU candidate search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence, cast

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.metrics import accuracy_score, mean_squared_error

from .budget import BudgetLedger
from .modeling import CpuModelAdapter, ModelFamily, TaskKind
from .resources import ResourceTracker, ResourceUsage


class ReplayBuffer:
    def __init__(self, *, max_samples: int) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be positive")
        self.max_samples = max_samples
        self._features: list[NDArray[np.float64]] = []
        self._targets: list[NDArray] = []

    def append(self, X: ArrayLike, y: ArrayLike) -> None:
        features = np.asarray(X, dtype=np.float64)
        targets = np.asarray(y)
        if features.ndim != 2 or targets.ndim != 1 or len(features) != len(targets):
            raise ValueError("replay data must be aligned matrix and vector")
        self._features.append(features)
        self._targets.append(targets)
        combined_X = np.concatenate(self._features)
        combined_y = np.concatenate(self._targets)
        self._features = [combined_X[-self.max_samples :]]
        self._targets = [combined_y[-self.max_samples :]]

    def arrays(self) -> tuple[NDArray[np.float64], NDArray]:
        if not self._targets:
            raise RuntimeError("replay buffer is empty")
        return self._features[0].copy(), self._targets[0].copy()


@dataclass(frozen=True)
class CandidateConfig:
    family: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class SearchConfig:
    max_trials: int = 4
    patience: int = 2
    min_improvement: float = 0.0


@dataclass(frozen=True)
class SearchTrial:
    family: str
    score: float | None
    status: str
    usage: ResourceUsage


@dataclass(frozen=True)
class SearchResult:
    best_model: CpuModelAdapter | None
    best_score: float | None
    trials: tuple[SearchTrial, ...]
    stopped_reason: str


def _score(task_kind: TaskKind, targets: NDArray, predictions: NDArray) -> float:
    if task_kind == "classification":
        return float(accuracy_score(targets, predictions))
    return -float(mean_squared_error(targets, predictions) ** 0.5)


class BoundedSearch:
    def __init__(self, *, task_kind: TaskKind, seed: int, config: SearchConfig) -> None:
        if config.max_trials < 1 or config.patience < 1:
            raise ValueError("search limits must be positive")
        self.task_kind = task_kind
        self.seed = seed
        self.config = config

    def run(
        self,
        *,
        candidates: Sequence[CandidateConfig],
        train_X: ArrayLike,
        train_y: ArrayLike,
        validation_X: ArrayLike,
        validation_y: ArrayLike,
        ledger: BudgetLedger,
    ) -> SearchResult:
        train_features = np.asarray(train_X, dtype=np.float64)
        train_targets = np.asarray(train_y)
        validation_features = np.asarray(validation_X, dtype=np.float64)
        validation_targets = np.asarray(validation_y)
        best_model: CpuModelAdapter | None = None
        best_score: float | None = None
        trials: list[SearchTrial] = []
        without_improvement = 0
        stopped_reason = "candidate_space_exhausted"

        for candidate_config in candidates[: self.config.max_trials]:
            budget = ledger.check_before_training(estimated_samples=len(train_targets))
            if not budget.allowed:
                stopped_reason = budget.reason
                break
            tracker: ResourceTracker | None = None
            model: CpuModelAdapter | None = None
            score: float | None = None
            status = "failed"
            try:
                with ResourceTracker() as tracker:
                    model = CpuModelAdapter(
                        task_kind=self.task_kind,
                        family=cast(ModelFamily, candidate_config.family),
                        seed=self.seed,
                        params=candidate_config.params,
                    ).fit(train_features, train_targets)
                score = _score(
                    self.task_kind,
                    validation_targets,
                    model.predict(validation_features),
                )
                status = "completed"
            except Exception:
                model = None
            usage = (
                tracker.usage
                if tracker is not None and tracker.usage is not None
                else ResourceUsage(0.0, 0.0, 0, 0, 0)
            )
            ledger.record_candidate(usage, training_samples=len(train_targets))
            trials.append(SearchTrial(candidate_config.family, score, status, usage))
            if score is not None and (
                best_score is None
                or score > best_score + self.config.min_improvement
            ):
                best_score = score
                best_model = model
                without_improvement = 0
            else:
                without_improvement += 1
            if without_improvement >= self.config.patience:
                stopped_reason = "patience_exhausted"
                break
        return SearchResult(best_model, best_score, tuple(trials), stopped_reason)
