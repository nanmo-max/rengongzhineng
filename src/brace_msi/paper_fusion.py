"""Leakage-safe CPU primitives for the paper-guided performance sprint."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import f1_score, mean_squared_error
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TaskKind = Literal["classification", "regression"]


@dataclass(frozen=True)
class OfficialRow:
    sample_id: str
    features: tuple[float, ...]
    feature_names: tuple[str, ...]
    target: Any
    group: str
    meta: Mapping[str, Any]


@dataclass(frozen=True)
class TeacherSpec:
    family: str
    params: Mapping[str, Any]

    @property
    def id(self) -> str:
        encoded = json.dumps(
            dict(self.params), sort_keys=True, separators=(",", ":")
        )
        return f"{self.family}:{encoded}"


@dataclass(frozen=True)
class TeacherEvaluation:
    spec: TeacherSpec
    primary_metric: float
    stage: str
    oof_predictions: NDArray[np.float64] | NDArray[Any] | None = None


@dataclass(frozen=True)
class HalvingResult:
    finalists: tuple[TeacherEvaluation, ...]
    all_results: tuple[TeacherEvaluation, ...]


@dataclass(frozen=True)
class PaperFusionCandidate:
    task_kind: TaskKind
    teacher_ids: tuple[str, ...]
    weights: Mapping[str, float]
    internal_primary_metric: float


def _flatten_inputs(value: Any, prefix: str = "input") -> tuple[list[str], list[float]]:
    names: list[str] = []
    values: list[float] = []

    def visit(child: Any, path: str) -> None:
        if isinstance(child, dict):
            for key in sorted(child):
                visit(child[key], f"{path}:{key}" if path else str(key))
        elif isinstance(child, list):
            for index, item in enumerate(child):
                visit(item, f"{path}[{index}]")
        elif isinstance(child, (int, float)) and not isinstance(child, bool):
            numeric = float(child)
            if not math.isfinite(numeric):
                raise ValueError("input feature must be finite")
            names.append(path)
            values.append(numeric)
        else:
            raise ValueError("inputs must contain only finite numeric leaves")

    visit(value, prefix)
    return names, values


def _group(profile: str, meta: Mapping[str, Any]) -> str:
    if profile == "A":
        return f"batch:{meta.get('source_batch', '')}"
    if profile == "B":
        group = str(meta.get("bearing", ""))
    elif profile == "C":
        group = f"{meta.get('source_subset', '')}:{meta.get('unit', '')}"
    else:
        raise ValueError(f"unsupported profile: {profile}")
    if not group or group.endswith(":"):
        raise ValueError(f"missing group metadata for profile {profile}")
    return group


def load_official_rows(path: Path, profile: str) -> list[OfficialRow]:
    """Load a package JSONL without exposing future-derived metadata as features."""

    if profile not in {"A", "B", "C"}:
        raise ValueError(f"unsupported profile: {profile}")
    rows: list[OfficialRow] = []
    identities: set[str] = set()
    expected_names: tuple[str, ...] | None = None
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            item = json.loads(raw)
            sample_id = str(item.get("id", ""))
            if not sample_id:
                raise ValueError(f"missing sample id at line {line_number}")
            if sample_id in identities:
                raise ValueError(f"duplicate sample id: {sample_id}")
            identities.add(sample_id)
            names, values = _flatten_inputs(item["inputs"])
            names_tuple = tuple(names)
            if expected_names is None:
                expected_names = names_tuple
            elif names_tuple != expected_names:
                raise ValueError("inconsistent input feature schema")
            target: Any = item["answer"] if profile == "A" else float(item["answer"])
            meta = dict(item.get("meta", {}))
            rows.append(
                OfficialRow(
                    sample_id=sample_id,
                    features=tuple(values),
                    feature_names=names_tuple,
                    target=target,
                    group=_group(profile, meta),
                    meta=meta,
                )
            )
    if not rows:
        raise ValueError("dataset is empty")
    return rows


def build_causal_features(
    rows: Sequence[OfficialRow], profile: str
) -> tuple[NDArray[np.float64], tuple[str, ...]]:
    """Add only metadata and history available at the prediction instant."""

    if not rows:
        raise ValueError("rows must not be empty")
    base_names = tuple(rows[0].feature_names)
    if any(tuple(row.feature_names) != base_names for row in rows):
        raise ValueError("inconsistent row feature schema")
    base = np.asarray([row.features for row in rows], dtype=np.float64)
    if profile == "A":
        return base, base_names
    if profile == "B":
        snapshot = np.asarray(
            [[float(row.meta["snapshot"])] for row in rows], dtype=np.float64
        )
        if np.any(snapshot < 0.0):
            raise ValueError("snapshot must be non-negative")
        return np.hstack((base, snapshot)), base_names + ("meta:snapshot",)
    if profile != "C":
        raise ValueError(f"unsupported profile: {profile}")

    cycle = np.asarray([float(row.meta["cycle"]) for row in rows], dtype=np.float64)
    if np.any(cycle < 0.0):
        raise ValueError("cycle must be non-negative")
    delta = np.zeros_like(base)
    expanding_mean = np.zeros_like(base)
    indices_by_group: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        indices_by_group.setdefault(row.group, []).append(index)
    for indices in indices_by_group.values():
        ordered = sorted(indices, key=lambda index: (cycle[index], rows[index].sample_id))
        running = np.zeros(base.shape[1], dtype=np.float64)
        previous: NDArray[np.float64] | None = None
        for count, index in enumerate(ordered, 1):
            current = base[index]
            delta[index] = 0.0 if previous is None else current - previous
            running += current
            expanding_mean[index] = running / count
            previous = current
    names = (
        base_names
        + ("meta:cycle",)
        + tuple(f"history:delta:{name}" for name in base_names)
        + tuple(f"history:mean:{name}" for name in base_names)
    )
    return np.hstack((base, cycle[:, None], delta, expanding_mean)), names


def grouped_folds(
    rows: Sequence[Any], profile: str, *, seed: int, n_splits: int = 3
) -> list[tuple[NDArray[np.int64], NDArray[np.int64]]]:
    if n_splits < 2:
        raise ValueError("n_splits must be at least two")
    targets = np.asarray([row.target for row in rows])
    indices = np.arange(len(rows))
    if profile == "A":
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        iterator = splitter.split(indices, targets)
    elif profile in {"B", "C"}:
        groups = np.asarray([row.group for row in rows])
        if len(np.unique(groups)) < n_splits:
            raise ValueError("not enough distinct groups for requested folds")
        splitter = GroupKFold(n_splits=n_splits)
        iterator = splitter.split(indices, targets, groups)
    else:
        raise ValueError(f"unsupported profile: {profile}")
    folds = [
        (np.asarray(train, dtype=np.int64), np.asarray(test, dtype=np.int64))
        for train, test in iterator
    ]
    return folds


def _estimator(spec: TeacherSpec, task_kind: TaskKind, *, seed: int, low_budget: bool):
    params = dict(spec.params)
    if low_budget:
        if spec.family == "extra_trees":
            params["n_estimators"] = min(int(params.get("n_estimators", 100)), 40)
        elif spec.family == "hist_gradient_boosting":
            params["max_iter"] = min(int(params.get("max_iter", 100)), 50)
        elif spec.family == "mlp":
            params["max_iter"] = min(int(params.get("max_iter", 100)), 50)
    if spec.family == "linear":
        if task_kind == "classification":
            return make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    max_iter=600, class_weight="balanced", random_state=seed, **params
                ),
            )
        return make_pipeline(StandardScaler(), Ridge(**params))
    if spec.family == "extra_trees":
        defaults: dict[str, Any] = {"n_estimators": 160, "n_jobs": 1}
        if task_kind == "classification":
            defaults["class_weight"] = "balanced"
            return ExtraTreesClassifier(random_state=seed, **(defaults | params))
        return ExtraTreesRegressor(random_state=seed, **(defaults | params))
    if spec.family == "hist_gradient_boosting":
        cls = (
            HistGradientBoostingClassifier
            if task_kind == "classification"
            else HistGradientBoostingRegressor
        )
        return cls(random_state=seed, **params)
    if spec.family == "mlp":
        defaults = {
            "hidden_layer_sizes": (64, 32),
            "max_iter": 160,
            "early_stopping": True,
        }
        cls = MLPClassifier if task_kind == "classification" else MLPRegressor
        return make_pipeline(
            StandardScaler(), cls(random_state=seed, **(defaults | params))
        )
    raise ValueError(f"unsupported teacher family: {spec.family}")


def aligned_predict_proba(
    estimator: Any, X: NDArray[np.float64], classes: NDArray[Any]
) -> NDArray[np.float64]:
    probabilities = np.asarray(estimator.predict_proba(X), dtype=np.float64)
    estimator_classes = np.asarray(estimator.classes_)
    result = np.zeros((len(X), len(classes)), dtype=np.float64)
    positions = {value: index for index, value in enumerate(classes.tolist())}
    for source, label in enumerate(estimator_classes.tolist()):
        if label not in positions:
            raise ValueError("estimator returned an unknown class")
        result[:, positions[label]] = probabilities[:, source]
    return result


def _metric(
    target: NDArray[Any], prediction: NDArray[Any], task_kind: TaskKind
) -> float:
    if task_kind == "classification":
        return float(f1_score(target, prediction, average="macro", zero_division=0))
    return float(mean_squared_error(target, prediction) ** 0.5)


def _cross_validate(
    X: NDArray[np.float64],
    y: NDArray[Any],
    folds: Sequence[tuple[NDArray[np.int64], NDArray[np.int64]]],
    spec: TeacherSpec,
    *,
    task_kind: TaskKind,
    seed: int,
    low_budget: bool,
) -> TeacherEvaluation:
    classes = np.unique(y) if task_kind == "classification" else None
    if task_kind == "classification":
        oof: NDArray[Any] = np.zeros((len(y), len(classes)), dtype=np.float64)
    else:
        oof = np.zeros(len(y), dtype=np.float64)
    covered = np.zeros(len(y), dtype=bool)
    for fold_index, (train, holdout) in enumerate(folds):
        estimator = _estimator(spec, task_kind, seed=seed + fold_index, low_budget=low_budget)
        estimator.fit(X[train], y[train])
        if task_kind == "classification":
            oof[holdout] = aligned_predict_proba(estimator, X[holdout], classes)
        else:
            oof[holdout] = np.maximum(0.0, np.asarray(estimator.predict(X[holdout])))
        covered[holdout] = True
    if not bool(np.any(covered)):
        raise ValueError("folds do not contain a holdout sample")
    if not low_budget and not bool(np.all(covered)):
        raise ValueError("full-budget folds do not cover every sample exactly once")
    if task_kind == "classification":
        hard_prediction = classes[np.argmax(oof[covered], axis=1)]
        primary = _metric(y[covered], hard_prediction, task_kind)
    else:
        primary = _metric(y[covered], oof[covered], task_kind)
    if not math.isfinite(primary):
        raise ValueError("teacher metric is not finite")
    return TeacherEvaluation(
        spec=spec,
        primary_metric=primary,
        stage="low_budget" if low_budget else "full_budget",
        oof_predictions=oof,
    )


def successive_halving(
    X: NDArray[np.float64],
    y: NDArray[Any],
    folds: Sequence[tuple[NDArray[np.int64], NDArray[np.int64]]],
    specs: Sequence[TeacherSpec],
    *,
    task_kind: TaskKind,
    finalist_count: int,
    seed: int,
) -> HalvingResult:
    if not specs or not 1 <= finalist_count <= len(specs):
        raise ValueError("invalid successive-halving candidate counts")
    first_fold = folds[:1]
    low = [
        _cross_validate(
            X,
            y,
            first_fold,
            spec,
            task_kind=task_kind,
            seed=seed,
            low_budget=True,
        )
        for spec in specs
    ]
    reverse = task_kind == "classification"
    selected = (
        low
        if finalist_count == len(specs)
        else sorted(
            low,
            key=lambda item: (item.primary_metric, item.spec.id),
            reverse=reverse,
        )[:finalist_count]
    )
    finalists = tuple(
        _cross_validate(
            X,
            y,
            folds,
            item.spec,
            task_kind=task_kind,
            seed=seed,
            low_budget=False,
        )
        for item in selected
    )
    full_by_id = {item.spec.id: item for item in finalists}
    all_results = tuple(full_by_id.get(item.spec.id, item) for item in low)
    return HalvingResult(finalists=finalists, all_results=all_results)


def fit_weighted_ensemble(
    predictions: Mapping[str, NDArray[Any]],
    targets: NDArray[Any],
    *,
    task_kind: TaskKind,
) -> dict[str, float]:
    if not predictions:
        raise ValueError("at least one teacher prediction is required")
    target = np.asarray(targets)
    quality: dict[str, float] = {}
    if task_kind == "classification":
        classes = np.unique(target)
        chance = 1.0 / max(1, len(classes))
        for name, raw in predictions.items():
            value = np.asarray(raw)
            hard = classes[np.argmax(value, axis=1)] if value.ndim == 2 else value
            score = float(f1_score(target, hard, average="macro", zero_division=0))
            quality[name] = max(score - chance, 1e-6)
    else:
        for name, raw in predictions.items():
            rmse = float(mean_squared_error(target, np.asarray(raw)) ** 0.5)
            quality[name] = 1.0 / max(rmse, 1e-9)
    total = sum(quality.values())
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("ensemble quality weights are invalid")
    return {name: value / total for name, value in quality.items()}
