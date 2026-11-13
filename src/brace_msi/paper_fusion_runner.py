"""Recoverable runner for the bounded paper-guided CPU model sprint."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Mapping

import joblib
import numpy as np
import psutil
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .paper_fusion import (
    TeacherSpec,
    _estimator,
    aligned_predict_proba,
    build_causal_features,
    fit_weighted_ensemble,
    grouped_folds,
    load_official_rows,
    successive_halving,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _metrics(profile: str, y: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    if profile == "A":
        return {
            "macro_f1": float(f1_score(y, prediction, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(y, prediction)),
        }
    return {
        "rmse": float(mean_squared_error(y, prediction) ** 0.5),
        "mae": float(mean_absolute_error(y, prediction)),
    }


def _primary(profile: str, metrics: Mapping[str, float]) -> float:
    return float(metrics["macro_f1"] if profile == "A" else metrics["rmse"])


def _improvement(profile: str, baseline: float, value: float) -> float:
    return (value - baseline) / baseline if profile == "A" else (baseline - value) / baseline


def _specs(config: Mapping[str, Any], profile: str) -> list[TeacherSpec]:
    key = "classification" if profile == "A" else "regression"
    raw = config["teacher_specs"][key]
    specs = [TeacherSpec(str(item["family"]), dict(item.get("params", {}))) for item in raw]
    if not 1 <= len(specs) <= 12:
        raise ValueError("each task requires 1..12 teacher specifications")
    return specs


def _ensemble_prediction(
    profile: str,
    predictions: Mapping[str, np.ndarray],
    weights: Mapping[str, float],
    classes: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    combined = sum(np.asarray(predictions[name]) * float(weights[name]) for name in weights)
    if profile == "A":
        if classes is None:
            raise ValueError("classification ensemble requires classes")
        return classes[np.argmax(combined, axis=1)], combined
    return np.maximum(0.0, combined), combined


def _fit_student_oof(
    X: np.ndarray,
    y: np.ndarray,
    teacher_probabilities: np.ndarray,
    folds: list[tuple[np.ndarray, np.ndarray]],
    classes: np.ndarray,
    *,
    seed: int,
    alpha: float,
    max_iter: int,
) -> tuple[np.ndarray, Any]:
    positions = {label: index for index, label in enumerate(classes.tolist())}
    hard = np.zeros_like(teacher_probabilities)
    for row_index, label in enumerate(y.tolist()):
        hard[row_index, positions[label]] = 1.0
    soft_targets = alpha * hard + (1.0 - alpha) * teacher_probabilities
    oof = np.zeros_like(teacher_probabilities)
    for fold_index, (train, holdout) in enumerate(folds):
        student = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                max_iter=max_iter,
                early_stopping=True,
                random_state=seed + fold_index,
            ),
        )
        student.fit(X[train], soft_targets[train])
        oof[holdout] = np.asarray(student.predict(X[holdout]))
    final_student = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            max_iter=max_iter,
            early_stopping=True,
            random_state=seed,
        ),
    )
    final_student.fit(X, soft_targets)
    return oof, final_student


def _develop_profile(
    profile: str,
    profile_config: Mapping[str, Any],
    config: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    result_path = output_dir / "development.json"
    if result_path.is_file():
        return json.loads(result_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    train_path = Path(profile_config["train"]).resolve()
    rows = load_official_rows(train_path, profile)
    X, feature_names = build_causal_features(rows, profile)
    y = np.asarray([row.target for row in rows])
    task_kind = "classification" if profile == "A" else "regression"
    folds = grouped_folds(
        rows,
        profile,
        seed=int(config["seed"]),
        n_splits=int(config.get("n_splits", 3)),
    )
    halving = successive_halving(
        X,
        y,
        folds,
        _specs(config, profile),
        task_kind=task_kind,
        finalist_count=int(config.get("finalist_count", 4)),
        seed=int(config["seed"]),
    )
    oof_predictions = {
        item.spec.id: np.asarray(item.oof_predictions) for item in halving.finalists
    }
    weights = fit_weighted_ensemble(oof_predictions, y, task_kind=task_kind)
    classes = np.unique(y) if profile == "A" else None
    ensemble_hard, ensemble_raw = _ensemble_prediction(
        profile, oof_predictions, weights, classes
    )
    ensemble_metrics = _metrics(profile, y, ensemble_hard)
    estimators: dict[str, Any] = {}
    for index, item in enumerate(halving.finalists):
        estimator = _estimator(
            item.spec,
            task_kind,
            seed=int(config["seed"]) + index,
            low_budget=False,
        )
        estimator.fit(X, y)
        estimators[item.spec.id] = estimator
        peak_rss = max(peak_rss, process.memory_info().rss)

    selected_mode = "teacher_ensemble"
    student = None
    student_metrics: dict[str, float] | None = None
    distillation = dict(config.get("distillation", {}))
    if profile == "A" and bool(distillation.get("enabled", False)):
        student_oof, student = _fit_student_oof(
            X,
            y,
            np.asarray(ensemble_raw),
            folds,
            np.asarray(classes),
            seed=int(config["seed"]),
            alpha=float(distillation.get("hard_label_weight", 0.5)),
            max_iter=int(distillation.get("max_iter", 180)),
        )
        student_hard = classes[np.argmax(student_oof, axis=1)]
        student_metrics = _metrics(profile, y, student_hard)
        if _primary(profile, student_metrics) > _primary(profile, ensemble_metrics):
            selected_mode = "compact_student"
        peak_rss = max(peak_rss, process.memory_info().rss)

    model_path = output_dir / "model.joblib"
    joblib.dump(
        {
            "format": "brace-msi.paper-fusion-model.v1",
            "profile": profile,
            "feature_names": feature_names,
            "classes": classes,
            "weights": weights,
            "estimators": estimators,
            "student": student,
            "selected_mode": selected_mode,
        },
        model_path,
        compress=3,
    )
    result: dict[str, Any] = {
        "profile": profile,
        "task_kind": task_kind,
        "train_path": str(train_path),
        "train_sha256": _sha256(train_path),
        "rows": len(rows),
        "features": int(X.shape[1]),
        "folds": len(folds),
        "teacher_results": [
            {
                "id": item.spec.id,
                "family": item.spec.family,
                "params": dict(item.spec.params),
                "stage": item.stage,
                "primary_metric": item.primary_metric,
                "finalist": item.spec.id in {final.spec.id for final in halving.finalists},
            }
            for item in halving.all_results
        ],
        "weights": weights,
        "ensemble_internal_metrics": ensemble_metrics,
        "student_internal_metrics": student_metrics,
        "selected_mode": selected_mode,
        "model_path": str(model_path.resolve()),
        "model_sha256": _sha256(model_path),
        "resources": {
            "cpu_seconds": time.process_time() - started_cpu,
            "wall_seconds": time.perf_counter() - started_wall,
            "peak_rss_bytes": peak_rss,
        },
    }
    _atomic_json(result_path, result)
    return result


def _predict_model(model: Mapping[str, Any], rows: list[Any], profile: str) -> np.ndarray:
    X, feature_names = build_causal_features(rows, profile)
    if tuple(feature_names) != tuple(model["feature_names"]):
        raise ValueError("validation feature schema differs from frozen model")
    predictions: dict[str, np.ndarray] = {}
    classes = model["classes"]
    for name, estimator in model["estimators"].items():
        if profile == "A":
            predictions[name] = aligned_predict_proba(estimator, X, classes)
        else:
            predictions[name] = np.maximum(0.0, np.asarray(estimator.predict(X)))
    _, raw = _ensemble_prediction(profile, predictions, model["weights"], classes)
    if model["selected_mode"] == "compact_student":
        raw = np.asarray(model["student"].predict(X))
    if profile == "A":
        return classes[np.argmax(raw, axis=1)]
    return np.maximum(0.0, raw)


def _finalize(config: Mapping[str, Any], output_root: Path) -> dict[str, Any]:
    lock = output_root / "validation-open.lock"
    if lock.exists():
        raise FileExistsError("public validation was already opened")
    lock.write_text(
        json.dumps({"opened_at_unix": time.time(), "count": 1}) + "\n",
        encoding="utf-8",
    )
    profiles: dict[str, Any] = {}
    for profile, profile_config in sorted(config["profiles"].items()):
        profile_dir = output_root / profile
        development = json.loads(
            (profile_dir / "development.json").read_text(encoding="utf-8")
        )
        model_path = profile_dir / "model.joblib"
        if _sha256(model_path) != development["model_sha256"]:
            raise ValueError("frozen model artifact changed before validation")
        validation_path = Path(profile_config["validation"]).resolve()
        rows = load_official_rows(validation_path, profile)
        model = joblib.load(model_path)
        prediction = _predict_model(model, rows, profile)
        y = np.asarray([row.target for row in rows])
        metrics = _metrics(profile, y, prediction)
        primary = _primary(profile, metrics)
        profiles[profile] = {
            "metrics": metrics,
            "baseline": float(profile_config["baseline"]),
            "rc3": float(profile_config["rc3"]),
            "relative_improvement_over_baseline": _improvement(
                profile, float(profile_config["baseline"]), primary
            ),
            "relative_improvement_over_rc3": _improvement(
                profile, float(profile_config["rc3"]), primary
            ),
            "validation_path": str(validation_path),
            "validation_sha256": _sha256(validation_path),
            "validation_rows": len(rows),
            "selected_mode": model["selected_mode"],
        }
        _atomic_json(profile_dir / "validation.json", profiles[profile])
    summary = {
        "format": "brace-msi.paper-fusion-result.v1",
        "status": "completed",
        "validation_open_count": 1,
        "profiles": profiles,
    }
    _atomic_json(output_root / "summary.json", summary)
    return summary


def run_paper_fusion_sprint(
    config_path: Path, output_root: Path, *, open_validation: bool
) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    output_root = Path(output_root).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("format") != "brace-msi.paper-fusion-sprint.v1":
        raise ValueError("unsupported paper-fusion configuration")
    config_sha = _canonical_sha256(config)
    manifest_path = output_root / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("config_sha256") != config_sha:
            raise ValueError("configuration changed after run creation")
    else:
        if output_root.exists() and any(output_root.iterdir()):
            raise FileExistsError("output root exists without a manifest")
        output_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "format": "brace-msi.paper-fusion-manifest.v1",
            "config_path": str(config_path),
            "config_sha256": config_sha,
            "branch": "codex/paper-fusion-sprint",
            "validation_exposure": "historically_exposed_open_once_after_freeze",
        }
        _atomic_json(manifest_path, manifest)

    frozen_path = output_root / "frozen.json"
    if not frozen_path.is_file():
        profiles = {
            profile: _develop_profile(
                profile,
                profile_config,
                config,
                output_root / profile,
            )
            for profile, profile_config in sorted(config["profiles"].items())
        }
        frozen = {
            "format": "brace-msi.paper-fusion-frozen.v1",
            "status": "candidate_frozen",
            "validation_open_count": 0,
            "profiles": profiles,
        }
        _atomic_json(frozen_path, frozen)
    else:
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if open_validation:
        return _finalize(config, output_root)
    return frozen


def validate_paper_fusion_output(output_root: Path) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    errors: list[str] = []
    try:
        manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
        summary = json.loads((output_root / "summary.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [str(exc)]}
    if manifest.get("format") != "brace-msi.paper-fusion-manifest.v1":
        errors.append("invalid manifest format")
    if summary.get("status") != "completed" or summary.get("validation_open_count") != 1:
        errors.append("run is not a single-open completed result")
    if set(summary.get("profiles", {})) != {"A", "B", "C"}:
        errors.append("A/B/C profile set is incomplete")
    for profile in ("A", "B", "C"):
        try:
            development = json.loads(
                (output_root / profile / "development.json").read_text(encoding="utf-8")
            )
            model_path = output_root / profile / "model.joblib"
            if _sha256(model_path) != development["model_sha256"]:
                errors.append(f"{profile} model hash mismatch")
            metrics = summary["profiles"][profile]["metrics"]
            if not metrics or not all(math.isfinite(float(value)) for value in metrics.values()):
                errors.append(f"{profile} metrics are not finite")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{profile} validation failed: {exc}")
    return {"valid": not errors, "errors": errors}
