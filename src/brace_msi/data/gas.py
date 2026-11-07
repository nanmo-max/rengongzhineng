"""Strict reader for the UCI Gas Sensor Array Drift proxy dataset."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import numpy as np

from .types import BatchData, TaskStream

FEATURE_COUNT = 128


class GasFormatError(ValueError):
    """Raised when a Gas dataset row violates the documented sparse format."""


def _opaque_id(namespace: str, local_key: str) -> str:
    return sha256(f"{namespace}|{local_key}".encode()).hexdigest()[:24]


def parse_gas_file(
    path: Path, *, batch_number: int, max_rows: int | None = None
) -> BatchData:
    features: list[list[float]] = []
    labels: list[int] = []
    sample_ids: list[str] = []

    with path.open("r", encoding="utf-8") as handle:
        for row_index, raw_line in enumerate(handle, start=1):
            if max_rows is not None and len(labels) >= max_rows:
                break
            tokens = raw_line.split()
            if not tokens:
                continue
            try:
                label = int(tokens[0])
            except ValueError as exc:
                raise GasFormatError(f"invalid label on row {row_index}") from exc

            row = [0.0] * FEATURE_COUNT
            seen: set[int] = set()
            for token in tokens[1:]:
                try:
                    raw_index, raw_value = token.split(":", maxsplit=1)
                    index = int(raw_index)
                    value = float(raw_value)
                except (ValueError, TypeError) as exc:
                    raise GasFormatError(
                        f"invalid sparse feature on row {row_index}"
                    ) from exc
                if index < 1 or index > FEATURE_COUNT or index in seen:
                    raise GasFormatError(
                        f"invalid or duplicate feature index on row {row_index}"
                    )
                seen.add(index)
                row[index - 1] = value
            if len(seen) != FEATURE_COUNT:
                raise GasFormatError(
                    f"row {row_index} must contain exactly {FEATURE_COUNT} features"
                )
            features.append(row)
            labels.append(label)
            sample_ids.append(_opaque_id("gas", f"b{batch_number}:r{row_index}"))

    if not labels:
        raise GasFormatError(f"no samples found in {path.name}")
    return BatchData(
        batch_id=f"gas-b{batch_number:02d}",
        X=np.asarray(features, dtype=np.float64),
        y=np.asarray(labels, dtype=np.int64),
        sample_ids=tuple(sample_ids),
    )


def _combine_initial(batches: list[BatchData]) -> BatchData:
    return BatchData(
        batch_id="gas-initial-b01-b03",
        X=np.concatenate([batch.X for batch in batches], axis=0),
        y=np.concatenate([batch.y for batch in batches], axis=0),
        sample_ids=tuple(
            sample_id for batch in batches for sample_id in batch.sample_ids
        ),
    )


def load_gas_stream(
    root: Path, *, smoke: bool = False, include_sealed: bool = True
) -> TaskStream:
    """Load the frozen 1-3 / 4-7 / 8-10 chronological proxy split."""

    root = Path(root)
    dataset = root / "Dataset" if (root / "Dataset").is_dir() else root
    max_rows = 96 if smoke else None
    final_batch = 10 if include_sealed else 7
    batches = [
        parse_gas_file(
            dataset / f"batch{batch_number}.dat",
            batch_number=batch_number,
            max_rows=max_rows,
        )
        for batch_number in range(1, final_batch + 1)
    ]
    stream = TaskStream(
        task_id="gas-drift-proxy",
        task_kind="classification",
        initial=_combine_initial(batches[:3]),
        development=tuple(batches[3:7]),
        sealed=tuple(batches[7:]) if include_sealed else (),
        metadata={
            "proxy_only": True,
            "split_rule": "batches 1-3 / 4-7 / 8-10",
            "feature_count": FEATURE_COUNT,
            "smoke": smoke,
            "sealed_loaded": include_sealed,
        },
    )
    if not stream.all_sample_ids_are_disjoint():
        raise GasFormatError("sample identity overlap across frozen splits")
    return stream
