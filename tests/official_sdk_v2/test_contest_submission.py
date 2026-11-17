from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def _write_parent(path: Path, *, task: str = "classification") -> None:
    hidden = 2
    paths = [
        '[["key","features"],["index",0]]',
        '[["key","features"],["index",1]]',
    ]
    classes = ["cold", "hot"] if task == "classification" else []
    outputs = len(classes) if classes else 1
    params = {
        "w1": np.asarray([[0.5, -0.2], [0.1, 0.3]], dtype=np.float64),
        "b1": np.zeros(hidden, dtype=np.float64),
        "w2": np.ones((hidden, outputs), dtype=np.float64) * 0.2,
        "b2": np.arange(outputs, dtype=np.float64) * 0.01,
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": "test-profile",
        "task": task,
        "paths": paths,
        "classes": classes,
        "hidden": hidden,
        "seed": 42,
        "epochs": 1,
        "steps": 1,
        "learning_rate": 0.01,
        "batch_size": 4,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 5.0 if task == "regression" else 0.0,
        "target_scale": 5.0 if task == "regression" else 1.0,
    }
    np.savez(
        path,
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        mean=np.zeros(len(paths), dtype=np.float64),
        scale=np.ones(len(paths), dtype=np.float64),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


class _FakeRound:
    def __init__(self, root: Path, parent: Path) -> None:
        self.root = root
        self.round_index = 1
        self.dataset_key = "A"
        self.model_name = "Qwen/Qwen3.5-4B"
        self.max_output_tokens = 768
        self.call_ids: list[str] = []
        self.frame = {"current_validation": {}}
        self.task = {"task": "classification", "metric": "macro_f1", "metric_direction": "higher"}
        self.data = SimpleNamespace(train_path=str(root / "train.jsonl"))
        self.parent = SimpleNamespace(
            artifact_id="parent-1",
            checkpoint_sha256="sha256:" + hashlib.sha256(parent.read_bytes()).hexdigest(),
            descriptor={"checkpoint_paths": ["checkpoint.npz"], "code_paths": []},
            path=lambda relative: parent if relative == "checkpoint.npz" else None,
        )
        self.submitted: dict | None = None
        self.saved_state: Path | None = None
        self.saved_state_payloads: list[dict] = []
        self.finished: dict | None = None

    def history(self):
        return []

    def model(self, messages, **options):
        assert messages and messages[0]["role"] == "user"
        assert options["max_tokens"] <= self.max_output_tokens
        self.call_ids.append("call-official-1")
        proposal = {
            "schema_version": "brace-msi.experiment-proposal.v1",
            "action": "incremental_update",
            "tool": "train_incremental",
            "rationale": "bounded official workspace proposal",
            "parameters": {"epochs": 1, "learning_rate": 0.01},
            "max_cpu_seconds": 30.0,
            "max_candidates": 1,
            "stop_conditions": ["budget_exhausted", "nonfinite_training_state"],
        }
        return SimpleNamespace(
            call_id="call-official-1",
            response={
                "choices": [{"message": {"content": json.dumps(proposal)}}],
                "usage": {"prompt_tokens": 101, "completion_tokens": 37},
            },
        )

    def state_workspace(self, destination):
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=False)
        return path

    def save_state(self, directory):
        self.saved_state = Path(directory)
        state_path = self.saved_state / "state.json"
        if state_path.is_file():
            self.saved_state_payloads.append(json.loads(state_path.read_text(encoding="utf-8")))
        return "sha256:" + "11" * 32

    def submit_candidate(self, directory, **kwargs):
        self.submitted = {"directory": Path(directory), **kwargs}
        return {
            "artifact_id": "candidate-1",
            "summary": {"metrics": {"macro_f1": 0.8}},
        }

    def finish(self, **kwargs):
        self.finished = kwargs
        return {"accepted": True}


def test_workspace_v2_train_uses_host_model_parent_and_candidate(monkeypatch, tmp_path: Path) -> None:
    from brace_msi import contest_submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    (tmp_path / "train.jsonl").write_text(
        '\n'.join(
            json.dumps(
                {
                    "id": f"s-{index}",
                    "inputs": {"features": [float(index), float(index % 2)]},
                    "answer": "hot" if index >= 5 else "cold",
                }
            )
            for index in range(10)
        )
        + "\n",
        encoding="utf-8",
    )
    rnd = _FakeRound(tmp_path, parent)

    def fake_start_round(data_path, previous_checkpoint, workspace_root, output_root, config, **kwargs):
        assert Path(data_path) == tmp_path / "train.jsonl"
        assert Path(previous_checkpoint) == parent
        assert kwargs["expected_round_index"] == 1
        assert kwargs["expected_parent_sha256"] == rnd.parent.checkpoint_sha256
        response = kwargs["model_transport"](
            {
                "model": rnd.model_name,
                "messages": [{"role": "user", "content": "choose one bounded action"}],
                "max_tokens": 256,
                "temperature": 0.0,
                "seed": 20261117,
            }
        )
        assert response["usage"]["prompt_tokens"] > 0
        Path(output_root).mkdir(parents=True, exist_ok=False)
        (Path(output_root) / "checkpoint.npz").write_bytes(parent.read_bytes())
        (Path(output_root) / "training.json").write_text("{}\n", encoding="utf-8")
        return {
            "candidate_trained": True,
            "deployed": True,
            "decision": {"rationale": "bounded official workspace proposal"},
            "checkpoint_sha256": hashlib.sha256(parent.read_bytes()).hexdigest(),
            "cpu_seconds": 0.1,
            "wall_seconds": 0.2,
        }

    monkeypatch.setattr(contest_submission, "start_round", fake_start_round)
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    contest_submission.train(rnd)

    assert rnd.call_ids == ["call-official-1"]
    assert rnd.saved_state is not None
    assert rnd.submitted is not None
    assert rnd.submitted["checkpoint_paths"] == ["checkpoint.npz"]
    assert rnd.submitted["predict_argv"] == ["python3", "/app/harness.py", "predict"]
    assert rnd.finished is not None
    assert rnd.finished["selected_artifact_id"] == "candidate-1"
    assert rnd.finished["model_call_ids"] == ["call-official-1"]


def test_workspace_v2_predict_uses_exact_selected_artifact(monkeypatch, tmp_path: Path) -> None:
    from brace_msi.contest_submission import predict

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    monkeypatch.setenv("CONTEST_ARTIFACT_PATH", str(parent))
    sample = SimpleNamespace(
        task="classification",
        inputs={"features": [1.0, 2.0]},
        dataset_key="A",
    )

    result = predict(sample, tmp_path)

    assert isinstance(result, list)
    assert {item["label"] for item in result} == {"cold", "hot"}
    assert all(0.0 <= item["score"] <= 1.0 for item in result)
    assert sum(item["score"] == max(piece["score"] for piece in result) for item in result) == 1


def test_workspace_v2_train_executes_real_native_continuation(monkeypatch, tmp_path: Path) -> None:
    from brace_msi import contest_submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    rows = [
        {
            "id": f"real-{index}",
            "inputs": {"features": [float(index), float(index % 3)]},
            "answer": "hot" if index >= 20 else "cold",
        }
        for index in range(40)
    ]
    (tmp_path / "train.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    rnd = _FakeRound(tmp_path, parent)
    work = tmp_path / "real-work"
    monkeypatch.setenv("CONTEST_WORK", str(work))

    contest_submission.train(rnd)

    assert rnd.call_ids == ["call-official-1"]
    assert (work / "state" / "state.json").is_file()
    assert rnd.finished is not None
    assert rnd.finished["selected_artifact_id"] in {"parent-1", "candidate-1"}
    if rnd.submitted is not None:
        assert (rnd.submitted["directory"] / "checkpoint.npz").is_file()


def test_platform_measurement_rejection_commits_parent_state(monkeypatch, tmp_path: Path) -> None:
    from brace_msi import contest_submission

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    (tmp_path / "train.jsonl").write_text(
        json.dumps(
            {
                "id": "s-1",
                "inputs": {"features": [1.0, 0.0]},
                "answer": "cold",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rnd = _FakeRound(tmp_path, parent)
    rnd.frame["current_validation"] = {"metrics": {"macro_f1": 0.9}}

    def fake_start_round(data_path, previous_checkpoint, workspace_root, output_root, config, **kwargs):
        kwargs["model_transport"](
            {
                "model": rnd.model_name,
                "messages": [{"role": "user", "content": "choose"}],
                "max_tokens": 64,
            }
        )
        state = Path(workspace_root)
        state.mkdir(parents=True, exist_ok=True)
        candidate_sha = "a" * 64
        (state / "state.json").write_text(
            json.dumps(
                {
                    "format": "brace-msi.platform-state.v1",
                    "rounds": [
                        {
                            "round_index": 1,
                            "deployed": True,
                            "gate_reason": "portfolio_gate_passed",
                            "checkpoint_sha256": candidate_sha,
                            "parent_checkpoint_sha256": hashlib.sha256(parent.read_bytes()).hexdigest(),
                            "metrics_before": {"macro_f1": 0.7},
                            "metrics_candidate": {"macro_f1": 0.8},
                            "model_artifact": {
                                "kind": "checkpoint",
                                "relative_path": "checkpoint.npz",
                                "sha256": candidate_sha,
                                "bytes": parent.stat().st_size,
                                "disposition": "deployed_candidate",
                            },
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (state / "shadow-predecessor.npz").write_bytes(parent.read_bytes())
        (state / "public-spool.jsonl").write_text(
            json.dumps(
                {
                    "round_index": 1,
                    "accepted": True,
                    "primary_metric": 0.8,
                    "checkpoint_sha256": candidate_sha,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        output = Path(output_root)
        output.mkdir(parents=True, exist_ok=True)
        (output / "checkpoint.npz").write_bytes(parent.read_bytes())
        return {
            "candidate_trained": True,
            "deployed": True,
            "decision": {"rationale": "candidate looked safe internally"},
            "checkpoint_sha256": candidate_sha,
        }

    monkeypatch.setattr(contest_submission, "start_round", fake_start_round)
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    contest_submission.train(rnd)

    assert rnd.finished is not None
    assert rnd.finished["selected_artifact_id"] == "parent-1"
    assert len(rnd.saved_state_payloads) == 1
    committed = rnd.saved_state_payloads[0]["rounds"][-1]
    assert committed["deployed"] is False
    assert committed["checkpoint_sha256"] == hashlib.sha256(parent.read_bytes()).hexdigest()
    assert committed["model_artifact"]["disposition"] == "retained_parent"
    spool = [
        json.loads(line)
        for line in (tmp_path / "work" / "state" / "public-spool.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert spool[-1]["accepted"] is False
    assert spool[-1]["gate_reason"] == "platform_measurement_rejected"
    assert spool[-1]["checkpoint_sha256"] == hashlib.sha256(parent.read_bytes()).hexdigest()
    assert not (tmp_path / "work" / "state" / "shadow-predecessor.npz").exists()


def test_workspace_v2_predict_rejects_artifact_outside_model_mount(monkeypatch, tmp_path: Path) -> None:
    from brace_msi.contest_submission import predict

    outside = tmp_path / "outside.npz"
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    _write_parent(outside, task="regression")
    monkeypatch.setenv("CONTEST_ARTIFACT_PATH", str(outside))
    sample = SimpleNamespace(task="regression", inputs={"features": [1.0, 2.0]}, dataset_key="B")

    try:
        predict(sample, model_dir)
    except ValueError as exc:
        assert "artifact path" in str(exc)
    else:
        raise AssertionError("artifact outside /model must be rejected")
