"""Local ten-round simulation of the native platform mount contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .platform_runtime import (
    PlatformAdvisor,
    PlatformRuntimeConfig,
    evaluate_checkpoint,
    start_round,
    submit_predictions,
)
from .swanlab_adapter import SwanLabOfflineConfig, export_public_spool


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_ten_round_simulation(
    data_path: Path,
    parent_checkpoint: Path,
    run_root: Path,
    *,
    prediction_data_path: Path | None = None,
    config: PlatformRuntimeConfig = PlatformRuntimeConfig(),
    export_swanlab: bool = True,
    swanlab_project: str = "brace-msi-platform-native",
    experiment_name: str = "platform-native-simulation",
    advisor: PlatformAdvisor | None = None,
) -> dict[str, Any]:
    """Materialize ten isolated batches and exercise the exact native runtime API."""

    data_path = Path(data_path).resolve()
    parent_checkpoint = Path(parent_checkpoint).resolve()
    root = Path(run_root).resolve()
    if root.exists() or root.is_symlink():
        raise FileExistsError("simulation output must be a new directory")
    if not data_path.is_file() or data_path.is_symlink():
        raise ValueError("simulation data must be a regular JSONL file")
    lines = [line for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 50:
        raise ValueError("ten-round simulation requires at least 50 labeled rows")
    root.mkdir(parents=True)
    workspace = root / "workspace"
    current_parent = parent_checkpoint
    receipts: list[dict[str, Any]] = []
    for offset in range(10):
        start = len(lines) * offset // 10
        stop = len(lines) * (offset + 1) // 10
        batch_root = root / "batches" / f"round-{offset + 1:02d}"
        batch_root.mkdir(parents=True)
        batch_file = batch_root / "data.jsonl"
        batch_file.write_text("\n".join(lines[start:stop]) + "\n", encoding="utf-8")
        output = root / f"round-{offset + 1:02d}"
        receipt = start_round(
            batch_file,
            current_parent,
            workspace,
            output,
            config,
            advisor=advisor,
        )
        receipts.append(receipt)
        current_parent = output / "checkpoint.npz"

    prediction_data = Path(prediction_data_path).resolve() if prediction_data_path else data_path
    initial_predictions = root / "initial-predictions.jsonl"
    submit_predictions(parent_checkpoint, prediction_data, initial_predictions)
    predictions = root / "predictions.jsonl"
    prediction_receipt = submit_predictions(current_parent, prediction_data, predictions)
    initial_metrics = evaluate_checkpoint(parent_checkpoint, prediction_data)
    final_metrics = evaluate_checkpoint(current_parent, prediction_data)
    parent_chain_valid = all(
        receipts[index]["parent_checkpoint_sha256"]
        == (
            _sha256(parent_checkpoint)
            if index == 0
            else receipts[index - 1]["checkpoint_sha256"]
        )
        for index in range(len(receipts))
    )
    swanlab_logdir: str | None = None
    if export_swanlab:
        result = export_public_spool(
            workspace / "public-spool.jsonl",
            SwanLabOfflineConfig(
                project=swanlab_project,
                experiment_name=experiment_name,
                logdir=root / "swanlab",
                public=False,
            ),
        )
        swanlab_logdir = str(result.logdir)
    summary: dict[str, Any] = {
        "format": "brace-msi.platform-simulation.v1",
        "status": "completed",
        "round_count": len(receipts),
        "decision_count": sum("decision" in row for row in receipts),
        "candidate_count": sum(bool(row["candidate_trained"]) for row in receipts),
        "accepted_count": sum(bool(row["deployed"]) for row in receipts),
        "noop_count": sum(not bool(row["candidate_trained"]) for row in receipts),
        "parent_chain_valid": parent_chain_valid,
        "final_checkpoint_sha256": receipts[-1]["checkpoint_sha256"],
        "prediction_sample_count": prediction_receipt["sample_count"],
        "initial_metrics": initial_metrics,
        "final_metrics": final_metrics,
        "complete_ten_rounds": len(receipts) == 10
        and all("decision" in row for row in receipts),
        "input_tokens": sum(int(row["input_tokens"]) for row in receipts),
        "output_tokens": sum(int(row["output_tokens"]) for row in receipts),
        "swanlab_logdir": swanlab_logdir,
        "rounds": receipts,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary

