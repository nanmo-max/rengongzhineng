from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brace_msi.data.xjtu import (
    FROZEN_BEARING_SPLIT,
    extract_bearing_cache,
    extract_signal_features,
    load_xjtu_stream,
    numeric_csv_files,
    XjtuFormatError,
)


def _write_signal(path: Path, offset: float) -> None:
    time = np.arange(64, dtype=float) / 64.0
    horizontal = np.sin(2.0 * np.pi * 4.0 * time) + offset
    vertical = np.cos(2.0 * np.pi * 7.0 * time) - offset
    matrix = np.column_stack([horizontal, vertical])
    np.savetxt(
        path,
        matrix,
        delimiter=",",
        header="Horizontal_vibration_signals,Vertical_vibration_signals",
        comments="",
    )


def test_numeric_csv_files_uses_numeric_order(tmp_path: Path) -> None:
    for name in ("3.csv", "2.csv", "1.csv"):
        _write_signal(tmp_path / name, 0.0)

    assert [path.name for path in numeric_csv_files(tmp_path)] == [
        "1.csv",
        "2.csv",
        "3.csv",
    ]


def test_numeric_csv_files_rejects_missing_minutes(tmp_path: Path) -> None:
    for name in ("1.csv", "3.csv"):
        _write_signal(tmp_path / name, 0.0)

    with pytest.raises(XjtuFormatError, match="contiguous"):
        numeric_csv_files(tmp_path)


def test_signal_features_are_finite_and_fixed_width() -> None:
    time = np.arange(128, dtype=float) / 128.0
    matrix = np.column_stack(
        [np.sin(2 * np.pi * 8 * time), np.cos(2 * np.pi * 12 * time)]
    )

    features, names = extract_signal_features(matrix, sample_rate_hz=128.0)

    assert features.shape == (len(names),)
    assert len(names) >= 30
    assert np.isfinite(features).all()
    assert all("remaining" not in name and "total" not in name for name in names)


def test_bearing_cache_uses_only_elapsed_time_as_sequence_feature(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Bearing1_1"
    source.mkdir()
    for index in range(1, 5):
        _write_signal(source / f"{index}.csv", float(index))
    cache_path = tmp_path / "bearing.npz"

    summary = extract_bearing_cache(
        source,
        cache_path,
        condition="35Hz12kN",
        bearing_id="Bearing1_1",
        speed_rpm=2100.0,
        load_kn=12.0,
        sample_rate_hz=64.0,
    )

    with np.load(cache_path, allow_pickle=False) as cache:
        assert cache["y"].tolist() == [3.0, 2.0, 1.0, 0.0]
        assert cache["elapsed_minutes"].tolist() == [0.0, 1.0, 2.0, 3.0]
        names = cache["feature_names"].tolist()
        assert "elapsed_minutes" in names
        assert all("remaining" not in name and "total" not in name for name in names)
        assert cache["X"].shape[0] == 4
    assert summary.sample_count == 4


def test_frozen_split_is_disjoint_and_stream_loads_grouped_caches(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    all_bearings = {
        bearing
        for bearings in FROZEN_BEARING_SPLIT.values()
        for bearing in bearings
    }
    assert len(all_bearings) == 15
    assert sum(len(value) for value in FROZEN_BEARING_SPLIT.values()) == 15

    for ordinal, bearing_id in enumerate(sorted(all_bearings)):
        X = np.asarray([[ordinal, 0.0], [ordinal, 1.0]], dtype=np.float64)
        np.savez_compressed(
            cache_root / f"{bearing_id}.npz",
            X=X,
            y=np.asarray([1.0, 0.0]),
            sample_ids=np.asarray([f"{bearing_id}:1", f"{bearing_id}:2"]),
            elapsed_minutes=np.asarray([0.0, 1.0]),
            feature_names=np.asarray(["signal", "elapsed_minutes"]),
            bearing_id=np.asarray(bearing_id),
        )

    stream = load_xjtu_stream(cache_root, include_sealed=False)

    assert stream.task_kind == "regression"
    assert {batch.batch_id for batch in stream.development} == {
        "xjtu-dev-Bearing1_4",
        "xjtu-dev-Bearing2_4",
        "xjtu-dev-Bearing3_4",
    }
    assert stream.sealed == ()
    assert stream.all_sample_ids_are_disjoint()
    assert stream.metadata["local_development_only"] is True

