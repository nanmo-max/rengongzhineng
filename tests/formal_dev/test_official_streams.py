from __future__ import annotations

import numpy as np

from brace_msi.data.types import BatchData, TaskStream
from brace_msi.official_streams import (
    align_bearing_stream,
    align_engine_stream,
    align_gas_stream,
    rebatch_contiguous,
    rebatch_grouped,
    rebatch_progress,
    select_bearing_platform_features,
)


def _batch(batch_id: str, start: int, count: int, group: str = "") -> BatchData:
    values = np.arange(start, start + count, dtype=np.float64)
    return BatchData(
        batch_id=batch_id,
        X=np.column_stack([values, values + 1.0]),
        y=values,
        sample_ids=tuple(f"{batch_id}:{index}" for index in range(count)),
        group_ids=tuple(group for _ in range(count)) if group else (),
    )


def test_contiguous_rebatch_preserves_order_and_identity_across_ten_rounds() -> None:
    batches = (_batch("b1", 0, 13), _batch("b2", 13, 17))

    result = rebatch_contiguous(batches, prefix="gas-opt", count=10)

    assert len(result) == 10
    assert tuple(item for batch in result for item in batch.sample_ids) == tuple(
        item for batch in batches for item in batch.sample_ids
    )
    assert all(len(batch.y) == 3 for batch in result)


def test_grouped_rebatch_keeps_each_device_in_exactly_one_round() -> None:
    batches = tuple(_batch(f"engine-{group}", group * 4, 4, str(group)) for group in range(20))

    result = rebatch_grouped(batches, prefix="engine-opt", count=10)

    assert len(result) == 10
    groups = [set(batch.group_ids) for batch in result]
    assert all(len(value) == 2 for value in groups)
    assert len(set.union(*groups)) == 20
    assert sum(len(value) for value in groups) == 20


def test_progress_rebatch_uses_all_three_trajectories_in_each_round() -> None:
    batches = (
        _batch("bearing-a", 0, 20, "11"),
        _batch("bearing-b", 20, 30, "24"),
        _batch("bearing-c", 50, 40, "34"),
    )

    result = rebatch_progress(batches, prefix="bearing-opt", count=10)

    assert len(result) == 10
    assert all(set(batch.group_ids) == {"11", "24", "34"} for batch in result)
    assert {item for batch in result for item in batch.sample_ids} == {
        item for batch in batches for item in batch.sample_ids
    }


def test_bearing_feature_selection_matches_published_parameter_count_input() -> None:
    X = np.arange(5 * 43, dtype=np.float64).reshape(5, 43)

    selected = select_bearing_platform_features(X)

    assert selected.shape == (5, 25)
    assert np.array_equal(selected[:, -3:], X[:, -3:])


def _stream(kind: str, feature_count: int, development: tuple[BatchData, ...]) -> TaskStream:
    initial = BatchData(
        "initial",
        np.ones((60, feature_count), dtype=np.float64),
        (np.tile(np.arange(1, 7), 10) if kind == "classification" else np.arange(60, dtype=float)),
        tuple(f"initial:{i}" for i in range(60)),
        (tuple(str(i // 6) for i in range(60)) if kind == "regression" else ()),
    )
    return TaskStream("source", kind, initial, development, (), {"sealed_loaded": False})


def test_alignment_assigns_official_metrics_and_exactly_ten_rounds() -> None:
    gas_development = tuple(
        BatchData(
            f"gas-{index}",
            np.ones((30, 128)),
            np.tile(np.arange(1, 7), 5),
            tuple(f"gas-{index}:{row}" for row in range(30)),
        )
        for index in range(4)
    )
    engine_development = tuple(
        BatchData(
            f"engine-{group}",
            np.ones((8, 24)),
            np.arange(8, dtype=float),
            tuple(f"engine-{group}:{row}" for row in range(8)),
            tuple(str(group) for _ in range(8)),
        )
        for group in range(20)
    )
    bearing_development = tuple(
        BatchData(
            f"bearing-{group}",
            np.ones((30, 43)),
            np.arange(29, -1, -1, dtype=float),
            tuple(f"bearing-{group}:{row}" for row in range(30)),
            tuple(str(group) for _ in range(30)),
        )
        for group in (11, 24, 34)
    )

    gas = align_gas_stream(_stream("classification", 128, gas_development))
    engine = align_engine_stream(_stream("regression", 24, engine_development))
    bearing = align_bearing_stream(_stream("regression", 43, bearing_development))

    assert [len(stream.development) for stream in (gas, bearing, engine)] == [10, 10, 10]
    assert [stream.metadata["primary_metric"] for stream in (gas, bearing, engine)] == [
        "macro_f1",
        "rmse",
        "rmse_nasa",
    ]
    assert [stream.metadata["published_parameter_count"] for stream in (gas, bearing, engine)] == [
        4326,
        865,
        833,
    ]
    assert bearing.initial.X.shape[1] == 25
    assert all(stream.sealed == () for stream in (gas, bearing, engine))

