"""Local exposed-stream comparison that genuinely continues official checkpoints."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Literal

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error

from .official_package import PackageAudit, audit_package_root
from .official_public_stream import OfficialCheckpointPredictor, freeze_public_validation_stream
from .official_trainer import CandidateConfig, OfficialTrainer


StreamPolicy = Literal["static", "fixed_update", "deterministic_dual_loop"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("materialized candidate dataset cannot be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _targets(task: str, rows: list[dict[str, Any]]) -> np.ndarray:
    if task == "classification":
        return np.asarray([str(row["answer"]) for row in rows], dtype=str)
    values = np.asarray([float(row["answer"]) for row in rows], dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("nonfinite regression target")
    return values


def _metrics(task: str, expected: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    if task == "classification":
        return {
            "macro_f1": float(f1_score(expected, predicted, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(expected, predicted)),
        }
    error = predicted.astype(float) - expected.astype(float)
    nasa = np.where(error >= 0.0, np.exp(np.minimum(error / 10.0, 50.0)) - 1.0,
                    np.exp(np.minimum(-error / 13.0, 50.0)) - 1.0)
    return {
        "rmse": float(mean_squared_error(expected, predicted) ** 0.5),
        "mae": float(mean_absolute_error(expected, predicted)),
        "nasa_score": float(np.sum(nasa)),
    }


def _primary(package: PackageAudit, metrics: dict[str, float]) -> float:
    value = float(metrics[package.primary_metric])
    if not math.isfinite(value):
        raise ValueError("primary metric is nonfinite")
    return value


def _split_indices_by_class(rows: list[dict[str, Any]], modulus: int) -> tuple[list[int], list[int]]:
    grouped: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        grouped.setdefault(str(row["answer"]), []).append(index)
    holdout = {
        index
        for indices in grouped.values()
        for position, index in enumerate(indices)
        if position % modulus == modulus - 1
    }
    if not holdout:
        holdout.add(len(rows) - 1)
    return (
        [index for index in range(len(rows)) if index not in holdout],
        sorted(holdout),
    )


def _split_rows(
    task: str, rows: list[dict[str, Any]], *, anchor: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = list(rows)
    anchor_rows: list[dict[str, Any]] = []
    if anchor:
        if task == "classification":
            keep, held = _split_indices_by_class(remaining, 10)
        else:
            count = max(1, len(remaining) // 10)
            held = list(range(count))
            keep = list(range(count, len(remaining)))
        anchor_rows = [remaining[index] for index in held]
        remaining = [remaining[index] for index in keep]
    if task == "classification":
        update_indices, gate_indices = _split_indices_by_class(remaining, 5)
    else:
        gate_count = max(1, len(remaining) // 5)
        update_indices = list(range(0, len(remaining) - gate_count))
        gate_indices = list(range(len(remaining) - gate_count, len(remaining)))
    update = [remaining[index] for index in update_indices]
    gate = [remaining[index] for index in gate_indices]
    if not update or not gate or (anchor and not anchor_rows):
        raise ValueError("feedback split is too small")
    return update, gate, anchor_rows


def _initial_anchor_and_replay(
    task: str, rows: list[dict[str, Any]], *, max_anchor_rows: int = 512
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if task == "classification":
        replay_indices, anchor_indices = _split_indices_by_class(rows, 10)
    else:
        groups: dict[str, list[int]] = {}
        for index, row in enumerate(rows):
            meta = row.get("meta", {})
            if "bearing" in meta:
                group = str(meta["bearing"])
            elif "source_subset" in meta and "unit" in meta:
                group = f"{meta['source_subset']}:{meta['unit']}"
            else:
                group = "ordered"
            groups.setdefault(group, []).append(index)
        anchor_indices = []
        for indices in groups.values():
            count = max(1, len(indices) // 10)
            anchor_indices.extend(indices[-count:])
        anchor_set = set(anchor_indices)
        replay_indices = [index for index in range(len(rows)) if index not in anchor_set]
    if len(anchor_indices) > max_anchor_rows:
        chosen_positions = {
            (len(anchor_indices) * index) // max_anchor_rows for index in range(max_anchor_rows)
        }
        selected = [
            index for position, index in enumerate(anchor_indices) if position in chosen_positions
        ]
        returned = [
            index for position, index in enumerate(anchor_indices) if position not in chosen_positions
        ]
        anchor_indices = selected
        replay_indices.extend(returned)
    replay_indices = sorted(replay_indices)
    anchor_indices = sorted(anchor_indices)
    return [rows[index] for index in anchor_indices], [rows[index] for index in replay_indices]


def _bounded_initial_replay(
    rows: list[dict[str, Any]], *, round_index: int, count: int
) -> list[dict[str, Any]]:
    if not rows or count <= 0:
        return []
    size = min(len(rows), count)
    start = ((round_index - 1) * size) % len(rows)
    return [rows[(start + offset) % len(rows)] for offset in range(size)]


def _ids(rows: list[dict[str, Any]]) -> frozenset[str]:
    values = frozenset(str(row["id"]) for row in rows)
    if len(values) != len(rows):
        raise ValueError("materialized rows contain duplicate IDs")
    return values


def _improved(package: PackageAudit, candidate: float, stable: float) -> bool:
    return candidate > stable if package.higher_is_better else candidate < stable


def _normalized_drop(package: PackageAudit, current: float, reference: float) -> float:
    denominator = max(abs(reference), 1e-12)
    raw = reference - current if package.higher_is_better else current - reference
    return max(0.0, raw / denominator)


def run_official_stream_policy(
    package: PackageAudit,
    policy: StreamPolicy,
    output_root: Path,
    trainer: OfficialTrainer,
    *,
    max_total_candidates: int = 8,
) -> dict[str, Any]:
    """Run one local policy; outputs are exposed-development evidence only."""

    if policy not in {"static", "fixed_update", "deterministic_dual_loop"}:
        raise ValueError(f"unsupported stream policy: {policy}")
    if not 1 <= max_total_candidates <= 8:
        raise ValueError("candidate limit must be in [1, 8]")
    output_root = Path(output_root)
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"experiment output already exists: {output_root}")
    output_root.mkdir(parents=True)
    stream = freeze_public_validation_stream(package, output_root / "stream", rounds=10)
    manifest_path = output_root / "stream" / "stream-manifest.json"
    predictor = OfficialCheckpointPredictor(package, output_root / "predictor")

    stable_checkpoint = package.checkpoint_path
    stable_sha = package.checkpoint_sha256
    shadow_checkpoint: Path | None = None
    anchor_rows, initial_replay_rows = _initial_anchor_and_replay(
        package.task, _read_rows(package.train_path)
    )
    quarantine: list[tuple[int, Path]] = []
    replay_paths: list[Path] = []
    rounds: list[dict[str, Any]] = []
    candidate_count = 0
    accepted_count = 0
    rollback_count = 0
    reference_metric: float | None = None
    total_cpu = 0.0
    total_wall = 0.0
    peak_rss = 0
    all_expected: list[np.ndarray] = []
    all_predicted: list[np.ndarray] = []

    for batch in stream.batches:
        round_index = batch.batch_index
        rows = _read_rows(batch.path)
        expected = _targets(package.task, rows)
        formal = predictor.predict_rows(
            stable_checkpoint, rows, stage_id=f"r{round_index:02d}-formal"
        )
        total_cpu += formal.cpu_seconds
        total_wall += formal.wall_seconds
        peak_rss = max(peak_rss, formal.peak_rss_bytes)
        metrics = _metrics(package.task, expected, formal.predictions)
        primary = _primary(package, metrics)
        all_expected.append(expected)
        all_predicted.append(formal.predictions)
        if reference_metric is None:
            reference_metric = primary

        shadow_delta: float | None = None
        rolled_back = False
        if shadow_checkpoint is not None:
            shadow = predictor.predict_rows(
                shadow_checkpoint, rows, stage_id=f"r{round_index:02d}-shadow"
            )
            total_cpu += shadow.cpu_seconds
            total_wall += shadow.wall_seconds
            peak_rss = max(peak_rss, shadow.peak_rss_bytes)
            shadow_primary = _primary(package, _metrics(package.task, expected, shadow.predictions))
            shadow_delta = (
                primary - shadow_primary
                if package.higher_is_better
                else shadow_primary - primary
            )
            if policy == "deterministic_dual_loop" and shadow_delta < 0.0:
                stable_checkpoint = shadow_checkpoint
                stable_sha = _sha256(stable_checkpoint)
                rollback_count += 1
                rolled_back = True
            shadow_checkpoint = None

        update_rows, gate_rows, new_anchor = _split_rows(
            package.task, rows, anchor=False
        )
        if new_anchor:
            raise RuntimeError("public feedback must not replace the fixed initial Anchor")
        round_root = output_root / "round-data" / f"round-{round_index:02d}"
        update_path = round_root / "update.jsonl"
        gate_path = round_root / "gate.jsonl"
        _write_rows(update_path, update_rows)
        _write_rows(gate_path, gate_rows)
        for eligible_round, replay_path in quarantine:
            if round_index >= eligible_round:
                replay_paths.append(replay_path)
        quarantine = [item for item in quarantine if round_index < item[0]]

        performance_drop = _normalized_drop(package, primary, reference_metric)
        should_train = False
        if policy == "fixed_update":
            should_train = round_index in {1, 4, 7}
        elif policy == "deterministic_dual_loop":
            should_train = candidate_count < 3 or performance_drop >= 0.05
        if candidate_count >= max_total_candidates:
            should_train = False

        candidate_records: list[dict[str, Any]] = []
        deployed = False
        if should_train:
            mechanisms = [
                "REPLAY_REFIT" if policy == "deterministic_dual_loop" else "INCREMENTAL_UPDATE"
            ]
            for candidate_number, mechanism in enumerate(mechanisms, 1):
                train_rows = list(update_rows)
                if mechanism == "REPLAY_REFIT":
                    train_rows.extend(
                        _bounded_initial_replay(
                            initial_replay_rows,
                            round_index=round_index,
                            count=max(len(update_rows), 256),
                        )
                    )
                    for replay_path in replay_paths:
                        train_rows.extend(_read_rows(replay_path))
                train_path = round_root / f"train-c{candidate_number}.jsonl"
                _write_rows(train_path, train_rows)
                stage_id = f"{policy}-r{round_index:02d}-c{candidate_number}"
                output = output_root / "candidates" / stage_id
                receipt = trainer.run_stream_candidate(
                    package,
                    stable_checkpoint,
                    train_path,
                    gate_path,
                    output,
                    CandidateConfig(1, package.base_learning_rate, package.base_batch_size),
                    stage_id,
                    allowed_train_ids=_ids(train_rows),
                    allowed_gate_ids=_ids(gate_rows),
                )
                candidate_count += 1
                total_cpu += receipt.cpu_seconds
                total_wall += receipt.wall_seconds
                peak_rss = max(peak_rss, receipt.peak_rss_bytes)
                candidate_checkpoint = output / "checkpoint.npz"
                stable_gate = float(receipt.metrics_before[package.primary_metric])
                candidate_gate = float(receipt.metrics_after[package.primary_metric])

                stable_anchor = predictor.predict_rows(
                    stable_checkpoint, anchor_rows, stage_id=f"{stage_id}-anchor-stable"
                )
                candidate_anchor = predictor.predict_rows(
                    candidate_checkpoint, anchor_rows, stage_id=f"{stage_id}-anchor-candidate"
                )
                total_cpu += stable_anchor.cpu_seconds + candidate_anchor.cpu_seconds
                total_wall += stable_anchor.wall_seconds + candidate_anchor.wall_seconds
                peak_rss = max(
                    peak_rss,
                    stable_anchor.peak_rss_bytes,
                    candidate_anchor.peak_rss_bytes,
                )
                anchor_expected = _targets(package.task, anchor_rows)
                stable_anchor_primary = _primary(
                    package,
                    _metrics(package.task, anchor_expected, stable_anchor.predictions),
                )
                candidate_anchor_primary = _primary(
                    package,
                    _metrics(package.task, anchor_expected, candidate_anchor.predictions),
                )
                if package.higher_is_better:
                    anchor_safe = candidate_anchor_primary >= stable_anchor_primary - 0.05
                else:
                    anchor_safe = candidate_anchor_primary <= stable_anchor_primary * 1.05 + 1e-9
                if package.higher_is_better:
                    gate_improved = candidate_gate - stable_gate >= 0.005
                else:
                    gate_improved = stable_gate - candidate_gate >= max(0.5, stable_gate * 0.01)
                accepted = policy == "fixed_update" or (gate_improved and anchor_safe)
                record = {
                    "candidate_id": stage_id,
                    "mechanism": mechanism,
                    "parent_sha256": receipt.parent_sha256,
                    "checkpoint_sha256": receipt.checkpoint_sha256,
                    "gate_before": stable_gate,
                    "gate_after": candidate_gate,
                    "anchor_before": stable_anchor_primary,
                    "anchor_after": candidate_anchor_primary,
                    "gate_improved": gate_improved,
                    "anchor_safe": anchor_safe,
                    "accepted": accepted,
                    "cpu_seconds": receipt.cpu_seconds,
                    "wall_seconds": receipt.wall_seconds,
                    "peak_rss_bytes": receipt.peak_rss_bytes,
                    "checkpoint_bytes": candidate_checkpoint.stat().st_size,
                }
                candidate_records.append(record)
                if accepted:
                    predecessor = stable_checkpoint
                    stable_checkpoint = candidate_checkpoint
                    stable_sha = receipt.checkpoint_sha256
                    shadow_checkpoint = predecessor
                    accepted_count += 1
                    deployed = True
                    break
                if (
                    policy == "deterministic_dual_loop"
                    and candidate_number == 1
                    and replay_paths
                    and candidate_count < max_total_candidates
                ):
                    mechanisms.append(
                        "INCREMENTAL_UPDATE"
                        if mechanism == "REPLAY_REFIT"
                        else "REPLAY_REFIT"
                    )

        quarantine.append((round_index + 2, gate_path))
        round_record = {
            "round": round_index,
            "batch_id": batch.batch_id,
            "sample_count": batch.sample_count,
            "prediction_submitted_before_feedback": True,
            "historically_exposed": True,
            "metrics": metrics,
            "primary_metric": primary,
            "performance_drop": performance_drop,
            "candidates": candidate_records,
            "decision": "deploy" if deployed else "reject" if candidate_records else "noop",
            "stable_sha256": stable_sha,
            "shadow_delta": shadow_delta,
            "rolled_back": rolled_back,
        }
        rounds.append(round_record)
        _atomic_json(output_root / "state.json", {"rounds": rounds, "stable_sha256": stable_sha})

    aggregate_expected = np.concatenate(all_expected)
    aggregate_predicted = np.concatenate(all_predicted)
    aggregate_metrics = _metrics(package.task, aggregate_expected, aggregate_predicted)
    result = {
        "format": "brace-msi.official-exposed-stream-policy.v1",
        "profile": package.profile,
        "task": package.task,
        "policy": policy,
        "complete": len(rounds) == 10,
        "formal_eligible": False,
        "historically_exposed": True,
        "official_test_opportunities_used": 0,
        "initial_checkpoint_sha256": package.checkpoint_sha256,
        "stable_checkpoint": str(stable_checkpoint),
        "stable_sha256": stable_sha,
        "stream_manifest_sha256": _sha256(manifest_path),
        "candidate_count": candidate_count,
        "accepted_count": accepted_count,
        "rollback_count": rollback_count,
        "aggregate_metrics": aggregate_metrics,
        "cpu_seconds": total_cpu,
        "wall_seconds": total_wall,
        "peak_rss_bytes": peak_rss,
        "rounds": rounds,
    }
    _atomic_json(output_root / "result.json", result)
    return result


def _completed_attempt(policy_root: Path) -> dict[str, Any] | None:
    for result_path in sorted(policy_root.glob("attempt-*/result.json")):
        value = json.loads(result_path.read_text(encoding="utf-8"))
        if value.get("complete") is True and len(value.get("rounds", [])) == 10:
            return value
    return None


def run_official_stream_matrix(
    package_root: Path,
    package_config_path: Path,
    output_root: Path,
    *,
    policies: tuple[StreamPolicy, ...] = (
        "static",
        "fixed_update",
        "deterministic_dual_loop",
    ),
    experiment_id: str = "DUAL-EXPERIMENT-001-A1",
    max_total_candidates: int = 8,
    timeout_seconds: float = 600.0,
) -> dict[str, Any]:
    """Run/resume the deterministic A/B/C matrix while preserving failed attempts."""

    package_config = json.loads(Path(package_config_path).read_text(encoding="utf-8"))
    audits = audit_package_root(Path(package_root), package_config)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    trainer = OfficialTrainer(
        __import__("sys").executable,
        timeout_seconds=timeout_seconds,
        allowed_learning_rate_multipliers=(0.5, 1.0),
    )
    results: dict[str, dict[str, Any]] = {}
    for profile in ("A", "B", "C"):
        results[profile] = {}
        for policy in policies:
            policy_root = output_root / profile / policy
            policy_root.mkdir(parents=True, exist_ok=True)
            result = _completed_attempt(policy_root)
            if result is None:
                attempts = tuple(policy_root.glob("attempt-*"))
                attempt_root = policy_root / f"attempt-{len(attempts) + 1:02d}"
                result = run_official_stream_policy(
                    audits[profile],
                    policy,
                    attempt_root,
                    trainer,
                    max_total_candidates=max_total_candidates,
                )
            results[profile][policy] = result

    for profile, policy_results in results.items():
        manifest_hashes = {
            str(value["stream_manifest_sha256"]) for value in policy_results.values()
        }
        if len(manifest_hashes) != 1:
            raise ValueError(f"{profile} policies did not share one frozen stream")
    summary = {
        "format": "brace-msi.official-exposed-stream-matrix.v1",
        "experiment_id": experiment_id,
        "complete": all(
            bool(value.get("complete"))
            for profile_results in results.values()
            for value in profile_results.values()
        ),
        "historically_exposed": True,
        "formal_eligible": False,
        "official_test_opportunities_used": 0,
        "policies": list(policies),
        "results": results,
    }
    _atomic_json(output_root / "summary.json", summary)
    return summary
