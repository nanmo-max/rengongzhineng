"""Grouped trajectory reader for the NASA C-MAPSS FD001 proxy task."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from .types import BatchData, TaskStream

COLUMN_COUNT = 26
FEATURE_COUNT = 24


class CmapssFormatError(ValueError):
    """Raised when an FD001 row or archive is malformed."""


def _opaque_id(engine_id: int, cycle: int) -> str:
    return sha256(f"cmapss-fd001|{engine_id}|{cycle}".encode()).hexdigest()[:24]


def _read_training_matrix(
    zip_path: Path, *, max_engine_id: int | None = None
) -> np.ndarray:
    try:
        with ZipFile(zip_path) as archive:
            if max_engine_id is None:
                payload = archive.read("train_FD001.txt")
            else:
                rows: list[bytes] = []
                with archive.open("train_FD001.txt") as handle:
                    for raw_line in handle:
                        try:
                            engine_id = int(raw_line.split(maxsplit=1)[0])
                        except (ValueError, IndexError) as exc:
                            raise CmapssFormatError("FD001 contains an invalid row") from exc
                        if engine_id > max_engine_id:
                            break
                        rows.append(raw_line)
                payload = b"".join(rows)
    except (KeyError, OSError) as exc:
        raise CmapssFormatError("archive must contain train_FD001.txt") from exc
    try:
        matrix = np.loadtxt(BytesIO(payload), dtype=np.float64)
    except ValueError as exc:
        raise CmapssFormatError("FD001 contains non-numeric values") from exc
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.shape[1] != COLUMN_COUNT:
        raise CmapssFormatError(
            f"FD001 rows must contain exactly {COLUMN_COUNT} columns"
        )
    return matrix


def _engine_chunks(engine_ids: list[int], *, count: int = 4) -> list[list[int]]:
    return [
        [int(engine_id) for engine_id in chunk]
        for chunk in np.array_split(np.asarray(engine_ids, dtype=int), count)
        if len(chunk)
    ]


def _make_batch(
    matrix: np.ndarray,
    engine_ids: list[int],
    *,
    batch_id: str,
    rul_cap: float,
) -> BatchData:
    rows: list[np.ndarray] = []
    targets: list[float] = []
    sample_ids: list[str] = []
    group_ids: list[str] = []
    for engine_id in engine_ids:
        engine_rows = matrix[matrix[:, 0] == engine_id]
        engine_rows = engine_rows[np.argsort(engine_rows[:, 1], kind="stable")]
        max_cycle = int(engine_rows[:, 1].max())
        for row in engine_rows:
            cycle = int(row[1])
            rows.append(row[2:].astype(np.float64, copy=False))
            targets.append(min(float(max_cycle - cycle), rul_cap))
            sample_ids.append(_opaque_id(engine_id, cycle))
            group_ids.append(str(engine_id))
    return BatchData(
        batch_id=batch_id,
        X=np.asarray(rows, dtype=np.float64),
        y=np.asarray(targets, dtype=np.float64),
        sample_ids=tuple(sample_ids),
        group_ids=tuple(group_ids),
    )


def load_cmapss_fd001_stream(
    zip_path: Path,
    *,
    smoke: bool = False,
    rul_cap: float = 125.0,
    include_sealed: bool = True,
) -> TaskStream:
    """Load FD001 using engine-group 60% / 20% / 20% proxy splits."""

    max_engine_id = None
    if not include_sealed:
        max_engine_id = 20 if smoke else 80
    matrix = _read_training_matrix(Path(zip_path), max_engine_id=max_engine_id)
    engine_ids = sorted({int(engine_id) for engine_id in matrix[:, 0]})
    if smoke:
        engine_ids = engine_ids[:20]
        matrix = matrix[np.isin(matrix[:, 0], engine_ids)]
    if len(engine_ids) < 5:
        raise CmapssFormatError("FD001 needs at least five engines for grouped splits")

    if include_sealed:
        initial_end = int(len(engine_ids) * 0.60)
        development_end = initial_end + int(len(engine_ids) * 0.20)
    else:
        initial_end = int(len(engine_ids) * 0.75)
        development_end = len(engine_ids)
    initial_ids = engine_ids[:initial_end]
    development_ids = engine_ids[initial_end:development_end]
    sealed_ids = engine_ids[development_end:]
    if not initial_ids or not development_ids or (include_sealed and not sealed_ids):
        raise CmapssFormatError("grouped 60/20/20 split produced an empty partition")

    stream = TaskStream(
        task_id="cmapss-fd001-proxy",
        task_kind="regression",
        initial=_make_batch(
            matrix, initial_ids, batch_id="cmapss-initial", rul_cap=rul_cap
        ),
        development=tuple(
            _make_batch(
                matrix,
                chunk,
                batch_id=f"cmapss-dev-{index:02d}",
                rul_cap=rul_cap,
            )
            for index, chunk in enumerate(_engine_chunks(development_ids), start=1)
        ),
        sealed=tuple(
            _make_batch(
                matrix,
                chunk,
                batch_id=f"cmapss-sealed-{index:02d}",
                rul_cap=rul_cap,
            )
            for index, chunk in enumerate(_engine_chunks(sealed_ids), start=1)
        ) if include_sealed else (),
        metadata={
            "proxy_only": True,
            "split_rule": "engine IDs 60% / 20% / 20%",
            "feature_count": FEATURE_COUNT,
            "rul_cap": rul_cap,
            "smoke": smoke,
            "external_test_reserved": True,
            "sealed_loaded": include_sealed,
        },
    )
    if not stream.all_sample_ids_are_disjoint():
        raise CmapssFormatError("engine-cycle identity overlap across frozen splits")
    return stream
