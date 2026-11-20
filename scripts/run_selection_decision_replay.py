"""Zero-training replay for preregistered selection strategies."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_formal.metrics import MetricContract  # noqa: E402
from brace_msi.selection_strategies import (  # noqa: E402
    ArtifactEvidence,
    ExplorationBudget,
    SelectionContext,
    decide,
)


OFFICIAL_REPORTS = {
    "gas": "009F5C2D023A1F8DC2112E730AE55C35F0F45D2B39A72817412F1677DB5146CA",
    "bearing_engine": "4A1AB20BEB255E1C50972B7C53BD8FD957E338117496A1E7531A3FD8CBDFA5EA",
}


def _frozen_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "O-PLATFORM-019-GAS-R5",
            "source_sha256": OFFICIAL_REPORTS["gas"],
            "contract": MetricContract("classification", "macro_f1", "higher"),
            "parent_value": 0.9213,
            "candidate_value": 0.8805,
        },
        {
            "case_id": "O-PLATFORM-019-BEARING-R2",
            "source_sha256": OFFICIAL_REPORTS["bearing_engine"],
            "contract": MetricContract("regression", "rmse", "lower"),
            "parent_value": 660.81,
            "candidate_value": 675.55,
        },
        {
            "case_id": "O-PLATFORM-019-ENGINE-R4",
            "source_sha256": OFFICIAL_REPORTS["bearing_engine"],
            "contract": MetricContract("regression", "rmse", "lower"),
            "parent_value": 52.71,
            "candidate_value": 52.94,
        },
    ]


def build_replay() -> dict[str, Any]:
    strategies = (
        "strict_parent_gate",
        "bounded_exploration",
        "conditional_champion",
        "recipe_feedback",
    )
    rows: list[dict[str, Any]] = []
    for case in _frozen_cases():
        scope = hashlib.sha256(case["case_id"].encode("utf-8")).hexdigest()
        context = SelectionContext(
            contract=case["contract"],
            validation_scope=scope,
            parent=ArtifactEvidence("parent", case["parent_value"], scope, True, True),
            candidate=ArtifactEvidence(
                "candidate", case["candidate_value"], scope, True, True
            ),
            exploration=ExplorationBudget(remaining=1, regression_tolerance=0.0),
            rollback_available=True,
        )
        decisions = {strategy: asdict(decide(strategy, context)) for strategy in strategies}
        rows.append(
            {
                "case_id": case["case_id"],
                "source_sha256": case["source_sha256"],
                "metric_contract": case["contract"].as_dict(),
                "validation_scope": scope,
                "parent_value": case["parent_value"],
                "candidate_value": case["candidate_value"],
                "decisions": decisions,
            }
        )

    strict_pass = all(
        row["decisions"]["strict_parent_gate"]["selected_artifact_id"] == "parent"
        for row in rows
    )
    return {
        "experiment_id": "GENERALIZATION-MATRIX-001-A1",
        "kind": "zero_training_decision_replay",
        "official_trial_count": 0,
        "training_count": 0,
        "public_confirmation_reads": 0,
        "pytrio_remote_calls": 0,
        "swanlab_sync_count": 0,
        "strict_regression_cases_rejected": sum(
            row["decisions"]["strict_parent_gate"]["selected_artifact_id"] == "parent"
            for row in rows
        ),
        "strict_case_count": len(rows),
        "valid": strict_pass,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("output must be new")
    result = build_replay()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

