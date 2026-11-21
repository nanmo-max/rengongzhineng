"""Exact-image black-box checks for selector correction and history rollback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

from brace_formal.data import load_rows
from brace_formal.history import HistoryStore
from brace_formal.model import FormalModel
from scripts.verify_workspace_v2_image import (
    _artifact_receipt,
    _predict,
    _run_round,
    run,
)


def _requested_worse_than_applied(record: Mapping[str, Any]) -> bool:
    selection = record.get("selection")
    contract = record.get("metric_contract")
    evaluations = record.get("artifact_evaluations")
    if not isinstance(selection, Mapping) or not isinstance(contract, Mapping) or not isinstance(evaluations, list):
        return False
    requested = selection.get("requested_artifact_id")
    applied = selection.get("applied_artifact_id")
    metric = contract.get("metric")
    direction = contract.get("direction")
    values = {
        item.get("artifact_id"): item.get("metrics", {}).get(metric)
        for item in evaluations
        if isinstance(item, Mapping) and isinstance(item.get("metrics"), Mapping)
    }
    if requested not in values or applied not in values:
        return False
    requested_value = float(values[requested])
    applied_value = float(values[applied])
    return requested_value < applied_value if direction == "higher" else requested_value > applied_value


def _degraded_parent(source: Path, destination: Path) -> None:
    model = FormalModel.load(source)
    for group in (model.params, model.first, model.second):
        for value in group.values():
            value.fill(0.0)
    model.save(destination)


def run_blackbox(image: str, package_root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    wrong = run(
        image,
        package_root,
        output / "wrong-request",
        proposal_mode="worst",
        profiles=("A",),
        round_count=1,
    )
    wrong_round = wrong["profiles"]["A"]["rounds"][0]
    wrong_was_worse = _requested_worse_than_applied(wrong_round)
    wrong_honored = bool(
        wrong_round.get("requested_artifact_id")
        == wrong_round.get("locally_applied_artifact_id")
    )

    package = package_root / "cpu-a-guide-20261110-v1"
    history_root = output / "history-good"
    history_root.mkdir()
    shutil.copy2(package / "checkpoint.npz", history_root / "checkpoint.npz")
    parent_root = output / "degraded-parent"
    parent_root.mkdir()
    _degraded_parent(package / "checkpoint.npz", parent_root / "checkpoint.npz")
    parent = _artifact_receipt("degraded-parent", parent_root)
    historical = _artifact_receipt("history-good", history_root)
    prior_state = output / "prior-state"
    prior_state.mkdir()
    degraded_model = FormalModel.load(parent_root / "checkpoint.npz")
    prior_batch = load_rows(
        package / "public" / "train.jsonl", degraded_model, require_answers=True
    )
    prior_history = HistoryStore(degraded_model)
    prior_history.append(prior_batch, 1)
    prior_history.save(prior_state)
    history_run = output / "history-rollback"
    history_run.mkdir()
    record, candidate, _ = _run_round(
        image=image,
        profile="A",
        round_index=2,
        package=package,
        parent_root=parent_root,
        parent=parent,
        state_root=prior_state,
        run_root=history_run,
        history=[{
            "id": "history-record-1",
            "round_index": 1,
            "selected_artifact_id": "history-good",
        }],
        artifacts=[parent, historical],
        artifact_roots={"degraded-parent": parent_root, "history-good": history_root},
        proposal_mode="best",
    )
    if candidate is None:
        raise RuntimeError("history rollback black-box produced no real candidate")
    count1, digest1 = _predict(image, "A", history_root, package / "public" / "validation.jsonl")
    count2, digest2 = _predict(image, "A", history_root, package / "public" / "validation.jsonl")

    result = {
        "format": "brace-msi.competition-release-blackbox.v1",
        "image": image,
        "wrong_request_was_measurably_worse": wrong_was_worse,
        "wrong_deploy_accepted": bool(wrong_was_worse and wrong_honored),
        "wrong_request_selection": {
            "requested_artifact_id": wrong_round.get("requested_artifact_id"),
            "applied_artifact_id": wrong_round.get("locally_applied_artifact_id"),
            "selection_reason": wrong_round.get("selection_reason"),
        },
        "history_rollback_valid": (
            record.get("selection", {}).get("applied_role") == "history"
            and record.get("selected_artifact_id") == "history-good"
        ),
        "history_selection": record.get("selection"),
        "model_reload_predictions_equal": count1 == count2 == 5 and digest1 == digest2,
        "prediction_sha256": digest1,
    }
    (output / "blackbox.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_blackbox(args.image, args.package_root, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    valid = (
        result["wrong_request_was_measurably_worse"] is True
        and result["wrong_deploy_accepted"] is False
        and result["history_rollback_valid"] is True
        and result["model_reload_predictions_equal"] is True
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
