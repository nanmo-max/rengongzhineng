from __future__ import annotations

import importlib

import pytest


def protocol_api():
    return importlib.import_module("brace_msi.protocol")


def test_predict_then_feedback_completes_valid_sequence() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.PREDICT_THEN_FEEDBACK)

    adapter.open_task("task-a")
    adapter.request_predictions("batch-1", ["s-1", "s-2"])
    adapter.submit_predictions("batch-1", ["s-1", "s-2"])
    adapter.provide_feedback("batch-1", ["s-1", "s-2"])
    adapter.request_batch_commit("batch-1")
    adapter.finish_task()

    snapshot = adapter.snapshot()
    assert snapshot.finished is True
    assert snapshot.closed_batch_ids == ("batch-1",)
    assert snapshot.training_sample_ids == frozenset({"s-1", "s-2"})
    assert adapter.history == (
        "task_opened",
        "prediction_requested",
        "prediction_submitted",
        "feedback_available",
        "batch_committed",
        "run_finished",
    )


def test_predict_then_feedback_rejects_feedback_before_prediction_submission() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.PREDICT_THEN_FEEDBACK)
    adapter.open_task("task-a")
    adapter.request_predictions("batch-1", ["s-1"])

    with pytest.raises(api.ProtocolViolation, match="prediction.*submitted"):
        adapter.provide_feedback("batch-1", ["s-1"])


def test_labeled_train_then_predict_accepts_distinct_samples() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.LABELED_TRAIN_THEN_PREDICT)

    adapter.open_task("task-b")
    adapter.provide_training_batch("batch-1", ["train-1", "train-2"])
    adapter.request_predictions("batch-1", ["score-1"])
    adapter.submit_predictions("batch-1", ["score-1"])
    adapter.request_batch_commit("batch-1")
    adapter.finish_task()

    snapshot = adapter.snapshot()
    assert snapshot.finished is True
    assert snapshot.training_sample_ids == frozenset({"train-1", "train-2"})
    assert snapshot.predicted_sample_ids == frozenset({"score-1"})


def test_labeled_train_then_predict_rejects_training_score_overlap() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.LABELED_TRAIN_THEN_PREDICT)
    adapter.open_task("task-b")
    adapter.provide_training_batch("batch-1", ["shared-1"])

    with pytest.raises(api.ProtocolViolation, match="leakage"):
        adapter.request_predictions("batch-1", ["shared-1"])


def test_labeled_train_then_predict_rejects_duplicate_prediction_request() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.LABELED_TRAIN_THEN_PREDICT)
    adapter.open_task("task-b")
    adapter.provide_training_batch("batch-1", ["train-1"])
    adapter.request_predictions("batch-1", ["score-1"])

    with pytest.raises(api.ProtocolViolation, match="not ready"):
        adapter.request_predictions("batch-1", ["score-2"])


def test_next_batch_is_rejected_until_current_batch_is_committed() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.PREDICT_THEN_FEEDBACK)
    adapter.open_task("task-a")
    adapter.request_predictions("batch-1", ["s-1"])
    adapter.submit_predictions("batch-1", ["s-1"])

    with pytest.raises(api.ProtocolViolation, match="batch-1.*open"):
        adapter.request_predictions("batch-2", ["s-2"])


def test_rejected_leaking_request_does_not_open_a_batch() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.PREDICT_THEN_FEEDBACK)
    adapter.open_task("task-a")
    adapter.request_predictions("batch-1", ["s-1"])
    adapter.submit_predictions("batch-1", ["s-1"])
    adapter.provide_feedback("batch-1", ["s-1"])
    adapter.request_batch_commit("batch-1")

    with pytest.raises(api.ProtocolViolation, match="leakage"):
        adapter.request_predictions("batch-2", ["s-1"])

    assert adapter.snapshot().current_batch_id is None
    adapter.request_predictions("batch-2", ["s-2"])


@pytest.mark.parametrize(
    ("mode", "invalid_operation"),
    [
        ("predict_then_feedback", "training"),
        ("labeled_train_then_predict", "feedback"),
    ],
)
def test_protocol_rejects_events_owned_by_the_other_mode(
    mode: str, invalid_operation: str
) -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode(mode))
    adapter.open_task("task-a")

    with pytest.raises(api.ProtocolViolation, match="not allowed"):
        if invalid_operation == "training":
            adapter.provide_training_batch("batch-1", ["train-1"])
        else:
            adapter.provide_feedback("batch-1", ["score-1"])


def test_task_cannot_finish_with_an_open_batch() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.PREDICT_THEN_FEEDBACK)
    adapter.open_task("task-a")
    adapter.request_predictions("batch-1", ["s-1"])

    with pytest.raises(api.ProtocolViolation, match="open batch"):
        adapter.finish_task()


@pytest.mark.parametrize("sample_ids", [[], ["s-1", "s-1"]])
def test_sample_ids_must_be_nonempty_and_unique(sample_ids: list[str]) -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.PREDICT_THEN_FEEDBACK)
    adapter.open_task("task-a")

    with pytest.raises(api.ProtocolViolation, match="sample IDs"):
        adapter.request_predictions("batch-1", sample_ids)


def test_submission_must_match_requested_batch_and_samples() -> None:
    api = protocol_api()
    adapter = api.SimulatedSdkAdapter(api.ProtocolMode.PREDICT_THEN_FEEDBACK)
    adapter.open_task("task-a")
    adapter.request_predictions("batch-1", ["s-1", "s-2"])

    with pytest.raises(api.ProtocolViolation, match="requested batch and samples"):
        adapter.submit_predictions("batch-other", ["s-1"])
