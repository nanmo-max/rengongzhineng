from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def write_parent(path: Path, *, task: str) -> None:
    feature_paths = ['[["key","features"],["index",0]]', '[["key","features"],["index",1]]']
    classes = ["cold", "hot"] if task == "classification" else []
    outputs = len(classes) if classes else 1
    parameters = {
        "w1": np.asarray([[0.5, -0.2], [0.1, 0.3]], dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.full((2, outputs), 0.2, dtype=np.float64),
        "b2": np.arange(outputs, dtype=np.float64) * 0.01,
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": "competition-core-characterization",
        "task": task,
        "paths": feature_paths,
        "classes": classes,
        "hidden": 2,
        "seed": 42,
        "epochs": 1,
        "steps": 1,
        "learning_rate": 0.01,
        "batch_size": 4,
        "parameter_count": sum(value.size for value in parameters.values()),
        "target_mean": 5.0 if task == "regression" else 0.0,
        "target_scale": 5.0 if task == "regression" else 1.0,
    }
    np.savez(
        path,
        **parameters,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in parameters.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in parameters.items()},
        mean=np.zeros(2, dtype=np.float64),
        scale=np.ones(2, dtype=np.float64),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


def write_rows(path: Path, *, task: str) -> None:
    rows = []
    for index in range(16):
        answer = ("hot" if index >= 8 else "cold") if task == "classification" else float(index)
        rows.append(
            {
                "id": f"{task}-{index}",
                "inputs": {"features": [float(index), float(index % 3)]},
                "answer": answer,
            }
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class CharacterizationRound:
    def __init__(self, root: Path, parent: Path, *, task: str) -> None:
        self.round_index = 1
        self.stage_id = "characterization"
        self.dataset_key = "opaque-task"
        self.model_name = "host-selected-model"
        self.max_output_tokens = 256
        metric = "macro_f1" if task == "classification" else "rmse"
        direction = "higher" if task == "classification" else "lower"
        self.task = {"task": task, "metric": metric, "metric_direction": direction}
        self.data = SimpleNamespace(
            train_path=str(root / "train.jsonl"),
            validation_path=str(root / "validation.jsonl"),
        )
        self.parent = SimpleNamespace(
            artifact_id="parent-1",
            checkpoint_sha256="sha256:" + hashlib.sha256(parent.read_bytes()).hexdigest(),
            descriptor={"checkpoint_paths": ["checkpoint.npz"], "code_paths": []},
            path=lambda relative: parent if relative == "checkpoint.npz" else None,
        )
        self.call_ids: list[str] = []
        self.submitted: dict[str, object] | None = None
        self.saved_state: Path | None = None
        self.finished: dict[str, object] | None = None

    def history(self):
        return [{"id": "history-0", "selected_artifact_id": "parent-0"}]

    def model(self, messages, **options):
        assert messages and options.get("max_tokens") is None
        call_id = f"call-{len(self.call_ids) + 1}"
        payload = (
            {"recipe": "e1_lr1", "rationale": "characterize one parent-compatible continuation"}
            if not self.call_ids
            else {"decision": "deploy", "rationale": "select the improved legal candidate"}
        )
        self.call_ids.append(call_id)
        return SimpleNamespace(call_id=call_id, text=json.dumps(payload), response={})

    def state_workspace(self, destination):
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=False)
        return path

    def save_state(self, directory):
        self.saved_state = Path(directory)
        return "sha256:" + "1" * 64

    def submit_candidate(self, directory, **kwargs):
        self.submitted = {"directory": Path(directory), **kwargs}
        return {"artifact_id": "candidate-1", "summary": {"metrics": {}}}

    def finish(self, **kwargs):
        self.finished = kwargs
        return {"accepted": True}


def make_round(tmp_path: Path, *, task: str) -> tuple[CharacterizationRound, Path]:
    parent = tmp_path / "checkpoint.npz"
    write_parent(parent, task=task)
    write_rows(tmp_path / "train.jsonl", task=task)
    write_rows(tmp_path / "validation.jsonl", task=task)
    return CharacterizationRound(tmp_path, parent, task=task), parent
