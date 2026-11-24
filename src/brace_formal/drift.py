"""Statistically calibrated, task-identity-independent drift evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any

import numpy as np


class DriftStatus(str, Enum):
    STABLE = "stable"
    WARNING = "warning"
    CONFIRMED = "confirmed"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_CALIBRATION = "insufficient_calibration"


@dataclass(frozen=True)
class StatisticContribution:
    name: str
    raw_value: float
    standardized_score: float
    empirical_p: float
    contribution: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "raw_value": self.raw_value,
            "standardized_score": self.standardized_score,
            "empirical_p": self.empirical_p,
            "contribution": self.contribution,
        }


@dataclass(frozen=True)
class FeatureDrift:
    feature_index: int
    dominant_statistic: str
    location_shift: float
    scale_shift: float
    wasserstein_shift: float
    ks_distance: float
    missing_delta: float
    omnibus_score: float
    empirical_p: float
    adjusted_p: float
    selected: bool
    contribution: float
    statistic_contributions: tuple[StatisticContribution, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature_index": self.feature_index,
            "dominant_statistic": self.dominant_statistic,
            "location_shift": self.location_shift,
            "scale_shift": self.scale_shift,
            "wasserstein_shift": self.wasserstein_shift,
            "ks_distance": self.ks_distance,
            "missing_delta": self.missing_delta,
            "omnibus_score": self.omnibus_score,
            "empirical_p": self.empirical_p,
            "adjusted_p": self.adjusted_p,
            "selected": self.selected,
            "contribution": self.contribution,
            "statistic_contributions": [
                item.as_dict() for item in self.statistic_contributions
            ],
        }


@dataclass(frozen=True)
class GroupDriftEvidence:
    available: bool
    total_variation: float
    empirical_p: float
    selected: bool
    category_count: int
    limitation: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "total_variation": self.total_variation,
            "empirical_p": self.empirical_p,
            "selected": self.selected,
            "category_count": self.category_count,
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class TimeHintEvidence:
    available: bool
    monotonic: bool
    limitation: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "monotonic": self.monotonic,
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class WindowQualityEvidence:
    acceptable_for_reference: bool
    maximum_robust_z: float
    maximum_feature_outlier_fraction: float
    limitation: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "acceptable_for_reference": self.acceptable_for_reference,
            "maximum_robust_z": self.maximum_robust_z,
            "maximum_feature_outlier_fraction": self.maximum_feature_outlier_fraction,
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class DriftReport:
    report_id: str
    status: DriftStatus
    calibration_method: str
    reference_scope_sha256: str
    current_scope_sha256: str
    sample_count: int
    history_window_count: int
    global_score: float
    alpha_run: float
    alpha_window: float
    alpha_spent: float
    permutation_count: int
    minimum_empirical_p: float
    reference_epoch: int
    features: tuple[FeatureDrift, ...]
    limitations: tuple[str, ...]
    group_evidence: GroupDriftEvidence | None = None
    time_evidence: TimeHintEvidence | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": "brace-formal.drift-report.v1",
            "report_id": self.report_id,
            "status": self.status.value,
            "calibration_method": self.calibration_method,
            "reference_scope_sha256": self.reference_scope_sha256,
            "current_scope_sha256": self.current_scope_sha256,
            "sample_count": self.sample_count,
            "history_window_count": self.history_window_count,
            "global_score": self.global_score,
            "alpha_run": self.alpha_run,
            "alpha_window": self.alpha_window,
            "alpha_spent": self.alpha_spent,
            "permutation_count": self.permutation_count,
            "minimum_empirical_p": self.minimum_empirical_p,
            "reference_epoch": self.reference_epoch,
            "features": [item.as_dict() for item in self.features],
            "limitations": list(self.limitations),
            "group_evidence": (
                self.group_evidence.as_dict() if self.group_evidence is not None else None
            ),
            "time_evidence": (
                self.time_evidence.as_dict() if self.time_evidence is not None else None
            ),
        }


@dataclass(frozen=True)
class MonitorConfig:
    calibration_method: str = "block_permutation_maxT"
    permutations: int = 2047
    effect_threshold: float = 2.0
    random_seed: int = 0
    numeric_floor: float = 1e-12
    group_effect_threshold: float = 0.10

    def __post_init__(self) -> None:
        if self.calibration_method not in {"block_permutation_maxT", "by_fallback"}:
            raise ValueError("unsupported calibration method")
        if type(self.permutations) is not int or self.permutations < 1:
            raise ValueError("permutations must be a positive integer")
        if not math.isfinite(self.effect_threshold) or self.effect_threshold < 0.0:
            raise ValueError("effect threshold must be finite and nonnegative")
        if not math.isfinite(self.numeric_floor) or self.numeric_floor <= 0.0:
            raise ValueError("numeric floor must be finite and positive")
        if not math.isfinite(self.group_effect_threshold) or not 0.0 <= self.group_effect_threshold <= 1.0:
            raise ValueError("group effect threshold must be finite and in [0, 1]")


def adjust_pvalues_by(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Yekutieli adjusted p-values under arbitrary dependence."""

    values = np.asarray(pvalues, dtype=np.float64)
    if values.ndim != 1 or not len(values):
        raise ValueError("p-values must be a nonempty vector")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
        raise ValueError("p-values must be finite and in [0, 1]")
    count = len(values)
    harmonic = float(np.sum(1.0 / np.arange(1, count + 1, dtype=np.float64)))
    order = np.argsort(values, kind="stable")
    ranked = values[order]
    raw = ranked * count * harmonic / np.arange(1, count + 1, dtype=np.float64)
    monotone = np.minimum.accumulate(raw[::-1])[::-1]
    adjusted = np.empty_like(monotone)
    adjusted[order] = np.minimum(monotone, 1.0)
    return adjusted


def apply_effect_gate(
    *,
    adjusted_p: np.ndarray,
    omnibus_score: np.ndarray,
    alpha: float,
    effect_threshold: float,
) -> np.ndarray:
    probabilities = np.asarray(adjusted_p, dtype=np.float64)
    effects = np.asarray(omnibus_score, dtype=np.float64)
    if probabilities.shape != effects.shape or probabilities.ndim != 1:
        raise ValueError("adjusted p-values and effects must be equal vectors")
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")
    if not math.isfinite(effect_threshold) or effect_threshold < 0.0:
        raise ValueError("effect threshold must be finite and nonnegative")
    return (probabilities <= alpha) & (effects >= effect_threshold)


def assess_window_quality(
    reference: np.ndarray,
    current: np.ndarray,
    *,
    robust_z_limit: float = 8.0,
    feature_outlier_fraction_limit: float = 0.01,
    numeric_floor: float = 1e-12,
) -> WindowQualityEvidence:
    """Fail closed for sparse extreme contamination before reference admission.

    This is a data-quality receipt, not a drift hypothesis test.  It never
    converts a non-rejection into positive stability evidence.
    """

    left = np.asarray(reference, dtype=np.float64)
    right = np.asarray(current, dtype=np.float64)
    if left.ndim != 2 or right.ndim != 2 or left.shape[1] != right.shape[1]:
        raise ValueError("reference and current must be two-dimensional with equal features")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        return WindowQualityEvidence(False, math.inf, 1.0, "non_finite_values")
    if robust_z_limit <= 0.0 or not 0.0 <= feature_outlier_fraction_limit <= 1.0:
        raise ValueError("quality thresholds are invalid")
    center = np.median(left, axis=0)
    iqr = np.quantile(left, 0.75, axis=0) - np.quantile(left, 0.25, axis=0)
    mad = np.median(np.abs(left - center), axis=0)
    scale = np.maximum.reduce(
        (iqr / 1.349, 1.4826 * mad, np.full(left.shape[1], numeric_floor))
    )
    robust_z = np.abs(right - center) / scale
    feature_fractions = np.mean(robust_z > robust_z_limit, axis=0)
    maximum_z = float(np.max(robust_z))
    maximum_fraction = float(np.max(feature_fractions))
    acceptable = maximum_fraction <= feature_outlier_fraction_limit
    return WindowQualityEvidence(
        acceptable,
        maximum_z,
        maximum_fraction,
        None if acceptable else "sparse_extreme_contamination",
    )


_STATISTIC_NAMES = (
    "missing_delta",
    "location_shift",
    "scale_shift",
    "wasserstein_shift",
    "ks_distance",
)


def _one_dimensional_distances(reference: np.ndarray, current: np.ndarray) -> tuple[float, float]:
    left = np.sort(reference[np.isfinite(reference)])
    right = np.sort(current[np.isfinite(current)])
    if not len(left) or not len(right):
        return 0.0, 0.0
    support = np.sort(np.concatenate((left, right)))
    if len(support) < 2:
        return 0.0, 0.0
    intervals = np.diff(support)
    left_cdf = np.searchsorted(left, support[:-1], side="right") / len(left)
    right_cdf = np.searchsorted(right, support[:-1], side="right") / len(right)
    wasserstein = float(np.sum(np.abs(left_cdf - right_cdf) * intervals))
    all_left = np.searchsorted(left, support, side="right") / len(left)
    all_right = np.searchsorted(right, support, side="right") / len(right)
    ks = float(np.max(np.abs(all_left - all_right)))
    return wasserstein, ks


def _feature_statistics(
    reference: np.ndarray,
    current: np.ndarray,
    *,
    numeric_floor: float,
) -> np.ndarray:
    dimension = reference.shape[1]
    result = np.zeros((dimension, len(_STATISTIC_NAMES)), dtype=np.float64)
    if np.all(np.isfinite(reference)) and np.all(np.isfinite(current)):
        left_median = np.median(reference, axis=0)
        right_median = np.median(current, axis=0)
        left_quartiles = np.quantile(reference, [0.25, 0.75], axis=0)
        right_quartiles = np.quantile(current, [0.25, 0.75], axis=0)
        left_iqr = left_quartiles[1] - left_quartiles[0]
        right_iqr = right_quartiles[1] - right_quartiles[0]
        left_mad = np.median(np.abs(reference - left_median), axis=0)
        right_mad = np.median(np.abs(current - right_median), axis=0)
        scale = np.maximum.reduce(
            (
                left_iqr / 1.349,
                1.4826 * left_mad,
                np.full(dimension, numeric_floor, dtype=np.float64),
            )
        )
        result[:, 1] = np.abs(right_median - left_median) / scale
        result[:, 2] = np.maximum(
            np.abs(np.log((right_iqr + numeric_floor) / (left_iqr + numeric_floor))),
            np.abs(np.log((right_mad + numeric_floor) / (left_mad + numeric_floor))),
        )
        if len(reference) == len(current):
            result[:, 3] = np.mean(
                np.abs(np.sort(reference, axis=0) - np.sort(current, axis=0)),
                axis=0,
            ) / scale
        else:
            for feature_index in range(dimension):
                wasserstein, _ = _one_dimensional_distances(
                    reference[:, feature_index], current[:, feature_index]
                )
                result[feature_index, 3] = wasserstein / scale[feature_index]
        combined = np.concatenate((reference, current), axis=0)
        order = np.argsort(combined, axis=0, kind="stable")
        left_labels = np.zeros_like(combined, dtype=np.float64)
        left_labels[: len(reference)] = 1.0
        ordered_left = np.take_along_axis(left_labels, order, axis=0)
        left_cdf = np.cumsum(ordered_left, axis=0) / len(reference)
        right_cdf = np.cumsum(1.0 - ordered_left, axis=0) / len(current)
        result[:, 4] = np.max(np.abs(left_cdf - right_cdf), axis=0)
        return result
    for feature_index in range(dimension):
        left_all = reference[:, feature_index]
        right_all = current[:, feature_index]
        left = left_all[np.isfinite(left_all)]
        right = right_all[np.isfinite(right_all)]
        result[feature_index, 0] = abs(
            float(np.mean(~np.isfinite(right_all))) - float(np.mean(~np.isfinite(left_all)))
        )
        if not len(left) or not len(right):
            continue
        left_median = float(np.median(left))
        right_median = float(np.median(right))
        left_quartiles = np.quantile(left, [0.25, 0.75])
        right_quartiles = np.quantile(right, [0.25, 0.75])
        left_iqr = float(left_quartiles[1] - left_quartiles[0])
        right_iqr = float(right_quartiles[1] - right_quartiles[0])
        left_mad = float(np.median(np.abs(left - left_median)))
        right_mad = float(np.median(np.abs(right - right_median)))
        scale = max(left_iqr / 1.349, 1.4826 * left_mad, numeric_floor)
        result[feature_index, 1] = abs(right_median - left_median) / scale
        result[feature_index, 2] = max(
            abs(math.log((right_iqr + numeric_floor) / (left_iqr + numeric_floor))),
            abs(math.log((right_mad + numeric_floor) / (left_mad + numeric_floor))),
        )
        wasserstein, ks = _one_dimensional_distances(left, right)
        result[feature_index, 3] = wasserstein / scale
        result[feature_index, 4] = ks
    return result


def _permutation_masks(
    reference_count: int,
    current_count: int,
    block_ids: np.ndarray | None,
    *,
    permutations: int,
    random_seed: int,
) -> tuple[np.ndarray | None, str | None]:
    total = reference_count + current_count
    if block_ids is None:
        return None, "exchangeability_not_declared"
    blocks = np.asarray(block_ids)
    if blocks.ndim != 1 or len(blocks) != total:
        return None, "block_ids_shape_invalid"
    units, inverse = np.unique(blocks, return_inverse=True)
    if len(units) < 4:
        return None, "insufficient_exchangeable_blocks"
    original_reference = np.arange(total) < reference_count
    reference_units: list[int] = []
    for unit_index in range(len(units)):
        membership = original_reference[inverse == unit_index]
        if np.any(membership) and not np.all(membership):
            return None, "blocks_cross_window_boundary"
        if np.all(membership):
            reference_units.append(unit_index)
    if not reference_units or len(reference_units) == len(units):
        return None, "blocks_do_not_define_two_windows"
    rng = np.random.default_rng(random_seed)
    masks = np.empty((permutations, total), dtype=bool)
    for index in range(permutations):
        selected = rng.choice(len(units), size=len(reference_units), replace=False)
        masks[index] = np.isin(inverse, selected)
    return masks, None


def _total_variation(left: np.ndarray, right: np.ndarray) -> tuple[float, int]:
    categories = np.unique(np.concatenate((left, right)))
    if not len(categories):
        return 0.0, 0
    left_probabilities = np.asarray([np.mean(left == value) for value in categories])
    right_probabilities = np.asarray([np.mean(right == value) for value in categories])
    return float(0.5 * np.sum(np.abs(left_probabilities - right_probabilities))), len(categories)


def _group_drift_evidence(
    reference_group_ids: np.ndarray | None,
    current_group_ids: np.ndarray | None,
    *,
    reference_count: int,
    current_count: int,
    masks: np.ndarray,
    alpha: float,
    effect_threshold: float,
) -> GroupDriftEvidence:
    if reference_group_ids is None and current_group_ids is None:
        return GroupDriftEvidence(False, 0.0, 1.0, False, 0, "group_identity_unavailable")
    if reference_group_ids is None or current_group_ids is None:
        return GroupDriftEvidence(False, 0.0, 1.0, False, 0, "group_identity_incomplete")
    left = np.asarray(reference_group_ids)
    right = np.asarray(current_group_ids)
    if left.ndim != 1 or right.ndim != 1 or len(left) != reference_count or len(right) != current_count:
        return GroupDriftEvidence(False, 0.0, 1.0, False, 0, "group_identity_shape_invalid")
    combined = np.concatenate((left, right))
    observed, category_count = _total_variation(left, right)
    null = np.asarray(
        [_total_variation(combined[mask], combined[~mask])[0] for mask in masks],
        dtype=np.float64,
    )
    empirical = float((1.0 + np.sum(null >= observed)) / (len(masks) + 1.0))
    return GroupDriftEvidence(
        True,
        observed,
        empirical,
        bool(empirical <= alpha and observed >= effect_threshold),
        category_count,
        None,
    )


def _time_hint_evidence(
    reference_time_hints: np.ndarray | None,
    current_time_hints: np.ndarray | None,
    *,
    reference_count: int,
    current_count: int,
) -> TimeHintEvidence:
    if reference_time_hints is None and current_time_hints is None:
        return TimeHintEvidence(False, False, "time_hints_unavailable")
    if reference_time_hints is None or current_time_hints is None:
        return TimeHintEvidence(False, False, "time_hints_incomplete")
    left = np.asarray(reference_time_hints, dtype=np.float64)
    right = np.asarray(current_time_hints, dtype=np.float64)
    if left.ndim != 1 or right.ndim != 1 or len(left) != reference_count or len(right) != current_count:
        return TimeHintEvidence(False, False, "time_hints_shape_invalid")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        return TimeHintEvidence(False, False, "time_hints_non_finite")
    monotonic = bool(np.all(np.diff(left) >= 0.0) and np.all(np.diff(right) >= 0.0))
    return TimeHintEvidence(True, monotonic, None if monotonic else "time_hints_non_monotonic")


def _scope_sha256(values: np.ndarray) -> str:
    array = np.asarray(values, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(str(array.shape).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _empty_report(
    *,
    status: DriftStatus,
    config: MonitorConfig,
    reference: np.ndarray,
    current: np.ndarray,
    alpha_run: float,
    alpha_window: float,
    alpha_spent: float,
    reference_epoch: int,
    history_window_count: int,
    limitation: str,
) -> DriftReport:
    payload = {
        "reference": _scope_sha256(reference),
        "current": _scope_sha256(current),
        "status": status.value,
        "limitation": limitation,
    }
    report_id = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DriftReport(
        report_id=report_id,
        status=status,
        calibration_method=config.calibration_method,
        reference_scope_sha256=payload["reference"],
        current_scope_sha256=payload["current"],
        sample_count=len(current),
        history_window_count=history_window_count,
        global_score=0.0,
        alpha_run=alpha_run,
        alpha_window=alpha_window,
        alpha_spent=alpha_spent,
        permutation_count=config.permutations,
        minimum_empirical_p=1.0 / (config.permutations + 1.0),
        reference_epoch=reference_epoch,
        features=(),
        limitations=(limitation,),
    )


class DriftMonitor:
    def __init__(self, config: MonitorConfig | None = None) -> None:
        self.config = config or MonitorConfig()

    def compare(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        *,
        alpha_run: float,
        alpha_window: float,
        alpha_spent: float,
        reference_epoch: int,
        history_window_count: int,
        block_ids: np.ndarray | None,
        reference_group_ids: np.ndarray | None = None,
        current_group_ids: np.ndarray | None = None,
        reference_time_hints: np.ndarray | None = None,
        current_time_hints: np.ndarray | None = None,
    ) -> DriftReport:
        left = np.asarray(reference, dtype=np.float64)
        right = np.asarray(current, dtype=np.float64)
        if left.ndim != 2 or right.ndim != 2 or left.shape[1] != right.shape[1]:
            raise ValueError("reference and current must be two-dimensional with equal features")
        if not len(left) or not len(right):
            raise ValueError("reference and current must be nonempty")
        if not 0.0 < alpha_window <= alpha_run <= 1.0:
            raise ValueError("alpha values must satisfy 0 < alpha_window <= alpha_run <= 1")
        if not 0.0 <= alpha_spent <= alpha_run + 1e-12:
            raise ValueError("alpha spent is outside the run budget")
        if self.config.calibration_method == "by_fallback":
            hypothesis_count = left.shape[1]
            harmonic = float(
                np.sum(1.0 / np.arange(1, hypothesis_count + 1, dtype=np.float64))
            )
            required = math.ceil(hypothesis_count * harmonic / alpha_window) - 1
            resolution_limitation = "by_rank_one_empirical_p_resolution_insufficient"
        else:
            required = math.ceil(10.0 / alpha_window) - 1
            resolution_limitation = "empirical_p_resolution_exceeds_alpha_budget"
        if self.config.permutations < required:
            return _empty_report(
                status=DriftStatus.INSUFFICIENT_CALIBRATION,
                config=self.config,
                reference=left,
                current=right,
                alpha_run=alpha_run,
                alpha_window=alpha_window,
                alpha_spent=alpha_spent,
                reference_epoch=reference_epoch,
                history_window_count=history_window_count,
                limitation=resolution_limitation,
            )
        combined = np.concatenate((left, right), axis=0)
        masks, block_error = _permutation_masks(
            len(left),
            len(right),
            block_ids,
            permutations=self.config.permutations,
            random_seed=self.config.random_seed,
        )
        if masks is None:
            return _empty_report(
                status=DriftStatus.INSUFFICIENT_CALIBRATION,
                config=self.config,
                reference=left,
                current=right,
                alpha_run=alpha_run,
                alpha_window=alpha_window,
                alpha_spent=alpha_spent,
                reference_epoch=reference_epoch,
                history_window_count=history_window_count,
                limitation=str(block_error),
            )

        group_evidence = _group_drift_evidence(
            reference_group_ids,
            current_group_ids,
            reference_count=len(left),
            current_count=len(right),
            masks=masks,
            alpha=alpha_window,
            effect_threshold=self.config.group_effect_threshold,
        )
        time_evidence = _time_hint_evidence(
            reference_time_hints,
            current_time_hints,
            reference_count=len(left),
            current_count=len(right),
        )

        observed = _feature_statistics(left, right, numeric_floor=self.config.numeric_floor)
        unique_masks, permutation_inverse = np.unique(
            masks, axis=0, return_inverse=True
        )
        unique_statistics = np.empty(
            (len(unique_masks), left.shape[1], len(_STATISTIC_NAMES)),
            dtype=np.float64,
        )
        for index, mask in enumerate(unique_masks):
            unique_statistics[index] = _feature_statistics(
                combined[mask],
                combined[~mask],
                numeric_floor=self.config.numeric_floor,
            )
        null_statistics = unique_statistics[permutation_inverse]
        center = np.median(null_statistics, axis=0)
        quartiles = np.quantile(null_statistics, [0.25, 0.75], axis=0)
        mad = np.median(np.abs(null_statistics - center), axis=0)
        null_scale = np.maximum.reduce(
            (
                (quartiles[1] - quartiles[0]) / 1.349,
                1.4826 * mad,
                np.full_like(center, self.config.numeric_floor),
            )
        )
        observed_standardized = np.maximum((observed - center) / null_scale, 0.0)
        null_standardized = np.maximum((null_statistics - center) / null_scale, 0.0)
        observed_omnibus = np.max(observed_standardized, axis=1)
        null_omnibus = np.max(null_standardized, axis=2)
        empirical = (1.0 + np.sum(null_omnibus >= observed_omnibus[None, :], axis=0)) / (
            self.config.permutations + 1.0
        )
        statistic_empirical = (
            1.0 + np.sum(null_statistics >= observed[None, :, :], axis=0)
        ) / (self.config.permutations + 1.0)
        if self.config.calibration_method == "block_permutation_maxT":
            null_global = np.max(null_omnibus, axis=1)
            adjusted = (1.0 + np.sum(null_global[:, None] >= observed_omnibus[None, :], axis=0)) / (
                self.config.permutations + 1.0
            )
        else:
            adjusted = adjust_pvalues_by(empirical)
        selected = apply_effect_gate(
            adjusted_p=adjusted,
            omnibus_score=observed_omnibus,
            alpha=alpha_window,
            effect_threshold=self.config.effect_threshold,
        )
        excess = np.where(selected, np.maximum(observed_omnibus - self.config.effect_threshold, 0.0), 0.0)
        contributions = excess / np.sum(excess) if np.sum(excess) > 0.0 else np.zeros_like(excess)
        dominant = np.argmax(observed_standardized, axis=1)
        within_feature_totals = np.sum(observed_standardized, axis=1)
        features = tuple(
            FeatureDrift(
                feature_index=index,
                dominant_statistic=_STATISTIC_NAMES[int(dominant[index])],
                missing_delta=float(observed[index, 0]),
                location_shift=float(observed[index, 1]),
                scale_shift=float(observed[index, 2]),
                wasserstein_shift=float(observed[index, 3]),
                ks_distance=float(observed[index, 4]),
                omnibus_score=float(observed_omnibus[index]),
                empirical_p=float(empirical[index]),
                adjusted_p=float(adjusted[index]),
                selected=bool(selected[index]),
                contribution=float(contributions[index]),
                statistic_contributions=tuple(
                    StatisticContribution(
                        name=name,
                        raw_value=float(observed[index, statistic_index]),
                        standardized_score=float(
                            observed_standardized[index, statistic_index]
                        ),
                        empirical_p=float(statistic_empirical[index, statistic_index]),
                        contribution=float(
                            observed_standardized[index, statistic_index]
                            / within_feature_totals[index]
                            if within_feature_totals[index] > 0.0
                            else 0.0
                        ),
                    )
                    for statistic_index, name in enumerate(_STATISTIC_NAMES)
                ),
            )
            for index in range(left.shape[1])
        )
        reference_hash = _scope_sha256(left)
        current_hash = _scope_sha256(right)
        report_payload = {
            "reference": reference_hash,
            "current": current_hash,
            "method": self.config.calibration_method,
            "features": [item.as_dict() for item in features],
            "group_evidence": group_evidence.as_dict(),
            "time_evidence": time_evidence.as_dict(),
        }
        report_id = "sha256:" + hashlib.sha256(
            json.dumps(
                report_payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        limitations = tuple(
            item
            for item in (group_evidence.limitation, time_evidence.limitation)
            if item is not None
        )
        return DriftReport(
            report_id=report_id,
            status=(
                DriftStatus.WARNING
                if np.any(selected) or group_evidence.selected
                else DriftStatus.STABLE
            ),
            calibration_method=self.config.calibration_method,
            reference_scope_sha256=reference_hash,
            current_scope_sha256=current_hash,
            sample_count=len(right),
            history_window_count=history_window_count,
            global_score=float(np.max(observed_omnibus)),
            alpha_run=alpha_run,
            alpha_window=alpha_window,
            alpha_spent=alpha_spent,
            permutation_count=self.config.permutations,
            minimum_empirical_p=1.0 / (self.config.permutations + 1.0),
            reference_epoch=reference_epoch,
            features=features,
            limitations=limitations,
            group_evidence=group_evidence,
            time_evidence=time_evidence,
        )
