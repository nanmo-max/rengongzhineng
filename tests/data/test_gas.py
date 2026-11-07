from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


def _gas_line(label: int, *, offset: float = 0.0) -> str:
    values = " ".join(f"{index}:{index + offset:.4f}" for index in range(1, 129))
    return f"{label} {values}\n"


def _write_gas_dataset(root: Path) -> Path:
    dataset = root / "Dataset"
    dataset.mkdir(parents=True)
    for batch in range(1, 11):
        content = _gas_line(1 + batch % 3, offset=batch / 10)
        content += _gas_line(1 + (batch + 1) % 3, offset=batch / 10 + 1)
        (dataset / f"batch{batch}.dat").write_text(content, encoding="utf-8")
    return root


def test_development_only_gas_loader_never_requires_sealed_batch_files(tmp_path: Path) -> None:
    from brace_msi.data.gas import load_gas_stream

    root = tmp_path / "gas"
    dataset = root / "Dataset"
    dataset.mkdir(parents=True)
    for batch in range(1, 8):
        content = _gas_line(1, offset=batch / 10) + _gas_line(2, offset=batch / 10)
        (dataset / f"batch{batch}.dat").write_text(content, encoding="utf-8")

    stream = load_gas_stream(root, include_sealed=False)

    assert len(stream.development) == 4
    assert stream.sealed == ()
    assert stream.metadata["sealed_loaded"] is False


def test_load_gas_stream_preserves_frozen_batch_split(tmp_path: Path) -> None:
    from brace_msi.data.gas import load_gas_stream

    stream = load_gas_stream(_write_gas_dataset(tmp_path / "gas"))

    assert stream.task_kind == "classification"
    assert stream.initial.batch_id == "gas-initial-b01-b03"
    assert stream.initial.X.shape == (6, 128)
    assert tuple(batch.batch_id for batch in stream.development) == (
        "gas-b04",
        "gas-b05",
        "gas-b06",
        "gas-b07",
    )
    assert tuple(batch.batch_id for batch in stream.sealed) == (
        "gas-b08",
        "gas-b09",
        "gas-b10",
    )
    assert stream.metadata["proxy_only"] is True
    assert stream.metadata["split_rule"] == "batches 1-3 / 4-7 / 8-10"
    assert stream.all_sample_ids_are_disjoint()
    np.testing.assert_allclose(stream.initial.X[0, :3], [1.1, 2.1, 3.1])


@pytest.mark.parametrize(
    "bad_line",
    [
        "1 1:1.0 1:2.0\n",
        "1 0:1.0\n",
        "1 129:1.0\n",
        "1 1:not-a-number\n",
    ],
)
def test_parse_gas_file_rejects_invalid_sparse_features(
    tmp_path: Path, bad_line: str
) -> None:
    from brace_msi.data.gas import GasFormatError, parse_gas_file

    path = tmp_path / "bad.dat"
    path.write_text(bad_line, encoding="utf-8")

    with pytest.raises(GasFormatError):
        parse_gas_file(path, batch_number=1)


def test_parse_gas_file_requires_exactly_128_features(tmp_path: Path) -> None:
    from brace_msi.data.gas import GasFormatError, parse_gas_file

    path = tmp_path / "short.dat"
    path.write_text("1 1:1.0 2:2.0\n", encoding="utf-8")

    with pytest.raises(GasFormatError, match="128"):
        parse_gas_file(path, batch_number=1)
