from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brace_msi.data.types import BatchData, TaskStream


def _batch(batch_id: str, start: int, *, regression: bool = False) -> BatchData:
    y = np.asarray([start, start + 1], dtype=np.float64 if regression else np.int64)
    return BatchData(
        batch_id=batch_id,
        X=np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64),
        y=y,
        sample_ids=(f"opaque-{start}", f"opaque-{start + 1}"),
        group_ids=("1", "1") if regression else (),
    )


def test_build_proxy_audit_contains_only_aggregate_evidence(tmp_path: Path) -> None:
    from brace_msi.data.audit import build_proxy_audit

    gas = TaskStream(
        task_id="gas",
        task_kind="classification",
        initial=_batch("gas-initial", 0),
        development=(_batch("gas-dev", 2),),
        sealed=(_batch("gas-sealed", 4),),
        metadata={"proxy_only": True, "split_rule": "test split"},
    )
    cmapss = TaskStream(
        task_id="cmapss",
        task_kind="regression",
        initial=_batch("cmapss-initial", 0, regression=True),
        development=(_batch("cmapss-dev", 2, regression=True),),
        sealed=(_batch("cmapss-sealed", 4, regression=True),),
        metadata={"proxy_only": True, "split_rule": "test groups"},
    )
    gas_zip = tmp_path / "gas.zip"
    cmapss_zip = tmp_path / "cmapss.zip"
    gas_zip.write_bytes(b"gas")
    cmapss_zip.write_bytes(b"cmapss")

    report = build_proxy_audit(
        gas,
        cmapss,
        gas_archive=gas_zip,
        cmapss_archive=cmapss_zip,
    )

    assert report["proxy_only"] is True
    assert report["datasets"]["gas"]["partition_samples"] == {
        "initial": 2,
        "development": 2,
        "sealed": 2,
    }
    assert report["datasets"]["cmapss"]["partition_groups"] == {
        "initial": 1,
        "development": 1,
        "sealed": 1,
    }
    assert report["checks"]["sample_ids_disjoint"] is True
    assert len(report["archives"]["gas_sha256"]) == 64
    serialized = json.dumps(report)
    assert "opaque-" not in serialized
    assert "[[1.0" not in serialized
