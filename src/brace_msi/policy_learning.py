"""Lightweight, auditable action-value statistics and Pareto planning."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class EvidenceState:
    task_kind: str
    performance_drop: float
    drift_score: float
    failure_streak: int
    remaining_budget_fraction: float
    action_uncertainty: float

    def __post_init__(self) -> None:
        if self.task_kind not in {"classification", "regression"}:
            raise ValueError("task_kind must be classification or regression")
        if self.failure_streak < 0:
            raise ValueError("failure_streak cannot be negative")
        for name in ("drift_score", "remaining_budget_fraction", "action_uncertainty"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")

    @staticmethod
    def _bucket(value: float, width: float) -> float:
        return round(round(float(value) / width) * width, 6)

    def profile(self) -> dict[str, Any]:
        """Identity-free evidence profile used as the statistics key."""
        return {
            "task_kind": self.task_kind,
            "performance_drop": self._bucket(self.performance_drop, 0.05),
            "drift_score": self._bucket(self.drift_score, 0.1),
            "failure_streak": min(self.failure_streak, 3),
            "remaining_budget_fraction": self._bucket(self.remaining_budget_fraction, 0.1),
            "action_uncertainty": self._bucket(self.action_uncertainty, 0.1),
        }

    @property
    def profile_key(self) -> str:
        payload = json.dumps(self.profile(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:20]


@dataclass(frozen=True)
class ActionObservation:
    action: str
    primary_delta: float
    cpu_seconds: float
    peak_memory_mb: float
    token_count: int
    model_bytes: int
    accepted: bool
    succeeded: bool
    reward_source: str
    attribution_confidence: str
    round_index: int

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("action is required")
        if self.cpu_seconds < 0 or self.peak_memory_mb < 0 or self.token_count < 0 or self.model_bytes < 0:
            raise ValueError("resource costs cannot be negative")
        if self.round_index < 1:
            raise ValueError("round_index must be positive")
        if self.reward_source not in {"delayed_shadow", "historical_fallback", "immediate_gate"}:
            raise ValueError("unsupported reward source")
        if self.attribution_confidence not in {"paired", "historical_low", "gate_low"}:
            raise ValueError("unsupported attribution confidence")


@dataclass(frozen=True)
class ActionStats:
    attempt_count: int
    reward_count: int
    high_confidence_count: int
    accepted_count: int
    failure_count: int
    mean_reward: float
    estimated_reward: float
    reward_lower: float
    reward_upper: float
    mean_cpu_seconds: float
    mean_peak_memory_mb: float
    mean_token_count: float
    mean_model_bytes: float


@dataclass(frozen=True)
class ParetoAction:
    action: str
    expected_delta: float
    reward_lower: float
    reward_upper: float
    cpu_seconds: float
    peak_memory_mb: float
    token_count: float
    model_bytes: float
    support_count: int
    attribution_confidence: str


def _new_record() -> dict[str, Any]:
    return {
        "attempt_count": 0,
        "reward_count": 0,
        "high_confidence_count": 0,
        "accepted_count": 0,
        "failure_count": 0,
        "reward_weight_sum": 0.0,
        "reward_weighted_sum": 0.0,
        "reward_weighted_square_sum": 0.0,
        "cpu_sum": 0.0,
        "memory_sum": 0.0,
        "token_sum": 0.0,
        "model_bytes_sum": 0.0,
    }


class ActionValueTable:
    def __init__(
        self,
        path: Path | None = None,
        *,
        weak_priors: Mapping[str, Mapping[str, float]] | None = None,
    ) -> None:
        self.path = None if path is None else Path(path)
        self.weak_priors = {
            str(action): {
                "mean_reward": float(values.get("mean_reward", 0.0)),
                "pseudo_count": float(values.get("pseudo_count", 0.0)),
            }
            for action, values in (weak_priors or {}).items()
        }
        for values in self.weak_priors.values():
            if not 0.0 <= values["pseudo_count"] <= 0.5:
                raise ValueError("weak-prior pseudo_count must be between zero and 0.5")
        self._records: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
        if self.path is not None and self.path.is_file():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._records = payload.get("records", {})
            persisted_priors = payload.get("weak_priors")
            if persisted_priors is not None:
                self.weak_priors = persisted_priors

    def record(self, task_id: str, evidence: EvidenceState, observation: ActionObservation) -> None:
        if not task_id:
            raise ValueError("task_id is required for isolated storage")
        task_records = self._records.setdefault(str(task_id), {})
        profile_records = task_records.setdefault(evidence.profile_key, {})
        record = profile_records.setdefault(observation.action, _new_record())
        record["attempt_count"] += 1
        record["accepted_count"] += int(observation.accepted)
        record["failure_count"] += int(not observation.succeeded)
        record["cpu_sum"] += float(observation.cpu_seconds)
        record["memory_sum"] += float(observation.peak_memory_mb)
        record["token_sum"] += int(observation.token_count)
        record["model_bytes_sum"] += int(observation.model_bytes)

        if observation.reward_source in {"delayed_shadow", "historical_fallback"}:
            weight = 1.0 if observation.attribution_confidence == "paired" else 0.25
            reward = float(observation.primary_delta)
            record["reward_count"] += 1
            record["high_confidence_count"] += int(observation.attribution_confidence == "paired")
            record["reward_weight_sum"] += weight
            record["reward_weighted_sum"] += weight * reward
            record["reward_weighted_square_sum"] += weight * reward * reward
        self._persist()

    def stats(self, task_id: str, evidence: EvidenceState, action: str) -> ActionStats:
        record = (
            self._records.get(str(task_id), {})
            .get(evidence.profile_key, {})
            .get(str(action), _new_record())
        )
        attempts = int(record["attempt_count"])
        rewards = int(record["reward_count"])
        weight_sum = float(record["reward_weight_sum"])
        mean_reward = (
            float(record["reward_weighted_sum"]) / weight_sum if weight_sum > 0 else 0.0
        )
        prior = self.weak_priors.get(str(action), {"mean_reward": 0.0, "pseudo_count": 0.0})
        pseudo = float(prior["pseudo_count"])
        estimated = (
            (float(record["reward_weighted_sum"]) + pseudo * float(prior["mean_reward"]))
            / (weight_sum + pseudo)
            if weight_sum + pseudo > 0
            else 0.0
        )
        if weight_sum > 0:
            variance = max(
                0.0,
                float(record["reward_weighted_square_sum"]) / weight_sum - mean_reward * mean_reward,
            )
            standard_error = math.sqrt(variance / max(weight_sum, 1.0))
            half_width = 1.96 * standard_error
        else:
            half_width = 1.0
        divisor = max(attempts, 1)
        return ActionStats(
            attempt_count=attempts,
            reward_count=rewards,
            high_confidence_count=int(record["high_confidence_count"]),
            accepted_count=int(record["accepted_count"]),
            failure_count=int(record["failure_count"]),
            mean_reward=mean_reward,
            estimated_reward=estimated,
            reward_lower=estimated - half_width,
            reward_upper=estimated + half_width,
            mean_cpu_seconds=float(record["cpu_sum"]) / divisor,
            mean_peak_memory_mb=float(record["memory_sum"]) / divisor,
            mean_token_count=float(record["token_sum"]) / divisor,
            mean_model_bytes=float(record["model_bytes_sum"]) / divisor,
        )

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        payload = {"schema_version": 1, "weak_priors": self.weak_priors, "records": self._records}
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)


def _cost(costs: Mapping[str, float], name: str) -> float:
    value = float(costs.get(name, 0.0))
    if value < 0:
        raise ValueError("estimated costs cannot be negative")
    return value


def _dominates(left: ParetoAction, right: ParetoAction) -> bool:
    no_worse = (
        left.expected_delta >= right.expected_delta
        and left.cpu_seconds <= right.cpu_seconds
        and left.peak_memory_mb <= right.peak_memory_mb
        and left.token_count <= right.token_count
        and left.model_bytes <= right.model_bytes
    )
    strictly_better = (
        left.expected_delta > right.expected_delta
        or left.cpu_seconds < right.cpu_seconds
        or left.peak_memory_mb < right.peak_memory_mb
        or left.token_count < right.token_count
        or left.model_bytes < right.model_bytes
    )
    return no_worse and strictly_better


def rank_actions(
    table: ActionValueTable,
    task_id: str,
    evidence: EvidenceState,
    actions: Sequence[str],
    estimated_costs: Mapping[str, Mapping[str, float]],
) -> tuple[ParetoAction, ...]:
    candidates: list[ParetoAction] = []
    for action in actions:
        stats = table.stats(task_id, evidence, action)
        costs = estimated_costs.get(action, {})
        candidates.append(
            ParetoAction(
                action=action,
                expected_delta=stats.estimated_reward,
                reward_lower=stats.reward_lower,
                reward_upper=stats.reward_upper,
                cpu_seconds=(stats.mean_cpu_seconds if stats.attempt_count else _cost(costs, "cpu_seconds")),
                peak_memory_mb=(
                    stats.mean_peak_memory_mb
                    if stats.attempt_count
                    else _cost(costs, "peak_memory_mb")
                ),
                token_count=(stats.mean_token_count if stats.attempt_count else _cost(costs, "token_count")),
                model_bytes=(stats.mean_model_bytes if stats.attempt_count else _cost(costs, "model_bytes")),
                support_count=stats.reward_count,
                attribution_confidence=(
                    "paired"
                    if stats.high_confidence_count > 0
                    else "historical_low"
                    if stats.reward_count > 0
                    else "prior"
                ),
            )
        )
    frontier = [
        candidate
        for candidate in candidates
        if not any(_dominates(other, candidate) for other in candidates if other is not candidate)
    ]
    frontier.sort(
        key=lambda item: (
            -item.expected_delta,
            item.cpu_seconds,
            item.peak_memory_mb,
            item.token_count,
            item.model_bytes,
            item.action,
        )
    )
    return tuple(frontier)
