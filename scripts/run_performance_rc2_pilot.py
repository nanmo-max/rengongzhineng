"""Run the local-only PERFORMANCE-RC2-PILOT-001 experiment.

The runner creates a train-internal development stream and an independent
group-safe confirmation split.  It never opens public/validation.jsonl and
does not call PyTRiO, SwanLab, Docker, or the official platform.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np
import psutil


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brace_formal.data import DataBatch, load_rows  # noqa: E402
from brace_formal.metrics import evaluate, resolve_metric_contract  # noqa: E402
from brace_formal.model import FormalModel  # noqa: E402
from brace_formal.recipes import RecipeRegistry, execute_recipe  # noqa: E402
from brace_msi.performance_rc2 import (  # noqa: E402
    CandidateEvidence,
    fit_research_candidate,
    recipes_for_task,
    select_robust_candidate,
)
from scripts.run_competition_core_experiments import _prepare_surrogate  # noqa: E402


FORMAT = "brace-msi.performance-rc2-pilot.v1"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _chunks(values: Sequence[int], count: int = 10) -> list[list[int]]:
    return [[int(value) for value in part] for part in np.array_split(np.asarray(values, dtype=np.int64), count)]


def split_stream_holdout_indices(
    raw: list[dict[str, Any]], task: str
) -> tuple[list[tuple[tuple[int, ...], tuple[int, ...]]], tuple[int, ...], dict[str, Any]]:
    """Freeze one confirmation split and ten development rounds.

    Task identity is never inspected. Group metadata and task contract alone
    select the split policy.
    """

    if task not in {"classification", "regression"} or len(raw) < 30:
        raise ValueError("task or sample count is unsupported")
    metas = [row.get("meta") if isinstance(row.get("meta"), dict) else {} for row in raw]
    rounds: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    holdout: list[int] = []
    policy = "row_hash"
    group_safe = False

    if task == "classification":
        by_label: dict[str, list[int]] = {}
        for index, row in enumerate(raw):
            by_label.setdefault(str(row["answer"]), []).append(index)
        per_round: list[list[int]] = [[] for _ in range(10)]
        for label in sorted(by_label):
            ordered = sorted(by_label[label], key=lambda index: str(raw[index].get("id", index)))
            label_holdout = ordered[::5]
            holdout.extend(label_holdout)
            development = [index for index in ordered if index not in set(label_holdout)]
            for round_index, part in enumerate(_chunks(development)):
                per_round[round_index].extend(part)
        for values in per_round:
            ordered = sorted(values)
            gate = tuple(ordered[::5])
            update = tuple(index for index in ordered if index not in set(gate))
            if not update or not gate:
                raise ValueError("classification round is too small")
            rounds.append((update, gate))
        policy = "stratified_id_order"
    elif all("bearing" in meta and "snapshot" in meta for meta in metas):
        groups: dict[str, list[int]] = {}
        for index, meta in enumerate(metas):
            groups.setdefault(str(meta["bearing"]), []).append(index)
        ordered_groups = sorted(groups)
        holdout_groups = set(ordered_groups[::5])
        stream_groups = [group for group in ordered_groups if group not in holdout_groups]
        for group in holdout_groups:
            holdout.extend(groups[group])
        trajectories = {
            group: _chunks(sorted(groups[group], key=lambda index: float(metas[index]["snapshot"])))
            for group in stream_groups
        }
        for round_index in range(10):
            gate_group = stream_groups[round_index % len(stream_groups)]
            gate = tuple(trajectories[gate_group][round_index])
            update = tuple(
                index
                for group in stream_groups
                if group != gate_group
                for index in trajectories[group][round_index]
            )
            if not update or not gate:
                raise ValueError("bearing round is empty")
            rounds.append((update, gate))
        policy = "heldout_bearings_ordered_trajectories"
        group_safe = True
    elif all("unit" in meta for meta in metas):
        groups: dict[tuple[str, str], list[int]] = {}
        for index, meta in enumerate(metas):
            key = (str(meta.get("source_subset", "default")), str(meta["unit"]))
            groups.setdefault(key, []).append(index)
        ordered_groups = sorted(groups)
        holdout_groups = set(ordered_groups[::5])
        stream_groups = [group for group in ordered_groups if group not in holdout_groups]
        for group in holdout_groups:
            holdout.extend(groups[group])
        for round_groups in np.array_split(np.asarray(stream_groups, dtype=object), 10):
            names = [tuple(value) for value in round_groups.tolist()]
            split = max(1, int(len(names) * 0.8))
            if split >= len(names):
                split = len(names) - 1
            update_names, gate_names = names[:split], names[split:]
            update = tuple(index for name in update_names for index in groups[name])
            gate = tuple(index for name in gate_names for index in groups[name])
            if not update or not gate:
                raise ValueError("grouped regression round is empty")
            rounds.append((update, gate))
        policy = "heldout_subset_unit_groups"
        group_safe = True
    else:
        ordered = sorted(range(len(raw)), key=lambda index: str(raw[index].get("id", index)))
        holdout = ordered[::5]
        development = [index for index in ordered if index not in set(holdout)]
        for part in _chunks(development):
            split = max(1, int(len(part) * 0.8))
            if split >= len(part):
                split = len(part) - 1
            update, gate = tuple(part[:split]), tuple(part[split:])
            if not update or not gate:
                raise ValueError("generic regression round is empty")
            rounds.append((update, gate))

    stream = [index for update, gate in rounds for index in (*update, *gate)]
    if len(rounds) != 10 or len(stream) != len(set(stream)) or set(stream) & set(holdout):
        raise ValueError("stream and confirmation split overlap")
    if set(stream) | set(holdout) != set(range(len(raw))):
        raise ValueError("split does not cover every row")
    return rounds, tuple(sorted(holdout)), {
        "policy": policy,
        "group_safe": group_safe,
        "stream_samples": len(stream),
        "confirmation_samples": len(holdout),
        "rounds": len(rounds),
        "overlap": 0,
    }


def _directed_gain(direction: str, candidate: float, parent: float) -> float:
    return candidate - parent if direction == "higher" else parent - candidate


def _fold_gains(parent: FormalModel, candidate: FormalModel, gate: DataBatch, contract: Any) -> tuple[float, ...]:
    gains: list[float] = []
    for fold in range(3):
        indices = np.flatnonzero(np.arange(len(gate.ids)) % 3 == fold)
        if not len(indices):
            continue
        subset = gate.select(indices.tolist())
        parent_metrics = evaluate(parent, subset.x, subset.y, contract)
        candidate_metrics = evaluate(candidate, subset.x, subset.y, contract)
        gains.append(_directed_gain(contract.direction, candidate_metrics[contract.name], parent_metrics[contract.name]))
    return tuple(gains)


def _core_candidate(parent: FormalModel, update: DataBatch, history: list[DataBatch]) -> Any:
    registry = RecipeRegistry()
    profile = type("Profile", (), {"task": str(parent.meta["task"])})()
    recipe_id = "class_weighted_ce" if parent.meta["task"] == "classification" else "regression_huber"
    recipe = registry.resolve(recipe_id, profile, {})
    training = DataBatch.concat([*history, update]) if history else update
    return execute_recipe(parent, recipe, training)


def _run_strategy(
    strategy: str,
    parent: FormalModel,
    rounds: list[tuple[DataBatch, DataBatch]],
    output: Path,
) -> tuple[FormalModel, dict[str, Any]]:
    current = parent.clone()
    static = parent.clone()
    history: list[DataBatch] = []
    contract = resolve_metric_contract(None, str(parent.meta["task"]))
    records: list[dict[str, Any]] = []
    total_cpu = 0.0
    total_wall = 0.0
    peak_rss = psutil.Process().memory_info().rss
    for round_index, (update, gate) in enumerate(rounds, 1):
        arrival = evaluate(current, gate.x, gate.y, contract)
        static_metrics = evaluate(static, gate.x, gate.y, contract)
        evidence: list[CandidateEvidence] = []
        receipts: list[dict[str, Any]] = []
        started_cpu = time.process_time()
        started_wall = time.perf_counter()
        if strategy == "core_robust":
            result = _core_candidate(current, update, history)
            metrics = evaluate(result.model, gate.x, gate.y, contract)
            evidence.append(
                CandidateEvidence(
                    result.receipt["recipe_id"], result.model, _fold_gains(current, result.model, gate, contract),
                    float(result.receipt.get("cpu_seconds", 0.0)), 0.0, 0.0, metrics,
                )
            )
            receipts.append(result.receipt)
        elif strategy == "rc2":
            for recipe in recipes_for_task(str(parent.meta["task"])):
                candidate_start = time.perf_counter()
                result = fit_research_candidate(current, recipe, update, history)
                metrics = evaluate(result.model, gate.x, gate.y, contract)
                evidence.append(
                    CandidateEvidence(
                        recipe.recipe_id,
                        result.model,
                        _fold_gains(current, result.model, gate, contract),
                        float(result.receipt["cpu_seconds"]),
                        time.perf_counter() - candidate_start,
                        float(psutil.Process().memory_info().rss),
                        metrics,
                    )
                )
                receipts.append(result.receipt)
        else:
            raise ValueError("unknown strategy")
        selected = select_robust_candidate(contract, evidence)
        if selected is not None:
            current = selected.model  # type: ignore[assignment]
        elapsed_cpu = time.process_time() - started_cpu
        elapsed_wall = time.perf_counter() - started_wall
        total_cpu += elapsed_cpu
        total_wall += elapsed_wall
        peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
        post = evaluate(current, gate.x, gate.y, contract)
        records.append(
            {
                "round_index": round_index,
                "arrival_metrics": arrival,
                "static_metrics": static_metrics,
                "candidate_metrics": {item.candidate_id: item.metrics for item in evidence},
                "candidate_fold_gains": {item.candidate_id: list(item.fold_gains) for item in evidence},
                "selected_candidate": None if selected is None else selected.candidate_id,
                "post_selection_metrics": post,
                "arrival_relative_gain_vs_static": _directed_gain(
                    contract.direction, arrival[contract.name], static_metrics[contract.name]
                ) / max(abs(static_metrics[contract.name]), 1e-12),
                "post_relative_gain_vs_static": _directed_gain(
                    contract.direction, post[contract.name], static_metrics[contract.name]
                ) / max(abs(static_metrics[contract.name]), 1e-12),
                "update_samples": len(update.ids),
                "gate_samples": len(gate.ids),
                "receipts": receipts,
                "cpu_seconds": elapsed_cpu,
                "wall_seconds": elapsed_wall,
            }
        )
        # Only legal Update rows become history. Gate rows are never replayed.
        history.append(update)
    output.mkdir(parents=True, exist_ok=True)
    current.save(output / "checkpoint.npz")
    result = {
        "strategy": strategy,
        "task": parent.meta["task"],
        "primary_metric": contract.name,
        "direction": contract.direction,
        "rounds": records,
        "worst_development_relative_gain": min(row["post_relative_gain_vs_static"] for row in records),
        "mean_development_relative_gain": float(np.mean([row["post_relative_gain_vs_static"] for row in records])),
        "cpu_seconds": total_cpu,
        "wall_seconds": total_wall,
        "peak_rss_bytes": int(peak_rss),
    }
    _write_json(output / "result.json", result)
    return current, result


def run_smoke(config: Mapping[str, Any], output: Path | str) -> dict[str, Any]:
    if config.get("format") != FORMAT:
        raise ValueError("RC2 manifest format is invalid")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    candidate_count = 0
    tasks: list[str] = []
    for spec in config["registered_surrogates"]:
        parent_path, _, rounds = _prepare_surrogate(spec, root / "sources")
        parent = FormalModel.load(parent_path)
        update, gate = rounds[0]
        history: list[DataBatch] = []
        contract = resolve_metric_contract(None, str(parent.meta["task"]))
        for recipe in recipes_for_task(str(parent.meta["task"])):
            result = fit_research_candidate(parent, recipe, update, history)
            metrics = evaluate(result.model, gate.x, gate.y, contract)
            if not all(np.isfinite(value) for value in metrics.values()):
                raise ValueError("smoke candidate metric is nonfinite")
            candidate_count += 1
        tasks.append(str(spec["key"]))
    summary = {
        "format": "brace-msi.performance-rc2-smoke.v1",
        "valid": candidate_count >= 8,
        "confirmation_reads": 0,
        "tasks": sorted(tasks),
        "candidate_count": candidate_count,
    }
    _write_json(root / "smoke-summary.json", summary)
    return summary


def run_full(config: Mapping[str, Any], output: Path | str) -> dict[str, Any]:
    if config.get("format") != FORMAT or config.get("confirmation_read_policy") != "once_after_strategy_freeze":
        raise ValueError("RC2 manifest is invalid")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    package_root = Path(str(config["official_package_root"]))
    task_results: list[dict[str, Any]] = []
    confirmation_reads = 0
    for key, spec in config["packages"].items():
        package = package_root / spec["directory"]
        checkpoint_path = package / "checkpoint.npz"
        train_path = package / "public" / "train.jsonl"
        if _sha(checkpoint_path) != spec["checkpoint_sha256"] or _sha(train_path) != spec["train_sha256"]:
            raise ValueError("registered source hash mismatch")
        parent = FormalModel.load(checkpoint_path)
        batch = load_rows(train_path, parent, require_answers=True)
        raw = _raw_rows(train_path)
        indices, holdout_indices, split_audit = split_stream_holdout_indices(raw, str(parent.meta["task"]))
        rounds = [(batch.select(list(update)), batch.select(list(gate))) for update, gate in indices]
        core_model, core_result = _run_strategy("core_robust", parent, rounds, root / key / "core_robust")
        rc2_model, rc2_result = _run_strategy("rc2", parent, rounds, root / key / "rc2")
        # The confirmation targets are evaluated exactly once per task, after
        # both strategies and all candidate policies have been frozen.
        confirmation = batch.select(list(holdout_indices))
        confirmation_reads += 1
        contract = resolve_metric_contract(None, str(parent.meta["task"]))
        confirmation_metrics = {
            "static_parent": evaluate(parent, confirmation.x, confirmation.y, contract),
            "core_robust": evaluate(core_model, confirmation.x, confirmation.y, contract),
            "rc2": evaluate(rc2_model, confirmation.x, confirmation.y, contract),
        }
        primary = contract.name
        core_value = confirmation_metrics["core_robust"][primary]
        rc2_value = confirmation_metrics["rc2"][primary]
        directed = _directed_gain(contract.direction, rc2_value, core_value)
        relative = directed / max(abs(core_value), 1e-12)
        task_results.append(
            {
                "task_key": key,
                "task": parent.meta["task"],
                "primary_metric": primary,
                "direction": contract.direction,
                "split_audit": split_audit,
                "confirmation_reads": 1,
                "confirmation_samples": len(confirmation.ids),
                "confirmation_metrics": confirmation_metrics,
                "rc2_directed_relative_gain_vs_core": relative,
                "core_development": core_result,
                "rc2_development": rc2_result,
            }
        )
    relative_gains = [row["rc2_directed_relative_gain_vs_core"] for row in task_results]
    worst_ok = all(
        row["rc2_development"]["worst_development_relative_gain"]
        >= row["core_development"]["worst_development_relative_gain"] - 1e-12
        for row in task_results
    )
    promotion_checks = {
        "positive_mean_confirmation_gain": float(np.mean(relative_gains)) > 0.0,
        "at_least_two_tasks_strictly_improve": sum(value > 1e-12 for value in relative_gains) >= 2,
        "no_task_primary_regression": all(value >= -1e-12 for value in relative_gains),
        "development_worst_stage_not_worse": worst_ok,
    }
    summary = {
        "format": "brace-msi.performance-rc2-pilot-result.v1",
        "experiment_id": config["experiment_id"],
        "valid": confirmation_reads == len(task_results) and all(row["split_audit"]["overlap"] == 0 for row in task_results),
        "promotion_pass": all(promotion_checks.values()),
        "promotion_checks": promotion_checks,
        "confirmation_reads": confirmation_reads,
        "public_validation_reads": 0,
        "official_hidden_score": None,
        "task_results": task_results,
    }
    _write_json(root / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = run_smoke(config, args.output) if args.smoke else run_full(config, args.output)
    print(json.dumps({"valid": result["valid"], "promotion_pass": result.get("promotion_pass"), "output": str(args.output)}, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
