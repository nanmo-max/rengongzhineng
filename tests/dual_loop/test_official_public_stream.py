from __future__ import annotations

import json
from pathlib import Path

from brace_msi.official_package import audit_package_root
from brace_msi.official_public_stream import (
    OfficialCheckpointPredictor,
    freeze_public_validation_stream,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


def _audits():
    config = json.loads(
        (REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8")
    )
    return audit_package_root(PACKAGE_ROOT, config)


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_public_validation_freezes_as_ten_disjoint_complete_batches(tmp_path: Path) -> None:
    for profile, package in _audits().items():
        stream = freeze_public_validation_stream(package, tmp_path / profile, rounds=10)

        assert len(stream.batches) == 10
        assert stream.historically_exposed is True
        ids: list[str] = []
        for batch in stream.batches:
            assert batch.path.is_file()
            rows = _rows(batch.path)
            assert len(rows) == batch.sample_count
            assert batch.sample_id_digest
            ids.extend(str(row["id"]) for row in rows)
        assert len(ids) == len(set(ids)) == package.validation_rows
        assert frozenset(ids) == package.validation_ids
        assert (tmp_path / profile / "stream-manifest.json").is_file()


def test_grouped_engine_units_never_cross_frozen_batches(tmp_path: Path) -> None:
    package = _audits()["C"]
    stream = freeze_public_validation_stream(package, tmp_path / "C", rounds=10)
    seen: dict[str, int] = {}

    for batch_index, batch in enumerate(stream.batches, 1):
        for row in _rows(batch.path):
            meta = row["meta"]
            group = f"{meta['source_subset']}:{meta['unit']}"
            assert group not in seen or seen[group] == batch_index
            seen[group] = batch_index

    assert len(seen) == len(package.validation_groups)


def test_prediction_worker_receives_inputs_but_no_labels_or_future_root(tmp_path: Path) -> None:
    package = _audits()["A"]
    rows = _rows(package.validation_path)[:8]
    predictor = OfficialCheckpointPredictor(package, tmp_path / "predictor")

    receipt = predictor.predict_rows(package.checkpoint_path, rows, stage_id="round-01")

    assert receipt.predictions.shape == (8,)
    assert set(receipt.predictions.tolist()) <= {
        "Ethanol",
        "Ethylene",
        "Ammonia",
        "Acetaldehyde",
        "Acetone",
        "Toluene",
    }
    assert receipt.wall_seconds >= 0
    assert receipt.cpu_seconds >= 0
    assert receipt.peak_rss_bytes >= 0
    assert receipt.request_sha256
    assert not (predictor.worker_root / "public").exists()
