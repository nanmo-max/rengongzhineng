"""Leakage-controlled utilities for Gas profile performance research."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from .official_package import PackageAudit
from .official_trainer import CandidateConfig, OfficialTrainer, recover_candidate_receipt


def freeze_stratified_development_confirmation(
    source: Path,
    output_dir: Path,
    *,
    classes: list[str],
    development_fraction: float,
    salt: str,
    exposure: str,
) -> dict[str, Any]:
    source = Path(source).resolve()
    output_dir = Path(output_dir).resolve()
    if not 0.0 < development_fraction < 1.0:
        raise ValueError("development_fraction must be between zero and one")
    if not salt or not exposure:
        raise ValueError("salt and exposure are required")
    rows = _read_rows(source)
    source_sha = _sha256(source)
    manifest_path = output_dir / "split-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("source_sha256") != source_sha:
            raise ValueError("source changed after split freeze")
        expected = {
            "classes": classes,
            "development_fraction": development_fraction,
            "salt_sha256": _sha256_text(salt),
            "exposure": exposure,
        }
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise ValueError(f"split configuration changed: {key}")
        for name in ("development", "confirmation"):
            path = output_dir / f"{name}.jsonl"
            if not path.is_file() or _sha256(path) != manifest[f"{name}_sha256"]:
                raise ValueError(f"frozen {name} split changed")
        return manifest

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        label = row.get("answer")
        if label not in classes:
            raise ValueError("source contains an unknown class")
        grouped[label].append(row)
    if set(grouped) != set(classes):
        raise ValueError("source does not contain every configured class")

    development_ids: set[str] = set()
    for label in classes:
        values = sorted(
            grouped[label],
            key=lambda row: _sha256_text(f"{salt}\0{label}\0{row['id']}"),
        )
        if len(values) < 2:
            raise ValueError("each class needs at least two samples")
        count = round(len(values) * development_fraction)
        count = min(len(values) - 1, max(1, count))
        development_ids.update(row["id"] for row in values[:count])

    development = [row for row in rows if row["id"] in development_ids]
    confirmation = [row for row in rows if row["id"] not in development_ids]
    if {row["id"] for row in development} & {row["id"] for row in confirmation}:
        raise ValueError("development and confirmation IDs overlap")
    output_dir.mkdir(parents=True, exist_ok=False)
    development_path = output_dir / "development.jsonl"
    confirmation_path = output_dir / "confirmation.jsonl"
    _write_rows(development_path, development)
    _write_rows(confirmation_path, confirmation)
    manifest = {
        "format": "brace-msi.stratified-split.v1",
        "source_sha256": source_sha,
        "classes": classes,
        "development_fraction": development_fraction,
        "salt_sha256": _sha256_text(salt),
        "exposure": exposure,
        "development_rows": len(development),
        "confirmation_rows": len(confirmation),
        "development_class_counts": dict(Counter(row["answer"] for row in development)),
        "confirmation_class_counts": dict(Counter(row["answer"] for row in confirmation)),
        "development_ids_sha256": _ids_sha(development),
        "confirmation_ids_sha256": _ids_sha(confirmation),
        "development_sha256": _sha256(development_path),
        "confirmation_sha256": _sha256(confirmation_path),
    }
    _atomic_json(manifest_path, manifest)
    return manifest


def create_oversampled_training_file(
    source: Path,
    output: Path,
    *,
    target_class: str,
    multiplier: int,
) -> dict[str, Any]:
    source = Path(source).resolve()
    output = Path(output).resolve()
    if isinstance(multiplier, bool) or not isinstance(multiplier, int) or not 1 <= multiplier <= 8:
        raise ValueError("multiplier must be an integer in [1, 8]")
    rows = _read_rows(source)
    targets = [row for row in rows if row.get("answer") == target_class]
    if not targets:
        raise ValueError("target class is not present")
    derived = list(rows)
    for copy_index in range(1, multiplier):
        for row in targets:
            duplicate = json.loads(json.dumps(row))
            duplicate["id"] = f"{row['id']}__oversample_{copy_index:02d}"
            meta = duplicate.setdefault("meta", {})
            meta["derived_method"] = "deterministic_random_oversampling"
            meta["derived_from_id_sha256"] = _sha256_text(row["id"])
            derived.append(duplicate)
    result = {
        "format": "brace-msi.oversampled-training.v1",
        "source_sha256": _sha256(source),
        "target_class": target_class,
        "multiplier": multiplier,
        "rows": len(derived),
        "class_counts": dict(Counter(row["answer"] for row in derived)),
    }
    if output.exists():
        if not output.is_file():
            raise ValueError("derived training output is not a file")
        if _sha256(output) != _sha256_bytes(_encode_rows(derived)):
            raise ValueError("existing derived training file differs")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_bytes(_encode_rows(derived))
        os.replace(temporary, output)
    result["sha256"] = _sha256(output)
    return result


def classification_metrics(
    expected: list[str], predicted: list[str], classes: list[str]
) -> dict[str, Any]:
    if len(expected) != len(predicted) or not expected:
        raise ValueError("expected and predicted labels must be nonempty and aligned")
    index = {label: position for position, label in enumerate(classes)}
    if len(index) != len(classes) or any(
        label not in index for label in [*expected, *predicted]
    ):
        raise ValueError("labels are outside the configured classes")
    confusion = [[0 for _ in classes] for _ in classes]
    for truth, guess in zip(expected, predicted, strict=True):
        confusion[index[truth]][index[guess]] += 1
    per_class: dict[str, float] = {}
    for position, label in enumerate(classes):
        actual = sum(confusion[position])
        guessed = sum(row[position] for row in confusion)
        denominator = actual + guessed
        per_class[label] = (
            2.0 * confusion[position][position] / denominator if denominator else 0.0
        )
    correct = sum(confusion[position][position] for position in range(len(classes)))
    return {
        "accuracy": correct / len(expected),
        "macro_f1": sum(per_class.values()) / len(per_class),
        "per_class_f1": per_class,
        "confusion_matrix": confusion,
        "rows": len(expected),
    }


def select_development_winner(
    candidates: list[dict[str, Any]],
    *,
    baseline_macro_f1: float,
    target_class: str,
    minimum_improvement: float,
    minimum_target_f1: float,
) -> dict[str, Any] | None:
    eligible = [
        candidate
        for candidate in candidates
        if float(candidate["metrics"]["macro_f1"])
        >= baseline_macro_f1 + minimum_improvement
        and float(candidate["metrics"]["per_class_f1"][target_class])
        >= minimum_target_f1
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda candidate: (
            float(candidate["metrics"]["macro_f1"]),
            float(candidate["metrics"]["per_class_f1"][target_class]),
            -float(candidate["cpu_seconds"]),
            candidate["id"],
        ),
    )


def evaluate_checkpoint(
    package: PackageAudit,
    checkpoint: Path,
    dataset: Path,
    *,
    classes: list[str],
    python_executable: Path | str,
) -> dict[str, Any]:
    rows = _read_rows(Path(dataset))
    requests = "".join(
        json.dumps(
            {"task": package.task, "inputs": row["inputs"]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    )
    environment = os.environ.copy()
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        BASELINE_CPU_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    started = time.monotonic()
    completed = subprocess.run(
        [
            str(python_executable),
            "-m",
            "baselines.predict",
            "--checkpoint",
            str(Path(checkpoint).resolve()),
        ],
        cwd=package.package_dir,
        env=environment,
        input=requests,
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    outputs = [
        json.loads(line) for line in completed.stdout.splitlines() if line.strip()
    ]
    if len(outputs) != len(rows):
        raise ValueError("prediction count does not match evaluation rows")
    predicted: list[str] = []
    for output in outputs:
        scores = output.get("outputs")
        if not isinstance(scores, list) or not scores:
            raise ValueError("classification output is invalid")
        best = max(scores, key=lambda item: float(item["score"]))
        predicted.append(str(best["label"]))
    metrics = classification_metrics(
        [str(row["answer"]) for row in rows], predicted, classes
    )
    metrics.update(
        evaluation_wall_seconds=time.monotonic() - started,
        dataset_sha256=_sha256(Path(dataset)),
        checkpoint_sha256=_sha256(Path(checkpoint)),
    )
    return metrics


def run_gas_oversampling_experiment(
    package: PackageAudit,
    runtime_root: Path,
    config: dict[str, Any],
    *,
    python_executable: Path | str,
) -> dict[str, Any]:
    runtime_root = Path(runtime_root).resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    config_sha = _sha256_bytes(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    if config.get("format") != "brace-msi.perf-a-oversampling.v1":
        raise ValueError("unsupported Gas optimization config")
    classes = list(
        json.loads(package.profile_path.read_text(encoding="utf-8"))["classes"]
    )
    split = freeze_stratified_development_confirmation(
        package.validation_path,
        runtime_root / "split",
        classes=classes,
        development_fraction=float(config["development_fraction"]),
        salt=str(config["split_salt"]),
        exposure=str(config["confirmation_exposure"]),
    )
    state_path = runtime_root / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("config_sha256") != config_sha:
            raise ValueError("experiment config changed")
        if state.get("official_package_tree_sha256") != package.package_tree_sha256:
            raise ValueError("official package changed")
    else:
        baseline_dev = evaluate_checkpoint(
            package,
            package.checkpoint_path,
            runtime_root / "split" / "development.jsonl",
            classes=classes,
            python_executable=python_executable,
        )
        state = {
            "format": "brace-msi.perf-a-oversampling-state.v1",
            "experiment_id": config["experiment_id"],
            "config_sha256": config_sha,
            "official_package_tree_sha256": package.package_tree_sha256,
            "official_checkpoint_sha256": package.checkpoint_sha256,
            "split_manifest_sha256": _sha256(
                runtime_root / "split" / "split-manifest.json"
            ),
            "baseline_development": baseline_dev,
            "candidates": [],
            "confirmation_opened": False,
            "official_test_opportunities_used": 0,
            "pytrio_calls": 0,
            "status": "running",
        }
        _atomic_json(state_path, state)

    completed_ids = {item["id"] for item in state["candidates"]}
    trainer = OfficialTrainer(python_executable, timeout_seconds=120)
    resource_limits = config["resource_limits"]
    for candidate in config["candidates"]:
        candidate_id = str(candidate["id"])
        if candidate_id in completed_ids:
            continue
        if len(state["candidates"]) >= int(resource_limits["max_candidates"]):
            raise ValueError("candidate resource limit exceeded")
        candidate_root = runtime_root / "candidates" / candidate_id
        train_path = candidate_root.parent / "derived" / f"{candidate_id}.jsonl"
        derived = create_oversampled_training_file(
            package.train_path,
            train_path,
            target_class=str(config["target_class"]),
            multiplier=int(candidate["target_multiplier"]),
        )
        development_path = runtime_root / "split" / "development.jsonl"
        research_package = _derived_package(
            package,
            train_path=train_path,
            train_info=derived,
            validation_path=development_path,
            validation_sha256=split["development_sha256"],
            validation_rows=int(split["development_rows"]),
            baseline_metrics=state["baseline_development"],
        )
        candidate_config = CandidateConfig(
            epochs=int(candidate["epochs"]),
            learning_rate=package.base_learning_rate
            * float(candidate["learning_rate_multiplier"]),
            batch_size=package.base_batch_size,
        )
        stage_id = f"perf-a-{candidate_id}"
        if candidate_root.is_dir() and (candidate_root / "candidate-receipt.json").is_file():
            receipt = recover_candidate_receipt(
                research_package,
                package.checkpoint_path,
                candidate_root,
                candidate_config,
                stage_id,
            )
        else:
            receipt = trainer.run_candidate(
                research_package,
                package.checkpoint_path,
                candidate_root,
                candidate_config,
                stage_id,
            )
        metrics = evaluate_checkpoint(
            package,
            candidate_root / "checkpoint.npz",
            development_path,
            classes=classes,
            python_executable=python_executable,
        )
        if not math.isclose(
            metrics["macro_f1"],
            receipt.metrics_after[package.primary_metric],
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError("independent development metric differs from trainer")
        state["candidates"].append(
            {
                "id": candidate_id,
                "configuration": candidate,
                "derived_training": derived,
                "checkpoint_sha256": receipt.checkpoint_sha256,
                "metrics": metrics,
                "cpu_seconds": receipt.cpu_seconds,
                "wall_seconds": receipt.wall_seconds,
                "peak_rss_bytes": receipt.peak_rss_bytes,
                "output_dir": str(candidate_root),
            }
        )
        total_cpu = sum(item["cpu_seconds"] for item in state["candidates"])
        total_wall = sum(item["wall_seconds"] for item in state["candidates"])
        peak_rss = max(item["peak_rss_bytes"] for item in state["candidates"])
        if (
            total_cpu > float(resource_limits["max_cpu_seconds"])
            or total_wall > float(resource_limits["max_wall_seconds"])
            or peak_rss > int(resource_limits["max_peak_rss_bytes"])
        ):
            state["status"] = "failed_resource_limit"
            _atomic_json(state_path, state)
            raise ValueError("candidate resource limit exceeded")
        _atomic_json(state_path, state)

    selected = select_development_winner(
        state["candidates"],
        baseline_macro_f1=float(state["baseline_development"]["macro_f1"]),
        target_class=str(config["target_class"]),
        minimum_improvement=float(config["minimum_development_improvement"]),
        minimum_target_f1=float(config["minimum_target_class_f1"]),
    )
    if selected is None:
        state["status"] = "stopped_no_candidate_met_development_gate"
        state["selected_candidate"] = None
        _atomic_json(state_path, state)
        return state

    state["selected_candidate"] = selected["id"]
    if not state["confirmation_opened"]:
        lock = {
            "format": "brace-msi.confirmation-open-lock.v1",
            "selected_candidate": selected["id"],
            "selected_checkpoint_sha256": selected["checkpoint_sha256"],
            "config_sha256": config_sha,
            "split_manifest_sha256": state["split_manifest_sha256"],
            "feedback_forbidden": True,
        }
        _atomic_json(runtime_root / "confirmation-open-lock.json", lock)
        state["confirmation_opened"] = True
        _atomic_json(state_path, state)
    if "confirmation" not in state:
        lock_path = runtime_root / "confirmation-open-lock.json"
        if not lock_path.is_file():
            raise ValueError("confirmation opened without a frozen selection lock")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if (
            lock.get("selected_candidate") != selected["id"]
            or lock.get("selected_checkpoint_sha256") != selected["checkpoint_sha256"]
            or lock.get("config_sha256") != config_sha
        ):
            raise ValueError("confirmation selection lock mismatch")
        confirmation_path = runtime_root / "split" / "confirmation.jsonl"
        state["confirmation"] = {
            "exposure": config["confirmation_exposure"],
            "baseline": evaluate_checkpoint(
                package,
                package.checkpoint_path,
                confirmation_path,
                classes=classes,
                python_executable=python_executable,
            ),
            "selected": evaluate_checkpoint(
                package,
                Path(selected["output_dir"]) / "checkpoint.npz",
                confirmation_path,
                classes=classes,
                python_executable=python_executable,
            ),
        }
    state["status"] = "completed"
    _atomic_json(state_path, state)
    return state


def _derived_package(
    package: PackageAudit,
    *,
    train_path: Path,
    train_info: dict[str, Any],
    validation_path: Path,
    validation_sha256: str,
    validation_rows: int,
    baseline_metrics: dict[str, Any],
) -> PackageAudit:
    train_rows = _read_rows(train_path)
    validation = _read_rows(validation_path)
    train_ids = frozenset(str(row["id"]) for row in train_rows)
    validation_ids = frozenset(str(row["id"]) for row in validation)
    if train_ids & validation_ids:
        raise ValueError("train and development IDs overlap")
    train_groups = frozenset(
        f"batch:{row.get('meta', {}).get('source_batch')}" for row in train_rows
    )
    validation_groups = frozenset(
        f"batch:{row.get('meta', {}).get('source_batch')}" for row in validation
    )
    return replace(
        package,
        train_rows=len(train_rows),
        validation_rows=validation_rows,
        train_ids=train_ids,
        validation_ids=validation_ids,
        train_groups=train_groups,
        validation_groups=validation_groups,
        baseline_metric=float(baseline_metrics[package.primary_metric]),
        baseline_metrics={
            "accuracy": float(baseline_metrics["accuracy"]),
            "macro_f1": float(baseline_metrics["macro_f1"]),
        },
        train_sha256=str(train_info["sha256"]),
        validation_sha256=validation_sha256,
        train_path=train_path,
        validation_path=validation_path,
    )


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("source must be a regular file")
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        identity = row.get("id") if isinstance(row, dict) else None
        if not isinstance(identity, str) or not identity or identity in ids:
            raise ValueError("source IDs must be unique nonempty strings")
        ids.add(identity)
        rows.append(row)
    if not rows:
        raise ValueError("source is empty")
    return rows


def _encode_rows(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_bytes(_encode_rows(rows))


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _ids_sha(rows: list[dict[str, Any]]) -> str:
    return _sha256_text("\n".join(sorted(row["id"] for row in rows)))


def _sha256(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
