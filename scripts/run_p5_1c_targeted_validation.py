"""Development-only validation for P5-1C targeted drift repairs.

This script uses synthetic data and newly registered development seeds only.
It is not a replacement for the sealed P5-1A final statistical validation.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import psutil


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brace_formal.drift import (  # noqa: E402
    DriftMonitor,
    DriftStatus,
    MonitorConfig,
    assess_window_quality,
)
from brace_formal.drift_state import (  # noqa: E402
    DriftState,
    Observation,
    ReferenceStateMachine,
    ReferenceStatus,
    StateMachineConfig,
)


CONFIG_DEFAULT = ROOT / "configs" / "p5_drift_targeted_repair.json"


def load_config(path: Path | str = CONFIG_DEFAULT) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("experiment_id") != "P5-1C-TARGETED-REPAIR-001":
        raise ValueError("unexpected P5-1C config")
    if payload.get("scope") != "development_only_not_final_validation":
        raise ValueError("P5-1C must remain development-only")
    return payload


def build_jobs(config: dict[str, Any]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    index = 0
    repeats = int(config["independent_streams_per_dimension_scenario"])
    for scenario in config["scenarios"]:
        for dimension in config["dimensions"]:
            for repeat in range(repeats):
                jobs.append(
                    {
                        "scenario": str(scenario),
                        "dimension": int(dimension),
                        "repeat": repeat,
                        "generation_seed": int(config["generation_seed_start"]) + index,
                        "permutation_seed": int(config["permutation_seed_start"]) + index,
                    }
                )
                index += 1
    if index != 72:
        raise ValueError("registered P5-1C job matrix must contain 72 jobs")
    if jobs[-1]["generation_seed"] > int(config["generation_seed_end"]):
        raise ValueError("generation seed allocation exceeded")
    if jobs[-1]["permutation_seed"] > int(config["permutation_seed_end"]):
        raise ValueError("permutation seed allocation exceeded")
    return jobs


def _canonical_sha256(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _window(seed: int, rows: int, dimension: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    factors = rng.normal(size=(rows, math.ceil(dimension / 8)))
    noise = rng.normal(size=(rows, dimension))
    values = np.empty_like(noise)
    for feature in range(dimension):
        values[:, feature] = (
            0.55 * factors[:, feature // 8]
            + math.sqrt(1.0 - 0.55**2) * noise[:, feature]
        )
    scales = np.exp(np.linspace(math.log(0.7), math.log(1.4), dimension))
    return values * scales


def _robust_scale(values: np.ndarray) -> np.ndarray:
    center = np.median(values, axis=0)
    iqr = np.quantile(values, 0.75, axis=0) - np.quantile(values, 0.25, axis=0)
    mad = np.median(np.abs(values - center), axis=0)
    return np.maximum.reduce((iqr / 1.349, 1.4826 * mad, np.full(values.shape[1], 1e-12)))


def _blocks(rows: int) -> np.ndarray:
    if rows % 4:
        raise ValueError("registered row count must be divisible by block size four")
    return np.repeat(np.arange(rows // 2), 4)


def _monitor(config: dict[str, Any], seed: int) -> DriftMonitor:
    return DriftMonitor(
        MonitorConfig(
            calibration_method="block_permutation_maxT",
            permutations=int(config["permutations"]),
            effect_threshold=float(config["effect_threshold"]),
            random_seed=seed,
        )
    )


def _compare(
    monitor: DriftMonitor,
    reference: np.ndarray,
    current: np.ndarray,
    config: dict[str, Any],
    *,
    group_ids: tuple[np.ndarray, np.ndarray] | None = None,
    look: int = 1,
) -> Any:
    rows = len(reference)
    group_kwargs: dict[str, Any] = {}
    if group_ids is not None:
        group_kwargs = {
            "reference_group_ids": group_ids[0],
            "current_group_ids": group_ids[1],
            "reference_time_hints": np.arange(rows, dtype=np.float64),
            "current_time_hints": np.arange(rows, rows * 2, dtype=np.float64),
        }
    return monitor.compare(
        reference,
        current,
        alpha_run=float(config["alpha_run"]),
        alpha_window=float(config["alpha_run"]) / int(config["windows"]),
        alpha_spent=min(
            float(config["alpha_run"]),
            look * float(config["alpha_run"]) / int(config["windows"]),
        ),
        reference_epoch=1,
        history_window_count=3,
        block_ids=_blocks(rows),
        **group_kwargs,
    )


def _calibrated_state(config: dict[str, Any]) -> tuple[ReferenceStateMachine, DriftState]:
    machine = ReferenceStateMachine(
        StateMachineConfig(
            calibration_min_windows=3,
            confirmation_windows=int(config["confirmation_windows"]),
            recovery_windows=2,
            rebase_min_windows=3,
            stable_delay_windows=1,
        )
    )
    state = DriftState.initial(alpha_run=float(config["alpha_run"]))
    for index in range(3):
        state = machine.observe(state, f"cal-{index}", Observation.STABLE)
    return machine, state


def run_job(job: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    process = psutil.Process()
    rss_before = process.memory_info().rss
    rows = int(config["rows_per_window"])
    dimension = int(job["dimension"])
    seed = int(job["generation_seed"])
    reference = _window(seed, rows, dimension)
    current = _window(seed + 100_000, rows, dimension)
    truth = tuple(range(min(3, dimension)))
    effects = config["development_effects"]
    monitor = _monitor(config, int(job["permutation_seed"]))
    scenario = str(job["scenario"])
    report = None
    detected = False
    quality_blocked = False
    state_confirmed = False
    state_recovered = False
    reference_polluted = False

    if scenario == "medium_variance":
        center = np.median(current[:, truth], axis=0)
        current[:, truth] = center + float(effects["variance_multiplier"]) * (
            current[:, truth] - center
        )
    elif scenario == "noise_increase":
        rng = np.random.default_rng(seed + 200_000)
        current[:, truth] += rng.normal(
            scale=float(effects["noise_standard_deviation_multiplier"])
            * _robust_scale(reference)[list(truth)],
            size=(rows, len(truth)),
        )
    elif scenario == "sparse_outlier":
        current[0, 0] += float(effects["sparse_outlier_robust_scale"]) * _robust_scale(reference)[0]

    if scenario == "group_composition":
        reference_a = round(rows * float(effects["group_reference_probability"]))
        current_a = round(rows * float(effects["group_current_probability"]))
        reference_groups = np.asarray(["a"] * reference_a + ["b"] * (rows - reference_a))
        current_groups = np.asarray(["a"] * current_a + ["b"] * (rows - current_a))
        report = _compare(
            monitor,
            reference,
            current,
            config,
            group_ids=(reference_groups, current_groups),
        )
        detected = bool(report.group_evidence and report.group_evidence.selected)
    elif scenario == "persistent_drift_recovery":
        machine, state = _calibrated_state(config)
        initial_reference = state.active_reference_ids
        statuses: list[str] = []
        for look in range(1, 6):
            episode = _window(seed + 300_000 + look, rows, dimension)
            if look <= 3:
                episode[:, truth] += float(effects["persistent_location_shift"]) * _robust_scale(reference)[list(truth)]
            episode_report = _compare(monitor, reference, episode, config, look=look)
            quality = assess_window_quality(reference, episode)
            if episode_report.status is DriftStatus.WARNING:
                observation = Observation.WARNING
            elif look > 3 and quality.acceptable_for_reference:
                # In this controlled recovery arm, clean generator provenance is
                # the independent positive stability evidence.
                observation = Observation.STABLE
            else:
                observation = Observation.NO_DRIFT_DETECTED
            state = machine.observe(
                state,
                f"episode-{look}",
                observation,
                data_quality_ok=quality.acceptable_for_reference,
            )
            statuses.append(state.status.value)
        state_confirmed = ReferenceStatus.CONFIRMED.value in statuses
        state_recovered = state.status is ReferenceStatus.STABLE
        reference_polluted = initial_reference != state.active_reference_ids
        detected = state_confirmed
        report = episode_report
    else:
        report = _compare(monitor, reference, current, config)
        detected = report.status is DriftStatus.WARNING

    quality = assess_window_quality(reference, current)
    if scenario == "sparse_outlier":
        quality_blocked = not quality.acceptable_for_reference
        machine, state = _calibrated_state(config)
        initial_reference = state.active_reference_ids
        state = machine.observe(
            state,
            "outlier-window",
            Observation.WARNING if detected else Observation.NO_DRIFT_DETECTED,
            data_quality_ok=quality.acceptable_for_reference,
        )
        reference_polluted = initial_reference != state.active_reference_ids

    receipt_names = sorted(
        {item.name for feature in report.features for item in feature.statistic_contributions}
    )
    return {
        **job,
        "job_id": _canonical_sha256(job)[:20],
        "detected": detected,
        "quality_blocked": quality_blocked,
        "reference_polluted": reference_polluted,
        "state_confirmed": state_confirmed,
        "state_recovered": state_recovered,
        "status": report.status.value,
        "group_available": bool(report.group_evidence and report.group_evidence.available),
        "time_available": bool(report.time_evidence and report.time_evidence.available),
        "statistic_receipt_names": receipt_names,
        "limitations": list(report.limitations),
        "cpu_seconds": time.process_time() - started_cpu,
        "wall_seconds": time.perf_counter() - started_wall,
        "rss_delta_bytes": max(0, process.memory_info().rss - rss_before),
    }


def aggregate(records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    gates = config["development_gates"]
    for scenario in config["scenarios"]:
        for dimension in config["dimensions"]:
            selected = [
                item
                for item in records
                if item["scenario"] == scenario and item["dimension"] == dimension
            ]
            rate = sum(bool(item["detected"]) for item in selected) / len(selected)
            row = {
                "scenario": scenario,
                "dimension": dimension,
                "independent_streams": len(selected),
                "detection_rate": rate,
                "quality_block_rate": sum(bool(item["quality_blocked"]) for item in selected)
                / len(selected),
                "reference_pollution_rate": sum(bool(item["reference_polluted"]) for item in selected)
                / len(selected),
                "confirmation_and_recovery_rate": sum(
                    bool(item["state_confirmed"] and item["state_recovered"])
                    for item in selected
                )
                / len(selected),
                "mean_cpu_seconds": sum(float(item["cpu_seconds"]) for item in selected)
                / len(selected),
                "mean_wall_seconds": sum(float(item["wall_seconds"]) for item in selected)
                / len(selected),
                "maximum_rss_delta_bytes": max(int(item["rss_delta_bytes"]) for item in selected),
            }
            rows.append(row)
            if scenario == "no_drift":
                passed = rate <= float(gates["no_drift_warning_rate_max"])
                target = f"<= {gates['no_drift_warning_rate_max']}"
                observed = rate
            elif scenario == "medium_variance":
                passed = rate >= float(gates["medium_variance_detection_rate_min"])
                target = f">= {gates['medium_variance_detection_rate_min']}"
                observed = rate
            elif scenario == "noise_increase":
                passed = rate >= float(gates["noise_detection_rate_min"])
                target = f">= {gates['noise_detection_rate_min']}"
                observed = rate
            elif scenario == "group_composition":
                passed = rate >= float(gates["group_composition_detection_rate_min"])
                target = f">= {gates['group_composition_detection_rate_min']}"
                observed = rate
            elif scenario == "sparse_outlier":
                observed = row["quality_block_rate"]
                passed = observed >= float(gates["outlier_reference_block_rate_min"]) and row[
                    "reference_pollution_rate"
                ] == 0.0
                target = f">= {gates['outlier_reference_block_rate_min']} and pollution=0"
            else:
                observed = row["confirmation_and_recovery_rate"]
                passed = observed >= float(
                    gates["persistent_confirmation_and_recovery_rate_min"]
                ) and row["reference_pollution_rate"] == 0.0
                target = (
                    f">= {gates['persistent_confirmation_and_recovery_rate_min']} "
                    "and pollution=0"
                )
            checks.append(
                {
                    "check_id": f"{scenario}.d{dimension}",
                    "passed": bool(passed),
                    "target": target,
                    "observed": observed,
                }
            )
    expected_receipts = {
        "missing_delta",
        "location_shift",
        "scale_shift",
        "wasserstein_shift",
        "ks_distance",
    }
    receipts_complete = all(
        set(item["statistic_receipt_names"]) == expected_receipts for item in records
    )
    checks.append(
        {
            "check_id": "receipt.all_five_statistics",
            "passed": receipts_complete,
            "target": "all jobs",
            "observed": sum(
                set(item["statistic_receipt_names"]) == expected_receipts for item in records
            ),
        }
    )
    return {
        "aggregates": rows,
        "checks": checks,
        "passed_checks": sum(bool(item["passed"]) for item in checks),
        "failed_checks": sum(not bool(item["passed"]) for item in checks),
        "overall_development_pass": all(bool(item["passed"]) for item in checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_DEFAULT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    args = parser.parse_args()
    config = load_config(args.config)
    output_root = args.output or Path(config["raw_output_dir"])
    output_root.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(config)
    records: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_job, job, config): job for job in jobs}
        for completed, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            records.append(record)
            if completed % 6 == 0 or completed == len(jobs):
                print(f"completed {completed}/{len(jobs)}", flush=True)
    records.sort(key=lambda item: (item["scenario"], item["dimension"], item["repeat"]))
    raw_path = output_root / "development-records.jsonl"
    raw_path.write_text(
        "".join(json.dumps(item, sort_keys=True, allow_nan=False) + "\n" for item in records),
        encoding="utf-8",
    )
    result = {
        "format": "brace-msi.p5-1c-targeted-validation.v1",
        "experiment_id": config["experiment_id"],
        "scope": config["scope"],
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest().upper(),
        "job_count": len(records),
        "raw_records": str(raw_path),
        "raw_records_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest().upper(),
        **aggregate(records, config),
    }
    result_path = output_root / "summary.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"result": str(result_path), "failed_checks": result["failed_checks"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
