"""Non-interactive local entry points for the platform-neutral Harness."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .budget import BudgetLimits
from .harness import HarnessConfig, UnifiedHarness
from .official_sdk import OfficialSdkSpec, load_official_adapter_factory
from .official_agent_harness import (
    DeterministicOfficialProposalProvider,
    FrozenScheduleOfficialProposalProvider,
    official_agent_config_from_mapping,
    run_official_agent_harness,
    validate_official_agent_harness,
)
from .official_package import audit_package_root
from .official_trainer import OfficialTrainer
from .pytrio_agent import PyTrioAgentClient, PyTrioAgentConfig
from .protocol import ProtocolMode
from .reporting import render_html_report
from .safety import GateConfig
from .simulation import synthetic_bearing_stream
from .swanlab_adapter import (
    SwanLabOfflineConfig,
    build_sync_command,
    export_public_spool,
)


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
    report = subparsers.add_parser("render-report", help="render an offline HTML report")
    report.add_argument("--input", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    swanlab_export = subparsers.add_parser(
        "swanlab-offline-export",
        help="convert the aggregate public spool into SwanLab offline logs",
    )
    swanlab_export.add_argument("--spool", type=Path, required=True)
    swanlab_export.add_argument("--logdir", type=Path, required=True)
    swanlab_export.add_argument("--project", required=True)
    swanlab_export.add_argument("--experiment-name", required=True)
    swanlab_export.add_argument("--public", action="store_true")
    sync_command = subparsers.add_parser(
        "swanlab-sync-command",
        help="print an explicit SwanLab sync command without executing it",
    )
    sync_command.add_argument("--run-dir", type=Path, required=True)
    sync_command.add_argument("--workspace")
    sync_command.add_argument("--project")
    sdk_check = subparsers.add_parser(
        "sdk-contract-check",
        help="validate an installed official SDK adapter plugin contract",
    )
    sdk_check.add_argument("--spec", type=Path, required=True)
    official_agent = subparsers.add_parser(
        "official-agent-run",
        help="run or resume the guarded Agent workflow on one immutable A/B/C package",
    )
    official_agent.add_argument("--config", type=Path, required=True)
    official_agent.add_argument("--package-root", type=Path, required=True)
    official_agent.add_argument("--runtime-root", type=Path, required=True)
    official_agent.add_argument("--profile", choices=("A", "B", "C"), required=True)
    official_agent.add_argument(
        "--provider", choices=("deterministic", "pytrio"), default="deterministic"
    )
    official_agent.add_argument("--model", default="Qwen/Qwen3.5-4B")
    official_agent.add_argument("--model-path")
    official_agent.add_argument("--max-rounds-this-call", type=int)
    official_agent.add_argument("--timeout-seconds", type=float, default=600.0)
    official_agent.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "render-report":
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_html_report(payload), encoding="utf-8")
        print(json.dumps({"status": "completed", "output": str(args.output)}))
        return 0
    if args.command == "swanlab-offline-export":
        result = export_public_spool(
            args.spool,
            SwanLabOfflineConfig(
                project=args.project,
                experiment_name=args.experiment_name,
                logdir=args.logdir,
                public=args.public,
            ),
        )
        print(
            json.dumps(
                {
                    "status": "offline_export_completed",
                    "logdir": str(result.logdir),
                    "record_count": result.record_count,
                }
            )
        )
        return 0
    if args.command == "swanlab-sync-command":
        command = build_sync_command(
            args.run_dir, workspace=args.workspace, project=args.project
        )
        print(json.dumps({"status": "manual_sync_required", "command": command}))
        return 0
    if args.command == "sdk-contract-check":
        spec = OfficialSdkSpec.from_json(args.spec)
        factory = load_official_adapter_factory(spec)
        modes = [mode.value for mode in ProtocolMode]
        for mode in ProtocolMode:
            factory(mode)
        print(
            json.dumps(
                {
                    "status": "contract_ready",
                    "sdk_version": spec.sdk_version,
                    "protocol_modes": modes,
                }
            )
        )
        return 0
    if args.command == "official-agent-run":
        raw_config = json.loads(args.config.read_text(encoding="utf-8"))
        package = audit_package_root(args.package_root, raw_config)[args.profile]
        harness_config = official_agent_config_from_mapping(
            raw_config, profile=args.profile
        )
        if args.validate_only:
            print(
                json.dumps(
                    validate_official_agent_harness(
                        args.runtime_root, package, harness_config
                    ),
                    allow_nan=False,
                )
            )
            return 0
        schedule = raw_config.get("deterministic_schedules", {}).get(args.profile)
        deterministic = (
            FrozenScheduleOfficialProposalProvider(package, tuple(schedule))
            if schedule
            else DeterministicOfficialProposalProvider(
                candidate_rounds=harness_config.max_candidates
            )
        )
        if args.provider == "pytrio":
            provider = PyTrioAgentClient(
                PyTrioAgentConfig(model=args.model, model_path=args.model_path),
                fallback=lambda context: deterministic.propose(context).proposal,
            )
        else:
            provider = deterministic
        result = run_official_agent_harness(
            package,
            args.runtime_root,
            harness_config,
            OfficialTrainer(
                python_executable=Path(sys.executable),
                timeout_seconds=args.timeout_seconds,
                allowed_learning_rate_multipliers=(
                    harness_config.allowed_learning_rate_multipliers
                ),
            ),
            provider,
            fallback_provider=deterministic,
            max_rounds_this_call=args.max_rounds_this_call,
        )
        print(
            json.dumps(
                {
                    "status": "completed" if result.complete else "paused",
                    "profile": result.profile,
                    "round_count": result.round_count,
                    "candidate_count": result.candidate_count,
                    "accepted_count": result.accepted_count,
                    "stable_metric": result.stable_metric,
                    "agent_call_count": result.agent_call_count,
                    "total_input_tokens": result.total_input_tokens,
                    "total_output_tokens": result.total_output_tokens,
                },
                allow_nan=False,
            )
        )
        return 0
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
