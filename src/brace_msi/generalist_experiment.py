"""One-shot train-internal selection and exposed validation for generalist candidates."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error

from .generalist_model import (
    DEFAULT_SPECS,
    GeneralistCheckpoint,
    GeneralistSpec,
    NumericRow,
    fit_generalist_candidate,
    load_numeric_rows,
)
from .official_package import PackageAudit, audit_package_root
from .resources import ResourceTracker


def _metrics(task: str, expected: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    if task == "classification":
        return {
            "macro_f1": float(f1_score(expected, predicted, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(expected, predicted)),
        }
    error = np.asarray(predicted, dtype=float) - np.asarray(expected, dtype=float)
    nasa = np.where(
        error >= 0.0,
        np.exp(np.minimum(error / 10.0, 50.0)) - 1.0,
        np.exp(np.minimum(-error / 13.0, 50.0)) - 1.0,
    )
    return {
        "rmse": float(mean_squared_error(expected, predicted) ** 0.5),
        "mae": float(mean_absolute_error(expected, predicted)),
        "nasa_score": float(np.sum(nasa)),
    }


def evaluate_generalist_artifact(
    package: PackageAudit,
    artifact: Path,
    rows: Sequence[NumericRow],
) -> dict[str, Any]:
    checkpoint = GeneralistCheckpoint.load(artifact)
    if checkpoint.metadata["parent_sha256"] != package.checkpoint_sha256:
        raise ValueError("generalist artifact parent does not match package")
    expected = np.asarray(
        [row.target for row in rows],
        dtype=str if package.task == "classification" else np.float64,
    )
    with ResourceTracker() as tracker:
        prediction = checkpoint.predict_rows(rows)
    usage = tracker.usage
    assert usage is not None
    parent = _metrics(package.task, expected, prediction.parent_predictions)
    candidate = _metrics(package.task, expected, prediction.candidate_predictions)
    blend = _metrics(package.task, expected, prediction.predictions)
    if package.task == "classification":
        accepted = (
            blend["macro_f1"] > parent["macro_f1"]
            and blend["accuracy"] >= parent["accuracy"] - 0.01
        )
    else:
        accepted = (
            blend["rmse"] < parent["rmse"]
            and blend["mae"] <= parent["mae"] * 1.03
        )
    return {
        "parent_metrics": parent,
        "candidate_metrics": candidate,
        "blend_metrics": blend,
        "accepted": bool(accepted),
        "gate_reason": "strict_primary_improvement_and_secondary_safe"
        if accepted
        else "no_safe_strict_improvement",
        "prediction_cpu_seconds": usage.cpu_seconds,
        "prediction_wall_seconds": usage.wall_seconds,
        "prediction_peak_rss_bytes": usage.peak_rss_bytes,
    }


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def run_generalist_experiment(
    package_root: Path,
    package_config_path: Path,
    output_root: Path,
    *,
    specs: Sequence[GeneralistSpec] = DEFAULT_SPECS,
    seed: int = 20261113,
) -> dict[str, Any]:
    """Freeze all three candidates before opening any public validation file."""

    output_root = Path(output_root)
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"generalist experiment output already exists: {output_root}")
    output_root.mkdir(parents=True)
    package_config = json.loads(Path(package_config_path).read_text(encoding="utf-8"))
    audits = audit_package_root(Path(package_root), package_config)
    training: dict[str, Any] = {}
    artifacts: dict[str, Path] = {}
    for profile in ("A", "B", "C"):
        artifact = output_root / profile / "checkpoint.npz"
        fit = fit_generalist_candidate(
            audits[profile], artifact, specs=specs, seed=seed
        )
        artifacts[profile] = artifact
        training[profile] = {
            **asdict(fit),
            "selected_spec": asdict(fit.selected_spec),
        }
        _atomic_json(output_root / profile / "training-result.json", training[profile])

    validation: dict[str, Any] = {}
    for profile in ("A", "B", "C"):
        rows = load_numeric_rows(audits[profile].validation_path)
        evaluation = evaluate_generalist_artifact(
            audits[profile], artifacts[profile], rows
        )
        validation[profile] = {
            **evaluation,
            "validation_sha256": audits[profile].validation_sha256,
            "historically_exposed": True,
            "validation_open_count": 1,
            "selected_model": "parent_generalist_blend"
            if evaluation["accepted"]
            else "official_parent",
            "final_checkpoint": str(
                artifacts[profile]
                if evaluation["accepted"]
                else audits[profile].checkpoint_path
            ),
        }
        _atomic_json(output_root / profile / "validation-result.json", validation[profile])

    summary = {
        "format": "brace-msi.generalist-experiment.v1",
        "experiment_id": "GENERALIST-MODEL-001-A1",
        "complete": True,
        "formal_eligible": False,
        "historically_exposed_validation": True,
        "official_test_opportunities_used": 0,
        "pytrio_calls": 0,
        "swanlab_calls": 0,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "training": training,
        "validation": validation,
        "accepted_profiles": [
            profile for profile, value in validation.items() if value["accepted"]
        ],
    }
    _atomic_json(output_root / "summary.json", summary)
    return summary
