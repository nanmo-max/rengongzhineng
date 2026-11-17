"""Local synthetic lifecycle test for the minimal formal runtime.

This script never reads official data and its metrics are not competition scores.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any

import numpy as np

from brace_formal.model import FormalModel
from brace_formal.submission import train


_LABEL = "LOCAL SYNTHETIC PROTOCOL TEST - NOT AN OFFICIAL SCORE"


def _initial_checkpoint(path: Path, task: str, seed: int) -> None:
    rng = np.random.default_rng(seed)
    classes = ["class-0", "class-1"] if task == "classification" else []
    outputs = len(classes) if classes else 1
    params = {
        "w1": rng.normal(0.0, 0.05, size=(2, 4)).astype(np.float64),
        "b1": np.zeros(4, dtype=np.float64),
        "w2": rng.normal(0.0, 0.05, size=(4, outputs)).astype(np.float64),
        "b2": np.zeros(outputs, dtype=np.float64),
    }
    arrays = {
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        "mean": np.zeros(2, dtype=np.float64),
        "scale": np.ones(2, dtype=np.float64),
    }
    metadata = {
        "format": "contest.cpu-mlp.v1", "device": "cpu", "profile": "synthetic-protocol-only",
        "task": task,
        "paths": ['[["key","features"],["index",0]]', '[["key","features"],["index",1]]'],
        "classes": classes, "hidden": 4, "seed": seed, "epochs": 0, "steps": 0,
        "learning_rate": 0.01, "batch_size": 16,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 60.0 if task == "regression" else 0.0,
        "target_scale": 30.0 if task == "regression" else 1.0,
    }
    FormalModel(arrays, metadata).save(path)


def _round_rows(path: Path, task_key: str, round_index: int, split: str) -> None:
    offset = 1000 if split == "validation" else 0
    rng = np.random.default_rng(3100 + 97 * round_index + offset + ord(task_key))
    rows = []
    for index in range(48 if split == "train" else 24):
        x1, x2 = rng.normal(round_index * 0.08, 1.0, size=2)
        if task_key == "A":
            answer: str | float = "class-1" if x1 + 0.35 * x2 > 0.15 * np.sin(round_index) else "class-0"
        elif task_key == "B":
            answer = float(max(0.0, 85.0 - 14.0 * x1 + 3.0 * x2 + rng.normal(0, 1.0)))
        else:
            answer = float(max(0.0, 115.0 - 9.0 * x1 - 5.0 * x2 + rng.normal(0, 1.5)))
        rows.append({"id": f"{task_key}-{round_index}-{split}-{index}", "inputs": {"features": [float(x1), float(x2)]}, "answer": answer})
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


class _SimulationRound:
    def __init__(self, *, task_key: str, task: str, round_index: int, root: Path, parent: Path, history: list[dict[str, Any]], state_source: Path | None) -> None:
        self.dataset_key = task_key
        self.round_index = round_index
        self.stage_id = f"local-{task_key}"
        self.max_output_tokens = 96
        self.model_name = "local-test-host"
        self.call_ids: list[str] = []
        self.task = {
            "task": task,
            "metric": "macro_f1" if task == "classification" else "rmse",
            "metric_direction": "higher" if task == "classification" else "lower",
        }
        self.data = SimpleNamespace(train_path=str(root / "train.jsonl"), validation_path=str(root / "validation.jsonl"))
        digest = hashlib.sha256(parent.read_bytes()).hexdigest()
        self.parent = SimpleNamespace(
            artifact_id=f"{task_key}-parent-{round_index}", checkpoint_sha256="sha256:" + digest,
            descriptor={"checkpoint_paths": ["checkpoint.npz"], "code_paths": []},
            path=lambda relative: parent if relative == "checkpoint.npz" else None,
        )
        self._history = list(history)
        self._state_source = state_source
        self.saved_state: Path | None = None
        self.submitted: dict[str, Any] | None = None
        self.finished: dict[str, Any] | None = None

    def history(self):
        return list(self._history)

    def model(self, messages, **options):
        call_id = f"call-{self.dataset_key}-{self.round_index:02d}"
        self.call_ids.append(call_id)
        proposal = {"action": "train", "epochs": 1, "learning_rate_multiplier": 1.0, "rationale": "local lifecycle exercise"}
        return SimpleNamespace(call_id=call_id, text=json.dumps(proposal), response={"choices": [{"message": {"content": json.dumps(proposal)}}]})

    def state_workspace(self, destination):
        destination = Path(destination)
        if self._state_source is None:
            destination.mkdir(parents=True, exist_ok=False)
        else:
            shutil.copytree(self._state_source, destination)
        return destination

    def submit_candidate(self, directory, **kwargs):
        self.submitted = {"directory": Path(directory), **kwargs}
        return {"artifact_id": f"{self.dataset_key}-candidate-{self.round_index}"}

    def save_state(self, directory):
        self.saved_state = Path(directory)
        digest = hashlib.sha256((self.saved_state / "formal-state.json").read_bytes()).hexdigest()
        return "sha256:" + digest

    def finish(self, **kwargs):
        self.finished = kwargs
        return {"accepted": True}


def _simulate_task(output: Path, task_key: str, task: str) -> dict[str, Any]:
    task_root = output / task_key
    task_root.mkdir(parents=True)
    initial = task_root / "initial-checkpoint.npz"
    _initial_checkpoint(initial, task, 1100 + ord(task_key))
    parent = initial
    state_source: Path | None = None
    history: list[dict[str, Any]] = []
    rounds: list[dict[str, Any]] = []
    parent_chain_valid = True
    state_chain_valid = True
    for round_index in range(1, 11):
        data_root = task_root / f"data-{round_index:02d}"
        data_root.mkdir()
        _round_rows(data_root / "train.jsonl", task_key, round_index, "train")
        _round_rows(data_root / "validation.jsonl", task_key, round_index, "validation")
        declared_parent = hashlib.sha256(parent.read_bytes()).hexdigest()
        rnd = _SimulationRound(
            task_key=task_key, task=task, round_index=round_index, root=data_root,
            parent=parent, history=history, state_source=state_source,
        )
        train(rnd)
        parent_chain_valid &= rnd.parent.checkpoint_sha256 == "sha256:" + declared_parent
        if rnd.finished is None or rnd.saved_state is None:
            raise RuntimeError("simulation round did not complete")
        state_payload = json.loads((rnd.saved_state / "formal-state.json").read_text(encoding="utf-8"))
        state_chain_valid &= len(state_payload["rounds"]) == round_index
        state_record = state_payload["rounds"][-1]
        selected = rnd.finished["selected_artifact_id"]
        selected_source = parent
        if rnd.submitted is not None and selected == f"{task_key}-candidate-{round_index}":
            selected_source = rnd.submitted["directory"] / "checkpoint.npz"
        artifact_root = task_root / f"artifact-{round_index:02d}"
        artifact_root.mkdir()
        next_parent = artifact_root / "checkpoint.npz"
        shutil.copyfile(selected_source, next_parent)
        rounds.append({
            "round_index": round_index,
            "model_call_id": rnd.call_ids[0],
            "action": state_record["action"],
            "outcome": state_record["outcome"],
            "parent_metrics": state_record["parent_metrics"],
            "candidate_metrics": state_record["candidate_metrics"],
            "selected_artifact_id": selected,
            "parent_sha256": declared_parent,
            "selected_sha256": hashlib.sha256(next_parent.read_bytes()).hexdigest(),
        })
        history.append({"id": f"history-{task_key}-{round_index}", "selected_artifact_id": selected})
        parent = next_parent
        state_source = rnd.saved_state
    return {
        "dataset_key": task_key, "task": task, "completed_rounds": 10,
        "parent_chain_valid": bool(parent_chain_valid), "state_chain_valid": bool(state_chain_valid),
        "rounds": rounds,
    }


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    rows = []
    for task in summary["tasks"]:
        selected = sum(item["outcome"] == "candidate_selected" for item in task["rounds"])
        rows.append(
            f"<tr><td>{html.escape(task['dataset_key'])}</td><td>{html.escape(task['task'])}</td>"
            f"<td>{task['completed_rounds']} / 10</td><td>{selected}</td>"
            f"<td>{'通过' if task['parent_chain_valid'] and task['state_chain_valid'] else '失败'}</td></tr>"
        )
    document = f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'>
<title>BRACE-MSI 本地正式协议复演</title><style>body{{font-family:system-ui;margin:40px;max-width:980px}}.warn{{padding:14px;background:#fff2cc;border:1px solid #d6b656}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:10px;text-align:left}}</style>
<h1>训练与评测报告（本地协议复演）</h1><p class='warn'><strong>非官方成绩：</strong>数据为独立构造的合成测试数据，只验证协议、状态与父链，不代表比赛性能。</p>
<p>工业模型优化流程：已完成　轮次：{summary['total_rounds']} / 30　宿主模型调用：{summary['total_model_calls']} / 30</p>
<table><thead><tr><th>任务</th><th>类型</th><th>完成轮次</th><th>采用候选</th><th>链路</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</html>"""
    path.write_text(document, encoding="utf-8")


def run_simulation(output: Path | str) -> dict[str, Any]:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    previous_work = os.environ.get("CONTEST_WORK")
    os.environ["CONTEST_WORK"] = str(output / "workspace")
    try:
        tasks = [
            _simulate_task(output, "A", "classification"),
            _simulate_task(output, "B", "regression"),
            _simulate_task(output, "C", "regression"),
        ]
    finally:
        if previous_work is None:
            os.environ.pop("CONTEST_WORK", None)
        else:
            os.environ["CONTEST_WORK"] = previous_work
    summary = {
        "label": _LABEL,
        "total_rounds": sum(item["completed_rounds"] for item in tasks),
        "total_model_calls": sum(len(item["rounds"]) for item in tasks),
        "tasks": tasks,
    }
    (output / "acceptance.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    _write_report(output / "report.html", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_simulation(args.output)
    print(args.output / "acceptance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
