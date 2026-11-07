"""Non-interactive local entry points for the platform-neutral Harness."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .budget import BudgetLimits
from .harness import HarnessConfig, UnifiedHarness
from .protocol import ProtocolMode
from .safety import GateConfig
from .simulation import synthetic_bearing_stream


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brace-msi")
    subparsers = parser.add_subparsers(dest="command", required=True)
    smoke = subparsers.add_parser(
        "synthetic-smoke", help="run a protocol-only synthetic integration smoke"
    )
    smoke.add_argument("--output", type=Path, required=True)
    smoke.add_argument(
        "--protocol",
        choices=[mode.value for mode in ProtocolMode],
        default=ProtocolMode.PREDICT_THEN_FEEDBACK.value,
    )
    smoke.add_argument("--max-batches", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "synthetic-smoke":
        raise RuntimeError(f"unsupported command: {args.command}")
    config = HarnessConfig(
        seed=20261107,
        protocol_mode=ProtocolMode(args.protocol),
        budget=BudgetLimits(8, 20_000, 60.0, 60.0),
        gate=GateConfig(
            min_validation_samples=4,
            min_primary_improvement=-1.0,
            max_anchor_degradation=1.0,
        ),
        minimum_candidate_events=3,
        replay_max_samples=1000,
        hpo_max_trials=2,
    )
    result = UnifiedHarness(args.output, config).run(
        synthetic_bearing_stream(seed=config.seed), max_batches=args.max_batches
    )
    payload = {
        "schema_version": 1,
        "proxy_only": True,
        "synthetic": True,
        "evidence_scope": "protocol_only",
        "task_id": result.task_id,
        "status": result.status,
        "completed_batches": result.completed_batches,
        "candidate_count": result.candidate_count,
        "rollback_count": result.rollback_count,
        "deployed_version": result.deployed_version,
        "batch_metrics": list(result.batch_metrics),
        "candidates": [asdict(event) for event in result.candidates],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: payload[key] for key in ("status", "candidate_count")}))
    return 0 if result.status in {"completed", "paused"} else 1
