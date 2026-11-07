"""Internal event protocol used before the official SDK is available.

Identifiers in this module are opaque internal strings. They deliberately do
not model or predict fields from the future competition SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol


class ProtocolMode(str, Enum):
    """Supported simulated batch interaction modes."""

    PREDICT_THEN_FEEDBACK = "predict_then_feedback"
    LABELED_TRAIN_THEN_PREDICT = "labeled_train_then_predict"


class ProtocolPhase(str, Enum):
    """Observable lifecycle phases for audit and tests."""

    NEW = "new"
    READY = "ready"
    TRAINING_AVAILABLE = "training_available"
    PREDICTION_REQUESTED = "prediction_requested"
    PREDICTION_SUBMITTED = "prediction_submitted"
    FEEDBACK_AVAILABLE = "feedback_available"
    FINISHED = "finished"


class ProtocolViolation(ValueError):
    """Raised when an event would violate the selected protocol."""


class EventProtocolAdapter(Protocol):
    """Internal boundary an official SDK mapping must implement."""

    @property
    def history(self) -> tuple[str, ...]: ...

    def open_task(self, task_id: str) -> None: ...
    def provide_training_batch(self, batch_id: str, sample_ids: Iterable[str]) -> None: ...
    def request_predictions(self, batch_id: str, sample_ids: Iterable[str]) -> None: ...
    def submit_predictions(self, batch_id: str, sample_ids: Iterable[str]) -> None: ...
    def provide_feedback(self, batch_id: str, sample_ids: Iterable[str]) -> None: ...
    def request_batch_commit(self, batch_id: str) -> None: ...
    def finish_task(self) -> None: ...


@dataclass(frozen=True)
class ProtocolSnapshot:
    """Immutable view of current state for audit consumers."""

    mode: ProtocolMode
    phase: ProtocolPhase
    task_id: str | None
    current_batch_id: str | None
    closed_batch_ids: tuple[str, ...]
    training_sample_ids: frozenset[str]
    predicted_sample_ids: frozenset[str]
    finished: bool


class SimulatedSdkAdapter:
    """Deterministic guard around the two documented internal protocols."""

    def __init__(self, mode: ProtocolMode) -> None:
        self._mode = ProtocolMode(mode)
        self._phase = ProtocolPhase.NEW
        self._task_id: str | None = None
        self._current_batch_id: str | None = None
        self._requested_sample_ids: tuple[str, ...] = ()
        self._closed_batch_ids: list[str] = []
        self._training_sample_ids: set[str] = set()
        self._predicted_sample_ids: set[str] = set()
        self._history: list[str] = []
        self._finished = False

    @property
    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    def open_task(self, task_id: str) -> None:
        if self._task_id is not None or self._finished:
            raise ProtocolViolation("task is already open or finished")
        self._task_id = self._normalize_identifier(task_id, "task ID")
        self._phase = ProtocolPhase.READY
        self._history.append("task_opened")

    def provide_training_batch(
        self, batch_id: str, sample_ids: Iterable[str]
    ) -> None:
        self._require_active_task()
        if self._mode is not ProtocolMode.LABELED_TRAIN_THEN_PREDICT:
            raise ProtocolViolation("training batches are not allowed in this mode")
        self._require_no_open_batch()
        normalized_batch = self._normalize_identifier(batch_id, "batch ID")
        normalized_samples = self._normalize_sample_ids(sample_ids)
        self._current_batch_id = normalized_batch
        self._training_sample_ids.update(normalized_samples)
        self._phase = ProtocolPhase.TRAINING_AVAILABLE
        self._history.append("training_available")

    def request_predictions(
        self, batch_id: str, sample_ids: Iterable[str]
    ) -> None:
        self._require_active_task()
        normalized_batch = self._normalize_identifier(batch_id, "batch ID")
        normalized_samples = self._normalize_sample_ids(sample_ids)

        if self._mode is ProtocolMode.PREDICT_THEN_FEEDBACK:
            self._require_no_open_batch()
        else:
            if self._current_batch_id is None:
                raise ProtocolViolation(
                    "a labeled training batch must be provided before prediction"
                )
            if self._phase is not ProtocolPhase.TRAINING_AVAILABLE:
                raise ProtocolViolation("batch is not ready for a prediction request")
            if normalized_batch != self._current_batch_id:
                raise ProtocolViolation(
                    f"batch {self._current_batch_id} is still open"
                )

        overlap = self._training_sample_ids.intersection(normalized_samples)
        if overlap:
            raise ProtocolViolation(
                "data leakage: scoring sample IDs are already in the training set"
            )

        if self._mode is ProtocolMode.PREDICT_THEN_FEEDBACK:
            self._current_batch_id = normalized_batch
        self._requested_sample_ids = normalized_samples
        self._phase = ProtocolPhase.PREDICTION_REQUESTED
        self._history.append("prediction_requested")

    def submit_predictions(
        self, batch_id: str, sample_ids: Iterable[str]
    ) -> None:
        self._require_active_task()
        normalized_batch = self._normalize_identifier(batch_id, "batch ID")
        normalized_samples = self._normalize_sample_ids(sample_ids)
        if (
            self._phase is not ProtocolPhase.PREDICTION_REQUESTED
            or normalized_batch != self._current_batch_id
            or normalized_samples != self._requested_sample_ids
        ):
            raise ProtocolViolation(
                "submission must match the requested batch and samples"
            )
        self._predicted_sample_ids.update(normalized_samples)
        self._phase = ProtocolPhase.PREDICTION_SUBMITTED
        self._history.append("prediction_submitted")

    def provide_feedback(
        self, batch_id: str, sample_ids: Iterable[str]
    ) -> None:
        self._require_active_task()
        if self._mode is not ProtocolMode.PREDICT_THEN_FEEDBACK:
            raise ProtocolViolation("feedback events are not allowed in this mode")
        normalized_batch = self._normalize_identifier(batch_id, "batch ID")
        normalized_samples = self._normalize_sample_ids(sample_ids)
        if self._phase is not ProtocolPhase.PREDICTION_SUBMITTED:
            raise ProtocolViolation("prediction must be submitted before feedback")
        if (
            normalized_batch != self._current_batch_id
            or normalized_samples != self._requested_sample_ids
        ):
            raise ProtocolViolation(
                "feedback must match the submitted batch and samples"
            )
        self._training_sample_ids.update(normalized_samples)
        self._phase = ProtocolPhase.FEEDBACK_AVAILABLE
        self._history.append("feedback_available")

    def request_batch_commit(self, batch_id: str) -> None:
        self._require_active_task()
        normalized_batch = self._normalize_identifier(batch_id, "batch ID")
        if normalized_batch != self._current_batch_id:
            raise ProtocolViolation("only the current open batch can be committed")

        required_phase = (
            ProtocolPhase.FEEDBACK_AVAILABLE
            if self._mode is ProtocolMode.PREDICT_THEN_FEEDBACK
            else ProtocolPhase.PREDICTION_SUBMITTED
        )
        if self._phase is not required_phase:
            raise ProtocolViolation("batch is not ready to commit")

        self._closed_batch_ids.append(normalized_batch)
        self._current_batch_id = None
        self._requested_sample_ids = ()
        self._phase = ProtocolPhase.READY
        self._history.append("batch_committed")

    def finish_task(self) -> None:
        self._require_active_task()
        if self._current_batch_id is not None:
            raise ProtocolViolation("task cannot finish with an open batch")
        self._finished = True
        self._phase = ProtocolPhase.FINISHED
        self._history.append("run_finished")

    def snapshot(self) -> ProtocolSnapshot:
        return ProtocolSnapshot(
            mode=self._mode,
            phase=self._phase,
            task_id=self._task_id,
            current_batch_id=self._current_batch_id,
            closed_batch_ids=tuple(self._closed_batch_ids),
            training_sample_ids=frozenset(self._training_sample_ids),
            predicted_sample_ids=frozenset(self._predicted_sample_ids),
            finished=self._finished,
        )

    def _require_active_task(self) -> None:
        if self._task_id is None:
            raise ProtocolViolation("task must be opened before protocol events")
        if self._finished:
            raise ProtocolViolation("task has already finished")

    def _require_no_open_batch(self) -> None:
        if self._current_batch_id is not None:
            raise ProtocolViolation(f"batch {self._current_batch_id} is still open")

    @staticmethod
    def _normalize_identifier(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ProtocolViolation(f"{label} must be a nonempty string")
        return value

    @staticmethod
    def _normalize_sample_ids(sample_ids: Iterable[str]) -> tuple[str, ...]:
        if isinstance(sample_ids, (str, bytes)):
            raise ProtocolViolation("sample IDs must be a nonempty unique sequence")
        try:
            normalized = tuple(sample_ids)
        except TypeError as exc:
            raise ProtocolViolation(
                "sample IDs must be a nonempty unique sequence"
            ) from exc
        if not normalized:
            raise ProtocolViolation("sample IDs must be a nonempty unique sequence")
        if any(not isinstance(item, str) or not item.strip() for item in normalized):
            raise ProtocolViolation("sample IDs must be nonempty strings")
        if len(set(normalized)) != len(normalized):
            raise ProtocolViolation("sample IDs must be unique")
        return normalized


__all__ = [
    "EventProtocolAdapter",
    "ProtocolMode",
    "ProtocolPhase",
    "ProtocolSnapshot",
    "ProtocolViolation",
    "SimulatedSdkAdapter",
]
