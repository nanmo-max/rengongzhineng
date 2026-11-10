"""Leakage-bounded local adapter for the XJTU-SY run-to-failure dataset."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

import numpy as np
from numpy.typing import NDArray

from .types import BatchData, TaskStream

FROZEN_BEARING_SPLIT: dict[str, tuple[str, ...]] = {
    "initial": (
        "Bearing1_1", "Bearing1_2", "Bearing1_3",
        "Bearing2_1", "Bearing2_2", "Bearing2_3",
        "Bearing3_1", "Bearing3_2", "Bearing3_3",
    ),
    "development": ("Bearing1_4", "Bearing2_4", "Bearing3_4"),
    "sealed": ("Bearing1_5", "Bearing2_5", "Bearing3_5"),
}

_BEARING_RE = re.compile(r"^Bearing([123])_([1-5])$")
_EPSILON = np.finfo(np.float64).eps


class XjtuFormatError(ValueError):
    """Raised when the derived XJTU-SY layout or a signal file is malformed."""


@dataclass(frozen=True)
class BearingCacheSummary:
    bearing_id: str
    sample_count: int
    feature_count: int
    output_path: str


def numeric_csv_files(directory: Path) -> tuple[Path, ...]:
    """Return CSV files by integer stem, independent of filesystem order."""

    directory = Path(directory)
    indexed: list[tuple[int, Path]] = []
    for path in directory.glob("*.csv"):
        try:
            number = int(path.stem)
        except ValueError as exc:
            raise XjtuFormatError(f"non-numeric CSV name: {path.name}") from exc
        if number < 1:
            raise XjtuFormatError(f"CSV sequence must be positive: {path.name}")
        indexed.append((number, path))
    if not indexed:
        raise XjtuFormatError(f"no CSV files found in {directory}")
    numbers = [number for number, _ in indexed]
    if len(numbers) != len(set(numbers)):
        raise XjtuFormatError(f"duplicate CSV sequence in {directory}")
    ordered = sorted(indexed, key=lambda item: item[0])
    ordered_numbers = [number for number, _ in ordered]
    if ordered_numbers != list(range(1, len(ordered_numbers) + 1)):
        raise XjtuFormatError(f"CSV sequence must be contiguous from 1 in {directory}")
    return tuple(path for _, path in ordered)


def _channel_features(
    values: NDArray[np.float64], sample_rate_hz: float
) -> tuple[list[float], tuple[str, ...]]:
    centered = values - float(np.mean(values))
    std = float(np.std(values))
    rms = float(np.sqrt(np.mean(values**2)))
    absolute = np.abs(values)
    abs_mean = float(np.mean(absolute))
    peak = float(np.max(absolute))
    root_abs_mean = float(np.mean(np.sqrt(absolute))) ** 2
    normalized = centered / max(std, _EPSILON)

    spectrum = np.abs(np.fft.rfft(centered)) ** 2
    frequencies = np.fft.rfftfreq(len(values), d=1.0 / sample_rate_hz)
    total_power = float(np.sum(spectrum))
    probabilities = spectrum / max(total_power, _EPSILON)
    centroid = float(np.sum(frequencies * probabilities))
    bandwidth = float(
        np.sqrt(np.sum(((frequencies - centroid) ** 2) * probabilities))
    )
    positive = probabilities[probabilities > 0]
    entropy = float(-np.sum(positive * np.log(positive)) / np.log(len(probabilities)))
    dominant = float(frequencies[int(np.argmax(spectrum))])
    nyquist = sample_rate_hz / 2.0
    band_edges = (0.0, 0.1 * nyquist, 0.25 * nyquist, 0.5 * nyquist, nyquist + 1.0)
    band_ratios = []
    for lower, upper in zip(band_edges[:-1], band_edges[1:]):
        mask = (frequencies >= lower) & (frequencies < upper)
        band_ratios.append(float(np.sum(spectrum[mask]) / max(total_power, _EPSILON)))

    features = [
        float(np.mean(values)), std, rms, abs_mean, peak,
        float(np.ptp(values)), float(np.mean(normalized**3)),
        float(np.mean(normalized**4)), peak / max(rms, _EPSILON),
        peak / max(abs_mean, _EPSILON), rms / max(abs_mean, _EPSILON),
        peak / max(root_abs_mean, _EPSILON), centroid, bandwidth, entropy,
        dominant, *band_ratios,
    ]
    names = (
        "mean", "std", "rms", "abs_mean", "max_abs", "peak_to_peak",
        "skewness", "kurtosis", "crest_factor", "impulse_factor",
        "shape_factor", "clearance_factor", "spectral_centroid_hz",
        "spectral_bandwidth_hz", "spectral_entropy", "dominant_frequency_hz",
        "band_power_00_10", "band_power_10_25", "band_power_25_50",
        "band_power_50_100",
    )
    return features, names


def extract_signal_features(
    matrix: NDArray[np.float64], *, sample_rate_hz: float = 25_600.0
) -> tuple[NDArray[np.float64], tuple[str, ...]]:
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != 2 or matrix.shape[0] < 8:
        raise XjtuFormatError("signal matrix must contain at least 8 rows and 2 channels")
    if not np.isfinite(matrix).all() or sample_rate_hz <= 0:
        raise XjtuFormatError("signal data and sample rate must be finite and positive")
    values: list[float] = []
    names: list[str] = []
    for prefix, channel in zip(("horizontal", "vertical"), matrix.T):
        channel_values, channel_names = _channel_features(channel, sample_rate_hz)
        values.extend(channel_values)
        names.extend(f"{prefix}_{name}" for name in channel_names)
    result = np.asarray(values, dtype=np.float64)
    if not np.isfinite(result).all():
        raise XjtuFormatError("feature extraction produced non-finite values")
    return result, tuple(names)


def _opaque_id(bearing_id: str, sequence: int) -> str:
    return sha256(f"xjtu-sy|{bearing_id}|{sequence}".encode()).hexdigest()[:24]


def _group_id(bearing_id: str) -> str:
    match = _BEARING_RE.match(bearing_id)
    if not match:
        raise XjtuFormatError(f"invalid bearing ID: {bearing_id}")
    return f"{match.group(1)}{match.group(2)}"


def extract_bearing_cache(
    source_dir: Path,
    output_path: Path,
    *,
    condition: str,
    bearing_id: str,
    speed_rpm: float,
    load_kn: float,
    sample_rate_hz: float = 25_600.0,
) -> BearingCacheSummary:
    """Extract one independent feature row per CSV and save it atomically."""

    _group_id(bearing_id)
    files = numeric_csv_files(source_dir)
    rows: list[NDArray[np.float64]] = []
    sample_ids: list[str] = []
    feature_names: tuple[str, ...] | None = None
    for elapsed, path in enumerate(files):
        try:
            matrix = np.loadtxt(path, delimiter=",", skiprows=1, dtype=np.float64)
        except (OSError, ValueError) as exc:
            raise XjtuFormatError(f"cannot parse signal CSV: {path}") from exc
        signal, names = extract_signal_features(matrix, sample_rate_hz=sample_rate_hz)
        if feature_names is None:
            feature_names = (*names, "speed_rpm", "load_kn", "elapsed_minutes")
        rows.append(
            np.concatenate(
                [signal, np.asarray([speed_rpm, load_kn, float(elapsed)])]
            )
        )
        sample_ids.append(_opaque_id(bearing_id, elapsed + 1))

    count = len(rows)
    y = np.arange(count - 1, -1, -1, dtype=np.float64)
    elapsed_minutes = np.arange(count, dtype=np.float64)
    X = np.asarray(rows, dtype=np.float64)
    if feature_names is None or not np.isfinite(X).all():
        raise XjtuFormatError(f"invalid extracted features for {bearing_id}")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp.npz")
    np.savez_compressed(
        temporary,
        X=X,
        y=y,
        sample_ids=np.asarray(sample_ids),
        elapsed_minutes=elapsed_minutes,
        feature_names=np.asarray(feature_names),
        bearing_id=np.asarray(bearing_id),
        condition=np.asarray(condition),
        speed_rpm=np.asarray(speed_rpm),
        load_kn=np.asarray(load_kn),
        source_file_count=np.asarray(count),
    )
    temporary.replace(output_path)
    return BearingCacheSummary(bearing_id, count, X.shape[1], str(output_path))


def _load_cache(path: Path, *, batch_id: str) -> BatchData:
    try:
        with np.load(path, allow_pickle=False) as cache:
            X = np.asarray(cache["X"], dtype=np.float64)
            y = np.asarray(cache["y"], dtype=np.float64)
            sample_ids = tuple(str(value) for value in cache["sample_ids"].tolist())
            bearing_id = str(cache["bearing_id"].item())
    except (OSError, KeyError, ValueError) as exc:
        raise XjtuFormatError(f"invalid bearing cache: {path}") from exc
    return BatchData(
        batch_id=batch_id,
        X=X,
        y=y,
        sample_ids=sample_ids,
        group_ids=tuple(_group_id(bearing_id) for _ in y),
    )


def load_xjtu_stream(cache_root: Path, *, include_sealed: bool = False) -> TaskStream:
    cache_root = Path(cache_root)
    initial_parts = [
        _load_cache(cache_root / f"{bearing}.npz", batch_id=f"xjtu-initial-{bearing}")
        for bearing in FROZEN_BEARING_SPLIT["initial"]
    ]
    feature_counts = {part.X.shape[1] for part in initial_parts}
    if len(feature_counts) != 1:
        raise XjtuFormatError("bearing caches have inconsistent feature widths")
    initial = BatchData(
        batch_id="xjtu-initial",
        X=np.concatenate([part.X for part in initial_parts]),
        y=np.concatenate([part.y for part in initial_parts]),
        sample_ids=tuple(value for part in initial_parts for value in part.sample_ids),
        group_ids=tuple(value for part in initial_parts for value in part.group_ids),
    )
    development = tuple(
        _load_cache(cache_root / f"{bearing}.npz", batch_id=f"xjtu-dev-{bearing}")
        for bearing in FROZEN_BEARING_SPLIT["development"]
    )
    sealed = tuple(
        _load_cache(cache_root / f"{bearing}.npz", batch_id=f"xjtu-sealed-{bearing}")
        for bearing in FROZEN_BEARING_SPLIT["sealed"]
    ) if include_sealed else ()
    stream = TaskStream(
        task_id="xjtu-sy-rul-local-development",
        task_kind="regression",
        initial=initial,
        development=development,
        sealed=sealed,
        metadata={
            "local_development_only": True,
            "target": "remaining sampling minutes within each bearing trajectory",
            "split_rule": "9 initial / 3 development / 3 sealed bearings",
            "sealed_loaded": include_sealed,
            "feature_count": next(iter(feature_counts)),
        },
    )
    if not stream.all_sample_ids_are_disjoint():
        raise XjtuFormatError("sample identity overlap across frozen XJTU splits")
    return stream

