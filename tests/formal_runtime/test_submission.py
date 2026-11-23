from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def _write_parent(path: Path, *, task: str = "classification") -> None:
    paths = ['[["key","features"],["index",0]]', '[["key","features"],["index",1]]']
    classes = ["cold", "hot"] if task == "classification" else []
    outputs = len(classes) if classes else 1
    params = {
        "w1": np.asarray([[0.5, -0.2], [0.1, 0.3]], dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.full((2, outputs), 0.2, dtype=np.float64),
        "b2": np.arange(outputs, dtype=np.float64) * 0.01,
    }
    metadata = {
        "format": "contest.cpu-mlp.v1", "device": "cpu", "profile": "test",
        "task": task, "paths": paths, "classes": classes, "hidden": 2,
        "seed": 42, "epochs": 1, "steps": 1, "learning_rate": 0.01,
        "batch_size": 4, "parameter_count": sum(v.size for v in params.values()),
        "target_mean": 5.0 if task == "regression" else 0.0,
        "target_scale": 5.0 if task == "regression" else 1.0,
    }
    np.savez(
        path, **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        mean=np.zeros(2), scale=np.ones(2),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


def _write_rows(path: Path, *, task: str = "classification") -> None:
    rows = []
    for index in range(12):
        answer = ("hot" if index >= 6 else "cold") if task == "classification" else float(index)
        rows.append({"id": f"s-{index}", "inputs": {"features": [float(index), float(index % 2)]}, "answer": answer})
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FakeRound:
    def __init__(
        self,
        root: Path,
        parent: Path,
        proposal: dict[str, object],
        *,
        deployment: dict[str, object] | None = None,
        host_metrics: dict[str, float] | None = None,
    ) -> None:
        self.round_index = 1
        self.stage_id = "stage-A"
        self.dataset_key = "A"
        self.max_output_tokens = 128
        self.model_name = "host-selected-alias"
        self.task = {"task": "classification", "metric": "macro_f1", "metric_direction": "higher"}
        self.data = SimpleNamespace(train_path=str(root / "train.jsonl"), validation_path=str(root / "validation.jsonl"))
        self.parent = SimpleNamespace(
            artifact_id="parent-1",
            checkpoint_sha256="sha256:" + hashlib.sha256(parent.read_bytes()).hexdigest(),
            descriptor={"checkpoint_paths": ["checkpoint.npz"], "code_paths": []},
            path=lambda relative: parent if relative == "checkpoint.npz" else None,
        )
        self.proposal = proposal
        self.deployment = deployment or {"decision": "deploy", "rationale": "candidate evidence supports deployment"}
        self.host_metrics = {"accuracy": 0.75, "macro_f1": 0.65} if host_metrics is None else host_metrics
        self.call_ids: list[str] = []
        self.model_messages: list[list[dict[str, object]]] = []
        self.submitted: dict[str, object] | None = None
        self.saved_state: Path | None = None
        self.finished: dict[str, object] | None = None

    def history(self):
        return [{"id": "history-0", "selected_artifact_id": "parent-0"}]

    def model(self, messages, **options):
        assert messages
        self.model_messages.append(messages)
        assert "max_tokens" not in options
        options = {**options, "max_tokens": self.max_output_tokens}
        assert options["max_tokens"] == 128
        call_id = f"call-{len(self.call_ids) + 1}"
        payload = self.proposal if not self.call_ids else self.deployment
        if not self.call_ids and "recipe" in payload:
            legacy = str(payload["recipe"])
            recipe_id = {
                "e1_lr1": "native_current",
                "e3_lr3": "native_current",
                "soup_e3_alpha0.25": "averaged_native",
            }[legacy]
            parameters = (
                {"epochs": 3, "learning_rate_multiplier": 3.0}
                if legacy == "e3_lr3"
                else {"epochs": 3, "parent_average_alpha": 0.25}
                if legacy == "soup_e3_alpha0.25"
                else {}
            )
            payload = {
                "recipe_id": recipe_id,
                "parameters": parameters,
                "history_policy": "current_plus_history" if recipe_id == "averaged_native" else "current",
                "hypothesis": str(payload["rationale"]),
                "rationale": str(payload["rationale"]),
            }
        elif self.call_ids and "decision" in payload:
            requested = {
                "deploy": "candidate-1",
                "retain": "parent-1",
                "rollback": "parent-1",
            }[str(payload["decision"])]
            payload = {"artifact_id": requested, "rationale": str(payload["rationale"])}
        self.call_ids.append(call_id)
        return SimpleNamespace(call_id=call_id, text=json.dumps(payload), response={})

    def state_workspace(self, destination):
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=False)
        return path

    def save_state(self, directory):
        self.saved_state = Path(directory)
        assert (self.saved_state / "formal-state.json").is_file()
        return "sha256:" + "1" * 64

    def submit_candidate(self, directory, **kwargs):
        self.submitted = {"directory": Path(directory), **kwargs}
        return {"artifact_id": "candidate-1", "summary": {"metrics": self.host_metrics}}

    def finish(self, **kwargs):
        self.finished = kwargs
        return {"accepted": True}


def test_retain_advice_still_trains_and_submits_one_real_candidate(monkeypatch, tmp_path: Path) -> None:
    from brace_formal.submission import train

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(
        tmp_path,
        parent,
        {"recipe": "e1_lr1", "rationale": "run a low-cost continuation"},
        deployment={"decision": "retain", "rationale": "candidate evidence does not justify deployment"},
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))

    train(rnd)

    assert rnd.call_ids == ["call-1", "call-2"]
    prompt = str(rnd.model_messages[0][0]["content"])
    assert '"candidate_training_required": true' in prompt
    assert '"available_recipes"' in prompt
    assert '"task_profile"' in prompt
    assert '"feature_count": 2' in prompt
    assert rnd.submitted is not None
    assert (rnd.submitted["directory"] / "checkpoint.npz").is_file()
    assert rnd.finished is not None
    assert rnd.finished["model_call_ids"] == ["call-1", "call-2"]
    assert rnd.finished["history_ids"] == ["history-0"]
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["rounds"][-1]["deployment_decision"]["requested_artifact_id"] == "parent-1"
    assert state["rounds"][-1]["action"] == "train"
    assert state["rounds"][-1]["recipe"] != "retain"
    assert state["rounds"][-1]["drift"]["status"] == "insufficient_history"
    assert state["rounds"][-1]["diagnosis"]["performance_impact"]["status"] == "unknown"
    assert state["rounds"][-1]["agent_evidence"]["validated_refs"] == []
    assert state["rounds"][-1]["agent_evidence"]["actual_result"]["candidate_trained"] is True
    assert state["rounds"][-1]["agent_evidence"]["selection_outcome"] == state["rounds"][-1]["applied_deployment_decision"]


def test_safe_candidate_is_submitted_and_selected(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(tmp_path, parent, {"recipe": "soup_e3_alpha0.25", "rationale": "reduce update variance"})
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    scores = iter([{"accuracy": 0.5, "macro_f1": 0.4}, {"accuracy": 0.7, "macro_f1": 0.6}])
    monkeypatch.setattr(submission, "evaluate", lambda *args: next(scores))

    submission.train(rnd)

    assert rnd.submitted is not None
    assert (rnd.submitted["directory"] / "checkpoint.npz").is_file()
    assert rnd.submitted["checkpoint_paths"] == ["checkpoint.npz"]
    assert rnd.submitted["predict_argv"] == ["python3", "/app/harness.py", "predict"]
    assert rnd.submitted["seed"] == 42
    assert rnd.submitted["configuration"]["recipe_id"] == "averaged_native"
    assert rnd.submitted["configuration"]["candidate_execution"]["epochs"] == 3
    assert rnd.submitted["configuration"]["candidate_execution"]["learning_rate_multiplier"] == 1.0
    assert rnd.submitted["seed"] == 42
    assert rnd.submitted["configuration"]["proposal_call_id"] == "call-1"
    assert rnd.submitted["configuration"]["deployment_call_id"] == "call-2"
    assert rnd.finished["selected_artifact_id"] == "candidate-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["format"] == "brace-formal-state.v2"
    assert state["rounds"][-1]["recipe"] == "averaged_native"
    assert state["rounds"][-1]["candidate_execution"]["epochs"] == 3
    assert state["rounds"][-1]["platform_metrics"]["macro_f1"] == 0.65
    assert state["rounds"][-1]["parent_artifact_id"] == "parent-1"
    assert state["rounds"][-1]["candidate_artifact_id"] == "candidate-1"
    assert state["rounds"][-1]["selected_artifact_id"] == "candidate-1"
    assert state["rounds"][-1]["best_stable_artifact_id"] is None
    assert state["rounds"][-1]["candidate_checkpoint_sha256"].startswith("sha256:")
    assert state["rounds"][-1]["selected_checkpoint_sha256"] == state["rounds"][-1]["candidate_checkpoint_sha256"]
    assert state["rounds"][-1]["metric_contract"]["metric_directions"]["accuracy"] == "higher"


def test_state_v1_is_explicitly_migrated_as_legacy(tmp_path: Path) -> None:
    from brace_formal.submission import _state_payload

    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "formal-state.json").write_text(
        json.dumps({"format": "brace-formal-state.v1", "rounds": [{"round_index": 1, "selected_artifact_id": "parent-1"}]}),
        encoding="utf-8",
    )

    payload = _state_payload(state_root)

    assert payload["format"] == "brace-formal-state.v2"
    record = payload["rounds"][0]
    assert record["legacy_source_format"] == "brace-formal-state.v1"
    assert record["candidate_artifact_id"] is None
    assert record["best_stable_artifact_id"] is None


def test_platform_measurement_does_not_replace_qwen_deployment_decision(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(
        tmp_path,
        parent,
        {"recipe": "e1_lr1", "rationale": "test bounded continuation"},
        host_metrics={"accuracy": 0.45, "macro_f1": 0.3},
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    scores = iter([{"accuracy": 0.5, "macro_f1": 0.4}, {"accuracy": 0.7, "macro_f1": 0.6}])
    monkeypatch.setattr(submission, "evaluate", lambda *args: next(scores))

    submission.train(rnd)

    assert rnd.submitted is not None
    assert rnd.finished["selected_artifact_id"] == "candidate-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["rounds"][-1]["outcome"] == "candidate_selected_by_selector"
    assert state["rounds"][-1]["platform_metrics"]["macro_f1"] == 0.3


def test_missing_platform_measurement_does_not_block_qwen_deploy(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(
        tmp_path,
        parent,
        {"recipe": "e1_lr1", "rationale": "test bounded continuation"},
        host_metrics={},
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    scores = iter([{"accuracy": 0.5, "macro_f1": 0.4}, {"accuracy": 0.7, "macro_f1": 0.6}])
    monkeypatch.setattr(submission, "evaluate", lambda *args: next(scores))

    submission.train(rnd)

    assert rnd.finished["selected_artifact_id"] == "candidate-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["rounds"][-1]["outcome"] == "candidate_selected_by_selector"
    assert state["rounds"][-1]["platform_metrics"] == {}


def test_qwen_rollback_keeps_parent_after_candidate_training(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(
        tmp_path,
        parent,
        {"recipe": "e1_lr1", "rationale": "test a conservative update"},
        deployment={"decision": "rollback", "rationale": "candidate regressed on measured evidence"},
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    scores = iter([{"accuracy": 0.8, "macro_f1": 0.7}, {"accuracy": 0.7, "macro_f1": 0.6}])
    monkeypatch.setattr(submission, "evaluate", lambda *args: next(scores))

    submission.train(rnd)

    assert rnd.submitted is not None
    assert rnd.finished["selected_artifact_id"] == "parent-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["rounds"][-1]["outcome"] == "candidate_retained_parent_by_selector"
    assert state["rounds"][-1]["recipe"] == "native_current"


def test_qwen_cannot_deploy_candidate_that_regresses_on_same_scope(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(
        tmp_path,
        parent,
        {"recipe": "e1_lr1", "rationale": "test bounded continuation"},
        deployment={"decision": "deploy", "rationale": "candidate should be deployed"},
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    scores = iter([{"accuracy": 0.85, "macro_f1": 0.80}, {"accuracy": 0.80, "macro_f1": 0.75}])
    monkeypatch.setattr(submission, "evaluate", lambda *args: next(scores))

    submission.train(rnd)

    assert rnd.submitted is not None
    assert rnd.finished["selected_artifact_id"] == "parent-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    record = state["rounds"][-1]
    assert record["selection"]["relation_to_parent"] == "unchanged"
    assert record["requested_deployment_decision"] == "deploy"
    assert record["applied_deployment_decision"] == "retain"
    assert record["deployment_decision"]["requested_artifact_id"] == "candidate-1"
    assert record["outcome"] == "candidate_retained_parent_by_selector"


def test_hard_gate_failure_never_submits_candidate(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(tmp_path, parent, {"recipe": "e1_lr1", "rationale": "test bounded continuation"})
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    monkeypatch.setattr(submission, "_hard_gate", lambda *args: ["checkpoint_unloadable:ValueError"])

    submission.train(rnd)

    assert rnd.submitted is None
    assert rnd.finished["selected_artifact_id"] == "parent-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    assert state["rounds"][-1]["outcome"] == "candidate_rejected_by_safety_gate"


def test_nonfinite_candidate_metric_fails_closed_but_finishes_round(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(tmp_path, parent, {"recipe": "e1_lr1", "rationale": "test bounded continuation"})
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    scores = iter([{"accuracy": 0.8, "macro_f1": 0.7}, {"accuracy": 0.7, "macro_f1": float("nan")}])
    monkeypatch.setattr(submission, "evaluate", lambda *args, **kwargs: next(scores))

    submission.train(rnd)

    assert rnd.call_ids == ["call-1", "call-2"]
    assert rnd.submitted is None
    assert rnd.finished["selected_artifact_id"] == "parent-1"
    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    record = state["rounds"][-1]
    assert record["candidate_metrics"]["macro_f1"] is None
    assert "candidate_metrics_nonfinite" in record["hard_failures"]


def test_incomparable_history_does_not_expose_old_metrics_to_qwen(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(tmp_path, parent, {"recipe": "e1_lr1", "rationale": "test bounded continuation"})
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    submission.train(rnd)

    prompt = str(rnd.model_messages[0][0]["content"])
    context = json.loads(prompt.split(" Context: ", 1)[1])
    assert context["history_summary"]["official_history_records"] == 1
    serialized = json.dumps(context["history_summary"])
    assert "parent_metrics" not in serialized
    assert "candidate_metrics" not in serialized


def test_post_training_qwen_receives_parent_candidate_resource_and_history_evidence(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(tmp_path, parent, {"recipe": "e1_lr1", "rationale": "test bounded continuation"})
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))

    submission.train(rnd)

    deployment_prompt = str(rnd.model_messages[1][0]["content"])
    assert '"artifact_metrics"' in deployment_prompt
    assert '"artifact_resources"' in deployment_prompt
    assert '"cpu_seconds"' in deployment_prompt
    assert '"peak_rss_bytes"' in deployment_prompt
    assert '"history_summary"' in deployment_prompt


def test_training_qwen_receives_explicit_metric_directions_for_rmse_nasa(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, task="regression")
    _write_rows(tmp_path / "train.jsonl", task="regression")
    _write_rows(tmp_path / "validation.jsonl", task="regression")
    rnd = FakeRound(tmp_path, parent, {"recipe": "e1_lr1", "rationale": "test bounded continuation"})
    rnd.task = {"task": "regression", "metric": "rmse_nasa", "metric_direction": "lower"}
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))

    submission.train(rnd)

    prompt = str(rnd.model_messages[0][0]["content"])
    context = json.loads(prompt.split(" Context: ", 1)[1])
    assert context["task_profile"]["primary_metric"] == "rmse"
    assert context["task_profile"]["metric_direction"] == "lower"


def test_round_records_scoped_non_overlapping_timings_without_raw_payloads(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(tmp_path, parent, {"recipe": "e1_lr1", "rationale": "test bounded continuation"})
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    scores = iter([{"accuracy": 0.5, "macro_f1": 0.4}, {"accuracy": 0.7, "macro_f1": 0.6}])
    monkeypatch.setattr(submission, "evaluate", lambda *args: next(scores))

    submission.train(rnd)

    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    timing = state["rounds"][-1]["timing"]
    assert set(timing) == {
        "proposal_seconds",
        "candidate_train_eval_submit_seconds",
        "deployment_seconds",
        "observed_seconds_before_state_rpc",
    }
    assert all(isinstance(value, float) and value >= 0.0 for value in timing.values())
    serialized = json.dumps({"state": state, "configuration": rnd.finished["configuration"]}).lower()
    for forbidden in ("messages", "raw_prompt", '"answer"', '"inputs"'):
        assert forbidden not in serialized


def test_skipped_candidate_submit_is_not_reported_as_fast_submit(monkeypatch, tmp_path: Path) -> None:
    from brace_formal import submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    rnd = FakeRound(tmp_path, parent, {"recipe": "e1_lr1", "rationale": "test bounded continuation"})
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))
    monkeypatch.setattr(submission, "_hard_gate", lambda *args: ["checkpoint_unloadable:ValueError"])

    submission.train(rnd)

    state = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
    record = state["rounds"][-1]
    assert record["candidate_artifact_id"] is None
    assert record["hard_failures"] == ["checkpoint_unloadable:ValueError"]


def test_predict_uses_selected_checkpoint(monkeypatch, tmp_path: Path) -> None:
    from brace_formal.submission import predict

    checkpoint = tmp_path / "checkpoint.npz"
    _write_parent(checkpoint)
    monkeypatch.setenv("CONTEST_ARTIFACT_PATH", str(checkpoint))
    sample = SimpleNamespace(task="classification", inputs={"features": [1.0, 0.0]})

    result = predict(sample, tmp_path)

    assert {item["label"] for item in result} == {"cold", "hot"}
    assert abs(sum(item["score"] for item in result) - 1.0) < 1e-12
    assert sum(item["score"] == max(piece["score"] for piece in result) for item in result) == 1


def test_real_official_round_transcript_for_retain(monkeypatch, tmp_path: Path) -> None:
    from brace_formal.submission import train
    from contest_harness.round import Round

    previous = tmp_path / "previous"
    previous.mkdir()
    parent = previous / "checkpoint.npz"
    _write_parent(parent)
    _write_rows(tmp_path / "train.jsonl")
    _write_rows(tmp_path / "validation.jsonl")
    digest = hashlib.sha256(parent.read_bytes()).hexdigest()
    frame = {
        "protocol": "contest.harness.workspace.v2",
        "prompt": "official prompt",
        "prompt_version": "1",
        "dataset_key": "A",
        "round_index": 1,
        "stage_id": "transcript",
        "task_contract": {
            "task": "classification", "metric": "macro_f1", "metric_direction": "higher",
            "public_projection": {"train_path": str(tmp_path / "train.jsonl"), "validation_path": str(tmp_path / "validation.jsonl")},
        },
        "model_name": "host-alias",
        "max_output_tokens": 64,
        "parent_checkpoint_sha256": "sha256:" + digest,
        "parent_artifact": {
            "artifact_id": "parent-1",
            "artifact": {"checkpoint_paths": ["checkpoint.npz"], "code_paths": [], "predict_argv": ["python3", "/app/harness.py", "predict"]},
            "files": [{"path": "checkpoint.npz", "sha256": "sha256:" + digest, "size_bytes": parent.stat().st_size}],
        },
        "artifacts": [],
    }
    responses = [
        {"type": "history_response", "id": 0, "records": [{"id": "history-0"}]},
            {"type": "model_response", "id": 1, "call_id": "call-real-1", "response": {"choices": [{"message": {"content": '{"recipe_id":"native_current","parameters":{},"history_policy":"current","hypothesis":"bounded continuation may improve the current task","rationale":"bounded continuation"}'}}]}},
            {"type": "model_response", "id": 2, "call_id": "call-real-2", "response": {"choices": [{"message": {"content": '{"artifact_id":"candidate-1","rationale":"candidate metrics improved"}'}}]}},
            {"type": "candidate_response", "id": 3, "artifact_id": "candidate-real-1", "summary": {"metrics": {"accuracy": 0.8, "macro_f1": 0.7}}},
            {"type": "state_response", "id": 4, "state_sha256": "sha256:" + "1" * 64},
        {"type": "round_ack", "accepted": True},
    ]
    reader = io.StringIO("".join(json.dumps(item) + "\n" for item in responses))
    writer = io.StringIO()
    rnd = Round(frame, reader, writer)
    rnd.parent.root = previous
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "workspace"))

    train(rnd)

    emitted = [json.loads(line) for line in writer.getvalue().splitlines()]
    assert [item["type"] for item in emitted] == ["history_request", "model_request", "model_request", "candidate_request", "state_request", "round_complete"]
    assert emitted[-1]["record"]["model_call_ids"] == ["call-real-1", "call-real-2"]
    assert emitted[-1]["record"]["selected_artifact_id"] == "candidate-real-1"
