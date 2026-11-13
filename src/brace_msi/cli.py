"""Non-interactive local entry points for the platform-neutral Harness."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import numpy as np

from .budget import BudgetLimits
from .controlled_harness import ControlledDualLoopHarness, ControlledHarnessConfig
from .harness import HarnessConfig, UnifiedHarness
from .generalist_experiment import run_generalist_experiment
from .generalist_model import GeneralistCheckpoint
from .model_gate import predict_checkpoint
from .official_sdk import OfficialSdkSpec, load_official_adapter_factory
from .official_agent_harness import (
    DeterministicOfficialProposalProvider,
    FrozenScheduleOfficialProposalProvider,
    official_agent_config_from_mapping,
    run_official_agent_harness,
    validate_official_agent_harness,
)
from .official_package import audit_package_root
from .official_stream_experiment import run_official_stream_matrix
from .official_trainer import OfficialTrainer
from .pytrio_agent import PyTrioAgentClient, PyTrioAgentConfig
from .protocol import ProtocolMode
from .paper_fusion_runner import (
    run_paper_fusion_sprint,
    validate_paper_fusion_output,
)
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
    controlled_smoke = subparsers.add_parser(
        "controlled-loop-smoke",
        help="run or resume the ten-round controlled dual loop on synthetic data",
    )
    controlled_smoke.add_argument("--output", type=Path, required=True)
    controlled_smoke.add_argument("--max-rounds-this-call", type=int)
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
        "--provider", choices=("deterministic", "pytrio")
    )
    official_agent.add_argument("--model", default="Qwen/Qwen3.5-4B")
    official_agent.add_argument("--model-path")
    official_agent.add_argument("--max-rounds-this-call", type=int)
    official_agent.add_argument("--agent-timeout-seconds", type=float, default=30.0)
    official_agent.add_argument("--timeout-seconds", type=float, default=600.0)
    official_agent.add_argument("--validate-only", action="store_true")
    official_stream = subparsers.add_parser(
        "official-stream-compare",
        help="run/resume the exposed A/B/C parent-checkpoint comparison matrix",
    )
    official_stream.add_argument("--experiment-config", type=Path, required=True)
    official_stream.add_argument("--package-root", type=Path, required=True)
    official_stream.add_argument("--output", type=Path, required=True)
    official_stream.add_argument("--timeout-seconds", type=float, default=600.0)
    generalist = subparsers.add_parser(
        "generalist-run",
        help="fit identity-blind parent ensembles and open public validation once",
    )
    generalist.add_argument("--package-config", type=Path, required=True)
    generalist.add_argument("--package-root", type=Path, required=True)
    generalist.add_argument("--output", type=Path, required=True)
    generalist_predict = subparsers.add_parser(
        "generalist-predict",
        help="run the independent parent-ensemble JSONL prediction entry",
    )
    generalist_predict.add_argument("--checkpoint", type=Path, required=True)
    generalist_predict.add_argument("--input-jsonl", type=Path, required=True)
    generalist_predict.add_argument("--output-jsonl", type=Path, required=True)
    paper_fusion = subparsers.add_parser(
        "paper-fusion-run",
        help="run/resume the bounded leakage-safe CPU paper-fusion trainer",
    )
    paper_fusion.add_argument("--config", type=Path)
    paper_fusion.add_argument("--output", type=Path, required=True)
    paper_fusion.add_argument("--open-validation", action="store_true")
    paper_fusion.add_argument("--validate-only", action="store_true")
    checkpoint_predict = subparsers.add_parser(
        "checkpoint-predict",
        help="run the independent NumPy checkpoint prediction entry",
    )
    checkpoint_predict.add_argument("--checkpoint", type=Path, required=True)
    checkpoint_predict.add_argument("--input-npy", type=Path, required=True)
    checkpoint_predict.add_argument("--output-npy", type=Path, required=True)
    return parser


def _validate_official_agent_selection(
    provider: str | None, model_path: str | None
) -> None:
    if provider is None:
        raise ValueError("--provider is required unless --validate-only is used")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "controlled-loop-smoke":
        summary = ControlledDualLoopHarness(
            args.output,
            ControlledHarnessConfig(
                performance_drop_threshold=0.0,
                drift_threshold=0.1,
                min_gate_gain=-1.0,
                max_anchor_degradation=1.0,
                min_gate_samples=4,
            ),
        ).run(
            synthetic_bearing_stream(seed=20261113, development_batches=10),
            max_rounds_this_call=args.max_rounds_this_call,
        )
        payload = {
            "schema_version": 1,
            "synthetic": True,
            "formal_eligible": False,
            "complete": summary.complete,
            "task_kind": summary.task_kind,
            "total_candidates": summary.total_candidates,
            "real_experiment_count": summary.real_experiment_count,
            "stable_model_id": summary.stable_model_id,
            "rounds": [asdict(item) for item in summary.rounds],
        }
        (args.output / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "completed" if summary.complete else "paused",
                    "round_count": len(summary.rounds),
                    "candidate_count": summary.total_candidates,
                },
                allow_nan=False,
            )
        )
        return 0
    if args.command == "checkpoint-predict":
        inputs = np.load(args.input_npy, allow_pickle=False)
        predictions = predict_checkpoint(args.checkpoint, inputs)
        args.output_npy.parent.mkdir(parents=True, exist_ok=True)
        np.save(args.output_npy, predictions, allow_pickle=False)
        print(
            json.dumps(
                {
                    "status": "completed",
                    "sample_count": int(len(predictions)),
                    "output": str(args.output_npy),
                },
                allow_nan=False,
            )
        )
        return 0
    if args.command == "official-stream-compare":
        experiment = json.loads(args.experiment_config.read_text(encoding="utf-8"))
        package_config = Path(str(experiment["package_manifest"]))
        result = run_official_stream_matrix(
            args.package_root,
            package_config,
            args.output,
            policies=tuple(experiment["policies"]),
            experiment_id=str(experiment["experiment_id"]),
            max_total_candidates=int(experiment["max_total_candidates"]),
            timeout_seconds=args.timeout_seconds,
        )
        print(
            json.dumps(
                {
                    "status": "completed" if result["complete"] else "partial",
                    "profiles": sorted(result["results"]),
                    "policies": result["policies"],
                    "official_test_opportunities_used": 0,
                },
                allow_nan=False,
            )
        )
        return 0 if result["complete"] else 1
    if args.command == "generalist-run":
        result = run_generalist_experiment(
            args.package_root,
            args.package_config,
            args.output,
        )
        print(
            json.dumps(
                {
                    "status": "completed",
                    "accepted_profiles": result["accepted_profiles"],
                    "official_test_opportunities_used": 0,
                },
                allow_nan=False,
            )
        )
        return 0
    if args.command == "generalist-predict":
        checkpoint = GeneralistCheckpoint.load(args.checkpoint)
        requests = [
            json.loads(line)
            for line in args.input_jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if any(
            not isinstance(request, dict)
            or set(request) - {"task", "inputs"}
            or "inputs" not in request
            or request.get("task", checkpoint.metadata["task"])
            != checkpoint.metadata["task"]
            for request in requests
        ):
            raise ValueError("prediction requests require only matching task and inputs")
        prediction = checkpoint.predict_inputs([request["inputs"] for request in requests])
        if checkpoint.metadata["task"] == "classification":
            classes = tuple(str(value) for value in checkpoint.metadata["classes"])
            payloads = [
                {
                    "outputs": [
                        {"label": label, "score": float(score)}
                        for label, score in zip(classes, row, strict=True)
                    ]
                }
                for row in prediction.raw
            ]
        else:
            payloads = [
                {"outputs": {"value": float(value)}} for value in prediction.predictions
            ]
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        args.output_jsonl.write_text(
            "".join(
                json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                + "\n"
                for payload in payloads
            ),
            encoding="utf-8",
            newline="\n",
        )
        print(
            json.dumps(
                {"status": "completed", "sample_count": len(payloads)},
                allow_nan=False,
            )
        )
        return 0
    if args.command == "paper-fusion-run":
        if args.validate_only:
            result = validate_paper_fusion_output(args.output)
            print(json.dumps(result, allow_nan=False))
            return 0 if result["valid"] else 1
        if args.config is None:
            raise ValueError("--config is required unless --validate-only is used")
        result = run_paper_fusion_sprint(
            args.config,
            args.output,
            open_validation=args.open_validation,
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "profiles": sorted(result["profiles"]),
                    "validation_open_count": result["validation_open_count"],
                },
                allow_nan=False,
            )
        )
        return 0
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
        _validate_official_agent_selection(args.provider, args.model_path)
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
                PyTrioAgentConfig(
                    model=args.model,
                    model_path=args.model_path,
                    timeout_seconds=args.agent_timeout_seconds,
                    allow_fallback=False,
                ),
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
            allow_provider_fallback=args.provider != "pytrio",
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
