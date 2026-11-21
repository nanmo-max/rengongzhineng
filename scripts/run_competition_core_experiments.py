"""Run the resumable Competition Core development/confirmation matrix.

The runner is local-only.  It never enters the formal upload image, never
calls the official platform, and opens each confirmation file once only after
all development trajectories and the winning Core strategy are frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import time
from typing import Any, Mapping

import numpy as np
import psutil


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brace_formal.data import DataBatch, load_rows  # noqa: E402
from brace_formal.metrics import evaluate, resolve_metric_contract  # noqa: E402
from brace_formal.model import FormalModel  # noqa: E402
from brace_formal.recipes import RecipeRegistry, execute_recipe  # noqa: E402
from brace_formal.selection import ArtifactEvaluation, select_artifact  # noqa: E402
from brace_msi.competition_simulator import _rows, _write_jsonl, _write_parent  # noqa: E402


FORMAT = "brace-msi.competition-core-experiments.v1"
SUMMARY_FORMAT = "brace-msi.competition-core-experiment-result.v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_manifest(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise ValueError("competition experiment manifest is invalid")
    if payload.get("confirmation_feedback") is not False or payload.get("confirmation_read_policy") != "once_after_development_freeze":
        raise ValueError("confirmation data must never feed development selection")
    if payload.get("rounds") != 10:
        raise ValueError("competition experiment requires exactly ten rounds")
    strategies = payload.get("strategies")
    if not isinstance(strategies, dict) or not strategies:
        raise ValueError("strategies are required")
    for name, strategy in strategies.items():
        if not isinstance(name, str) or not isinstance(strategy, dict):
            raise ValueError("strategy manifest is invalid")
        recipes = strategy.get("recipes", {})
        if not isinstance(recipes, dict) or set(recipes) - {"classification", "regression"}:
            raise ValueError("recipes may route only by task contract")
        if strategy.get("kind") not in {"static", "fixed", "competition_core"}:
            raise ValueError("unknown strategy kind")
    return payload


def validate_sources(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    root = Path(str(manifest["official_package_root"]))
    results: dict[str, dict[str, Any]] = {}
    for key, item in manifest["packages"].items():
        package = root / item["directory"]
        checkpoint = package / "checkpoint.npz"
        train_path = package / "public" / "train.jsonl"
        confirmation = package / "public" / "validation.jsonl"
        observed = {
            "checkpoint_sha256": _sha(checkpoint),
            "train_sha256": _sha(train_path),
            "confirmation_sha256": _sha(confirmation),
        }
        results[str(key)] = {
            **observed,
            "expected_checkpoint_sha256": item["checkpoint_sha256"],
            "expected_train_sha256": item["train_sha256"],
            "expected_confirmation_sha256": item["confirmation_sha256"],
            "valid": (
                observed["checkpoint_sha256"] == item["checkpoint_sha256"]
                and observed["train_sha256"] == item["train_sha256"]
                and observed["confirmation_sha256"] == item["confirmation_sha256"]
            ),
        }
    if not all(item["valid"] for item in results.values()):
        raise ValueError("official source hash mismatch")
    return results


def prepare_output(manifest: Mapping[str, Any], output: Path | str) -> str:
    root = Path(output)
    fingerprint = hashlib.sha256(_canonical(manifest)).hexdigest()
    marker = root / "manifest-lock.json"
    if root.exists():
        if not marker.is_file():
            raise ValueError("existing output has no manifest lock")
        locked = json.loads(marker.read_text(encoding="utf-8"))
        if locked.get("manifest_sha256") != fingerprint:
            raise ValueError("existing output belongs to a different manifest")
        return fingerprint
    root.mkdir(parents=True)
    _write_json(marker, {"format": FORMAT, "experiment_id": manifest["experiment_id"], "manifest_sha256": fingerprint})
    return fingerprint


def validate_parent_lineage(rounds: list[Mapping[str, Any]]) -> bool:
    if not rounds:
        return False
    for index, item in enumerate(rounds, 1):
        if item.get("round_index") != index:
            return False
        if index > 1 and item.get("parent_sha256") != rounds[index - 2].get("selected_sha256"):
            return False
    return True


def _raw_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _split_indices(raw: list[dict[str, Any]], task: str) -> list[tuple[np.ndarray, np.ndarray]]:
    rounds: list[list[int]] = [[] for _ in range(10)]
    if task == "classification":
        by_label: dict[str, list[int]] = {}
        for index, row in enumerate(raw):
            by_label.setdefault(str(row["answer"]), []).append(index)
        for indices in by_label.values():
            for offset, chunk in enumerate(np.array_split(np.asarray(indices, dtype=np.int64), 10)):
                rounds[offset].extend(int(value) for value in chunk)
        result = []
        for round_indices in rounds:
            ordered = np.asarray(sorted(round_indices), dtype=np.int64)
            gate_mask = np.arange(len(ordered)) % 5 == 0
            gate = ordered[gate_mask]
            update = ordered[~gate_mask]
            result.append((update, gate))
        return result

    metas = [row.get("meta") if isinstance(row.get("meta"), dict) else {} for row in raw]
    if all("bearing" in meta and "snapshot" in meta for meta in metas):
        groups: dict[str, list[int]] = {}
        for index, meta in enumerate(metas):
            groups.setdefault(str(meta["bearing"]), []).append(index)
        ordered_groups = sorted(groups)
        chunks = {
            group: np.array_split(np.asarray(sorted(indices, key=lambda value: int(metas[value]["snapshot"])), dtype=np.int64), 10)
            for group, indices in groups.items()
        }
        for round_index in range(10):
            gate_group = ordered_groups[round_index % len(ordered_groups)]
            gate = chunks[gate_group][round_index]
            update = np.concatenate([chunks[group][round_index] for group in ordered_groups if group != gate_group])
            rounds[round_index] = [int(value) for value in np.concatenate([update, gate])]
            if not len(update) or not len(gate):
                raise ValueError("bearing proxy round has empty update or gate")
            rounds[round_index] = []
            rounds[round_index].extend(int(value) for value in update)
            rounds[round_index].extend(int(value) for value in gate)
            # Return immediately below from the preserved update/gate arrays.
        return [
            (
                np.concatenate([chunks[group][idx] for group in ordered_groups if group != ordered_groups[idx % len(ordered_groups)]]),
                chunks[ordered_groups[idx % len(ordered_groups)]][idx],
            )
            for idx in range(10)
        ]

    if all("unit" in meta for meta in metas):
        groups: dict[str, list[int]] = {}
        for index, meta in enumerate(metas):
            groups.setdefault(str(meta["unit"]), []).append(index)
        group_chunks = np.array_split(np.asarray(sorted(groups, key=int), dtype=object), 10)
        result = []
        for chunk in group_chunks:
            names = [str(value) for value in chunk]
            if len(names) < 2:
                raise ValueError("grouped regression round needs at least two groups")
            gate_name = names[-1]
            update = np.asarray([index for name in names[:-1] for index in groups[name]], dtype=np.int64)
            gate = np.asarray(groups[gate_name], dtype=np.int64)
            result.append((update, gate))
        return result

    all_indices = np.arange(len(raw), dtype=np.int64)
    for index, chunk in enumerate(np.array_split(all_indices, 10)):
        split = max(1, int(len(chunk) * 0.8))
        rounds[index] = [int(value) for value in chunk]
        if split >= len(chunk):
            split = len(chunk) - 1
        if split < 1:
            raise ValueError("not enough rows for ten-round split")
    return [
        (np.asarray(chunk[: max(1, int(len(chunk) * 0.8))], dtype=np.int64), np.asarray(chunk[max(1, int(len(chunk) * 0.8)) :], dtype=np.int64))
        for chunk in rounds
    ]


def _task_rounds(train_path: Path, parent: FormalModel) -> tuple[list[tuple[DataBatch, DataBatch]], DataBatch]:
    batch = load_rows(train_path, parent, require_answers=True)
    raw = _raw_rows(train_path)
    splits = _split_indices(raw, str(parent.meta["task"]))
    used: list[int] = []
    result = []
    for update_indices, gate_indices in splits:
        if not len(update_indices) or not len(gate_indices):
            raise ValueError("each development round needs update and gate rows")
        used.extend(int(value) for value in update_indices)
        used.extend(int(value) for value in gate_indices)
        result.append((batch.select(update_indices.tolist()), batch.select(gate_indices.tolist())))
    if sorted(used) != list(range(len(batch.ids))) or len(used) != len(set(used)):
        raise ValueError("development split must cover each training row exactly once")
    return result, batch


def _metric_gain(direction: str, candidate: float, reference: float) -> float:
    return candidate - reference if direction == "higher" else reference - candidate


def _recovery_lags(gains: list[float]) -> list[int]:
    result: list[int] = []
    started: int | None = None
    for index, gain in enumerate(gains):
        if gain < 0.0 and started is None:
            started = index
        elif gain >= 0.0 and started is not None:
            result.append(index - started)
            started = None
    if started is not None:
        result.append(len(gains) - started)
    return result


def _run_arm(
    task_key: str,
    parent_path: Path,
    rounds: list[tuple[DataBatch, DataBatch]],
    strategy_name: str,
    strategy: Mapping[str, Any],
    output: Path,
    manifest_sha256: str,
) -> dict[str, Any]:
    arm_root = output / task_key / strategy_name
    result_path = arm_root / "result.json"
    final_path = arm_root / "checkpoint.npz"
    if result_path.is_file() and final_path.is_file():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("manifest_sha256") != manifest_sha256:
            raise ValueError("resumed arm manifest mismatch")
        return result
    arm_root.mkdir(parents=True, exist_ok=True)
    initial = FormalModel.load(parent_path)
    current = initial.clone()
    contract = resolve_metric_contract(None, str(initial.meta["task"]))
    registry = RecipeRegistry()
    profile = SimpleNamespace(task=str(initial.meta["task"]))
    history: list[DataBatch] = []
    records: list[dict[str, Any]] = []
    cpu_total = 0.0
    wall_total = 0.0
    peak_rss = psutil.Process().memory_info().rss
    initial_digest = hashlib.sha256(parent_path.read_bytes()).hexdigest()
    selected_digest = initial_digest
    kind = str(strategy["kind"])
    target_batch_means: list[float] = []

    for round_index, (update, gate) in enumerate(rounds, 1):
        parent_digest = selected_digest
        static_metrics = evaluate(initial, gate.x, gate.y, contract)
        arrival_metrics = evaluate(current, gate.x, gate.y, contract)
        parent_metrics = dict(arrival_metrics)
        candidate_metrics: dict[str, float] | None = None
        recipe_id: str | None = None
        selected_role = "parent"
        candidate_digest: str | None = None
        started_cpu = time.process_time()
        started_wall = time.perf_counter()
        if kind != "static":
            recipe_id = str(strategy["recipes"][str(initial.meta["task"])])
            recipe_parameters: dict[str, Any] = {}
            if (
                strategy.get("policy") == "target_stage_scale"
                and initial.meta["task"] == "regression"
            ):
                target_batch_means.append(float(np.mean(update.y)))
                normalized_span = (
                    (max(target_batch_means) - min(target_batch_means))
                    / max(1.0, abs(float(initial.meta["target_scale"])))
                    if len(target_batch_means) >= 2
                    else 0.0
                )
                if normalized_span >= 1.0:
                    recipe_id = "regression_mse"
                    recipe_parameters = {"epochs": 3, "learning_rate_multiplier": 3.0}
            recipe = registry.resolve(recipe_id, profile, recipe_parameters)
            if recipe.history_policy == "current":
                training = update
            elif recipe.history_policy == "current_plus_history":
                training = DataBatch.concat([*history, update]) if history else update
            else:
                training = DataBatch.concat(history)
            candidate_result = execute_recipe(current, recipe, training)
            candidate_metrics = evaluate(candidate_result.model, gate.x, gate.y, contract)
            buffer = arm_root / f"candidate-{round_index:02d}.npz"
            candidate_result.model.save(buffer)
            candidate_digest = hashlib.sha256(buffer.read_bytes()).hexdigest()
            if kind == "fixed":
                current = candidate_result.model
                selected_role = "candidate"
            else:
                selection = select_artifact(
                    contract,
                    [
                        ArtifactEvaluation("parent", "parent", parent_metrics, gate.sha256, {}),
                        ArtifactEvaluation("candidate", "candidate", candidate_metrics, gate.sha256, {}),
                    ],
                    "candidate",
                )
                if selection.applied_role == "candidate":
                    current = candidate_result.model
                    selected_role = "candidate"
            if selected_role == "candidate":
                selected_digest = candidate_digest
            buffer.unlink()
        elapsed_cpu = time.process_time() - started_cpu
        elapsed_wall = time.perf_counter() - started_wall
        cpu_total += elapsed_cpu
        wall_total += elapsed_wall
        peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
        post_metrics = evaluate(current, gate.x, gate.y, contract)
        primary = contract.name
        signed_gain = _metric_gain(contract.direction, float(arrival_metrics[primary]), float(static_metrics[primary]))
        post_gain = _metric_gain(contract.direction, float(post_metrics[primary]), float(static_metrics[primary]))
        records.append(
            {
                "round_index": round_index,
                "parent_sha256": parent_digest,
                "candidate_sha256": candidate_digest,
                "selected_sha256": selected_digest,
                "recipe_id": recipe_id,
                "recipe_parameters": recipe_parameters if kind != "static" else {},
                "selected_role": selected_role,
                "static_metrics": static_metrics,
                "arrival_metrics": arrival_metrics,
                "candidate_metrics": candidate_metrics,
                "post_selection_metrics": post_metrics,
                "arrival_signed_gain_vs_static": signed_gain,
                "post_signed_gain_vs_static": post_gain,
                "validation_sha256": gate.sha256,
                "update_samples": len(update.ids),
                "gate_samples": len(gate.ids),
                "cpu_seconds": elapsed_cpu,
                "wall_seconds": elapsed_wall,
            }
        )
        history.append(DataBatch.concat([update, gate]))

    current.save(final_path)
    gains = [float(item["arrival_signed_gain_vs_static"]) for item in records]
    static_values = [float(item["static_metrics"][contract.name]) for item in records]
    relative = [gain / max(1.0, abs(reference)) for gain, reference in zip(gains, static_values, strict=True)]
    result = {
        "format": "brace-msi.competition-core-arm.v1",
        "manifest_sha256": manifest_sha256,
        "task_key": task_key,
        "strategy": strategy_name,
        "kind": kind,
        "task": initial.meta["task"],
        "primary_metric": contract.name,
        "direction": contract.direction,
        "initial_checkpoint_sha256": initial_digest,
        "final_checkpoint_sha256": _sha(final_path),
        "final_checkpoint_bytes": final_path.stat().st_size,
        "parent_lineage_valid": validate_parent_lineage(records),
        "rounds": records,
        "mean_arrival_signed_gain_vs_static": float(np.mean(gains)),
        "mean_relative_gain_vs_static": float(np.mean(relative)),
        "worst_relative_gain_vs_static": float(min(relative)),
        "recovery_lags": _recovery_lags(gains),
        "cpu_seconds": cpu_total,
        "wall_seconds": wall_total,
        "peak_rss_bytes": int(peak_rss),
        "token_count": 0,
    }
    _write_json(result_path, result)
    return result


def _prepare_surrogate(spec: Mapping[str, Any], root: Path) -> tuple[Path, Path, list[tuple[DataBatch, DataBatch]]]:
    task = str(spec["task"])
    task_root = root / str(spec["key"])
    task_root.mkdir(parents=True, exist_ok=True)
    parent_path = task_root / "checkpoint.npz"
    _write_parent(parent_path, task, int(spec["feature_count"]), int(spec["seed"]))
    parent = FormalModel.load(parent_path)
    rounds = []
    for index in range(1, 11):
        update_path = task_root / f"round-{index:02d}-update.jsonl"
        gate_path = task_root / f"round-{index:02d}-gate.jsonl"
        _write_jsonl(update_path, _rows(task, int(spec["samples_per_round"]), int(spec["feature_count"]), int(spec["seed"]) + 100 * index, f"u{index}", 0.1 * index))
        _write_jsonl(gate_path, _rows(task, max(8, int(spec["samples_per_round"]) // 4), int(spec["feature_count"]), int(spec["seed"]) + 100 * index + 1, f"g{index}", 0.1 * index + 0.02))
        rounds.append((load_rows(update_path, parent, require_answers=True), load_rows(gate_path, parent, require_answers=True)))
    confirmation_path = task_root / "confirmation.jsonl"
    _write_jsonl(confirmation_path, _rows(task, int(spec["confirmation_samples"]), int(spec["feature_count"]), int(spec["seed"]) + 9900, "confirmation", 1.1))
    return parent_path, confirmation_path, rounds


def run_smoke(manifest: Mapping[str, Any], output: Path | str) -> dict[str, Any]:
    fingerprint = prepare_output(manifest, output)
    root = Path(output)
    tasks: dict[str, int] = {}
    for spec in manifest["registered_surrogates"]:
        parent_path, _, rounds = _prepare_surrogate(spec, root / "smoke-sources")
        result = _run_arm(str(spec["key"]), parent_path, rounds[:1], "fixed_update", manifest["strategies"]["fixed_update"], root / "smoke", fingerprint)
        tasks[str(spec["task"])] = tasks.get(str(spec["task"]), 0) + len(result["rounds"])
    summary = {"valid": tasks == {"classification": 1, "regression": 1}, "tasks": tasks}
    _write_json(root / "smoke-summary.json", summary)
    return summary


def choose_winner(results: list[dict[str, Any]], strategies: Mapping[str, Any]) -> str:
    candidates = [name for name, item in strategies.items() if item["kind"] == "competition_core"]
    ranked = []
    for name in candidates:
        rows = [item for item in results if item["strategy"] == name]
        ranked.append(
            (
                min(float(item["worst_relative_gain_vs_static"]) for item in rows),
                float(np.mean([item["mean_relative_gain_vs_static"] for item in rows])),
                -sum(float(item["cpu_seconds"]) for item in rows),
                name,
            )
        )
    return max(ranked)[-1]


def run_full(manifest: Mapping[str, Any], output: Path | str) -> dict[str, Any]:
    fingerprint = prepare_output(manifest, output)
    output = Path(output)
    sources_before = validate_sources(manifest)
    tasks: dict[str, dict[str, Any]] = {}
    package_root = Path(str(manifest["official_package_root"]))
    for key, spec in manifest["packages"].items():
        package = package_root / spec["directory"]
        parent_path = package / "checkpoint.npz"
        parent = FormalModel.load(parent_path)
        rounds, _ = _task_rounds(package / "public" / "train.jsonl", parent)
        tasks[str(key)] = {
            "parent_path": parent_path,
            "confirmation_path": package / "public" / "validation.jsonl",
            "rounds": rounds,
            "task": str(parent.meta["task"]),
            "source": "official_public_package",
        }
    for surrogate in manifest["registered_surrogates"]:
        parent_path, confirmation_path, rounds = _prepare_surrogate(surrogate, output / "surrogate-sources")
        tasks[str(surrogate["key"])] = {
            "parent_path": parent_path,
            "confirmation_path": confirmation_path,
            "rounds": rounds,
            "task": str(surrogate["task"]),
            "source": "registered_same_format_surrogate",
        }

    results: list[dict[str, Any]] = []
    for task_key, task in tasks.items():
        for strategy_name, strategy in manifest["strategies"].items():
            results.append(
                _run_arm(task_key, task["parent_path"], task["rounds"], strategy_name, strategy, output / "arms", fingerprint)
            )
    winner = choose_winner(results, manifest["strategies"])
    confirmation_results = []
    by_key_strategy = {(item["task_key"], item["strategy"]): item for item in results}
    for task_key, task in tasks.items():
        initial = FormalModel.load(task["parent_path"])
        confirmation = load_rows(task["confirmation_path"], initial, require_answers=True)
        contract = resolve_metric_contract(None, str(initial.meta["task"]))
        arms = {}
        for strategy_name in ("static_parent", "fixed_update", winner):
            checkpoint = output / "arms" / task_key / strategy_name / "checkpoint.npz"
            model = FormalModel.load(checkpoint)
            arms[strategy_name] = evaluate(model, confirmation.x, confirmation.y, contract)
        confirmation_results.append(
            {
                "task_key": task_key,
                "task": task["task"],
                "source": task["source"],
                "confirmation_sha256": confirmation.sha256,
                "confirmation_file_reads": 1,
                "frozen_winner": winner,
                "metrics": arms,
            }
        )
    sources_after = validate_sources(manifest)
    summary = {
        "format": SUMMARY_FORMAT,
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": fingerprint,
        "valid": (
            sources_before == sources_after
            and all(item["parent_lineage_valid"] for item in results)
            and all(item["confirmation_file_reads"] == 1 for item in confirmation_results)
        ),
        "official_hidden_score": None,
        "confirmation_feedback": False,
        "frozen_competition_core_strategy": winner,
        "development_results": results,
        "confirmation_results": confirmation_results,
        "source_audit_before": sources_before,
        "source_audit_after": sources_after,
    }
    _write_json(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest(args.config)
    result = run_smoke(manifest, args.output) if args.smoke else run_full(manifest, args.output)
    print(json.dumps({"valid": result["valid"], "output": str(args.output)}, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
