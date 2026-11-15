"""Run a preregistered, platform-shaped generalization simulation on unseen datasets."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import html
import io
import json
from pathlib import Path
import shutil
import time
from typing import Any, Iterable
import zipfile

import numpy as np
import scipy.io as sio

from brace_msi.platform_runtime import (
    PlatformRuntimeConfig,
    _NativeModel,
    evaluate_checkpoint,
)
from brace_msi.platform_advisor import build_platform_advisor
from brace_msi.platform_simulation import run_ten_round_simulation


SEED = 20261115
SENSOR_STATS = (
    "count",
    "mean",
    "std",
    "min",
    "max",
    "median",
    "q25",
    "q75",
    "rms",
    "delta",
    "slope",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _series_stats(values: Any) -> list[float]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if not len(array) or not np.all(np.isfinite(array)):
        raise ValueError("sensor series must be nonempty and finite")
    centered = np.arange(len(array), dtype=np.float64) - (len(array) - 1) / 2.0
    denominator = float(np.dot(centered, centered))
    slope = float(np.dot(centered, array - array.mean()) / denominator) if denominator else 0.0
    q25, median, q75 = np.quantile(array, (0.25, 0.5, 0.75))
    return [
        float(len(array)),
        float(array.mean()),
        float(array.std()),
        float(array.min()),
        float(array.max()),
        float(median),
        float(q25),
        float(q75),
        float(np.sqrt(np.mean(array * array))),
        float(array[-1] - array[0]),
        slope,
    ]


def _finite_scalar(value: Any) -> float | None:
    array = np.asarray(value)
    if array.size != 1:
        return None
    try:
        result = float(array.reshape(-1)[0])
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _matrix_stats(values: np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or not matrix.shape[1] or not np.all(np.isfinite(matrix)):
        raise ValueError("sensor matrix must be finite and two-dimensional")
    length = matrix.shape[1]
    centered = np.arange(length, dtype=np.float64) - (length - 1) / 2.0
    denominator = float(np.dot(centered, centered))
    slopes = ((matrix - matrix.mean(axis=1, keepdims=True)) @ centered) / denominator
    quantiles = np.quantile(matrix, (0.25, 0.5, 0.75), axis=1).T
    return np.column_stack(
        (
            np.full(len(matrix), length, dtype=np.float64),
            matrix.mean(axis=1),
            matrix.std(axis=1),
            matrix.min(axis=1),
            matrix.max(axis=1),
            quantiles[:, 1],
            quantiles[:, 0],
            quantiles[:, 2],
            np.sqrt(np.mean(matrix * matrix, axis=1)),
            matrix[:, -1] - matrix[:, 0],
            slopes,
        )
    )


def _feature_names(sensor_names: Iterable[str], extras: Iterable[str] = ()) -> list[str]:
    return [f"{sensor}.{stat}" for sensor in sensor_names for stat in SENSOR_STATS] + list(extras)


def _battery_rows(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    archive_root = root / "5.+Battery+Data+Set" / "5. Battery Data Set"
    unique: dict[str, tuple[str, bytes]] = {}
    duplicates: dict[str, set[str]] = defaultdict(set)
    for archive in sorted(archive_root.glob("*.zip")):
        with zipfile.ZipFile(archive) as handle:
            for name in sorted(handle.namelist()):
                if not name.lower().endswith(".mat"):
                    continue
                battery_id = Path(name).stem
                payload = handle.read(name)
                digest = hashlib.sha256(payload).hexdigest()
                duplicates[battery_id].add(digest)
                unique.setdefault(battery_id, (digest, payload))
    if any(len(values) != 1 for values in duplicates.values()):
        raise ValueError("duplicate battery IDs differ in content")
    fields = (
        "Voltage_measured",
        "Current_measured",
        "Temperature_measured",
        "Current_load",
        "Voltage_load",
        "Time",
    )
    rows: list[dict[str, Any]] = []
    for battery_id, (_, payload) in sorted(unique.items()):
        loaded = sio.loadmat(io.BytesIO(payload), squeeze_me=True, struct_as_record=False)
        root_object = loaded[battery_id]
        discharge_index = 0
        for cycle_index, cycle in enumerate(np.atleast_1d(root_object.cycle)):
            if str(cycle.type).lower() != "discharge":
                continue
            capacity = _finite_scalar(cycle.data.Capacity)
            if capacity is None:
                continue
            features: list[float] = []
            for field in fields:
                features.extend(_series_stats(getattr(cycle.data, field)))
            features.extend((float(cycle.ambient_temperature), float(discharge_index)))
            rows.append(
                {
                    "id": f"battery-{battery_id}-{discharge_index:04d}",
                    "group": battery_id,
                    "order": discharge_index,
                    "features": features,
                    "answer": capacity,
                }
            )
            discharge_index += 1
    names = _feature_names(fields, ("ambient_temperature", "cycle_index"))
    return rows, names


def _hydraulic_rows(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    task_root = root / "condition+monitoring+of+hydraulic+systems"
    sensor_names = (
        "PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2",
        "TS1", "TS2", "TS3", "TS4", "VS1", "CE", "CP", "SE",
    )
    matrices: list[np.ndarray] = []
    row_count: int | None = None
    for sensor in sensor_names:
        values = np.loadtxt(task_root / f"{sensor}.txt", dtype=np.float64)
        if row_count is None:
            row_count = len(values)
        if len(values) != row_count:
            raise ValueError("hydraulic sensor row counts differ")
        matrices.append(_matrix_stats(values))
    features = np.concatenate(matrices, axis=1)
    profile = np.loadtxt(task_root / "profile.txt", dtype=np.float64)
    if len(profile) != len(features):
        raise ValueError("hydraulic profile length differs from sensors")
    targets = profile[:, 3].astype(np.int64)
    run_ids = np.empty(len(targets), dtype=np.int64)
    run = 0
    run_ids[0] = run
    for index in range(1, len(targets)):
        if targets[index] != targets[index - 1]:
            run += 1
        run_ids[index] = run
    rows = [
        {
            "id": f"hydraulic-{index:04d}",
            "group": f"run-{int(run_ids[index]):02d}",
            "order": index,
            "features": features[index].tolist(),
            "answer": str(int(targets[index])),
        }
        for index in range(len(features))
    ]
    return rows, _feature_names(sensor_names)


def _mill_rows(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records = sio.loadmat(
        root / "mill" / "mill.mat", squeeze_me=True, struct_as_record=False
    )["mill"]
    sensors = ("smcAC", "smcDC", "vib_table", "vib_spindle", "AE_table", "AE_spindle")
    rows: list[dict[str, Any]] = []
    for record in records:
        target = float(record.VB)
        if not np.isfinite(target):
            continue
        features: list[float] = []
        for sensor in sensors:
            features.extend(_series_stats(getattr(record, sensor)))
        features.extend((float(record.time), float(record.DOC), float(record.feed), float(record.material)))
        rows.append(
            {
                "id": f"mill-{int(record.case):02d}-{int(record.run):03d}",
                "group": f"case-{int(record.case):02d}",
                "order": int(record.run),
                "features": features,
                "answer": target,
            }
        )
    names = _feature_names(sensors, ("elapsed_time", "depth_of_cut", "feed", "material"))
    return rows, names


def _partition_rows(task: str, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if task == "battery":
        groups = sorted({row["group"] for row in rows})
        shuffled = np.asarray(groups, dtype=object)
        np.random.default_rng(SEED).shuffle(shuffled)
        bootstrap_groups = set(shuffled[:14].tolist())
        adaptation_groups = set(shuffled[14:26].tolist())
        confirmation_groups = set(shuffled[26:].tolist())
    elif task == "hydraulic":
        by_target: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            if row["group"] not in by_target[row["answer"]]:
                by_target[row["answer"]].append(row["group"])
        if any(len(groups) != 3 for groups in by_target.values()):
            raise ValueError("expected three contiguous hydraulic runs per target")
        bootstrap_groups = {groups[0] for groups in by_target.values()}
        adaptation_groups = {groups[1] for groups in by_target.values()}
        confirmation_groups = {groups[2] for groups in by_target.values()}
    elif task == "mill":
        bootstrap_groups = {f"case-{index:02d}" for index in range(1, 7)}
        adaptation_groups = {f"case-{index:02d}" for index in range(7, 13)}
        confirmation_groups = {f"case-{index:02d}" for index in range(13, 17)}
    else:
        raise ValueError(f"unknown task: {task}")
    if bootstrap_groups & adaptation_groups or bootstrap_groups & confirmation_groups or adaptation_groups & confirmation_groups:
        raise ValueError("partition groups overlap")
    partitions = {"bootstrap": [], "adaptation": [], "confirmation": []}
    for row in rows:
        group = row["group"]
        if group in bootstrap_groups:
            partitions["bootstrap"].append(row)
        elif group in adaptation_groups:
            partitions["adaptation"].append(row)
        elif group in confirmation_groups:
            partitions["confirmation"].append(row)
    for name, selected in partitions.items():
        selected.sort(key=lambda row: (row["group"], row["order"], row["id"]))
        if not selected:
            raise ValueError(f"{task} {name} partition is empty")
    if len(partitions["adaptation"]) < 50:
        raise ValueError(f"{task} adaptation partition has fewer than 50 rows")
    return partitions


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            public = {"id": row["id"], "inputs": {"features": row["features"]}, "answer": row["answer"]}
            stream.write(json.dumps(public, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")


def _build_parent(
    path: Path,
    rows: list[dict[str, Any]],
    feature_names: list[str],
    *,
    task_kind: str,
    profile: str,
) -> dict[str, Any]:
    values = np.asarray([row["features"] for row in rows], dtype=np.float64)
    if values.shape != (len(rows), len(feature_names)) or not np.all(np.isfinite(values)):
        raise ValueError("bootstrap feature matrix is invalid")
    classes = sorted({str(row["answer"]) for row in rows}) if task_kind == "classification" else []
    if task_kind == "classification" and len(classes) < 2:
        raise ValueError("bootstrap classification needs all task classes")
    targets = (
        np.asarray([classes.index(str(row["answer"])) for row in rows], dtype=np.int64)
        if task_kind == "classification"
        else np.asarray([float(row["answer"]) for row in rows], dtype=np.float64)
    )
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale[scale < 1e-8] = 1.0
    target_mean = float(targets.mean()) if task_kind == "regression" else 0.0
    target_scale = float(targets.std()) if task_kind == "regression" else 1.0
    target_scale = max(target_scale, 1e-8)
    hidden = 32
    output = len(classes) if classes else 1
    rng = np.random.default_rng(SEED)
    params = {
        "w1": rng.normal(0.0, 1.0 / np.sqrt(len(feature_names)), size=(len(feature_names), hidden)),
        "b1": np.zeros(hidden, dtype=np.float64),
        "w2": rng.normal(0.0, 1.0 / np.sqrt(hidden), size=(hidden, output)),
        "b2": np.zeros(output, dtype=np.float64),
    }
    paths = [json.dumps([["key", "features"], ["index", index]], separators=(",", ":")) for index in range(len(feature_names))]
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": profile,
        "task": task_kind,
        "paths": paths,
        "classes": classes,
        "hidden": hidden,
        "seed": SEED,
        "epochs": 0,
        "steps": 0,
        "learning_rate": 0.003,
        "batch_size": 32,
        "parameter_count": int(sum(value.size for value in params.values())),
        "target_mean": target_mean,
        "target_scale": target_scale,
        "simulated_parent": True,
        "feature_schema_sha256": _json_sha256(feature_names),
    }
    arrays = {
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        "mean": mean.astype(np.float64),
        "scale": scale.astype(np.float64),
    }
    model = _NativeModel(arrays, metadata)
    losses = model.fit(values, targets, 30)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save(path)
    return {
        "epochs": 30,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "parameter_count": metadata["parameter_count"],
        "checkpoint_bytes": path.stat().st_size,
        "checkpoint_sha256": _sha256(path),
    }


def _primary(task_kind: str, metrics: dict[str, float]) -> float:
    return float(metrics["macro_f1"] if task_kind == "classification" else metrics["rmse"])


def _improvement(task_kind: str, before: dict[str, float], after: dict[str, float]) -> float:
    if task_kind == "classification":
        return float(after["macro_f1"] - before["macro_f1"])
    return float(before["rmse"] - after["rmse"])


def _task_report(
    task_root: Path,
    task_name: str,
    task_kind: str,
    rows: list[dict[str, Any]],
    feature_names: list[str],
    advisor: Any | None,
) -> dict[str, Any]:
    partitions = _partition_rows(task_name, rows)
    data_root = task_root / "data"
    for name, selected in partitions.items():
        _write_jsonl(data_root / f"{name}.jsonl", selected)
    parent = task_root / "parent" / "checkpoint.npz"
    parent_info = _build_parent(
        parent,
        partitions["bootstrap"],
        feature_names,
        task_kind=task_kind,
        profile=f"UNSEEN-{task_kind.upper()}",
    )
    run_root = task_root / "run"
    summary = run_ten_round_simulation(
        data_root / "adaptation.jsonl",
        parent,
        run_root,
        prediction_data_path=data_root / "confirmation.jsonl",
        config=PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=10),
        export_swanlab=False,
        advisor=advisor,
    )
    confirmation_path = data_root / "confirmation.jsonl"
    per_round: list[dict[str, Any]] = []
    checkpoints = [(0, parent)] + [
        (index, run_root / f"round-{index:02d}" / "checkpoint.npz") for index in range(1, 11)
    ]
    for round_index, checkpoint in checkpoints:
        metrics = evaluate_checkpoint(checkpoint, confirmation_path)
        per_round.append(
            {
                "round": round_index,
                "metrics": metrics,
                "checkpoint_sha256": _sha256(checkpoint),
                "checkpoint_bytes": checkpoint.stat().st_size,
            }
        )
    best = (
        max(per_round, key=lambda row: _primary(task_kind, row["metrics"]))
        if task_kind == "classification"
        else min(per_round, key=lambda row: _primary(task_kind, row["metrics"]))
    )
    initial = per_round[0]["metrics"]
    final = per_round[-1]["metrics"]
    groups = {
        name: sorted({row["group"] for row in selected}) for name, selected in partitions.items()
    }
    group_sets = [set(value) for value in groups.values()]
    group_overlap = bool(
        group_sets[0] & group_sets[1]
        or group_sets[0] & group_sets[2]
        or group_sets[1] & group_sets[2]
    )
    return {
        "task": task_name,
        "task_kind": task_kind,
        "simulated_parent": True,
        "feature_count": len(feature_names),
        "feature_schema_sha256": _json_sha256(feature_names),
        "partition_counts": {name: len(value) for name, value in partitions.items()},
        "partition_groups": groups,
        "partition_manifest_sha256": _json_sha256(groups),
        "group_overlap": group_overlap,
        "parent": parent_info,
        "round_count": summary["round_count"],
        "candidate_count": summary["candidate_count"],
        "accepted_count": summary["accepted_count"],
        "noop_count": summary["noop_count"],
        "parent_chain_valid": summary["parent_chain_valid"],
        "input_tokens": summary["input_tokens"],
        "output_tokens": summary["output_tokens"],
        "initial_confirmation_metrics": initial,
        "final_confirmation_metrics": final,
        "final_improvement": _improvement(task_kind, initial, final),
        "best_confirmation_round": best["round"],
        "best_confirmation_metrics": best["metrics"],
        "best_improvement": _improvement(task_kind, initial, best["metrics"]),
        "per_round_confirmation": per_round,
        "rounds": summary["rounds"],
    }


def _raw_manifest(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        rows.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return rows


def _render_html(report: dict[str, Any]) -> str:
    task_rows = []
    for task in report["tasks"]:
        initial = task["initial_confirmation_metrics"]
        final = task["final_confirmation_metrics"]
        if task["task_kind"] == "classification":
            metric = "Macro-F1"
            before = initial["macro_f1"]
            after = final["macro_f1"]
        else:
            metric = "RMSE"
            before = initial["rmse"]
            after = final["rmse"]
        task_rows.append(
            "<tr>"
            f"<td>{html.escape(task['task'])}</td><td>{html.escape(metric)}</td>"
            f"<td>{before:.6f}</td><td>{after:.6f}</td>"
            f"<td>{task['final_improvement']:.6f}</td>"
            f"<td>{task['candidate_count']}</td><td>{task['accepted_count']}</td>"
            f"<td>{task['best_confirmation_round']}</td>"
            "</tr>"
        )
    return """<!doctype html><html lang='zh-CN'><meta charset='utf-8'>
<title>UNSEEN-SIM-001</title><style>body{font-family:system-ui;margin:2rem;max-width:1100px}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:.5rem;text-align:right}
th:first-child,td:first-child{text-align:left}.note{background:#fff3cd;padding:1rem}</style>
<h1>BRACE-MSI 未知工业任务本地复演</h1>
<p class='note'>这是模拟父模型和本地公开数据上的压力测试，不是官方隐藏成绩，不用于修改冻结RC7。</p>
<table><thead><tr><th>任务</th><th>主指标</th><th>静态父模型</th><th>第10轮</th><th>改善</th><th>候选</th><th>部署</th><th>报告最佳轮</th></tr></thead>
<tbody>""" + "".join(task_rows) + "</tbody></table></html>"


def run(
    source_root: Path,
    output_root: Path,
    *,
    experiment_id: str,
    advisor_mode: str,
    pytrio_timeout_seconds: float,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError("output root must be new")
    output_root.mkdir(parents=True)
    started = time.time()
    raw_manifest = _raw_manifest(source_root)
    (output_root / "raw-manifest.json").write_text(
        json.dumps(raw_manifest, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    task_specs = (
        ("battery", "regression", _battery_rows),
        ("hydraulic", "classification", _hydraulic_rows),
        ("mill", "regression", _mill_rows),
    )
    task_reports = []
    for task_name, task_kind, loader in task_specs:
        rows, feature_names = loader(source_root)
        advisor = (
            build_platform_advisor(
                model="Qwen/Qwen3.5-4B",
                model_path=None,
                timeout_seconds=pytrio_timeout_seconds,
            )
            if advisor_mode == "pytrio"
            else None
        )
        task_reports.append(
            _task_report(
                output_root / task_name,
                task_name,
                task_kind,
                rows,
                feature_names,
                advisor,
            )
        )
    successful = [
        task["round_count"] == 10
        and task["parent_chain_valid"]
        and not task["group_overlap"]
        and task["final_improvement"] >= -1e-12
        for task in task_reports
    ]
    all_rounds = [round_row for task in task_reports for round_row in task["rounds"]]
    pytrio_response_count = sum(
        round_row.get("decision", {}).get("advisor_source") == "pytrio"
        and int(round_row.get("input_tokens", 0)) > 0
        and int(round_row.get("output_tokens", 0)) > 0
        for round_row in all_rounds
    )
    pytrio_executed_count = sum(
        round_row.get("decision", {}).get("advisor_source") == "pytrio"
        and bool(round_row.get("decision", {}).get("proposal_accepted"))
        for round_row in all_rounds
    )
    report = {
        "format": "brace-msi.unseen-platform-simulation.v1",
        "experiment_id": experiment_id,
        "status": "completed",
        "official_score": False,
        "official_trial_consumed": False,
        "rc_modified": False,
        "simulated_parent": True,
        "seed": SEED,
        "advisor_mode": advisor_mode,
        "advisor_model": "Qwen/Qwen3.5-4B" if advisor_mode == "pytrio" else None,
        "pytrio_response_count": pytrio_response_count,
        "pytrio_executed_count": pytrio_executed_count,
        "input_tokens": sum(int(row.get("input_tokens", 0)) for row in all_rounds),
        "output_tokens": sum(int(row.get("output_tokens", 0)) for row in all_rounds),
        "agent_gate_met": (
            pytrio_response_count >= 3 and pytrio_executed_count >= 1
            if advisor_mode == "pytrio"
            else None
        ),
        "source_manifest_sha256": _json_sha256(raw_manifest),
        "task_count": len(task_reports),
        "all_protocol_checks_passed": all(
            task["round_count"] == 10 and task["parent_chain_valid"] and not task["group_overlap"]
            for task in task_reports
        ),
        "all_final_not_worse": all(successful),
        "strictly_improved_task_count": sum(task["final_improvement"] > 1e-12 for task in task_reports),
        "success_standard_met": all(successful)
        and sum(task["final_improvement"] > 1e-12 for task in task_reports) >= 2,
        "elapsed_seconds": time.time() - started,
        "tasks": task_reports,
    }
    report_path = output_root / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "report.html").write_text(_render_html(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--advisor", choices=("deterministic", "pytrio"), default="deterministic")
    parser.add_argument("--pytrio-timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    report = run(
        args.source,
        args.output,
        experiment_id=args.experiment_id,
        advisor_mode=args.advisor,
        pytrio_timeout_seconds=args.pytrio_timeout_seconds,
    )
    print(json.dumps({key: report[key] for key in (
        "experiment_id", "status", "all_protocol_checks_passed", "all_final_not_worse",
        "strictly_improved_task_count", "success_standard_met", "pytrio_response_count",
        "pytrio_executed_count", "agent_gate_met", "input_tokens", "output_tokens",
        "elapsed_seconds",
    )}, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
