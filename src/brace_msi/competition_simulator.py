"""Local host simulator for the official workspace-v2 competition protocol.

This module is deliberately excluded from the formal upload image.  It drives
the vendored official ``contest_harness.Round`` object with host frames, keeps
the confirmation partition outside every round, and produces auditable local
receipts without claiming an official score.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import os
from pathlib import Path
import shutil
from typing import Any, Mapping

import numpy as np

from brace_formal.data import load_rows
from brace_formal.metrics import evaluate, resolve_metric_contract
from brace_formal.model import FormalModel
from brace_formal.submission import predict, train
from contest_harness.predict import Sample, normalize_output
from contest_harness.protocol import PROTOCOL
from contest_harness.round import Round, _validate_start


_LABEL = "LOCAL OFFICIAL-PROTOCOL SIMULATION — NOT AN OFFICIAL SCORE"
_CONFIG_FORMAT = "brace-msi.competition-simulation-config.v1"
_REPORT_FORMAT = "brace-msi.competition-simulation-report.v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _artifact_receipt(artifact_id: str, root: Path, descriptor: Mapping[str, Any]) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": len(raw),
                "sha256": "sha256:" + _sha256(raw),
            }
        )
    compact = {"files": files, "artifact": dict(descriptor)}
    return {
        "artifact_id": artifact_id,
        **compact,
        "artifact_sha256": "sha256:" + _sha256(_json_bytes(compact)),
    }


def _write_parent(path: Path, task: str, feature_count: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    paths = [
        json.dumps([["key", "signals"], ["index", index]], separators=(",", ":"))
        for index in range(feature_count)
    ]
    classes = ["class-0", "class-1", "class-2"] if task == "classification" else []
    hidden = min(12, max(4, feature_count * 2))
    output = len(classes) if classes else 1
    parameters = {
        "w1": rng.normal(0.0, 0.08, size=(feature_count, hidden)).astype(np.float64),
        "b1": np.zeros(hidden, dtype=np.float64),
        "w2": rng.normal(0.0, 0.05, size=(hidden, output)).astype(np.float64),
        "b2": np.zeros(output, dtype=np.float64),
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": "local-official-protocol-simulation",
        "task": task,
        "paths": paths,
        "classes": classes,
        "hidden": hidden,
        "seed": seed,
        "epochs": 0,
        "steps": 0,
        "learning_rate": 0.01 if task == "classification" else 0.003,
        "batch_size": 16,
        "parameter_count": sum(value.size for value in parameters.values()),
        "target_mean": 20.0 if task == "regression" else 0.0,
        "target_scale": 10.0 if task == "regression" else 1.0,
    }
    np.savez(
        path,
        **parameters,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in parameters.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in parameters.items()},
        mean=np.zeros(feature_count, dtype=np.float64),
        scale=np.ones(feature_count, dtype=np.float64),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


def _rows(task: str, count: int, feature_count: int, seed: int, prefix: str, drift: float) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    values = rng.normal(drift, 1.0, size=(count, feature_count))
    if task == "classification":
        score = 1.35 * values[:, 0] - 0.8 * values[:, 1] + 0.4 * values[:, -1]
        thresholds = np.quantile(score, [1 / 3, 2 / 3])
        targets = np.digitize(score, thresholds)
        answers: list[Any] = [f"class-{int(value)}" for value in targets]
    else:
        coefficients = np.linspace(1.5, 0.4, feature_count)
        answers = np.maximum(0.0, 20.0 + values @ coefficients + rng.normal(0.0, 0.25, count)).tolist()
    return [
        {
            "id": f"{prefix}-{index:05d}",
            "inputs": {"signals": [float(value) for value in row]},
            "answer": answer,
        }
        for index, (row, answer) in enumerate(zip(values, answers, strict=True))
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


class _LocalHost:
    """Synchronous host side of the official JSONL RPC protocol."""

    def __init__(self, root: Path, dataset_key: str, round_index: int) -> None:
        self.root = root
        self.dataset_key = dataset_key
        self.round_index = round_index
        self.pending: list[str] = []
        self.requests: list[dict[str, Any]] = []
        self.model_receipts: list[dict[str, Any]] = []
        self.artifacts: dict[str, tuple[dict[str, Any], Path]] = {}
        self.history: list[dict[str, Any]] = []
        self.selected_artifact_id: str | None = None
        self.state_sha256 = ""
        self.state_mount = root / "state-mount"
        self.state_mount.mkdir(parents=True, exist_ok=True)

    def write(self, value: str) -> int:
        for line in value.splitlines():
            if not line.strip():
                continue
            request = json.loads(line)
            self.requests.append(request)
            response = self._handle(request)
            self.pending.append(json.dumps(response, separators=(",", ":")) + "\n")
        return len(value)

    def flush(self) -> None:
        return None

    def readline(self) -> str:
        return self.pending.pop(0) if self.pending else ""

    def register_artifact(self, receipt: dict[str, Any], root: Path) -> None:
        self.artifacts[str(receipt["artifact_id"])] = (receipt, root)

    def _model_response(self, request: Mapping[str, Any]) -> dict[str, Any]:
        call_number = len(self.model_receipts) + 1
        call_id = f"local-{self.dataset_key}-{self.round_index}-{call_number}"
        if call_number == 1:
            recipe_id = "native_current" if self.round_index == 1 else "native_replay"
            history_policy = "current" if self.round_index == 1 else "current_plus_history"
            payload = {
                "recipe_id": recipe_id,
                "parameters": {},
                "history_policy": history_policy,
                "hypothesis": "a bounded parent-compatible continuation may improve same-scope evidence",
                "rationale": "use current legal evidence and retained history without task-name routing",
            }
        else:
            payload = {
                "artifact_id": f"candidate-{self.round_index}",
                "rationale": "request the measured candidate while deterministic selection checks metric direction",
            }
        content = json.dumps(payload, separators=(",", ":"))
        request_json = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        prompt_tokens = max(1, len(request_json.encode("utf-8")) // 4)
        completion_tokens = max(1, len(content.encode("utf-8")) // 4)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        receipt = {
            "call_id": call_id,
            "request_json": request_json,
            "response_text": content,
            "usage": usage,
        }
        self.model_receipts.append(receipt)
        return {
            "type": "model_response",
            "id": request["id"],
            "call_id": call_id,
            "response": {
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": usage,
            },
        }

    def _handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        kind = request.get("type")
        if kind == "history_request":
            return {"type": "history_response", "id": request["id"], "records": list(self.history)}
        if kind == "model_request":
            return self._model_response(request)
        if kind == "candidate_request":
            artifact_id = f"artifact-{self.dataset_key}-{self.round_index}"
            root = self.root / "artifacts" / artifact_id
            root.mkdir(parents=True, exist_ok=False)
            for item in request["files"]:
                target = root / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(base64.b64decode(item["data_base64"], validate=True))
            descriptor = dict(request["artifact"])
            receipt = _artifact_receipt(artifact_id, root, descriptor)
            self.register_artifact(receipt, root)
            return {
                "type": "candidate_response",
                "id": request["id"],
                "artifact_id": artifact_id,
                "summary": {"metrics": {}},
            }
        if kind == "state_request":
            shutil.rmtree(self.state_mount, ignore_errors=True)
            self.state_mount.mkdir(parents=True)
            manifest = []
            for item in request["files"]:
                raw = base64.b64decode(item["data_base64"], validate=True)
                target = self.state_mount / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                manifest.append({"path": item["path"], "sha256": _sha256(raw), "size": len(raw)})
            self.state_sha256 = "sha256:" + _sha256(_json_bytes(manifest))
            return {"type": "state_response", "id": request["id"], "state_sha256": self.state_sha256}
        if kind == "artifact_read_request":
            receipt, root = self.artifacts[str(request["artifact_id"])]
            path = root / str(request["path"])
            raw = path.read_bytes()
            offset = int(request["offset"])
            chunk = raw[offset : offset + int(request["length"])]
            return {
                "type": "artifact_read_response",
                "id": request["id"],
                "data_base64": base64.b64encode(chunk).decode("ascii"),
                "eof": offset + len(chunk) == len(raw),
            }
        if kind == "round_complete":
            self.selected_artifact_id = str(request["record"]["selected_artifact_id"])
            return {"type": "round_ack", "accepted": True}
        raise ValueError(f"unsupported host request: {kind}")


def _validate_task_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    task = str(raw.get("task"))
    dataset_key = str(raw.get("dataset_key"))
    if task not in {"classification", "regression"}:
        raise ValueError("simulation task must be classification or regression")
    if dataset_key not in {"A", "B", "C"}:
        raise ValueError("official SDK 1.0.2 simulation dataset_key must be A, B or C")
    rounds = int(raw.get("rounds", 0))
    if rounds != 10:
        raise ValueError("competition simulation requires exactly ten rounds")
    opaque_name = str(raw.get("opaque_name", "")).strip()
    if not opaque_name:
        raise ValueError("opaque_name is required for identity-blind validation")
    return {
        "dataset_key": dataset_key,
        "opaque_name": opaque_name,
        "task": task,
        "rounds": rounds,
        "samples_per_round": int(raw.get("samples_per_round", 24)),
        "validation_samples": int(raw.get("validation_samples", 20)),
        "confirmation_samples": int(raw.get("confirmation_samples", 32)),
        "feature_count": int(raw.get("feature_count", 4)),
        "seed": int(raw.get("seed", 1)),
    }


def _simulate_task(config: Mapping[str, Any], output: Path) -> dict[str, Any]:
    cfg = _validate_task_config(config)
    task_root = output / cfg["opaque_name"]
    task_root.mkdir(parents=True, exist_ok=False)
    source_root = task_root / "source"
    source_root.mkdir()
    initial_checkpoint = source_root / "checkpoint.npz"
    _write_parent(initial_checkpoint, cfg["task"], cfg["feature_count"], cfg["seed"])

    confirmation_path = source_root / "confirmation.jsonl"
    confirmation_rows = _rows(
        cfg["task"], cfg["confirmation_samples"], cfg["feature_count"], cfg["seed"] + 9900,
        "confirmation", 0.9,
    )
    _write_jsonl(confirmation_path, confirmation_rows)
    confirmation_sha256 = _sha256(confirmation_path.read_bytes())

    artifact_root = task_root / "host-artifacts" / "initial"
    artifact_root.mkdir(parents=True)
    shutil.copy2(initial_checkpoint, artifact_root / "checkpoint.npz")
    descriptor = {
        "checkpoint_paths": ["checkpoint.npz"],
        "code_paths": [],
        "predict_argv": ["python3", "/app/harness.py", "predict"],
    }
    parent_receipt = _artifact_receipt(f"initial-{cfg['dataset_key']}", artifact_root, descriptor)
    artifacts: dict[str, tuple[dict[str, Any], Path]] = {
        str(parent_receipt["artifact_id"]): (parent_receipt, artifact_root)
    }
    history: list[dict[str, Any]] = []
    persisted_state = task_root / "persisted-state"
    persisted_state.mkdir()
    state_sha256 = ""
    parent_chain = [str(parent_receipt["artifact_id"])]
    round_reports: list[dict[str, Any]] = []
    all_model_receipts: list[dict[str, Any]] = []

    previous_work = os.environ.get("CONTEST_WORK")
    try:
        for round_index in range(1, 11):
            round_root = task_root / f"round-{round_index:02d}"
            round_root.mkdir()
            train_path = round_root / "train.jsonl"
            validation_path = round_root / "validation.jsonl"
            drift = (round_index - 1) * 0.12
            _write_jsonl(
                train_path,
                _rows(cfg["task"], cfg["samples_per_round"], cfg["feature_count"], cfg["seed"] + 100 * round_index, f"r{round_index}-train", drift),
            )
            _write_jsonl(
                validation_path,
                _rows(cfg["task"], cfg["validation_samples"], cfg["feature_count"], cfg["seed"] + 100 * round_index + 1, f"r{round_index}-gate", drift + 0.03),
            )

            parent_id = parent_chain[-1]
            parent_receipt, parent_store = artifacts[parent_id]
            parent_checkpoint = parent_store / "checkpoint.npz"
            parent_digest = "sha256:" + _sha256(parent_checkpoint.read_bytes())
            task_contract = {
                "task": cfg["task"],
                "metric": "macro_f1" if cfg["task"] == "classification" else "rmse",
                "metric_direction": "higher" if cfg["task"] == "classification" else "lower",
                "public_projection": {
                    "train_path": str(train_path),
                    "validation_path": str(validation_path),
                },
            }
            frame = {
                "protocol": PROTOCOL,
                "prompt": "Autonomously design and assess one bounded industrial-model continuation experiment.",
                "prompt_version": "local-official-sim-v1",
                "dataset_key": cfg["dataset_key"],
                "round_index": round_index,
                "stage_id": "local-official-protocol-simulation",
                "task_contract": task_contract,
                "model_name": "Qwen/Qwen3.5-4B",
                "max_output_tokens": 4096,
                "resource_limits": {"cpu_count": 4, "memory_bytes": 8 * 1024**3},
                "parent_checkpoint_sha256": parent_digest,
                "parent_artifact": parent_receipt,
                "artifacts": [item[0] for item in artifacts.values()],
                "state_path": str(persisted_state) if any(persisted_state.iterdir()) else None,
                "state_sha256": state_sha256,
            }
            _validate_start(frame)
            host = _LocalHost(round_root / "host", cfg["dataset_key"], round_index)
            host.history = list(history)
            host.artifacts = dict(artifacts)
            rnd = Round(frame, host, host)
            rnd.parent.root = parent_store
            work_root = round_root / "work"
            os.environ["CONTEST_WORK"] = str(work_root)
            train(rnd)
            if host.selected_artifact_id is None:
                raise RuntimeError("round completed without selected artifact")
            for artifact_id, artifact in host.artifacts.items():
                artifacts[artifact_id] = artifact
            shutil.rmtree(persisted_state, ignore_errors=True)
            shutil.copytree(host.state_mount, persisted_state)
            state_sha256 = host.state_sha256
            history.append(
                {
                    "id": f"history-{cfg['dataset_key']}-{round_index}",
                    "round_index": round_index,
                    "selected_artifact_id": host.selected_artifact_id,
                }
            )
            parent_chain.append(host.selected_artifact_id)
            all_model_receipts.extend(host.model_receipts)
            ledger = json.loads((persisted_state / "round-ledger.json").read_text(encoding="utf-8"))
            receipt = ledger["rounds"][-1]
            usage = {
                key: sum(int(item["usage"][key]) for item in host.model_receipts)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
            evaluations = receipt["artifact_evaluations"]
            candidate_eval = next((item for item in evaluations if item["role"] == "candidate"), None)
            round_reports.append(
                {
                    "round_index": round_index,
                    "hypothesis": receipt["experiment_proposal"]["hypothesis"],
                    "executed_recipe_id": receipt["executed_recipe_id"],
                    "candidate_trained": receipt["candidate_trained"],
                    "candidate_artifact_id": receipt["candidate_artifact_id"],
                    "parent_artifact_id": receipt["parent_artifact_id"],
                    "parent_checkpoint_sha256": receipt["parent_checkpoint_sha256"],
                    "selected_checkpoint_sha256": receipt["selected_checkpoint_sha256"],
                    "parent_metrics": receipt["parent_metrics"],
                    "candidate_metrics": receipt["candidate_metrics"],
                    "requested_artifact_id": receipt["selection"]["requested_artifact_id"],
                    "applied_artifact_id": receipt["selected_artifact_id"],
                    "applied_role": receipt["selection"]["applied_role"],
                    "request_honored": receipt["selection"]["request_honored"],
                    "model_call_ids": [item["call_id"] for item in host.model_receipts],
                    "token_usage": usage,
                    "cpu_seconds": float((candidate_eval or {}).get("resource_evidence", {}).get("cpu_seconds", 0.0)),
                    "wall_seconds": float(receipt["timing"]["observed_seconds_before_state_rpc"]),
                    "peak_rss_bytes": (candidate_eval or {}).get("resource_evidence", {}).get("peak_rss_bytes"),
                    "history_count_before_round": round_index - 1,
                    "host_resource_fields": dict(frame["resource_limits"]),
                    "validation_sha256": receipt["validation_sha256"],
                }
            )
    finally:
        if previous_work is None:
            os.environ.pop("CONTEST_WORK", None)
        else:
            os.environ["CONTEST_WORK"] = previous_work

    final_id = parent_chain[-1]
    _, final_root = artifacts[final_id]
    final_checkpoint = final_root / "checkpoint.npz"
    model = FormalModel.load(final_checkpoint)
    confirmation = load_rows(confirmation_path, model, require_answers=True)
    contract = resolve_metric_contract(
        {"task": cfg["task"], "metric": "macro_f1" if cfg["task"] == "classification" else "rmse"},
        cfg["task"],
    )
    confirmation_metrics = evaluate(model, confirmation.x, confirmation.y, contract)
    predictions = []
    previous_artifact = os.environ.get("CONTEST_ARTIFACT_PATH")
    try:
        os.environ.pop("CONTEST_ARTIFACT_PATH", None)
        for row in confirmation_rows:
            result = normalize_output(
                cfg["task"],
                predict(Sample(cfg["task"], row["inputs"]), final_root),
            )
            predictions.append({"id": row["id"], **result})
    finally:
        if previous_artifact is not None:
            os.environ["CONTEST_ARTIFACT_PATH"] = previous_artifact
    predictions_path = task_root / "predictions.jsonl"
    predictions_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
            for item in predictions
        ),
        encoding="utf-8",
    )

    return {
        "dataset_key": cfg["dataset_key"],
        "opaque_name": cfg["opaque_name"],
        "task": cfg["task"],
        "resource_contract": {"cpu_count": 4, "memory_bytes": 8 * 1024**3},
        "rounds": round_reports,
        "model_calls": len(all_model_receipts),
        "model_receipts": all_model_receipts,
        "real_candidates": sum(bool(item["candidate_trained"]) for item in round_reports),
        "history_records": len(history),
        "parent_chain": parent_chain,
        "final_artifact_id": final_id,
        "final_checkpoint_sha256": "sha256:" + _sha256(final_checkpoint.read_bytes()),
        "final_confirmation_sha256": confirmation_sha256,
        "final_confirmation_read_count": 1,
        "final_confirmation_metrics": {key: float(value) for key, value in confirmation_metrics.items()},
        "final_prediction_count": len(predictions),
        "final_predictions_path": str(predictions_path.relative_to(output).as_posix()),
    }


def render_html(report: Mapping[str, Any]) -> str:
    sections = []
    for task in report["tasks"]:
        rows = []
        for item in task["rounds"]:
            rows.append(
                "<tr>"
                f"<td>{item['round_index']}</td>"
                f"<td>{html.escape(str(item['executed_recipe_id']))}</td>"
                f"<td><code>{html.escape(str(item['parent_metrics']))}</code></td>"
                f"<td><code>{html.escape(str(item['candidate_metrics']))}</code></td>"
                f"<td>{html.escape(str(item['applied_role']))}</td>"
                f"<td>{item['token_usage']['total_tokens']}</td>"
                f"<td>{item['cpu_seconds']:.4f}</td>"
                f"<td>{item['wall_seconds']:.4f}</td>"
                "</tr>"
            )
        sections.append(
            f"<section><h2>{html.escape(task['opaque_name'])} · {html.escape(task['task'])}</h2>"
            f"<p>10轮完成；真实候选 {task['real_candidates']}/10；模型调用 {task['model_calls']}；"
            f"最终确认（仅冻结后一次）：<code>{html.escape(str(task['final_confirmation_metrics']))}</code></p>"
            "<table><thead><tr><th>轮次</th><th>实验recipe</th><th>父模型指标</th><th>候选指标</th>"
            "<th>实际选择</th><th>Token</th><th>CPU秒</th><th>墙钟秒</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></section>"
        )
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>BRACE-MSI 本地训练与评测报告</title>
<style>body{font-family:system-ui,sans-serif;max-width:1500px;margin:28px auto;padding:0 20px;color:#222}header{border:2px solid #b45309;background:#fff7ed;padding:18px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #ddd;padding:7px;vertical-align:top}th{background:#f3f4f6}code{white-space:pre-wrap}section{margin:28px 0}.warn{font-weight:700;color:#9a3412}</style></head><body>""" + (
        f"<header><h1>{html.escape(str(report['label']))}</h1>"
        "<p class=\"warn\">本报告仅验证本地协议、训练、选择、父链、预测与资源记录；不代表官方隐藏评测成绩。</p>"
        "<p>Agent：官方宿主模型RPC的本地替身（PyTRiO/Qwen结构化决策语义）；"
        "SwanLab：仅在后续正式实验任务同步脱敏聚合记录，本模拟未伪造云端运行。</p></header>"
        + "".join(sections)
        + "</body></html>"
    )


def run_simulation(config: Mapping[str, Any], output: Path | str) -> dict[str, Any]:
    if config.get("format") != _CONFIG_FORMAT or not isinstance(config.get("tasks"), list):
        raise ValueError("competition simulation config is invalid")
    root = Path(output)
    if root.exists():
        raise FileExistsError(f"simulation output already exists: {root}")
    root.mkdir(parents=True)
    tasks = [_simulate_task(item, root) for item in config["tasks"]]
    report: dict[str, Any] = {
        "format": _REPORT_FORMAT,
        "label": _LABEL,
        "valid": all(
            len(task["rounds"]) == 10
            and task["model_calls"] == 20
            and task["real_candidates"] == 10
            and task["final_prediction_count"] > 0
            for task in tasks
        ),
        "official_hidden_score": None,
        "official_protocol": PROTOCOL,
        "model_name": str(config.get("model_name", "Qwen/Qwen3.5-4B")),
        "pytrio_mode": "local host receipt substitute; no remote call claimed",
        "swanlab_mode": "not synced in local simulator; Task 11 owns sanitized aggregate sync",
        "tasks": tasks,
    }
    _atomic_json(root / "report.json", report)
    (root / "report.html").write_text(render_html(report), encoding="utf-8")
    return report


def load_and_run(config_path: Path | str, output: Path | str) -> dict[str, Any]:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("config root must be an object")
    return run_simulation(config, output)

