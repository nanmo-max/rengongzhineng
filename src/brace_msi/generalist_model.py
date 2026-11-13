"""Identity-blind CPU candidates that retain the official parent as an ensemble member."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import f1_score, mean_squared_error
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .official_package import PackageAudit
from .resources import ResourceTracker


MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class NumericRow:
    raw: dict[str, Any]
    features: tuple[float, ...]
    feature_names: tuple[str, ...]
    target: str | float
    group: str


@dataclass(frozen=True)
class GeneralistSpec:
    family: str
    parameters: Mapping[str, Any]

    @property
    def identifier(self) -> str:
        return f"{self.family}:{json.dumps(dict(self.parameters), sort_keys=True, separators=(',', ':'))}"


@dataclass(frozen=True)
class GeneralistFitResult:
    parent_sha256: str
    artifact_sha256: str
    artifact_bytes: int
    selected_spec: GeneralistSpec
    internal_primary_metric: float
    candidate_metrics: Mapping[str, float]
    cpu_seconds: float
    wall_seconds: float
    peak_rss_bytes: int


@dataclass(frozen=True)
class GeneralistPrediction:
    predictions: np.ndarray
    raw: np.ndarray
    parent_predictions: np.ndarray
    parent_raw: np.ndarray
    candidate_predictions: np.ndarray
    candidate_raw: np.ndarray


def _flatten_inputs(value: Any) -> tuple[tuple[str, ...], tuple[float, ...]]:
    paths: list[str] = []
    values: list[float] = []

    def visit(child: Any, path: list[tuple[str, Any]], depth: int) -> None:
        if depth > 16:
            raise ValueError("input nesting exceeds limit")
        if isinstance(child, dict):
            for key in sorted(child):
                visit(child[key], [*path, ("key", key)], depth + 1)
        elif isinstance(child, list):
            for index, item in enumerate(child):
                visit(item, [*path, ("index", index)], depth + 1)
        elif isinstance(child, (int, float)) and not isinstance(child, bool):
            numeric = float(child)
            if not math.isfinite(numeric):
                raise ValueError("input feature is nonfinite")
            paths.append(json.dumps(path, ensure_ascii=False, separators=(",", ":")))
            values.append(numeric)
        else:
            raise ValueError("inputs must contain finite numeric leaves only")

    visit(value, [], 0)
    if not values:
        raise ValueError("inputs contain no numeric features")
    return tuple(paths), tuple(values)


def _group_from_meta(meta: Mapping[str, Any], sequence: int) -> str:
    if "bearing" in meta:
        return f"bearing:{meta['bearing']}"
    if "source_subset" in meta and "unit" in meta:
        return f"unit:{meta['source_subset']}:{meta['unit']}"
    if "source_batch" in meta:
        return f"batch:{meta['source_batch']}"
    return f"ordered-block:{sequence // 256}"


def load_numeric_rows(path: Path) -> list[NumericRow]:
    rows: list[NumericRow] = []
    expected_names: tuple[str, ...] | None = None
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict) or not {"id", "inputs", "answer"} <= set(raw):
            raise ValueError(f"invalid JSONL row {line_number}")
        names, values = _flatten_inputs(raw["inputs"])
        if expected_names is None:
            expected_names = names
        elif names != expected_names:
            raise ValueError("input feature schema changed")
        answer = raw["answer"]
        target: str | float
        if isinstance(answer, str):
            target = answer
        elif isinstance(answer, (int, float)) and not isinstance(answer, bool):
            target = float(answer)
        else:
            raise ValueError("unsupported target type")
        meta = raw.get("meta", {})
        if not isinstance(meta, dict):
            raise ValueError("meta must be an object")
        rows.append(
            NumericRow(
                raw=raw,
                features=values,
                feature_names=names,
                target=target,
                group=_group_from_meta(meta, len(rows)),
            )
        )
    if not rows:
        raise ValueError("dataset is empty")
    return rows


def _parent_arrays(parent_bytes: bytes) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    try:
        with np.load(io.BytesIO(parent_bytes), allow_pickle=False) as archive:
            metadata = archive["metadata"]
            if metadata.shape != () or metadata.dtype.kind != "U":
                raise ValueError("parent metadata is invalid")
            meta = json.loads(str(metadata.item()))
            arrays = {
                name: np.asarray(archive[name]).copy()
                for name in ("w1", "b1", "w2", "b2", "mean", "scale")
            }
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("embedded parent checkpoint is invalid") from exc
    return meta, arrays


def _parent_predict(parent_bytes: bytes, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    meta, arrays = _parent_arrays(parent_bytes)
    normalized = np.clip((X - arrays["mean"]) / arrays["scale"], -10.0, 10.0)
    hidden = np.tanh(normalized @ arrays["w1"] + arrays["b1"])
    logits = hidden @ arrays["w2"] + arrays["b2"]
    classes = tuple(str(value) for value in meta["classes"])
    if meta["task"] == "classification":
        logits -= logits.max(axis=1, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        predictions = np.asarray(classes, dtype=str)[np.argmax(probabilities, axis=1)]
        return predictions, probabilities, classes
    values = np.maximum(
        0.0,
        logits[:, 0] * float(meta["target_scale"]) + float(meta["target_mean"]),
    )
    return values, values, ()


def _estimator(spec: GeneralistSpec, task: str, seed: int):
    params = dict(spec.parameters)
    if spec.family == "linear":
        regularization = float(params.pop("regularization", 1.0))
        if params:
            raise ValueError("unknown linear parameters")
        if task == "classification":
            return make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    C=1.0 / max(regularization, 1e-12),
                    max_iter=600,
                    class_weight="balanced",
                    random_state=seed,
                ),
            )
        return make_pipeline(StandardScaler(), Ridge(alpha=regularization))
    if spec.family == "hist_gradient_boosting":
        defaults = {
            "learning_rate": 0.06,
            "max_iter": 100,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 20,
            "l2_regularization": 1.0,
        }
        cls = (
            HistGradientBoostingClassifier
            if task == "classification"
            else HistGradientBoostingRegressor
        )
        return cls(random_state=seed, **(defaults | params))
    if spec.family == "extra_trees":
        defaults = {
            "n_estimators": 48,
            "max_depth": 12,
            "min_samples_leaf": 2,
            "max_features": 0.7,
            "n_jobs": 1,
        }
        if task == "classification":
            return ExtraTreesClassifier(
                random_state=seed, class_weight="balanced", **(defaults | params)
            )
        return ExtraTreesRegressor(random_state=seed, **(defaults | params))
    raise ValueError(f"unsupported generalist family: {spec.family}")


def _folds(rows: Sequence[NumericRow], task: str, y: np.ndarray, seed: int):
    indices = np.arange(len(rows))
    groups = np.asarray([row.group for row in rows])
    if len(np.unique(groups)) >= 3:
        return list(GroupKFold(n_splits=3).split(indices, y, groups))
    if task == "classification":
        return list(StratifiedKFold(n_splits=3, shuffle=True, random_state=seed).split(indices, y))
    return list(KFold(n_splits=3, shuffle=False).split(indices, y))


def _aligned_probabilities(estimator: Any, X: np.ndarray, classes: tuple[str, ...]) -> np.ndarray:
    probabilities = np.asarray(estimator.predict_proba(X), dtype=np.float64)
    estimator_classes = tuple(str(value) for value in estimator.classes_)
    result = np.zeros((len(X), len(classes)), dtype=np.float64)
    positions = {label: index for index, label in enumerate(classes)}
    for source, label in enumerate(estimator_classes):
        if label not in positions:
            raise ValueError("candidate produced an unknown class")
        result[:, positions[label]] = probabilities[:, source]
    return result


def _primary(task: str, y: np.ndarray, raw: np.ndarray, classes: tuple[str, ...]) -> float:
    if task == "classification":
        prediction = np.asarray(classes, dtype=str)[np.argmax(raw, axis=1)]
        return float(f1_score(y, prediction, average="macro", zero_division=0))
    return float(mean_squared_error(y, raw) ** 0.5)


class GeneralistCheckpoint:
    def __init__(
        self,
        metadata: dict[str, Any],
        parent_bytes: bytes,
        estimator: Any,
    ) -> None:
        self.metadata = metadata
        self.parent_bytes = parent_bytes
        self.estimator = estimator

    @classmethod
    def load(cls, path: Path) -> "GeneralistCheckpoint":
        path = Path(path)
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError("generalist checkpoint is missing or exceeds 64 MiB")
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != {"metadata", "parent_checkpoint", "model_blob"}:
                raise ValueError("generalist checkpoint schema mismatch")
            metadata_raw = archive["metadata"]
            if metadata_raw.shape != () or metadata_raw.dtype.kind != "U":
                raise ValueError("generalist metadata is invalid")
            metadata = json.loads(str(metadata_raw.item()))
            parent_bytes = np.asarray(archive["parent_checkpoint"], dtype=np.uint8).tobytes()
            model_bytes = np.asarray(archive["model_blob"], dtype=np.uint8).tobytes()
        if hashlib.sha256(parent_bytes).hexdigest() != metadata.get("parent_sha256"):
            raise ValueError("embedded parent hash mismatch")
        if hashlib.sha256(model_bytes).hexdigest() != metadata.get("model_blob_sha256"):
            raise ValueError("embedded model hash mismatch")
        estimator = joblib.load(io.BytesIO(model_bytes))
        return cls(metadata, parent_bytes, estimator)

    def predict_rows(self, rows: Sequence[NumericRow]) -> GeneralistPrediction:
        if not rows:
            raise ValueError("prediction rows cannot be empty")
        names = tuple(rows[0].feature_names)
        if names != tuple(self.metadata["feature_names"]):
            raise ValueError("generalist feature schema mismatch")
        if any(tuple(row.feature_names) != names for row in rows):
            raise ValueError("prediction row schema changed")
        X = np.asarray([row.features for row in rows], dtype=np.float64)
        parent_predictions, parent_raw, parent_classes = _parent_predict(self.parent_bytes, X)
        task = str(self.metadata["task"])
        weight = float(self.metadata["blend_parent_weight"])
        if task == "classification":
            classes = tuple(str(value) for value in self.metadata["classes"])
            if parent_classes != classes:
                raise ValueError("parent class order mismatch")
            candidate_raw = _aligned_probabilities(self.estimator, X, classes)
            candidate_predictions = np.asarray(classes, dtype=str)[
                np.argmax(candidate_raw, axis=1)
            ]
            blended = weight * parent_raw + (1.0 - weight) * candidate_raw
            predictions = np.asarray(classes, dtype=str)[np.argmax(blended, axis=1)]
        else:
            candidate_raw = np.maximum(
                0.0, np.asarray(self.estimator.predict(X), dtype=np.float64)
            )
            candidate_predictions = candidate_raw
            blended = np.maximum(0.0, weight * parent_raw + (1.0 - weight) * candidate_raw)
            predictions = blended
        return GeneralistPrediction(
            predictions=np.asarray(predictions),
            raw=np.asarray(blended),
            parent_predictions=np.asarray(parent_predictions),
            parent_raw=np.asarray(parent_raw),
            candidate_predictions=np.asarray(candidate_predictions),
            candidate_raw=np.asarray(candidate_raw),
        )

    def predict_inputs(self, inputs: Sequence[Any]) -> GeneralistPrediction:
        rows: list[NumericRow] = []
        for index, value in enumerate(inputs):
            names, features = _flatten_inputs(value)
            rows.append(
                NumericRow(
                    raw={"inputs": value},
                    features=features,
                    feature_names=names,
                    target="" if self.metadata["task"] == "classification" else 0.0,
                    group=f"prediction:{index}",
                )
            )
        return self.predict_rows(rows)


DEFAULT_SPECS = (
    GeneralistSpec("linear", {"regularization": 1.0}),
    GeneralistSpec("hist_gradient_boosting", {}),
    GeneralistSpec("extra_trees", {}),
)


def fit_generalist_candidate(
    package: PackageAudit,
    output_path: Path,
    *,
    specs: Sequence[GeneralistSpec] = DEFAULT_SPECS,
    max_train_rows: int | None = None,
    seed: int = 20261113,
) -> GeneralistFitResult:
    if not specs:
        raise ValueError("generalist candidate pool is empty")
    rows = load_numeric_rows(package.train_path)
    if max_train_rows is not None and len(rows) > max_train_rows:
        positions = [(len(rows) * index) // max_train_rows for index in range(max_train_rows)]
        rows = [rows[index] for index in positions]
    X = np.asarray([row.features for row in rows], dtype=np.float64)
    y = np.asarray(
        [row.target for row in rows],
        dtype=str if package.task == "classification" else np.float64,
    )
    parent_bytes = package.checkpoint_path.read_bytes()
    parent_meta, _ = _parent_arrays(parent_bytes)
    feature_names = tuple(rows[0].feature_names)
    if feature_names != tuple(parent_meta["paths"]):
        raise ValueError("training schema differs from official parent")
    classes = tuple(str(value) for value in parent_meta["classes"])
    folds = _folds(rows, package.task, y, seed)
    metrics: dict[str, float] = {}
    with ResourceTracker() as tracker:
        for spec_index, spec in enumerate(specs):
            raw = (
                np.zeros((len(rows), len(classes)), dtype=np.float64)
                if package.task == "classification"
                else np.zeros(len(rows), dtype=np.float64)
            )
            covered = np.zeros(len(rows), dtype=bool)
            for fold_index, (train, holdout) in enumerate(folds):
                estimator = _estimator(spec, package.task, seed + spec_index * 10 + fold_index)
                estimator.fit(X[train], y[train])
                if package.task == "classification":
                    raw[holdout] = _aligned_probabilities(estimator, X[holdout], classes)
                else:
                    raw[holdout] = np.maximum(
                        0.0, np.asarray(estimator.predict(X[holdout]), dtype=np.float64)
                    )
                covered[holdout] = True
            if not covered.all():
                raise ValueError("generalist folds do not cover all rows")
            metrics[spec.identifier] = _primary(package.task, y, raw, classes)
        selected = (
            max(specs, key=lambda spec: (metrics[spec.identifier], spec.identifier))
            if package.task == "classification"
            else min(specs, key=lambda spec: (metrics[spec.identifier], spec.identifier))
        )
        estimator = _estimator(selected, package.task, seed)
        estimator.fit(X, y)
    usage = tracker.usage
    assert usage is not None
    buffer = io.BytesIO()
    joblib.dump(estimator, buffer, compress=3)
    model_bytes = buffer.getvalue()
    metadata = {
        "format": "brace-msi.generalist-parent-ensemble.v1",
        "task": package.task,
        "feature_names": list(feature_names),
        "classes": list(classes),
        "blend_parent_weight": 0.5,
        "parent_sha256": package.checkpoint_sha256,
        "model_blob_sha256": hashlib.sha256(model_bytes).hexdigest(),
        "selected_family": selected.family,
        "selected_parameters": dict(selected.parameters),
        "training_rows": len(rows),
        "seed": seed,
    }
    output_path = Path(output_path)
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"generalist artifact already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as stream:
        np.savez_compressed(
            stream,
            metadata=np.asarray(
                json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            ),
            parent_checkpoint=np.frombuffer(parent_bytes, dtype=np.uint8),
            model_blob=np.frombuffer(model_bytes, dtype=np.uint8),
        )
    if output_path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("generalist artifact exceeds 64 MiB")
    loaded = GeneralistCheckpoint.load(output_path)
    sample = rows[: min(32, len(rows))]
    first = loaded.predict_rows(sample).predictions
    second = GeneralistCheckpoint.load(output_path).predict_rows(sample).predictions
    if not np.array_equal(first, second):
        raise ValueError("generalist save/load prediction mismatch")
    return GeneralistFitResult(
        parent_sha256=package.checkpoint_sha256,
        artifact_sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
        artifact_bytes=output_path.stat().st_size,
        selected_spec=selected,
        internal_primary_metric=metrics[selected.identifier],
        candidate_metrics=metrics,
        cpu_seconds=usage.cpu_seconds,
        wall_seconds=usage.wall_seconds,
        peak_rss_bytes=usage.peak_rss_bytes,
    )
