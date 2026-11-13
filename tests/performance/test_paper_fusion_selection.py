from __future__ import annotations

import json
from pathlib import Path

import pytest

from brace_msi.paper_fusion_selection import build_safe_hybrid_manifest


def _summary(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "format": "brace-msi.paper-fusion-result.v1",
                "status": "completed",
                "validation_open_count": 1,
                "profiles": {
                    "A": {
                        "metrics": {"macro_f1": 0.68},
                        "rc3": 0.72,
                        "relative_improvement_over_rc3": -0.05,
                    },
                    "B": {
                        "metrics": {"rmse": 640.0},
                        "rc3": 637.0,
                        "relative_improvement_over_rc3": -0.004,
                    },
                    "C": {
                        "metrics": {"rmse": 42.0},
                        "rc3": 51.0,
                        "relative_improvement_over_rc3": 0.17,
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_safe_hybrid_only_promotes_strict_improvement(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    _summary(summary)

    result = build_safe_hybrid_manifest(summary, tmp_path / "hybrid.json")

    assert result["profiles"]["A"]["selected_source"] == "rc3"
    assert result["profiles"]["B"]["selected_source"] == "rc3"
    assert result["profiles"]["C"]["selected_source"] == "paper_fusion"
    assert result["public_validation_reopened"] is False


def test_safe_hybrid_rejects_incomplete_or_nonfinite_results(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    _summary(summary)
    payload = json.loads(summary.read_text())
    payload["profiles"]["C"]["metrics"]["rmse"] = float("nan")
    summary.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="finite"):
        build_safe_hybrid_manifest(summary, tmp_path / "hybrid.json")
