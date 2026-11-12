"""Causal Gas batch conversion and bounded replay research utilities."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from .gas_optimization import evaluate_checkpoint
from .official_package import PackageAudit
from .official_trainer import CandidateConfig, OfficialTrainer, recover_candidate_receipt


def convert_gas_batch(
    source: Path,
    output: Path,
    *,
    batch_number: int,
    label_names: dict[int, str],
) -> dict[str, Any]:
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not 1 <= batch_number <= 10:
        raise ValueError("batch_number must be in [1, 10]")
    rows: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as handle:
        for index, raw in enumerate(handle, 1):
            tokens = raw.split()
            if not tokens:
                continue
            label_number = int(tokens[0])
            if label_number not in label_names:
                raise ValueError("unknown Gas class")
            features = [0.0] * 128
            seen: set[int] = set()
            for token in tokens[1:]:
                raw_index, raw_value = token.split(":", 1)
                feature_index = int(raw_index)
                if not 1 <= feature_index <= 128 or feature_index in seen:
                    raise ValueError("invalid or duplicate Gas feature")
                seen.add(feature_index)
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError("nonfinite Gas feature")
                features[feature_index - 1] = value
            if len(seen) != 128:
                raise ValueError("Gas row does not contain 128 features")
            rows.append(
                {
                    "id": f"gas_b{batch_number:02d}_{index:06d}",
                    "inputs": {"features": features},
                    "answer": label_names[label_number],
                    "meta": {
                        "source_batch": batch_number,
                        "source_index": index,
                    },
                }
            )
    if not rows:
        raise ValueError("Gas batch is empty")
    encoded = _encode_rows(rows)
    if output.exists():
        if not output.is_file() or output.read_bytes() != encoded:
            raise ValueError("existing converted Gas batch differs")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, output)
    return {
        "source_sha256": _sha256(source),
        "output_sha256": _sha256(output),
        "rows": len(rows),
        "batch_number": batch_number,
    }


def split_feedback_rows(
    rows: list[dict[str, Any]], *, holdout_fraction: float, salt: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.0 < holdout_fraction < 1.0 or not salt:
        raise ValueError("invalid feedback split settings")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["answer"])].append(row)
    train_ids: set[str] = set()
    for label, values in grouped.items():
        ordered = sorted(
            values,
            key=lambda row: _hash_text(f"{salt}\0{label}\0{row['id']}"),
        )
        if len(ordered) < 2:
            raise ValueError("each feedback class needs at least two samples")
        holdout_count = round(len(ordered) * holdout_fraction)
        holdout_count = min(len(ordered) - 1, max(1, holdout_count))
        train_ids.update(row["id"] for row in ordered[holdout_count:])
    train = [row for row in rows if row["id"] in train_ids]
    holdout = [row for row in rows if row["id"] not in train_ids]
    if {row["id"] for row in train} & {row["id"] for row in holdout}:
        raise ValueError("feedback split overlaps")
    return train, holdout


def build_replay_rows(
    history: list[dict[str, Any]], *, mode: str, capacity: int, seed: int
) -> list[dict[str, Any]]:
    if capacity < 0:
        raise ValueError("replay capacity must be nonnegative")
    if mode == "none" or capacity == 0:
        return []
    if mode == "uniform_hash":
        return sorted(
            history,
            key=lambda row: _hash_text(f"{seed}\0{row['id']}"),
        )[:capacity]
    if mode != "class_balanced_hash":
        raise ValueError("unsupported replay mode")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        grouped[str(row["answer"])].append(row)
    if not grouped:
        return []
    labels = sorted(grouped)
    base, extra = divmod(capacity, len(labels))
    selected: list[dict[str, Any]] = []
    for position, label in enumerate(labels):
        quota = base + (1 if position < extra else 0)
        ordered = sorted(
            grouped[label],
            key=lambda row: _hash_text(f"{seed}\0{label}\0{row['id']}"),
        )
        selected.extend(ordered[:quota])
    return sorted(selected, key=lambda row: str(row["id"]))


def replay_safety_gate(
    *,
    stable_current: float,
    candidate_current: float,
    stable_anchor: float,
    candidate_anchor: float,
    minimum_current_improvement: float,
    maximum_anchor_degradation: float,
) -> tuple[bool, str]:
    values = (
        stable_current,
        candidate_current,
        stable_anchor,
        candidate_anchor,
        minimum_current_improvement,
        maximum_anchor_degradation,
    )
    if not all(math.isfinite(float(value)) for value in values):
        return False, "nonfinite_metric"
    if candidate_current - stable_current < minimum_current_improvement:
        return False, "current_holdout_not_improved"
    if stable_anchor - candidate_anchor > maximum_anchor_degradation:
        return False, "anchor_degradation_exceeded"
    return True, "current_improved_anchor_retained"


def run_gas_replay_experiment(
    package: PackageAudit,
    raw_root: Path,
    runtime_root: Path,
    config: dict[str, Any],
    *,
    python_executable: Path | str,
) -> dict[str, Any]:
    if config.get("format") != "brace-msi.perf-a-replay.v1":
        raise ValueError("unsupported Gas replay config")
    development = [int(value) for value in config["development_batches"]]
    confirmation = [int(value) for value in config["confirmation_batches"]]
    forbidden = {int(value) for value in config["forbidden_batches"]}
    requested = development + confirmation
    if len(set(requested)) != len(requested) or set(requested) & forbidden:
        raise ValueError("batch phases overlap or include a forbidden batch")
    raw_root = Path(raw_root).resolve()
    dataset_root = raw_root / "Dataset" if (raw_root / "Dataset").is_dir() else raw_root
    runtime_root = Path(runtime_root).resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    config_sha = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    classes = list(
        json.loads(package.profile_path.read_text(encoding="utf-8"))["classes"]
    )
    label_names = {index + 1: label for index, label in enumerate(classes)}
    batches: dict[int, Path] = {}
    batch_manifest: dict[str, Any] = {}
    for batch_number in requested:
        source = dataset_root / f"batch{batch_number}.dat"
        expected_sha = str(config["raw_batch_sha256"][str(batch_number)]).lower()
        if _sha256(source) != expected_sha:
            raise ValueError(f"raw batch hash mismatch: {batch_number}")
        output = runtime_root / "converted" / f"batch{batch_number}.jsonl"
        batch_manifest[str(batch_number)] = convert_gas_batch(
            source, output, batch_number=batch_number, label_names=label_names
        )
        batches[batch_number] = output
    _atomic_json(runtime_root / "batch-manifest.json", batch_manifest)

    state_path = runtime_root / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("config_sha256") != config_sha:
            raise ValueError("Gas replay config changed")
        if state.get("official_package_tree_sha256") != package.package_tree_sha256:
            raise ValueError("official package changed")
        if state.get("status") == "completed":
            return state
    else:
        state = {
            "format": "brace-msi.perf-a-replay-state.v1",
            "experiment_id": config["experiment_id"],
            "config_sha256": config_sha,
            "official_package_tree_sha256": package.package_tree_sha256,
            "official_checkpoint_sha256": package.checkpoint_sha256,
            "batch_manifest_sha256": _sha256(runtime_root / "batch-manifest.json"),
            "phase": "development",
            "strategies": {},
            "selected_strategy": None,
            "official_test_opportunities_used": 0,
            "pytrio_calls": 0,
            "status": "running",
        }
        _atomic_json(state_path, state)

    trainer = OfficialTrainer(python_executable, timeout_seconds=180)
    static_development = [
        evaluate_checkpoint(
            package,
            package.checkpoint_path,
            batches[batch_number],
            classes=classes,
            python_executable=python_executable,
        )
        for batch_number in development
    ]
    state["static_development_summary"] = {
        "mean_prequential_macro_f1": sum(
            float(item["macro_f1"]) for item in static_development
        )
        / len(static_development),
        "worst_prequential_macro_f1": min(
            float(item["macro_f1"]) for item in static_development
        ),
        "batch_metrics": static_development,
    }
    for strategy in config["strategies"]:
        strategy_id = str(strategy["id"])
        strategy_state = state["strategies"].setdefault(
            strategy_id,
            {
                "configuration": strategy,
                "stable_checkpoint": str(package.checkpoint_path),
                "stable_sha256": package.checkpoint_sha256,
                "history_batches": [],
                "rounds": [],
                "development_complete": False,
                "confirmation_complete": False,
            },
        )
        if not strategy_state["development_complete"]:
            _run_strategy_phase(
                package,
                batches,
                development,
                runtime_root,
                config,
                strategy_id,
                strategy_state,
                trainer,
                classes,
                python_executable,
                train_after_last=True,
            )
            strategy_state["development_complete"] = True
            _atomic_json(state_path, state)

    development_summary: dict[str, Any] = {}
    for strategy_id, strategy_state in state["strategies"].items():
        values = [
            float(row["prequential"]["macro_f1"])
            for row in strategy_state["rounds"]
            if row["phase"] == "development"
        ]
        development_summary[strategy_id] = {
            "mean_prequential_macro_f1": sum(values) / len(values),
            "worst_prequential_macro_f1": min(values),
            "batch_count": len(values),
            "accepted_updates": sum(
                1
                for row in strategy_state["rounds"]
                if row["phase"] == "development" and row.get("deployed")
            ),
        }
    state["development_summary"] = development_summary
    current = development_summary["current_only"]
    ranked = sorted(
        development_summary,
        key=lambda strategy_id: (
            development_summary[strategy_id]["mean_prequential_macro_f1"],
            development_summary[strategy_id]["worst_prequential_macro_f1"],
            strategy_id,
        ),
        reverse=True,
    )
    best = ranked[0]
    minimum_gain = float(config["selection"]["minimum_mean_gain_over_current_only"])
    if (
        best != "current_only"
        and development_summary[best]["mean_prequential_macro_f1"]
        >= current["mean_prequential_macro_f1"] + minimum_gain
    ):
        selected = best
        selection_reason = "replay_beats_current_only_gate"
    else:
        selected = "current_only"
        selection_reason = "complex_replay_did_not_beat_simple_gate"
    state["selected_strategy"] = selected
    state["selection_reason"] = selection_reason
    freeze = {
        "format": "brace-msi.gas-replay-development-freeze.v1",
        "config_sha256": config_sha,
        "development_summary": development_summary,
        "selected_strategy": selected,
        "selection_reason": selection_reason,
        "confirmation_feedback_forbidden": True,
    }
    freeze_path = runtime_root / "development-freeze.json"
    if freeze_path.exists():
        if json.loads(freeze_path.read_text(encoding="utf-8")) != freeze:
            raise ValueError("development freeze changed")
    else:
        _atomic_json(freeze_path, freeze)
    state["phase"] = "confirmation"
    _atomic_json(state_path, state)

    for strategy in config["strategies"]:
        strategy_id = str(strategy["id"])
        strategy_state = state["strategies"][strategy_id]
        if strategy_state["confirmation_complete"]:
            continue
        _run_strategy_phase(
            package,
            batches,
            confirmation,
            runtime_root,
            config,
            strategy_id,
            strategy_state,
            trainer,
            classes,
            python_executable,
            train_after_last=False,
        )
        strategy_state["confirmation_complete"] = True
        _atomic_json(state_path, state)

    confirmation_summary: dict[str, Any] = {}
    for strategy_id, strategy_state in state["strategies"].items():
        values = [
            float(row["prequential"]["macro_f1"])
            for row in strategy_state["rounds"]
            if row["phase"] == "confirmation"
        ]
        confirmation_summary[strategy_id] = {
            "mean_prequential_macro_f1": sum(values) / len(values),
            "worst_prequential_macro_f1": min(values),
            "batch_count": len(values),
        }
    state["confirmation_summary"] = confirmation_summary
    static_confirmation = [
        evaluate_checkpoint(
            package,
            package.checkpoint_path,
            batches[batch_number],
            classes=classes,
            python_executable=python_executable,
        )
        for batch_number in confirmation
    ]
    state["static_confirmation_summary"] = {
        "mean_prequential_macro_f1": sum(
            float(item["macro_f1"]) for item in static_confirmation
        )
        / len(static_confirmation),
        "worst_prequential_macro_f1": min(
            float(item["macro_f1"]) for item in static_confirmation
        ),
        "batch_metrics": static_confirmation,
    }
    state["phase"] = "complete"
    state["status"] = "completed"
    _check_resource_limits(state, config)
    _atomic_json(state_path, state)
    return state


def _run_strategy_phase(
    package: PackageAudit,
    batches: dict[int, Path],
    batch_numbers: list[int],
    runtime_root: Path,
    config: dict[str, Any],
    strategy_id: str,
    strategy_state: dict[str, Any],
    trainer: OfficialTrainer,
    classes: list[str],
    python_executable: Path | str,
    *,
    train_after_last: bool,
) -> None:
    strategy = strategy_state["configuration"]
    phase = "development" if batch_numbers == list(config["development_batches"]) else "confirmation"
    completed = {
        int(row["batch"])
        for row in strategy_state["rounds"]
        if row["phase"] == phase
    }
    history = []
    for number in strategy_state["history_batches"]:
        history.extend(_read_rows(batches[int(number)]))
    for position, batch_number in enumerate(batch_numbers):
        if batch_number in completed:
            continue
        stable_checkpoint = Path(strategy_state["stable_checkpoint"])
        batch_rows = _read_rows(batches[batch_number])
        prequential = evaluate_checkpoint(
            package,
            stable_checkpoint,
            batches[batch_number],
            classes=classes,
            python_executable=python_executable,
        )
        should_train = train_after_last or position < len(batch_numbers) - 1
        round_record: dict[str, Any] = {
            "phase": phase,
            "batch": batch_number,
            "prediction_checkpoint_sha256": _sha256(stable_checkpoint),
            "prequential": prequential,
            "label_feedback_after_prediction": True,
            "candidate_trained": should_train,
        }
        if should_train:
            train_rows, holdout_rows = split_feedback_rows(
                batch_rows,
                holdout_fraction=float(config["current_holdout_fraction"]),
                salt=f"{config['split_salt']}:{batch_number}",
            )
            replay_rows = build_replay_rows(
                history,
                mode=str(strategy["replay_mode"]),
                capacity=int(strategy["buffer_size"]),
                seed=int(config["seed"]),
            )
            candidate_dir = runtime_root / "strategies" / strategy_id / "candidates" / f"batch-{batch_number:02d}"
            derived_dir = runtime_root / "strategies" / strategy_id / "derived" / f"batch-{batch_number:02d}"
            train_path = derived_dir / "train.jsonl"
            holdout_path = derived_dir / "holdout.jsonl"
            _write_rows_once(train_path, [*train_rows, *replay_rows])
            _write_rows_once(holdout_path, holdout_rows)
            research_package = _research_package(
                package, train_path, holdout_path, stable_checkpoint, classes, python_executable
            )
            candidate_config = CandidateConfig(
                epochs=int(strategy["epochs"]),
                learning_rate=package.base_learning_rate
                * float(strategy["learning_rate_multiplier"]),
                batch_size=package.base_batch_size,
            )
            estimated_cpu_seconds = (
                package.training_seconds
                / max(1, package.base_epochs)
                * (len(train_rows) + len(replay_rows))
                / max(1, package.train_rows)
                * candidate_config.epochs
            )
            if estimated_cpu_seconds > float(
                config["resource_limits"]["max_cpu_seconds"]
            ):
                raise ValueError("candidate estimated CPU exceeds experiment budget")
            stage_id = f"perf-a-{strategy_id}-b{batch_number:02d}"
            if candidate_dir.is_dir() and (candidate_dir / "candidate-receipt.json").is_file():
                receipt = recover_candidate_receipt(
                    research_package,
                    stable_checkpoint,
                    candidate_dir,
                    candidate_config,
                    stage_id,
                )
            else:
                receipt = trainer.run_candidate(
                    research_package,
                    stable_checkpoint,
                    candidate_dir,
                    candidate_config,
                    stage_id,
                )
            stable_current = evaluate_checkpoint(
                package, stable_checkpoint, holdout_path, classes=classes, python_executable=python_executable
            )
            candidate_current = evaluate_checkpoint(
                package, candidate_dir / "checkpoint.npz", holdout_path, classes=classes, python_executable=python_executable
            )
            stable_anchor = evaluate_checkpoint(
                package, stable_checkpoint, package.train_path, classes=classes, python_executable=python_executable
            )
            candidate_anchor = evaluate_checkpoint(
                package, candidate_dir / "checkpoint.npz", package.train_path, classes=classes, python_executable=python_executable
            )
            gate = replay_safety_gate(
                stable_current=float(stable_current["macro_f1"]),
                candidate_current=float(candidate_current["macro_f1"]),
                stable_anchor=float(stable_anchor["macro_f1"]),
                candidate_anchor=float(candidate_anchor["macro_f1"]),
                minimum_current_improvement=float(
                    config["safety_gate"]["minimum_current_holdout_improvement"]
                ),
                maximum_anchor_degradation=float(
                    config["safety_gate"]["maximum_anchor_macro_f1_degradation"]
                ),
            )
            deployed, reason = gate
            round_record.update(
                train_rows=len(train_rows),
                replay_rows=len(replay_rows),
                estimated_cpu_seconds=estimated_cpu_seconds,
                holdout_rows=len(holdout_rows),
                train_ids_sha256=_ids_sha([*train_rows, *replay_rows]),
                holdout_ids_sha256=_ids_sha(holdout_rows),
                candidate_checkpoint_sha256=receipt.checkpoint_sha256,
                stable_current_holdout=stable_current,
                candidate_current_holdout=candidate_current,
                stable_anchor=stable_anchor,
                candidate_anchor=candidate_anchor,
                deployed=deployed,
                gate_reason=reason,
                cpu_seconds=receipt.cpu_seconds,
                wall_seconds=receipt.wall_seconds,
                peak_rss_bytes=receipt.peak_rss_bytes,
                candidate_output=str(candidate_dir),
            )
            if deployed:
                strategy_state["stable_checkpoint"] = str(candidate_dir / "checkpoint.npz")
                strategy_state["stable_sha256"] = receipt.checkpoint_sha256
        strategy_state["rounds"].append(round_record)
        strategy_state["history_batches"].append(batch_number)
        history.extend(batch_rows)


def _research_package(
    package: PackageAudit,
    train_path: Path,
    validation_path: Path,
    stable_checkpoint: Path,
    classes: list[str],
    python_executable: Path | str,
) -> PackageAudit:
    train_rows = _read_rows(train_path)
    validation_rows = _read_rows(validation_path)
    train_ids = frozenset(row["id"] for row in train_rows)
    validation_ids = frozenset(row["id"] for row in validation_rows)
    if train_ids & validation_ids:
        raise ValueError("round train and holdout IDs overlap")
    baseline = evaluate_checkpoint(
        package,
        stable_checkpoint,
        validation_path,
        classes=classes,
        python_executable=python_executable,
    )
    return replace(
        package,
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        train_ids=train_ids,
        validation_ids=validation_ids,
        train_groups=frozenset(
            f"batch:{row['meta']['source_batch']}" for row in train_rows
        ),
        validation_groups=frozenset(
            f"batch:{row['meta']['source_batch']}" for row in validation_rows
        ),
        baseline_metric=float(baseline["macro_f1"]),
        baseline_metrics={
            "accuracy": float(baseline["accuracy"]),
            "macro_f1": float(baseline["macro_f1"]),
        },
        train_sha256=_sha256(train_path),
        validation_sha256=_sha256(validation_path),
        train_path=train_path,
        validation_path=validation_path,
    )


def _check_resource_limits(state: dict[str, Any], config: dict[str, Any]) -> None:
    candidate_rows = [
        row
        for strategy in state["strategies"].values()
        for row in strategy["rounds"]
        if row.get("candidate_trained")
    ]
    limits = config["resource_limits"]
    if len(candidate_rows) > int(limits["max_total_candidates"]):
        raise ValueError("replay candidate limit exceeded")
    if sum(float(row["cpu_seconds"]) for row in candidate_rows) > float(limits["max_cpu_seconds"]):
        raise ValueError("replay CPU limit exceeded")
    if sum(float(row["wall_seconds"]) for row in candidate_rows) > float(limits["max_wall_seconds"]):
        raise ValueError("replay wall limit exceeded")
    if candidate_rows and max(int(row["peak_rss_bytes"]) for row in candidate_rows) > int(limits["max_peak_rss_bytes"]):
        raise ValueError("replay memory limit exceeded")


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_rows_once(path: Path, rows: list[dict[str, Any]]) -> None:
    encoded = _encode_rows(rows)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("derived replay dataset changed")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def _ids_sha(rows: list[dict[str, Any]]) -> str:
    return _hash_text("\n".join(sorted(str(row["id"]) for row in rows)))


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _encode_rows(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
