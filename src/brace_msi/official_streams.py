"""Leakage-bounded ten-round streams aligned with the latest platform rules."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .data.cmapss import load_cmapss_fd001_stream
from .data.gas import load_gas_stream
from .data.types import BatchData, TaskStream
from .data.xjtu import load_xjtu_stream


def _take(batch: BatchData, indices: NDArray[np.int64], *, batch_id: str) -> BatchData:
    return BatchData(
        batch_id=batch_id,
        X=batch.X[indices],
        y=batch.y[indices],
        sample_ids=tuple(batch.sample_ids[int(index)] for index in indices),
        group_ids=(
            tuple(batch.group_ids[int(index)] for index in indices)
            if batch.group_ids
            else ()
        ),
    )


def _combine(parts: list[BatchData], *, batch_id: str) -> BatchData:
    if not parts:
        raise ValueError("cannot combine an empty batch list")
    has_groups = all(part.group_ids for part in parts)
    return BatchData(
        batch_id=batch_id,
        X=np.concatenate([part.X for part in parts]),
        y=np.concatenate([part.y for part in parts]),
        sample_ids=tuple(value for part in parts for value in part.sample_ids),
        group_ids=(
            tuple(value for part in parts for value in part.group_ids)
            if has_groups
            else ()
        ),
    )


def rebatch_contiguous(
    batches: tuple[BatchData, ...], *, prefix: str, count: int = 10
) -> tuple[BatchData, ...]:
    combined = _combine(list(batches), batch_id=f"{prefix}-source")
    if len(combined.y) < count:
        raise ValueError("not enough samples for requested optimization rounds")
    chunks = np.array_split(np.arange(len(combined.y), dtype=np.int64), count)
    return tuple(
        _take(combined, chunk, batch_id=f"{prefix}-{index:02d}")
        for index, chunk in enumerate(chunks, start=1)
    )


def rebatch_grouped(
    batches: tuple[BatchData, ...], *, prefix: str, count: int = 10
) -> tuple[BatchData, ...]:
    combined = _combine(list(batches), batch_id=f"{prefix}-source")
    if not combined.group_ids:
        raise ValueError("grouped rebatching requires group identities")
    groups = sorted(set(combined.group_ids), key=int)
    if len(groups) < count:
        raise ValueError("not enough groups for requested optimization rounds")
    group_chunks = np.array_split(np.asarray(groups, dtype=object), count)
    result: list[BatchData] = []
    group_array = np.asarray(combined.group_ids, dtype=object)
    for index, group_chunk in enumerate(group_chunks, start=1):
        indices = np.flatnonzero(np.isin(group_array, group_chunk)).astype(np.int64)
        result.append(_take(combined, indices, batch_id=f"{prefix}-{index:02d}"))
    return tuple(result)


def rebatch_progress(
    batches: tuple[BatchData, ...], *, prefix: str, count: int = 10
) -> tuple[BatchData, ...]:
    if any(len(batch.y) < count for batch in batches):
        raise ValueError("every trajectory must cover all optimization rounds")
    per_trajectory = [
        np.array_split(np.arange(len(batch.y), dtype=np.int64), count)
        for batch in batches
    ]
    return tuple(
        _combine(
            [
                _take(batch, chunks[index], batch_id=f"{batch.batch_id}-stage")
                for batch, chunks in zip(batches, per_trajectory)
            ],
            batch_id=f"{prefix}-{index + 1:02d}",
        )
        for index in range(count)
    )


def select_bearing_platform_features(X: NDArray[np.float64]) -> NDArray[np.float64]:
    """Select 22 signal statistics plus speed, load and elapsed minute."""

    values = np.asarray(X, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 43:
        raise ValueError("XJTU local cache must contain exactly 43 features")
    indices = (*range(0, 11), *range(20, 31), 40, 41, 42)
    return values[:, indices]


def _with_features(batch: BatchData, X: NDArray[np.float64]) -> BatchData:
    return BatchData(
        batch_id=batch.batch_id,
        X=np.asarray(X, dtype=np.float64),
        y=batch.y,
        sample_ids=batch.sample_ids,
        group_ids=batch.group_ids,
    )


def _aligned_metadata(
    source: TaskStream, *, primary_metric: str, parameter_count: int
) -> dict[str, object]:
    return {
        **source.metadata,
        "official_rules_aligned": True,
        "official_checkpoint": False,
        "primary_metric": primary_metric,
        "published_parameter_count": parameter_count,
        "optimization_rounds": 10,
        "sealed_loaded": False,
    }


def align_gas_stream(source: TaskStream) -> TaskStream:
    """Map a public Gas development split to ten unsealed optimization rounds."""

    if source.task_kind != "classification" or source.initial.X.shape[1] != 128:
        raise ValueError("Gas alignment requires a 128-feature classification stream")
    if source.sealed:
        raise ValueError("Gas alignment refuses a stream with loaded sealed data")
    aligned = TaskStream(
        task_id="gas",
        task_kind="classification",
        initial=source.initial,
        development=rebatch_contiguous(
            source.development, prefix="gas-opt", count=10
        ),
        sealed=(),
        metadata=_aligned_metadata(
            source, primary_metric="macro_f1", parameter_count=4326
        ),
    )
    if not aligned.all_sample_ids_are_disjoint():
        raise ValueError("Gas alignment introduced overlapping sample identities")
    return aligned


def align_engine_stream(source: TaskStream) -> TaskStream:
    """Map FD001 development engines to ten grouped optimization rounds."""

    if source.task_kind != "regression" or source.initial.X.shape[1] != 24:
        raise ValueError("Engine alignment requires a 24-feature regression stream")
    if source.sealed:
        raise ValueError("Engine alignment refuses a stream with loaded sealed data")
    aligned = TaskStream(
        task_id="engine",
        task_kind="regression",
        initial=source.initial,
        development=rebatch_grouped(
            source.development, prefix="engine-opt", count=10
        ),
        sealed=(),
        metadata=_aligned_metadata(
            source, primary_metric="rmse_nasa", parameter_count=833
        ),
    )
    if not aligned.all_sample_ids_are_disjoint():
        raise ValueError("Engine alignment introduced overlapping sample identities")
    return aligned


def align_bearing_stream(source: TaskStream) -> TaskStream:
    """Map the XJTU feature cache to the published 25-input MLP topology."""

    if source.task_kind != "regression" or source.initial.X.shape[1] != 43:
        raise ValueError("Bearing alignment requires a 43-feature regression cache")
    if source.sealed:
        raise ValueError("Bearing alignment refuses a stream with loaded sealed data")
    initial = _with_features(
        source.initial, select_bearing_platform_features(source.initial.X)
    )
    development = tuple(
        _with_features(batch, select_bearing_platform_features(batch.X))
        for batch in source.development
    )
    aligned = TaskStream(
        task_id="bearing",
        task_kind="regression",
        initial=initial,
        development=rebatch_progress(
            development, prefix="bearing-opt", count=10
        ),
        sealed=(),
        metadata=_aligned_metadata(
            source, primary_metric="rmse", parameter_count=865
        ),
    )
    if not aligned.all_sample_ids_are_disjoint():
        raise ValueError("Bearing alignment introduced overlapping sample identities")
    return aligned


def build_official_development_streams(
    *, gas_root: str, cmapss_zip: str, xjtu_cache_root: str
) -> dict[str, TaskStream]:
    """Load only preregistered public development partitions; never load sealed data."""

    return {
        "gas": align_gas_stream(
            load_gas_stream(gas_root, include_sealed=False)
        ),
        "bearing": align_bearing_stream(
            load_xjtu_stream(xjtu_cache_root, include_sealed=False)
        ),
        "engine": align_engine_stream(
            load_cmapss_fd001_stream(cmapss_zip, include_sealed=False)
        ),
    }

