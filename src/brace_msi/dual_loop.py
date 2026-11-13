"""Transactional controller for BRACE-MSI's controlled dual loop."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error


ALLOWED_ACTIONS = {
    "NOOP",
    "RECALIBRATE",
    "INCREMENTAL_UPDATE",
    "REPLAY_REFIT",
    "FAMILY_SWITCH",
    "BOUNDED_HPO",
    "REGISTERED_PLUGIN",
    "ROLLBACK",
}


def _plain_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    copied = dict(value)
    json.dumps(copied, sort_keys=True)
    return copied


@dataclass(frozen=True)
class DecisionContext:
    round_index: int
    batch_id: str
    stable_model_id: str
    submitted_prediction_digest: str
    labels_open: bool
    remaining_cpu_seconds: float
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.round_index < 1:
            raise ValueError("round_index must be positive")
        if not self.batch_id or not self.stable_model_id:
            raise ValueError("batch_id and stable_model_id are required")
        if not self.submitted_prediction_digest:
            raise ValueError("prediction must be submitted before decision")
        if not self.labels_open:
            raise ValueError("labels must be legally open before decision")
        if self.remaining_cpu_seconds < 0:
            raise ValueError("remaining CPU budget cannot be negative")
        object.__setattr__(self, "evidence", _plain_mapping(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "batch_id": self.batch_id,
            "stable_model_id": self.stable_model_id,
            "submitted_prediction_digest": self.submitted_prediction_digest,
            "labels_open": self.labels_open,
            "remaining_cpu_seconds": self.remaining_cpu_seconds,
            "evidence": dict(self.evidence),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecisionContext":
        return cls(**dict(value))


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    action: str
    mechanism: str
    estimated_cpu_seconds: float
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.mechanism:
            raise ValueError("candidate_id and mechanism are required")
        normalized_action = self.action.upper()
        if normalized_action not in ALLOWED_ACTIONS or normalized_action == "NOOP":
            raise ValueError("candidate action is not an executable whitelist action")
        if self.estimated_cpu_seconds < 0:
            raise ValueError("candidate CPU estimate cannot be negative")
        object.__setattr__(self, "action", normalized_action)
        object.__setattr__(self, "parameters", _plain_mapping(self.parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "mechanism": self.mechanism,
            "estimated_cpu_seconds": self.estimated_cpu_seconds,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandidateSpec":
        return cls(**dict(value))


@dataclass(frozen=True)
class DecisionPlan:
    round_index: int
    candidates: tuple[CandidateSpec, ...]
    reason: str
    escalation_evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "reason": self.reason,
            "escalation_evidence": self.escalation_evidence,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecisionPlan":
        return cls(
            round_index=int(value["round_index"]),
            candidates=tuple(CandidateSpec.from_dict(item) for item in value["candidates"]),
            reason=str(value["reason"]),
            escalation_evidence=value.get("escalation_evidence"),
        )


@dataclass(frozen=True)
class CandidateOutcome:
    candidate_id: str
    completed: bool
    accepted: bool
    gate_gain: float | None
    cpu_seconds: float
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required")
        if self.cpu_seconds < 0:
            raise ValueError("cpu_seconds cannot be negative")
        if self.accepted and not self.completed:
            raise ValueError("an incomplete candidate cannot be accepted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "completed": self.completed,
            "accepted": self.accepted,
            "gate_gain": self.gate_gain,
            "cpu_seconds": self.cpu_seconds,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandidateOutcome":
        return cls(**dict(value))


@dataclass(frozen=True)
class PolicyState:
    next_round: int = 1
    committed_batch_ids: tuple[str, ...] = ()
    total_candidates: int = 0
    real_experiment_count: int = 0
    stable_model_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_round": self.next_round,
            "committed_batch_ids": list(self.committed_batch_ids),
            "total_candidates": self.total_candidates,
            "real_experiment_count": self.real_experiment_count,
            "stable_model_id": self.stable_model_id,
        }


@dataclass(frozen=True)
class RoundCommit:
    round_index: int
    batch_id: str
    decision: str
    deployed_model_id: str
    predecessor_model_id: str
    submitted_prediction_digest: str
    candidates: tuple[CandidateSpec, ...]
    outcomes: tuple[CandidateOutcome, ...]
    commit_hash: str

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        result = {
            "round_index": self.round_index,
            "batch_id": self.batch_id,
            "decision": self.decision,
            "deployed_model_id": self.deployed_model_id,
            "predecessor_model_id": self.predecessor_model_id,
            "submitted_prediction_digest": self.submitted_prediction_digest,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }
        if include_hash:
            result["commit_hash"] = self.commit_hash
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RoundCommit":
        return cls(
            round_index=int(value["round_index"]),
            batch_id=str(value["batch_id"]),
            decision=str(value["decision"]),
            deployed_model_id=str(value["deployed_model_id"]),
            predecessor_model_id=str(value["predecessor_model_id"]),
            submitted_prediction_digest=str(value["submitted_prediction_digest"]),
            candidates=tuple(CandidateSpec.from_dict(item) for item in value["candidates"]),
            outcomes=tuple(CandidateOutcome.from_dict(item) for item in value["outcomes"]),
            commit_hash=str(value["commit_hash"]),
        )


@dataclass(frozen=True)
class ShadowReward:
    primary_delta: float
    confidence: str
    details: Mapping[str, float]
    cpu_seconds: float


@dataclass
class _PendingRound:
    context: DecisionContext
    plan: DecisionPlan | None = None
    outcomes: dict[str, CandidateOutcome] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": self.context.to_dict(),
            "plan": None if self.plan is None else self.plan.to_dict(),
            "outcomes": {key: value.to_dict() for key, value in sorted(self.outcomes.items())},
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "_PendingRound":
        plan_value = value.get("plan")
        return cls(
            context=DecisionContext.from_dict(value["context"]),
            plan=None if plan_value is None else DecisionPlan.from_dict(plan_value),
            outcomes={key: CandidateOutcome.from_dict(item) for key, item in value["outcomes"].items()},
        )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _commit_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DualLoopController:
    def __init__(
        self,
        root: Path,
        *,
        minimum_gate_gain: float,
        max_rounds: int = 10,
        max_candidates_per_round: int = 2,
        max_total_candidates: int = 8,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.commits_root = self.root / "commits"
        self.commits_root.mkdir(exist_ok=True)
        self.minimum_gate_gain = float(minimum_gate_gain)
        self.max_rounds = int(max_rounds)
        self.max_candidates_per_round = int(max_candidates_per_round)
        self.max_total_candidates = int(max_total_candidates)
        if self.max_candidates_per_round != 2:
            raise ValueError("controlled dual loop requires a two-candidate hard ceiling")
        self._commits = self._load_commits()
        self._state = self._derive_state(self._commits)
        self._pending = self._load_pending()
        if self._pending is not None and self._pending.context.round_index < self._state.next_round:
            self._pending = None
            self._remove_pending()

    @property
    def state(self) -> PolicyState:
        return self._state

    @property
    def pending_plan(self) -> DecisionPlan | None:
        return None if self._pending is None else self._pending.plan

    def _load_commits(self) -> list[RoundCommit]:
        commits: list[RoundCommit] = []
        for path in sorted(self.commits_root.glob("round-*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            commit = RoundCommit.from_dict(value)
            expected = _commit_digest(commit.to_dict(include_hash=False))
            if expected != commit.commit_hash:
                raise RuntimeError(f"commit hash mismatch: {path}")
            commits.append(commit)
        for expected_round, commit in enumerate(commits, start=1):
            if commit.round_index != expected_round:
                raise RuntimeError("committed rounds are not a contiguous prefix")
        return commits

    @staticmethod
    def _derive_state(commits: list[RoundCommit]) -> PolicyState:
        if not commits:
            return PolicyState()
        return PolicyState(
            next_round=commits[-1].round_index + 1,
            committed_batch_ids=tuple(commit.batch_id for commit in commits),
            total_candidates=sum(len(commit.candidates) for commit in commits),
            real_experiment_count=sum(1 for commit in commits if commit.candidates),
            stable_model_id=commits[-1].deployed_model_id,
        )

    def _load_pending(self) -> _PendingRound | None:
        path = self.root / "pending.json"
        if not path.is_file():
            return None
        return _PendingRound.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _persist_pending(self) -> None:
        if self._pending is None:
            return
        _atomic_write_json(self.root / "pending.json", self._pending.to_dict())

    def _persist_state(self) -> None:
        _atomic_write_json(self.root / "state.json", self._state.to_dict())

    def _remove_pending(self) -> None:
        path = self.root / "pending.json"
        if path.exists():
            path.unlink()

    def begin_round(self, context: DecisionContext) -> None:
        if self._pending is not None:
            raise RuntimeError("a decision round is already open")
        if context.batch_id in self._state.committed_batch_ids:
            raise ValueError("batch is already committed")
        if context.round_index != self._state.next_round:
            raise ValueError("round must extend the committed prefix")
        if context.round_index > self.max_rounds:
            raise ValueError("round exceeds configured ten-batch horizon")
        if self._state.stable_model_id is not None and context.stable_model_id != self._state.stable_model_id:
            raise ValueError("context stable model does not match committed state")
        self._pending = _PendingRound(context=context)
        self._persist_pending()

    def plan_first_candidate(self, candidate: CandidateSpec | None, *, reason: str) -> DecisionPlan:
        pending = self._require_pending()
        if pending.plan is not None:
            raise RuntimeError("round is already planned")
        candidates = () if candidate is None else (candidate,)
        if candidate is not None:
            self._check_candidate_budget(candidate, pending, extra_candidates=1)
        pending.plan = DecisionPlan(
            round_index=pending.context.round_index,
            candidates=candidates,
            reason=reason,
        )
        self._persist_pending()
        return pending.plan

    def record_candidate_outcome(self, outcome: CandidateOutcome) -> None:
        pending = self._require_pending()
        if pending.plan is None:
            raise RuntimeError("candidate plan is not established")
        planned_ids = {candidate.candidate_id for candidate in pending.plan.candidates}
        if outcome.candidate_id not in planned_ids:
            raise ValueError("outcome does not belong to the current plan")
        if outcome.candidate_id in pending.outcomes:
            raise RuntimeError("candidate outcome is already recorded")
        pending.outcomes[outcome.candidate_id] = outcome
        self._persist_pending()

    def escalate_second_candidate(
        self,
        candidate: CandidateSpec,
        *,
        new_evidence: str,
        budget_remaining: bool,
    ) -> DecisionPlan:
        pending = self._require_pending()
        if pending.plan is None or not pending.plan.candidates:
            raise RuntimeError("first candidate must be planned")
        if len(pending.plan.candidates) >= self.max_candidates_per_round:
            raise RuntimeError("round already contains two candidates")
        first = pending.plan.candidates[0]
        first_outcome = pending.outcomes.get(first.candidate_id)
        if first_outcome is None:
            raise RuntimeError("first outcome is required before escalation")
        if first_outcome.completed and first_outcome.gate_gain is not None and first_outcome.gate_gain >= self.minimum_gate_gain:
            raise RuntimeError("first candidate produced sufficient benefit")
        if candidate.mechanism == first.mechanism:
            raise ValueError("second candidate must use a different mechanism")
        if not new_evidence.strip():
            raise ValueError("second candidate requires new evidence")
        if not budget_remaining:
            raise ValueError("second candidate requires remaining budget")
        self._check_candidate_budget(candidate, pending, extra_candidates=1)
        pending.plan = DecisionPlan(
            round_index=pending.plan.round_index,
            candidates=(*pending.plan.candidates, candidate),
            reason=pending.plan.reason,
            escalation_evidence=new_evidence,
        )
        self._persist_pending()
        return pending.plan

    def _check_candidate_budget(
        self,
        candidate: CandidateSpec,
        pending: _PendingRound,
        *,
        extra_candidates: int,
    ) -> None:
        planned_count = 0 if pending.plan is None else len(pending.plan.candidates)
        if self._state.total_candidates + planned_count + extra_candidates > self.max_total_candidates:
            raise ValueError("total candidate budget is exhausted")
        used_cpu = sum(outcome.cpu_seconds for outcome in pending.outcomes.values())
        if used_cpu + candidate.estimated_cpu_seconds > pending.context.remaining_cpu_seconds:
            raise ValueError("round CPU budget is insufficient")

    def commit_round(self, *, decision: str, deployed_model_id: str) -> RoundCommit:
        pending = self._require_pending()
        if pending.plan is None:
            raise RuntimeError("round has no decision plan")
        missing = [
            candidate.candidate_id
            for candidate in pending.plan.candidates
            if candidate.candidate_id not in pending.outcomes
        ]
        if missing:
            raise RuntimeError(f"candidate outcomes are missing: {missing}")
        outcomes = tuple(pending.outcomes[candidate.candidate_id] for candidate in pending.plan.candidates)
        if decision == "deploy" and not any(outcome.accepted for outcome in outcomes):
            raise ValueError("deploy decision requires an accepted candidate")
        if decision not in {"deploy", "reject", "rollback", "noop"}:
            raise ValueError("unsupported commit decision")
        base = {
            "round_index": pending.context.round_index,
            "batch_id": pending.context.batch_id,
            "decision": decision,
            "deployed_model_id": deployed_model_id,
            "predecessor_model_id": pending.context.stable_model_id,
            "submitted_prediction_digest": pending.context.submitted_prediction_digest,
            "candidates": [candidate.to_dict() for candidate in pending.plan.candidates],
            "outcomes": [outcome.to_dict() for outcome in outcomes],
        }
        commit = RoundCommit(
            round_index=pending.context.round_index,
            batch_id=pending.context.batch_id,
            decision=decision,
            deployed_model_id=deployed_model_id,
            predecessor_model_id=pending.context.stable_model_id,
            submitted_prediction_digest=pending.context.submitted_prediction_digest,
            candidates=pending.plan.candidates,
            outcomes=outcomes,
            commit_hash=_commit_digest(base),
        )
        commit_path = self.commits_root / f"round-{commit.round_index:03d}.json"
        if commit_path.exists():
            raise RuntimeError("round commit already exists")
        _atomic_write_json(commit_path, commit.to_dict())
        self._commits.append(commit)
        self._state = self._derive_state(self._commits)
        self._persist_state()
        self._pending = None
        self._remove_pending()
        return commit

    def _require_pending(self) -> _PendingRound:
        if self._pending is None:
            raise RuntimeError("no decision round is open")
        return self._pending


def paired_shadow_reward(
    *,
    task_kind: str,
    y_true: np.ndarray,
    deployed_predictions: np.ndarray,
    predecessor_predictions: np.ndarray | None,
    cpu_seconds: float,
    historical_baseline: float | None = None,
    deployed_metric: float | None = None,
    bootstrap_samples: int = 200,
) -> ShadowReward:
    true = np.asarray(y_true).reshape(-1)
    deployed = np.asarray(deployed_predictions).reshape(-1)
    if true.shape != deployed.shape:
        raise ValueError("deployed predictions must align with labels")
    if cpu_seconds < 0:
        raise ValueError("shadow CPU cost cannot be negative")
    if predecessor_predictions is None:
        if historical_baseline is None or deployed_metric is None:
            raise ValueError("historical fallback requires baseline and deployed metric")
        if task_kind == "classification":
            delta = float(deployed_metric - historical_baseline)
        elif task_kind == "regression":
            delta = float(historical_baseline - deployed_metric)
        else:
            raise ValueError("task_kind must be classification or regression")
        return ShadowReward(
            primary_delta=delta,
            confidence="historical_low",
            details={"historical_baseline": float(historical_baseline), "deployed_metric": float(deployed_metric)},
            cpu_seconds=float(cpu_seconds),
        )

    predecessor = np.asarray(predecessor_predictions).reshape(-1)
    if predecessor.shape != true.shape:
        raise ValueError("shadow predictions must use the identical sample set")
    if not np.all(np.isfinite(deployed)) or not np.all(np.isfinite(predecessor)):
        raise ValueError("shadow predictions must be finite")

    if task_kind == "classification":
        deployed_primary = float(f1_score(true, deployed, average="macro", zero_division=0))
        predecessor_primary = float(f1_score(true, predecessor, average="macro", zero_division=0))
        primary_delta = deployed_primary - predecessor_primary
        details = {
            "macro_f1_delta": primary_delta,
            "accuracy_delta": float(accuracy_score(true, deployed) - accuracy_score(true, predecessor)),
        }

        def statistic(indices: np.ndarray) -> float:
            return float(
                f1_score(true[indices], deployed[indices], average="macro", zero_division=0)
                - f1_score(true[indices], predecessor[indices], average="macro", zero_division=0)
            )

    elif task_kind == "regression":
        deployed_rmse = float(mean_squared_error(true, deployed) ** 0.5)
        predecessor_rmse = float(mean_squared_error(true, predecessor) ** 0.5)
        primary_delta = predecessor_rmse - deployed_rmse
        details = {
            "rmse_improvement": primary_delta,
            "mae_improvement": float(
                mean_absolute_error(true, predecessor) - mean_absolute_error(true, deployed)
            ),
        }

        def statistic(indices: np.ndarray) -> float:
            old_rmse = float(mean_squared_error(true[indices], predecessor[indices]) ** 0.5)
            new_rmse = float(mean_squared_error(true[indices], deployed[indices]) ** 0.5)
            return old_rmse - new_rmse

    else:
        raise ValueError("task_kind must be classification or regression")

    if true.size >= 2 and bootstrap_samples > 0:
        rng = np.random.default_rng(20261113)
        samples = np.asarray(
            [statistic(rng.integers(0, true.size, size=true.size)) for _ in range(bootstrap_samples)],
            dtype=np.float64,
        )
        details["paired_ci_low"] = float(np.quantile(samples, 0.025))
        details["paired_ci_high"] = float(np.quantile(samples, 0.975))
    return ShadowReward(
        primary_delta=float(primary_delta),
        confidence="paired",
        details=details,
        cpu_seconds=float(cpu_seconds),
    )
