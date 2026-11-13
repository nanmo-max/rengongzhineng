"""Fail-closed promotion gate for a frozen paper-fusion experiment."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def build_safe_hybrid_manifest(summary_path: Path, output_path: Path) -> dict[str, Any]:
    """Select a paper candidate only when its single-open result beats RC3."""

    summary_path = Path(summary_path).resolve()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        summary.get("format") != "brace-msi.paper-fusion-result.v1"
        or summary.get("status") != "completed"
        or summary.get("validation_open_count") != 1
        or set(summary.get("profiles", {})) != {"A", "B", "C"}
    ):
        raise ValueError("paper-fusion summary is incomplete or not single-open")

    selected: dict[str, Any] = {}
    for profile in ("A", "B", "C"):
        result = summary["profiles"][profile]
        metric_name = "macro_f1" if profile == "A" else "rmse"
        paper_metric = float(result["metrics"][metric_name])
        rc3_metric = float(result["rc3"])
        improvement = float(result["relative_improvement_over_rc3"])
        if not all(math.isfinite(value) for value in (paper_metric, rc3_metric, improvement)):
            raise ValueError(f"{profile} metrics must be finite")
        promote = improvement > 0.0
        selected[profile] = {
            "metric": metric_name,
            "selected_source": "paper_fusion" if promote else "rc3",
            "selected_value": paper_metric if promote else rc3_metric,
            "paper_fusion_value": paper_metric,
            "rc3_value": rc3_metric,
            "relative_improvement_over_rc3": improvement,
            "promotion_rule": "strictly_positive_relative_improvement_over_rc3",
        }

    manifest: dict[str, Any] = {
        "format": "brace-msi.paper-fusion-hybrid.v1",
        "source_summary_sha256": _sha256(summary_path),
        "evidence_scope": "historically_exposed_public_validation",
        "public_validation_reopened": False,
        "profiles": selected,
    }
    _write_atomic(Path(output_path).resolve(), manifest)
    return manifest
