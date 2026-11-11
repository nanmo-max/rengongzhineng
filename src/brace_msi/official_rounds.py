"""Resumable candidate-adaptation decision rounds for official packages."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from .official_package import PackageAudit
from .official_trainer import CandidateConfig, CandidateReceipt


RoundPolicy = Literal["performance_triggered", "brace"]


@dataclass(frozen=True)
class PolicyResult:
    profile: str
    policy: RoundPolicy
    complete: bool
    round_count: int
    candidate_count: int
    accepted_count: int
    stable_checkpoint: str
    stable_sha256: str
    stable_metric: float
    rounds: list[dict[str, Any]]
    cpu_seconds: float
    wall_seconds: float
    peak_rss_bytes: int
    validation_file_reads: int
    validation_metric_evaluations: int
    round_semantics: str = "candidate_adaptation_decision"
    real_drift_stream: bool = False
    official_package: bool = True
    official_scoring_ready: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    os.replace(temporary, path)


def _initial_state(package: PackageAudit, policy: RoundPolicy, total_rounds: int) -> dict[str, Any]:
    return {
        "format": "brace-msi.official-policy-state.v1",
        "profile": package.profile,
        "task": package.task,
        "policy": policy,
        "round_semantics": "candidate_adaptation_decision",
        "real_drift_stream": False,
        "official_package": True,
        "official_scoring_ready": False,
        "expected_rounds": total_rounds,
        "initial_checkpoint": str(package.checkpoint_path),
        "initial_sha256": package.checkpoint_sha256,
        "initial_metric": package.baseline_metric,
        "stable_checkpoint": str(package.checkpoint_path),
        "stable_sha256": package.checkpoint_sha256,
        "stable_metric": package.baseline_metric,
        "candidate_count": 0,
        "accepted_count": 0,
        "cpu_seconds": 0.0,
        "wall_seconds": 0.0,
        "peak_rss_bytes": 0,
        "validation_file_reads": 0,
        "validation_metric_evaluations": 0,
        "rounds": [],
        "validation_usage": [],
    }


def _load_state(runtime_dir: Path, package: PackageAudit, policy: RoundPolicy, total_rounds: int) -> dict[str, Any]:
    path = runtime_dir / "state.json"
    if not path.exists():
        return _initial_state(package, policy, total_rounds)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("policy state is not valid JSON") from exc
    expected = {
        "format": "brace-msi.official-policy-state.v1",
        "profile": package.profile,
        "task": package.task,
        "policy": policy,
        "expected_rounds": total_rounds,
        "initial_sha256": package.checkpoint_sha256,
        "round_semantics": "candidate_adaptation_decision",
        "real_drift_stream": False,
    }
    for key, value in expected.items():
        if state.get(key) != value:
            raise ValueError(f"policy state mismatch: {key}")
    if len(state.get("rounds", [])) > total_rounds:
        raise ValueError("policy state contains too many rounds")
    return state


def _persist(runtime_dir: Path, state: dict[str, Any]) -> None:
    _atomic_json(runtime_dir / "state.json", state)
    _atomic_jsonl(runtime_dir / "audit.jsonl", state["rounds"])
    _atomic_jsonl(runtime_dir / "validation-usage.jsonl", state["validation_usage"])


def _candidate_action(package: PackageAudit, policy: RoundPolicy, state: Mapping[str, Any], config: Mapping[str, Any]) -> CandidateConfig | None:
    candidate_count = int(state["candidate_count"])
    maximum = int(config.get("max_candidates_per_policy", 3))
    if candidate_count >= maximum:
        return None
    if float(state["cpu_seconds"]) >= float(config.get("max_cpu_seconds_per_policy", math.inf)):
        return None
    if float(state["wall_seconds"]) >= float(config.get("max_wall_seconds_per_policy", math.inf)):
        return None
    if policy == "performance_triggered":
        if candidate_count > 0:
            return None
        return CandidateConfig(1, package.base_learning_rate, package.base_batch_size)

    minimum = int(config.get("minimum_brace_candidates", 3))
    if candidate_count >= minimum:
        return None
    previous_candidates = [row for row in state["rounds"] if row["kind"] == "candidate"]
    if not previous_candidates:
        return CandidateConfig(1, package.base_learning_rate, package.base_batch_size)
    if previous_candidates[-1]["deployed"]:
        return CandidateConfig(1, package.base_learning_rate * 0.5, package.base_batch_size)
    return CandidateConfig(2, package.base_learning_rate * 0.25, package.base_batch_size)


def _is_improvement(package: PackageAudit, candidate: float, stable: float) -> bool:
    return candidate > stable if package.higher_is_better else candidate < stable


def _next_output(runtime_dir: Path, round_number: int) -> tuple[Path, int]:
    candidates = runtime_dir / "candidates"
    attempt = 1
    while True:
        output = candidates / f"round-{round_number:02d}-attempt-{attempt:02d}"
        failure = output.with_name(output.name + ".failure.json")
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"candidate output conflict: {output}")
        if not failure.exists():
            return output, attempt
        attempt += 1


def _validate_receipt(
    package: PackageAudit,
    receipt: CandidateReceipt,
    parent_sha256: str,
    output: Path,
) -> float:
    if receipt.parent_sha256 != parent_sha256:
        raise ValueError("candidate receipt parent does not match stable model")
    if Path(receipt.output_dir).resolve() != output.resolve():
        raise ValueError("candidate receipt output directory mismatch")
    checkpoint = output / "checkpoint.npz"
    if not checkpoint.is_file() or _sha256(checkpoint) != receipt.checkpoint_sha256:
        raise ValueError("candidate receipt checkpoint hash mismatch")
    if not receipt.model_state_changed or not receipt.optimizer_state_changed:
        raise ValueError("candidate lacks model/optimizer continuation evidence")
    value = receipt.metrics_after.get(package.primary_metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError("candidate primary metric is missing or nonfinite")
    return float(value)


def _result(state: dict[str, Any]) -> PolicyResult:
    return PolicyResult(
        profile=state["profile"],
        policy=state["policy"],
        complete=len(state["rounds"]) == int(state["expected_rounds"]),
        round_count=len(state["rounds"]),
        candidate_count=int(state["candidate_count"]),
        accepted_count=int(state["accepted_count"]),
        stable_checkpoint=state["stable_checkpoint"],
        stable_sha256=state["stable_sha256"],
        stable_metric=float(state["stable_metric"]),
        rounds=list(state["rounds"]),
        cpu_seconds=float(state["cpu_seconds"]),
        wall_seconds=float(state["wall_seconds"]),
        peak_rss_bytes=int(state["peak_rss_bytes"]),
        validation_file_reads=int(state["validation_file_reads"]),
        validation_metric_evaluations=int(state["validation_metric_evaluations"]),
    )


def run_policy(
    package: PackageAudit,
    policy: RoundPolicy,
    runtime_dir: Path,
    config: Mapping[str, Any],
    trainer: Any,
) -> PolicyResult:
    """Run or resume one bounded policy without treating rounds as a real data stream."""

    if policy not in ("performance_triggered", "brace"):
        raise ValueError(f"unsupported policy: {policy}")
    total_rounds = int(config.get("rounds", 10))
    if total_rounds != 10:
        raise ValueError("official package development requires exactly 10 decision rounds")
    runtime_dir = Path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(runtime_dir, package, policy, total_rounds)
    call_limit = int(config.get("max_rounds_this_call", total_rounds))
    if call_limit < 1:
        raise ValueError("max_rounds_this_call must be positive")
    stop_at = min(total_rounds, len(state["rounds"]) + call_limit)

    while len(state["rounds"]) < stop_at:
        round_number = len(state["rounds"]) + 1
        action = _candidate_action(package, policy, state, config)
        if action is None:
            state["rounds"].append(
                {
                    "round": round_number,
                    "kind": "noop",
                    "reason": "no_evidence_justified_candidate_or_budget_exhausted",
                    "stable_sha256": state["stable_sha256"],
                    "stable_metric": state["stable_metric"],
                }
            )
            _persist(runtime_dir, state)
            continue

        output, attempt = _next_output(runtime_dir, round_number)
        parent = Path(state["stable_checkpoint"])
        parent_sha = state["stable_sha256"]
        stage_id = f"{package.profile}-{policy}-round-{round_number:02d}-attempt-{attempt:02d}"
        receipt = trainer.run_candidate(package, parent, output, action, stage_id)
        metric = _validate_receipt(package, receipt, parent_sha, output)
        deployed = _is_improvement(package, metric, float(state["stable_metric"]))
        record = {
            "round": round_number,
            "kind": "candidate",
            "stage_id": stage_id,
            "attempt": attempt,
            "config": asdict(action),
            "parent_sha256": parent_sha,
            "checkpoint_sha256": receipt.checkpoint_sha256,
            "metric_before": state["stable_metric"],
            "metric_after": metric,
            "primary_metric": package.primary_metric,
            "deployed": deployed,
            "gate_reason": "strict_public_validation_improvement" if deployed else "no_strict_public_validation_improvement",
            "output_dir": str(output),
            "cpu_seconds": receipt.cpu_seconds,
            "wall_seconds": receipt.wall_seconds,
            "peak_rss_bytes": receipt.peak_rss_bytes,
        }
        state["rounds"].append(record)
        state["candidate_count"] += 1
        state["cpu_seconds"] += receipt.cpu_seconds
        state["wall_seconds"] += receipt.wall_seconds
        state["peak_rss_bytes"] = max(int(state["peak_rss_bytes"]), receipt.peak_rss_bytes)
        state["validation_file_reads"] += receipt.validation_file_reads
        state["validation_metric_evaluations"] += receipt.validation_metric_evaluations
        state["validation_usage"].append(
            {
                "profile": package.profile,
                "task": package.task,
                "policy": policy,
                "round": round_number,
                "candidate": stage_id,
                "purpose": "candidate_gate",
                "file_reads": receipt.validation_file_reads,
                "metric_evaluations": receipt.validation_metric_evaluations,
                "cumulative_file_reads": state["validation_file_reads"],
                "cumulative_metric_evaluations": state["validation_metric_evaluations"],
                "validation_sha256": package.validation_sha256,
                "used_for_training": False,
                "used_for_preprocessing_fit": False,
            }
        )
        if deployed:
            state["accepted_count"] += 1
            state["stable_checkpoint"] = str(output / "checkpoint.npz")
            state["stable_sha256"] = receipt.checkpoint_sha256
            state["stable_metric"] = metric
        _persist(runtime_dir, state)
    return _result(state)


def validate_policy_result(runtime_dir: Path, expected_rounds: int = 10, minimum_candidates: int = 3) -> dict[str, Any]:
    """Machine-check a persisted policy result, including its accepted-only parent chain."""

    runtime_dir = Path(runtime_dir)
    state = json.loads((runtime_dir / "state.json").read_text(encoding="utf-8"))
    rounds = state.get("rounds", [])
    if len(rounds) != expected_rounds:
        raise ValueError(f"expected {expected_rounds} rounds, found {len(rounds)}")
    if [row.get("round") for row in rounds] != list(range(1, expected_rounds + 1)):
        raise ValueError("round sequence is not contiguous")
    candidates = [row for row in rounds if row.get("kind") == "candidate"]
    if len(candidates) < minimum_candidates:
        raise ValueError(f"minimum candidates not met: {len(candidates)} < {minimum_candidates}")
    stable_sha = state["initial_sha256"]
    for row in candidates:
        if row["parent_sha256"] != stable_sha:
            raise ValueError("candidate parent chain includes an unaccepted or unknown checkpoint")
        if row["deployed"]:
            stable_sha = row["checkpoint_sha256"]
    if stable_sha != state["stable_sha256"]:
        raise ValueError("final stable checkpoint does not match accepted parent chain")
    validation_rows = [json.loads(line) for line in (runtime_dir / "validation-usage.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if len(validation_rows) != len(candidates):
        raise ValueError("validation usage ledger does not match candidate count")
    if any(row.get("used_for_training") or row.get("used_for_preprocessing_fit") for row in validation_rows):
        raise ValueError("validation leakage recorded")
    return {
        "valid": True,
        "profile": state["profile"],
        "policy": state["policy"],
        "rounds": len(rounds),
        "candidates": len(candidates),
        "accepted": sum(bool(row["deployed"]) for row in candidates),
        "round_semantics": state["round_semantics"],
        "real_drift_stream": state["real_drift_stream"],
        "official_package": state["official_package"],
        "official_scoring_ready": state["official_scoring_ready"],
    }

