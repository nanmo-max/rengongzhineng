from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np


def _cmapss_row(engine: int, cycle: int) -> str:
    settings = [engine / 1000, cycle / 1000, 100.0]
    sensors = [engine + cycle + index / 100 for index in range(21)]
    values = [engine, cycle, *settings, *sensors]
    return " ".join(str(value) for value in values) + "\n"


def _write_cmapss_zip(path: Path, *, engines: int = 10, cycles: int = 3) -> Path:
    rows = "".join(
        _cmapss_row(engine, cycle)
        for engine in range(1, engines + 1)
        for cycle in range(1, cycles + 1)
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("train_FD001.txt", rows)
        archive.writestr("test_FD001.txt", _cmapss_row(1, 1))
        archive.writestr("RUL_FD001.txt", "10\n")
        archive.writestr("readme.txt", "synthetic test fixture")
    return path


def test_load_cmapss_stream_groups_engines_and_constructs_rul(tmp_path: Path) -> None:
    from brace_msi.data.cmapss import load_cmapss_fd001_stream

    stream = load_cmapss_fd001_stream(_write_cmapss_zip(tmp_path / "cmapss.zip"))

    assert stream.task_kind == "regression"
    assert stream.initial.X.shape == (18, 24)
    assert stream.initial.group_ids == tuple(str(engine) for engine in range(1, 7) for _ in range(3))
    np.testing.assert_array_equal(stream.initial.y[:3], [2.0, 1.0, 0.0])
    assert stream.metadata["proxy_only"] is True
    assert stream.metadata["split_rule"] == "engine IDs 60% / 20% / 20%"
    assert stream.all_sample_ids_are_disjoint()

    initial_groups = set(stream.initial.group_ids)
    development_groups = {group for batch in stream.development for group in batch.group_ids}
    sealed_groups = {group for batch in stream.sealed for group in batch.group_ids}
    assert initial_groups.isdisjoint(development_groups)
    assert initial_groups.isdisjoint(sealed_groups)
    assert development_groups.isdisjoint(sealed_groups)


def test_cmapss_cycles_remain_ordered_inside_each_engine(tmp_path: Path) -> None:
    from brace_msi.data.cmapss import load_cmapss_fd001_stream

    stream = load_cmapss_fd001_stream(_write_cmapss_zip(tmp_path / "cmapss.zip"))

    for batch in (stream.initial, *stream.development, *stream.sealed):
        for engine in sorted(set(batch.group_ids), key=int):
            rul_values = [
                target
                for target, group in zip(batch.y, batch.group_ids, strict=True)
                if group == engine
            ]
            assert rul_values == sorted(rul_values, reverse=True)


def test_cmapss_rejects_wrong_column_count(tmp_path: Path) -> None:
    from brace_msi.data.cmapss import CmapssFormatError, load_cmapss_fd001_stream

    path = tmp_path / "bad.zip"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("train_FD001.txt", "1 1 0.0\n")

    try:
        load_cmapss_fd001_stream(path)
    except CmapssFormatError as exc:
        assert "26" in str(exc)
    else:
        raise AssertionError("invalid C-MAPSS row was accepted")
