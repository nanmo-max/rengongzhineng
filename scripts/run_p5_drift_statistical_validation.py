"""Reproducible synthetic validation for the frozen P5 drift core.

This is a research harness, not part of the formal competition image.
It never reads competition data and it does not train an industrial model.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import threading
import time
from typing import Any, Iterable

import numpy as np
import psutil


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brace_formal.drift import DriftMonitor, DriftStatus, MonitorConfig  # noqa: E402
from brace_formal.drift_state import (  # noqa: E402
    AlphaSpending,
    DriftState,
    Observation,
    ReferenceStateMachine,
    ReferenceStatus,
    StateMachineConfig,
)


CONFIG_DEFAULT = ROOT / "configs" / "p5_drift_statistical_validation.json"


def load_config(path: Path | str = CONFIG_DEFAULT) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("format") != "brace-msi.p5-drift-statistical-validation-config.v1":
        raise ValueError("unsupported validation config")
    return payload


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _seeds(config: dict[str, Any], name: str) -> list[int]:
    spec = config["seed_sets"][name]
    return list(range(int(spec["start"]), int(spec["start"]) + int(spec["count"])))


def wilson_interval(
    *, successes: int, trials: int, confidence: float = 0.95
) -> tuple[float, float]:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("invalid binomial counts")
    if not math.isclose(confidence, 0.95, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("this frozen harness supports the preregistered 95% interval")
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)
    ) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def bootstrap_mean_interval(
    values: Iterable[float], *, seed: int, resamples: int = 2000
) -> tuple[float, float]:
    data = np.asarray(list(values), dtype=np.float64)
    if not len(data):
        return math.nan, math.nan
    if len(data) == 1:
        value = float(data[0])
        return value, value
    rng = np.random.default_rng(seed)
    samples = rng.choice(data, size=(resamples, len(data)), replace=True)
    means = np.mean(samples, axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def generate_window(
    *,
    seed: int,
    dimension: int,
    correlation: str,
    rows: int = 80,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    scales = np.exp(np.linspace(math.log(0.65), math.log(1.45), dimension))
    locations = np.linspace(-0.4, 0.4, dimension)
    noise = rng.normal(size=(rows, dimension))
    if correlation == "independent":
        standardized = noise
    elif correlation == "block_positive":
        group_count = math.ceil(dimension / 8)
        factors = rng.normal(size=(rows, group_count))
        standardized = np.empty_like(noise)
        for feature in range(dimension):
            standardized[:, feature] = (
                0.65 * factors[:, feature // 8] + math.sqrt(1.0 - 0.65**2) * noise[:, feature]
            )
    elif correlation == "mixed_sign":
        group_count = math.ceil(dimension / 8)
        factors = rng.normal(size=(rows, group_count))
        standardized = np.empty_like(noise)
        for feature in range(dimension):
            sign = -1.0 if feature % 2 else 1.0
            standardized[:, feature] = (
                sign * 0.60 * factors[:, feature // 8]
                + math.sqrt(1.0 - 0.60**2) * noise[:, feature]
            )
    elif correlation == "strong_collinear":
        group_count = math.ceil(dimension / 8)
        factors = rng.normal(size=(rows, group_count))
        standardized = np.empty_like(noise)
        for feature in range(dimension):
            standardized[:, feature] = (
                0.92 * factors[:, feature // 8] + math.sqrt(1.0 - 0.92**2) * noise[:, feature]
            )
    else:
        raise ValueError(f"unknown correlation structure: {correlation}")
    return locations + standardized * scales


def _robust_scale(reference: np.ndarray) -> np.ndarray:
    median = np.median(reference, axis=0)
    iqr = np.quantile(reference, 0.75, axis=0) - np.quantile(reference, 0.25, axis=0)
    mad = np.median(np.abs(reference - median), axis=0)
    return np.maximum.reduce((iqr / 1.349, 1.4826 * mad, np.full(reference.shape[1], 1e-12)))


def apply_group_composition(
    values: np.ndarray,
    *,
    seed: int,
    probability: float,
    truth: tuple[int, ...],
    shift: float,
    scale: np.ndarray,
) -> np.ndarray:
    result = values.copy()
    rng = np.random.default_rng(seed)
    groups = rng.binomial(1, probability, size=len(result))
    for feature in truth:
        result[:, feature] += groups * shift * scale[feature]
    return result


def _inject(
    current: np.ndarray,
    reference: np.ndarray,
    *,
    scenario: str,
    magnitude: float,
    seed: int,
    truth: tuple[int, ...],
    config: dict[str, Any],
) -> np.ndarray:
    result = current.copy()
    scale = _robust_scale(reference)
    rng = np.random.default_rng(seed)
    if scenario in {"mean_shift", "progressive_shift", "transient_shift", "reverse_recovery"}:
        result[:, truth] += magnitude * scale[list(truth)]
    elif scenario == "variance_shift":
        center = np.median(result[:, truth], axis=0)
        result[:, truth] = center + magnitude * (result[:, truth] - center)
    elif scenario == "joint_shift":
        center = np.median(result[:, truth], axis=0)
        result[:, truth] = center + 1.35 * (result[:, truth] - center)
        result[:, truth] += magnitude * scale[list(truth)]
    elif scenario == "noise_increase":
        result[:, truth] += rng.normal(
            scale=magnitude * scale[list(truth)], size=(len(result), len(truth))
        )
    elif scenario == "outlier_burst":
        count = max(1, int(round(len(result) * config["effects"]["outlier_fraction"])))
        rows = rng.choice(len(result), size=count, replace=False)
        for feature in truth:
            result[rows, feature] += magnitude * scale[feature]
    elif scenario == "composition_change":
        probability = float(config["effects"]["composition_current_probability"])
        result = apply_group_composition(
            result,
            seed=seed,
            probability=probability,
            truth=truth,
            shift=magnitude,
            scale=scale,
        )
    elif scenario in {"no_drift", "correlation_check", "invalid_exchangeability", "by_comparison"}:
        pass
    else:
        raise ValueError(f"unknown scenario injection: {scenario}")
    return result


def _job_id(job: dict[str, Any]) -> str:
    return canonical_sha256(job)[:20]


def _job(
    *,
    split: str,
    scenario: str,
    seed: int,
    dimension: int,
    correlation: str,
    method: str,
    effect: str = "none",
    variant: str = "primary",
) -> dict[str, Any]:
    payload = {
        "split": split,
        "scenario": scenario,
        "seed": seed,
        "dimension": dimension,
        "correlation": correlation,
        "method": method,
        "effect": effect,
        "variant": variant,
    }
    payload["job_id"] = _job_id(payload)
    return payload


def build_final_jobs(config: dict[str, Any]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    dimensions = config["dimensions"]
    primary_correlation = config["primary_correlation"]
    primary_method = config["primary_method"]
    for dimension in dimensions:
        for seed in _seeds(config, "final_null"):
            jobs.append(
                _job(
                    split="final",
                    scenario="no_drift",
                    seed=seed,
                    dimension=dimension,
                    correlation=primary_correlation,
                    method=primary_method,
                )
            )
        for seed in _seeds(config, "final_effect"):
            for scenario in ("mean_shift", "variance_shift"):
                for effect in ("small", "medium", "large"):
                    jobs.append(
                        _job(
                            split="final",
                            scenario=scenario,
                            seed=seed,
                            dimension=dimension,
                            correlation=primary_correlation,
                            method=primary_method,
                            effect=effect,
                        )
                    )
            for scenario in (
                "joint_shift",
                "progressive_shift",
                "noise_increase",
                "composition_change",
            ):
                jobs.append(
                    _job(
                        split="final",
                        scenario=scenario,
                        seed=seed,
                        dimension=dimension,
                        correlation=primary_correlation,
                        method=primary_method,
                        effect="medium",
                    )
                )
        for seed in _seeds(config, "final_recovery"):
            for scenario in ("outlier_burst", "transient_shift", "reverse_recovery"):
                jobs.append(
                    _job(
                        split="final",
                        scenario=scenario,
                        seed=seed,
                        dimension=dimension,
                        correlation=primary_correlation,
                        method=primary_method,
                        effect="medium",
                    )
                )
        for seed in _seeds(config, "final_correlation"):
            for correlation in config["correlation_structures"]:
                for variant in ("null", "mean_medium"):
                    jobs.append(
                        _job(
                            split="final",
                            scenario="correlation_check",
                            seed=seed,
                            dimension=dimension,
                            correlation=correlation,
                            method=primary_method,
                            effect="medium" if variant == "mean_medium" else "none",
                            variant=variant,
                        )
                    )
            jobs.append(
                _job(
                    split="final",
                    scenario="invalid_exchangeability",
                    seed=seed,
                    dimension=dimension,
                    correlation=primary_correlation,
                    method=primary_method,
                    effect="medium",
                )
            )
            for method in config["methods"]:
                for variant in ("null", "mean_medium"):
                    jobs.append(
                        _job(
                            split="final",
                            scenario="by_comparison",
                            seed=seed,
                            dimension=dimension,
                            correlation=primary_correlation,
                            method=method,
                            effect="medium" if variant == "mean_medium" else "none",
                            variant=variant,
                        )
                    )
    return jobs


def build_preflight_jobs(config: dict[str, Any], split: str) -> list[dict[str, Any]]:
    seed_name = "calibration" if split == "calibration" else "development"
    scenarios = ("no_drift", "mean_shift", "variance_shift", "progressive_shift")
    jobs: list[dict[str, Any]] = []
    for seed in _seeds(config, seed_name):
        for dimension in config["dimensions"]:
            for scenario in scenarios:
                jobs.append(
                    _job(
                        split=split,
                        scenario=scenario,
                        seed=seed,
                        dimension=dimension,
                        correlation=config["primary_correlation"],
                        method=config["primary_method"],
                        effect="medium" if scenario != "no_drift" else "none",
                    )
                )
    return jobs


def _stable_state(alpha_run: float) -> DriftState:
    return DriftState(
        status=ReferenceStatus.STABLE,
        reference_epoch=1,
        alpha_run=alpha_run,
        alpha_spent=0.0,
        look_index=0,
        active_reference_ids=("reference",),
        candidate_reference_ids=(),
        quarantine_ids=(),
        rejected_window_ids=(),
        seen_window_ids=("reference",),
        warning_streak=0,
        recovery_streak=0,
    )


def _schedule(job: dict[str, Any], config: dict[str, Any]) -> tuple[list[float], int | None]:
    scenario = job["scenario"]
    effect = job["effect"]
    effects = config["effects"]
    if scenario == "no_drift":
        return [0.0] * config["windows_per_run"], None
    if scenario in {"mean_shift", "variance_shift"}:
        table = effects["mean_shift"] if scenario == "mean_shift" else effects["scale_multiplier"]
        return [float(table[effect])] * 4, 0
    if scenario in {"joint_shift", "noise_increase", "composition_change"}:
        magnitude = {
            "joint_shift": effects["mean_shift"]["medium"],
            "noise_increase": effects["noise_added_std"],
            "composition_change": effects["composition_group_shift"],
        }[scenario]
        return [float(magnitude)] * 4, 0
    if scenario == "progressive_shift":
        final = float(effects["progressive_final_shift"])
        return [0.0, final * 0.2, final * 0.4, final * 0.6, final * 0.8, final, final, final], 1
    if scenario == "outlier_burst":
        return [0.0, float(effects["outlier_magnitude"]), 0.0, 0.0, 0.0], 1
    if scenario == "transient_shift":
        medium = float(effects["mean_shift"]["medium"])
        return [0.0, medium, 0.0, 0.0, 0.0], 1
    if scenario == "reverse_recovery":
        medium = float(effects["mean_shift"]["medium"])
        large = float(effects["mean_shift"]["large"])
        return [0.0, medium, large, large, medium, 0.0, 0.0, 0.0, 0.0], 1
    if scenario in {"correlation_check", "by_comparison"}:
        if job["variant"] == "null":
            return [0.0] * 4, None
        return [float(effects["mean_shift"]["medium"])] * 4, 0
    if scenario == "invalid_exchangeability":
        return [float(effects["mean_shift"]["medium"])], 0
    raise ValueError(f"no schedule for {scenario}")


def _truth_features(job: dict[str, Any], config: dict[str, Any]) -> tuple[int, ...]:
    if job["scenario"] in {"joint_shift", "composition_change"}:
        return tuple(range(min(config["effects"]["joint_feature_count"], job["dimension"])))
    if job["scenario"] == "no_drift" or job.get("variant") == "null":
        return ()
    return (0,)


def _recall_at_k(report: Any, truth: tuple[int, ...]) -> float | None:
    if not truth:
        return None
    ranked = sorted(
        report.features,
        key=lambda item: (item.contribution, item.omnibus_score),
        reverse=True,
    )[: len(truth)]
    return len({item.feature_index for item in ranked}.intersection(truth)) / len(truth)


def baseline_contamination_count(
    *, active_ids: Iterable[str], truth_drift_ids: Iterable[str]
) -> int:
    return len(set(active_ids).intersection(truth_drift_ids))


def run_job(job: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    reference = generate_window(
        seed=job["seed"] * 1000 + 1,
        dimension=job["dimension"],
        correlation=job["correlation"],
        rows=config["samples_per_window"],
    )
    schedule, onset = _schedule(job, config)
    truth = _truth_features(job, config)
    if job["scenario"] == "composition_change":
        base_scale = _robust_scale(reference)
        reference = apply_group_composition(
            reference,
            seed=job["seed"] * 1000 + 50,
            probability=float(config["effects"]["composition_reference_probability"]),
            truth=truth,
            shift=float(config["effects"]["composition_group_shift"]),
            scale=base_scale,
        )
    monitor = DriftMonitor(
        MonitorConfig(
            calibration_method=job["method"],
            permutations=config["monitor"]["permutations"],
            effect_threshold=config["monitor"]["effect_threshold"],
            random_seed=job["seed"],
        )
    )
    machine = ReferenceStateMachine(
        StateMachineConfig(
            confirmation_windows=config["monitor"]["confirmation_windows"],
            recovery_windows=config["monitor"]["recovery_windows"],
            rebase_min_windows=config["monitor"]["rebase_min_windows"],
        )
    )
    state = _stable_state(config["monitor"]["alpha_run"])
    spending = AlphaSpending(
        config["monitor"]["alpha_run"], horizon=config["windows_per_run"]
    )
    warning_count = 0
    first_confirmation: int | None = None
    recalls: list[float] = []
    statuses: list[str] = []
    limitations: list[str] = []
    selected_features: list[list[int]] = []
    truth_drift_ids: list[str] = []
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    if job["scenario"] == "invalid_exchangeability":
        current = generate_window(
            seed=job["seed"] * 1000 + 100,
            dimension=job["dimension"],
            correlation=job["correlation"],
            rows=config["samples_per_window"],
        )
        current = _inject(
            current,
            reference,
            scenario="mean_shift",
            magnitude=schedule[0],
            seed=job["seed"] * 1000 + 200,
            truth=truth,
            config=config,
        )
        crossing = np.tile(
            np.arange(config["samples_per_window"] // config["block_size"]),
            2 * config["block_size"],
        )
        report = monitor.compare(
            reference,
            current,
            alpha_run=config["monitor"]["alpha_run"],
            alpha_window=config["monitor"]["alpha_window"],
            alpha_spent=config["monitor"]["alpha_window"],
            reference_epoch=1,
            history_window_count=1,
            block_ids=crossing,
        )
        statuses.append(report.status.value)
        limitations.extend(report.limitations)
    else:
        for window_index, magnitude in enumerate(schedule):
            alpha_window, state = spending.spend(state)
            current = generate_window(
                seed=job["seed"] * 1000 + 100 + window_index,
                dimension=job["dimension"],
                correlation=job["correlation"],
                rows=config["samples_per_window"],
            )
            injection_scenario = job["scenario"]
            if job["scenario"] in {"correlation_check", "by_comparison"}:
                injection_scenario = "mean_shift" if job["variant"] == "mean_medium" else "no_drift"
            current = _inject(
                current,
                reference,
                scenario=injection_scenario,
                magnitude=magnitude,
                seed=job["seed"] * 1000 + 500 + window_index,
                truth=truth,
                config=config,
            )
            block_count = config["samples_per_window"] // config["block_size"]
            block_ids = np.repeat(np.arange(2 * block_count), config["block_size"])
            report = monitor.compare(
                reference,
                current,
                alpha_run=config["monitor"]["alpha_run"],
                alpha_window=alpha_window,
                alpha_spent=state.alpha_spent,
                reference_epoch=state.reference_epoch,
                history_window_count=window_index + 1,
                block_ids=block_ids,
            )
            statuses.append(report.status.value)
            limitations.extend(report.limitations)
            selected_features.append(
                [item.feature_index for item in report.features if item.selected]
            )
            if report.status is DriftStatus.WARNING:
                warning_count += 1
                observation = Observation.WARNING
            else:
                observation = Observation.STABLE
            window_id = f"{job['job_id']}-window-{window_index}"
            if magnitude != 0.0 and injection_scenario != "no_drift":
                truth_drift_ids.append(window_id)
            state = machine.observe(
                state,
                window_id,
                observation,
            )
            if state.status is ReferenceStatus.CONFIRMED and first_confirmation is None:
                first_confirmation = window_index
                recall = _recall_at_k(report, truth)
                if recall is not None:
                    recalls.append(recall)
    cpu_seconds = time.process_time() - cpu_start
    wall_seconds = time.perf_counter() - wall_start
    detected = first_confirmation is not None
    delay = None if not detected or onset is None else max(0, first_confirmation - onset)
    contamination_count = baseline_contamination_count(
        active_ids=state.active_reference_ids,
        truth_drift_ids=truth_drift_ids,
    )
    return {
        **job,
        "windows": len(schedule),
        "window_warnings": warning_count,
        "confirmed": detected,
        "first_confirmation_window": first_confirmation,
        "onset_window": onset,
        "detection_delay": delay,
        "recall_at_k": float(np.mean(recalls)) if recalls else None,
        "truth_features": list(truth),
        "selected_features_by_window": selected_features,
        "statuses": statuses,
        "limitations": sorted(set(limitations)),
        "final_reference_status": state.status.value,
        "reference_epoch": state.reference_epoch,
        "baseline_contamination_count": contamination_count,
        "alpha_spent": state.alpha_spent,
        "alpha_excess": max(0.0, state.alpha_spent - config["monitor"]["alpha_run"]),
        "cpu_seconds": cpu_seconds,
        "wall_seconds": wall_seconds,
    }


def aggregate_no_drift(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("no records")
    stream_rates = [item["window_warnings"] / item["windows"] for item in records]
    confirmed = sum(bool(item["confirmed"]) for item in records)
    low, high = wilson_interval(successes=confirmed, trials=len(records))
    return {
        "stream_count": len(records),
        "window_count": sum(item["windows"] for item in records),
        "single_window_fpr": sum(item["window_warnings"] for item in records)
        / sum(item["windows"] for item in records),
        "single_window_fpr_by_stream": stream_rates,
        "confirmation_fpr": confirmed / len(records),
        "run_level_false_alarm": confirmed / len(records),
        "run_level_trials": len(records),
        "run_level_wilson_95": [low, high],
        "alpha_excess_count": sum(item["alpha_excess"] > 1e-12 for item in records),
    }


def _group_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["scenario"],
        record["dimension"],
        record["effect"],
        record["correlation"],
        record["method"],
        record["variant"],
    )


def aggregate_records(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(_group_key(record), []).append(record)
    output: list[dict[str, Any]] = []
    bootstrap_seed = _seeds(config, "bootstrap")[0]
    for key, items in sorted(grouped.items(), key=lambda pair: tuple(str(x) for x in pair[0])):
        scenario, dimension, effect, correlation, method, variant = key
        detected = sum(bool(item["confirmed"]) for item in items)
        event_low, event_high = wilson_interval(successes=detected, trials=len(items))
        delays = [float(item["detection_delay"]) for item in items if item["detection_delay"] is not None]
        recalls = [float(item["recall_at_k"]) for item in items if item["recall_at_k"] is not None]
        aggregate: dict[str, Any] = {
            "scenario": scenario,
            "dimension": dimension,
            "effect": effect,
            "correlation": correlation,
            "method": method,
            "variant": variant,
            "stream_count": len(items),
            "event_recall": detected / len(items),
            "event_recall_wilson_95": [event_low, event_high],
            "miss_rate": 1.0 - detected / len(items),
            "median_detection_delay": statistics.median(delays) if delays else None,
            "mean_recall_at_k": float(np.mean(recalls)) if recalls else None,
            "baseline_contamination_rate": sum(
                item["baseline_contamination_count"] > 0 for item in items
            )
            / len(items),
            "alpha_excess_rate": sum(item["alpha_excess"] > 1e-12 for item in items)
            / len(items),
            "mean_cpu_seconds": float(np.mean([item["cpu_seconds"] for item in items])),
            "mean_wall_seconds": float(np.mean([item["wall_seconds"] for item in items])),
            "insufficient_calibration_rate": sum(
                "insufficient_calibration" in item["statuses"] for item in items
            )
            / len(items),
        }
        if scenario == "no_drift" or (scenario in {"correlation_check", "by_comparison"} and variant == "null"):
            null = aggregate_no_drift(items)
            low, high = bootstrap_mean_interval(
                null.pop("single_window_fpr_by_stream"),
                seed=bootstrap_seed + int(dimension),
                resamples=config["statistics"]["bootstrap_resamples"],
            )
            null["single_window_fpr_stream_bootstrap_95"] = [low, high]
            aggregate.update(null)
        output.append(aggregate)
    return output


def _manifest(jobs: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": "brace-msi.p5-validation-job-manifest.v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": canonical_sha256(config),
        "job_count": len(jobs),
        "jobs_sha256": canonical_sha256(jobs),
        "jobs": jobs,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def execute_split(
    *,
    split: str,
    config: dict[str, Any],
    output_root: Path,
    workers: int,
) -> list[dict[str, Any]]:
    jobs = build_final_jobs(config) if split == "final" else build_preflight_jobs(config, split)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / f"{split}-manifest.json"
    manifest = _manifest(jobs, config)
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise RuntimeError(f"{split} manifest differs from frozen plan")
    else:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    raw_path = output_root / f"{split}-records.jsonl"
    existing_records = _read_jsonl(raw_path)
    by_id = {item["job_id"]: item for item in existing_records}
    pending = [job for job in jobs if job["job_id"] not in by_id]
    if pending:
        with raw_path.open("a", encoding="utf-8", newline="\n") as handle:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(run_job, job, config): job for job in pending}
                for completed, future in enumerate(as_completed(futures), start=1):
                    result = future.result()
                    handle.write(json.dumps(result, sort_keys=True, allow_nan=False) + "\n")
                    handle.flush()
                    by_id[result["job_id"]] = result
                    if completed % 10 == 0 or completed == len(pending):
                        print(f"{split}: completed {completed}/{len(pending)} pending jobs", flush=True)
    ordered = [by_id[job["job_id"]] for job in jobs]
    if len(ordered) != len(jobs):
        raise RuntimeError(f"{split} did not produce every frozen job")
    summary = {
        "format": "brace-msi.p5-validation-split-summary.v1",
        "split": split,
        "manifest_sha256": canonical_sha256(manifest),
        "records_sha256": canonical_sha256(ordered),
        "job_count": len(ordered),
        "aggregates": aggregate_records(ordered, config),
    }
    (output_root / f"{split}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return ordered


class _MemorySampler:
    def __init__(self) -> None:
        self.process = psutil.Process()
        self.peak = self.process.memory_info().rss
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.wait(0.005):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __enter__(self) -> "_MemorySampler":
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop.set()
        self.thread.join()
        self.peak = max(self.peak, self.process.memory_info().rss)


def benchmark_affinity(config: dict[str, Any], logical_cpus: int) -> dict[str, Any]:
    process = psutil.Process()
    available = process.cpu_affinity() if hasattr(process, "cpu_affinity") else list(range(os.cpu_count() or 1))
    selected = available[: min(logical_cpus, len(available))]
    if not selected:
        raise RuntimeError("no CPUs available for benchmark")
    original = list(available)
    if hasattr(process, "cpu_affinity"):
        process.cpu_affinity(selected)
    try:
        seed = _seeds(config, "performance")[0]
        job = _job(
            split="performance",
            scenario="mean_shift",
            seed=seed,
            dimension=128,
            correlation=config["primary_correlation"],
            method=config["primary_method"],
            effect="medium",
        )
        rss_before = process.memory_info().rss
        cpu_start = time.process_time()
        wall_start = time.perf_counter()
        with _MemorySampler() as sampler:
            result = run_job(job, config)
        cpu_seconds = time.process_time() - cpu_start
        wall_seconds = time.perf_counter() - wall_start
        return {
            "logical_cpu_limit": len(selected),
            "cpu_affinity": selected,
            "cpu_seconds": cpu_seconds,
            "wall_seconds": wall_seconds,
            "peak_rss_bytes": sampler.peak,
            "rss_before_bytes": rss_before,
            "rss_delta_bytes": max(0, sampler.peak - rss_before),
            "permutations": config["monitor"]["permutations"],
            "dimension": 128,
            "windows": result["windows"],
            "per_window_cpu_seconds": cpu_seconds / result["windows"],
            "per_window_wall_seconds": wall_seconds / result["windows"],
            "selected_features": result["selected_features_by_window"],
        }
    finally:
        if hasattr(process, "cpu_affinity"):
            process.cpu_affinity(original)


def run_benchmarks(config: dict[str, Any], output_root: Path) -> list[dict[str, Any]]:
    results = [benchmark_affinity(config, limit) for limit in (8, 4)]
    (output_root / "resource-results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_DEFAULT)
    parser.add_argument(
        "--split", choices=("calibration", "development", "final", "all"), default="all"
    )
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    output_root = Path(config["execution"]["raw_output_root"])
    workers = args.workers or int(config["execution"]["max_workers"])
    splits = ("calibration", "development", "final") if args.split == "all" else (args.split,)
    for split in splits:
        execute_split(split=split, config=config, output_root=output_root, workers=workers)
    if args.benchmark:
        run_benchmarks(config, output_root)
    print(json.dumps({"status": "completed", "output_root": str(output_root)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
