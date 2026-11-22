"""Immutable state contract for sequential drift monitoring."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Any


class ReferenceStatus(str, Enum):
    CALIBRATING = "calibrating"
    STABLE = "stable"
    WARNING = "warning"
    CONFIRMED = "confirmed"
    RECOVERY = "recovery"
    REBASE_PENDING = "rebase_pending"
    STABLE_NEW_BASELINE = "stable_new_baseline"


class Observation(str, Enum):
    NO_DRIFT_DETECTED = "no_drift_detected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    STABLE = "stable"
    WARNING = "warning"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class StateMachineConfig:
    calibration_min_windows: int = 3
    confirmation_windows: int = 2
    recovery_windows: int = 2
    rebase_min_windows: int = 3
    stable_delay_windows: int = 1

    def __post_init__(self) -> None:
        values = (
            self.calibration_min_windows,
            self.confirmation_windows,
            self.recovery_windows,
            self.rebase_min_windows,
        )
        if any(type(value) is not int or value < 1 for value in values):
            raise ValueError("state machine window counts must be positive integers")
        if type(self.stable_delay_windows) is not int or self.stable_delay_windows < 0:
            raise ValueError("stable delay must be a nonnegative integer")


@dataclass(frozen=True)
class AlphaSpending:
    alpha_run: float
    horizon: int | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha_run) or not 0.0 < self.alpha_run <= 1.0:
            raise ValueError("alpha_run must be in (0, 1]")
        if self.horizon is not None and (type(self.horizon) is not int or self.horizon < 1):
            raise ValueError("horizon must be a positive integer")

    def alpha_for_look(self, look_index: int) -> float:
        if type(look_index) is not int or look_index < 1:
            raise ValueError("look index must be positive")
        if self.horizon is not None:
            if look_index > self.horizon:
                raise ValueError("look index exceeds the alpha-spending horizon")
            return self.alpha_run / self.horizon
        return self.alpha_run / (look_index * (look_index + 1.0))

    def spend(self, state: "DriftState") -> tuple[float, "DriftState"]:
        if not math.isclose(state.alpha_run, self.alpha_run, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("state alpha budget differs from spending policy")
        look_index = state.look_index + 1
        allocation = self.alpha_for_look(look_index)
        spent = state.alpha_spent + allocation
        if spent > self.alpha_run + 1e-12:
            raise ValueError("alpha-spending budget exceeded")
        return allocation, replace(state, look_index=look_index, alpha_spent=spent)


@dataclass(frozen=True)
class DriftState:
    status: ReferenceStatus
    reference_epoch: int
    alpha_run: float
    alpha_spent: float
    look_index: int
    active_reference_ids: tuple[str, ...]
    candidate_reference_ids: tuple[str, ...]
    quarantine_ids: tuple[str, ...]
    rejected_window_ids: tuple[str, ...]
    seen_window_ids: tuple[str, ...]
    warning_streak: int
    recovery_streak: int
    non_admissible_window_ids: tuple[str, ...] = ()

    @classmethod
    def initial(cls, *, alpha_run: float) -> "DriftState":
        if not math.isfinite(alpha_run) or not 0.0 < alpha_run <= 1.0:
            raise ValueError("alpha_run must be in (0, 1]")
        return cls(
            status=ReferenceStatus.CALIBRATING,
            reference_epoch=0,
            alpha_run=float(alpha_run),
            alpha_spent=0.0,
            look_index=0,
            active_reference_ids=(),
            candidate_reference_ids=(),
            quarantine_ids=(),
            rejected_window_ids=(),
            seen_window_ids=(),
            warning_streak=0,
            recovery_streak=0,
            non_admissible_window_ids=(),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": "brace-formal.drift-state.v1",
            "status": self.status.value,
            "reference_epoch": self.reference_epoch,
            "alpha_run": self.alpha_run,
            "alpha_spent": self.alpha_spent,
            "look_index": self.look_index,
            "active_reference_ids": list(self.active_reference_ids),
            "candidate_reference_ids": list(self.candidate_reference_ids),
            "quarantine_ids": list(self.quarantine_ids),
            "rejected_window_ids": list(self.rejected_window_ids),
            "seen_window_ids": list(self.seen_window_ids),
            "warning_streak": self.warning_streak,
            "recovery_streak": self.recovery_streak,
            "non_admissible_window_ids": list(self.non_admissible_window_ids),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DriftState":
        if payload.get("format") != "brace-formal.drift-state.v1":
            raise ValueError("drift state format is invalid")
        try:
            state = cls(
                status=ReferenceStatus(str(payload["status"])),
                reference_epoch=int(payload["reference_epoch"]),
                alpha_run=float(payload["alpha_run"]),
                alpha_spent=float(payload["alpha_spent"]),
                look_index=int(payload["look_index"]),
                active_reference_ids=tuple(str(item) for item in payload["active_reference_ids"]),
                candidate_reference_ids=tuple(
                    str(item) for item in payload["candidate_reference_ids"]
                ),
                quarantine_ids=tuple(str(item) for item in payload["quarantine_ids"]),
                rejected_window_ids=tuple(str(item) for item in payload["rejected_window_ids"]),
                seen_window_ids=tuple(str(item) for item in payload["seen_window_ids"]),
                warning_streak=int(payload["warning_streak"]),
                recovery_streak=int(payload["recovery_streak"]),
                non_admissible_window_ids=tuple(
                    str(item) for item in payload.get("non_admissible_window_ids", ())
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("drift state payload is invalid") from exc
        if (
            state.reference_epoch < 0
            or state.look_index < 0
            or state.warning_streak < 0
            or state.recovery_streak < 0
            or not 0.0 <= state.alpha_spent <= state.alpha_run <= 1.0
        ):
            raise ValueError("drift state values are invalid")
        collections = (
            state.active_reference_ids,
            state.candidate_reference_ids,
            state.quarantine_ids,
            state.rejected_window_ids,
            state.seen_window_ids,
            state.non_admissible_window_ids,
        )
        if any(not item for values in collections for item in values):
            raise ValueError("drift state window IDs are invalid")
        if len(state.seen_window_ids) != len(set(state.seen_window_ids)):
            raise ValueError("drift state contains duplicate window IDs")
        pools = (
            set(state.active_reference_ids),
            set(state.candidate_reference_ids),
            set(state.quarantine_ids),
            set(state.rejected_window_ids),
            set(state.non_admissible_window_ids),
        )
        if any(
            pools[left].intersection(pools[right])
            for left in range(len(pools))
            for right in range(left + 1, len(pools))
        ):
            raise ValueError("drift state reference pools overlap")
        if not set().union(*pools).issubset(set(state.seen_window_ids)):
            raise ValueError("drift state pools contain unseen windows")
        return state


class ReferenceStateMachine:
    def __init__(self, config: StateMachineConfig | None = None) -> None:
        self.config = config or StateMachineConfig()

    def observe(
        self,
        state: DriftState,
        window_id: str,
        observation: Observation,
        *,
        candidate_stable: bool = False,
        data_quality_ok: bool = True,
    ) -> DriftState:
        if not isinstance(window_id, str) or not window_id:
            raise ValueError("window ID must be a nonempty string")
        if window_id in state.seen_window_ids:
            raise ValueError("window was already observed")
        if not isinstance(observation, Observation):
            raise ValueError("observation is invalid")
        updated = replace(state, seen_window_ids=(*state.seen_window_ids, window_id))
        if not data_quality_ok:
            return replace(
                updated,
                rejected_window_ids=(*state.rejected_window_ids, window_id),
            )
        if observation in {
            Observation.NO_DRIFT_DETECTED,
            Observation.INSUFFICIENT_EVIDENCE,
        }:
            return replace(
                updated,
                non_admissible_window_ids=(*state.non_admissible_window_ids, window_id),
            )
        if updated.status is ReferenceStatus.CALIBRATING:
            if observation is not Observation.STABLE:
                return replace(
                    updated,
                    candidate_reference_ids=(),
                    warning_streak=1,
                )
            candidates = (*updated.candidate_reference_ids, window_id)
            if len(candidates) < self.config.calibration_min_windows:
                return replace(updated, candidate_reference_ids=candidates)
            return replace(
                updated,
                status=ReferenceStatus.STABLE,
                reference_epoch=1,
                active_reference_ids=candidates,
                candidate_reference_ids=(),
                quarantine_ids=(),
                warning_streak=0,
                recovery_streak=0,
            )

        status = updated.status
        if status is ReferenceStatus.STABLE_NEW_BASELINE:
            status = ReferenceStatus.STABLE
            updated = replace(updated, status=status)

        if status is ReferenceStatus.STABLE:
            if observation is Observation.STABLE:
                quarantine = (*updated.quarantine_ids, window_id)
                active = updated.active_reference_ids
                while len(quarantine) > self.config.stable_delay_windows:
                    active = (*active, quarantine[0])
                    quarantine = quarantine[1:]
                return replace(updated, active_reference_ids=active, quarantine_ids=quarantine)
            if observation is Observation.CONFIRMED:
                return replace(
                    updated,
                    status=ReferenceStatus.CONFIRMED,
                    quarantine_ids=(),
                    warning_streak=self.config.confirmation_windows,
                )
            return replace(
                updated,
                status=ReferenceStatus.WARNING,
                quarantine_ids=(),
                warning_streak=1,
            )

        if status is ReferenceStatus.WARNING:
            if observation is Observation.STABLE:
                return replace(
                    updated,
                    status=ReferenceStatus.RECOVERY,
                    recovery_streak=1,
                    warning_streak=0,
                )
            streak = updated.warning_streak + 1
            if observation is Observation.CONFIRMED or streak >= self.config.confirmation_windows:
                return replace(
                    updated,
                    status=ReferenceStatus.CONFIRMED,
                    warning_streak=streak,
                    recovery_streak=0,
                )
            return replace(updated, warning_streak=streak)

        if status is ReferenceStatus.CONFIRMED:
            if observation is Observation.STABLE:
                return replace(
                    updated,
                    status=ReferenceStatus.RECOVERY,
                    recovery_streak=1,
                    warning_streak=0,
                    candidate_reference_ids=(),
                )
            if candidate_stable:
                return replace(
                    updated,
                    status=ReferenceStatus.REBASE_PENDING,
                    candidate_reference_ids=(window_id,),
                    recovery_streak=0,
                )
            return updated

        if status is ReferenceStatus.RECOVERY:
            if observation is Observation.STABLE:
                streak = updated.recovery_streak + 1
                if streak >= self.config.recovery_windows:
                    return replace(
                        updated,
                        status=ReferenceStatus.STABLE,
                        recovery_streak=0,
                        warning_streak=0,
                        candidate_reference_ids=(),
                        quarantine_ids=(),
                    )
                return replace(updated, recovery_streak=streak)
            if observation is Observation.CONFIRMED:
                return replace(
                    updated,
                    status=ReferenceStatus.CONFIRMED,
                    recovery_streak=0,
                    warning_streak=self.config.confirmation_windows,
                )
            return replace(
                updated,
                status=ReferenceStatus.WARNING,
                recovery_streak=0,
                warning_streak=1,
            )

        if status is ReferenceStatus.REBASE_PENDING:
            if observation is Observation.STABLE:
                return replace(
                    updated,
                    status=ReferenceStatus.RECOVERY,
                    candidate_reference_ids=(),
                    recovery_streak=1,
                )
            if not candidate_stable:
                return updated
            candidates = (*updated.candidate_reference_ids, window_id)
            if len(candidates) < self.config.rebase_min_windows:
                return replace(updated, candidate_reference_ids=candidates)
            return replace(
                updated,
                status=ReferenceStatus.STABLE_NEW_BASELINE,
                reference_epoch=updated.reference_epoch + 1,
                active_reference_ids=candidates,
                candidate_reference_ids=(),
                quarantine_ids=(),
                warning_streak=0,
                recovery_streak=0,
            )
        raise ValueError("unsupported reference state")
