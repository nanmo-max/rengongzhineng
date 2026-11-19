"""Protocol-only Docker acceptance for contest.harness.workspace.v2.

The stand-in host follows the public SDK 1.0.2 frames and returns locally
computed candidate measurements through the authoritative host response.
It never represents official scoring.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from brace_formal.data import load_rows
from brace_formal.metrics import evaluate
from brace_formal.model import FormalModel


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}
TASKS = {
    "A": ("classification", "macro_f1", "higher"),
    "B": ("regression", "rmse", "lower"),
    "C": ("regression", "rmse", "lower"),
}
PROMPT = (
    "从官方父检查点与本轮公开投影出发，在授权预算内提出一个结构化、"
    "可审计且不绕过安全门的续训或保留决策。"
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_receipt(artifact_id: str, root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": "sha256:" + _sha(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    descriptor = {
        "checkpoint_paths": ["checkpoint.npz"],
        "code_paths": [],
        "predict_argv": ["python3", "/app/harness.py", "predict"],
    }
    encoded = json.dumps(
        {"files": files, "artifact": descriptor},
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "artifact_id": artifact_id,
        "artifact_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "artifact": descriptor,
        "files": files,
    }


def _score_candidate(artifact_root: Path, validation_path: Path) -> dict[str, float]:
    model = FormalModel.load(artifact_root / "checkpoint.npz")
    validation = load_rows(validation_path, model, require_answers=True)
    return evaluate(model, validation.x, validation.y)


def _decode_files(items: list[dict[str, Any]], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for item in items:
        target = destination / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(item["data_base64"], validate=True))


def _proposal(messages: list[dict[str, Any]]) -> dict[str, Any]:
    content = str(messages[0].get("content", "")) if messages else ""
    if "Required fields: recipe" in content:
        proposal = {
            "recipe": "e1_lr1",
            "rationale": "run one low-cost parent-compatible continuation before evaluating deployment",
        }
    else:
        context = json.loads(content.split(" Context: ", 1)[1])
        metric = context["metric"]
        before = float(context["parent_metrics"][metric])
        after = float(context["candidate_metrics"][metric])
        improved = after > before if context["metric_direction"] == "higher" else after < before
        unchanged = abs(after - before) <= 1e-12
        decision = "deploy" if improved else ("retain" if unchanged else "rollback")
        rationale = {
            "deploy": "deploy because the locally measured primary metric improved",
            "retain": "retain the parent because the candidate was equivalent on the primary metric",
            "rollback": "rollback to the parent because the candidate regressed on the primary metric",
        }[decision]
        proposal = {"decision": decision, "rationale": rationale}
    return {
        "id": "chatcmpl-local-protocol",
        "model": "Qwen/Qwen3.5-4B",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(proposal)},
            }
        ],
        "usage": {"prompt_tokens": 101, "completion_tokens": 37, "total_tokens": 138},
    }


def _start_frame(
    profile: str,
    round_index: int,
    parent: dict[str, Any],
    state_root: Path | None,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    task, metric, direction = TASKS[profile]
    checkpoint = next(
        item for item in parent["files"] if item["path"] == "checkpoint.npz"
    )
    return {
        "protocol": "contest.harness.workspace.v2",
        "run_id": f"local-{profile}",
        "dataset_key": profile,
        "round_index": round_index,
        "stage_id": "local-protocol-only",
        "prompt": PROMPT,
        "prompt_version": "industrial-workspace-flexible-v3",
        "rounds_per_dataset": 10,
        "parent_checkpoint_sha256": checkpoint["sha256"],
        "task_contract": {
            "dataset_key": profile,
            "task": task,
            "metric": metric,
            "metric_direction": direction,
            "public_projection": {
                "train_path": "/data/train.jsonl",
                "validation_path": "/data/validation.jsonl",
                "row_fields": ["id", "inputs", "answer"],
                "source_metadata": False,
            },
        },
        "model_name": "Qwen/Qwen3.5-4B",
        "parent_artifact": parent,
        "artifacts": artifacts,
        "state_sha256": "" if state_root is None else "sha256:" + _tree_sha(state_root),
        "state_path": None if state_root is None else "/state",
        "max_output_tokens": 768,
        "resource_limits": {
            "candidate_upload_bytes_per_round": 64 * 1024 * 1024,
            "state_upload_bytes_per_round": 64 * 1024 * 1024,
        },
        "current_validation": {},
        "wall_seconds": 600,
    }


def _tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _docker_mount(path: Path, target: str, readonly: bool = False) -> list[str]:
    suffix = ":ro" if readonly else ""
    return ["-v", f"{path.resolve()}:{target}{suffix}"]


def _run_round(
    *,
    image: str,
    profile: str,
    round_index: int,
    package: Path,
    parent_root: Path,
    parent: dict[str, Any],
    state_root: Path | None,
    run_root: Path,
    history: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None, Path | None]:
    workspace = run_root / "workspace"
    workspace.mkdir(exist_ok=True)
    command = [
        "docker", "run", "--rm", "-i", "--network", "none", "--cpus", "4",
        "--memory", "8g", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        *_docker_mount(package / "public", "/data", True),
        *_docker_mount(parent_root, "/previous", True),
        *_docker_mount(workspace, "/workspace"),
    ]
    if state_root is not None:
        command.extend(_docker_mount(state_root, "/state", True))
    command.extend([image, "train"])
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdin is not None and process.stdout is not None
    frame = _start_frame(profile, round_index, parent, state_root, artifacts)
    process.stdin.write(json.dumps(frame, ensure_ascii=False) + "\n")
    process.stdin.flush()
    sequence = 0
    candidate_receipt = None
    next_state = None
    record = None
    model_calls = []
    while True:
        line = process.stdout.readline()
        if not line:
            break
        message = json.loads(line)
        kind = message.get("type")
        if kind == "round_failed":
            raise RuntimeError(f"round {profile}-{round_index} failed: {message}")
        if kind == "round_complete":
            record = message["record"]
            process.stdin.write(json.dumps({"type": "round_ack", "accepted": True}) + "\n")
            process.stdin.flush()
            process.stdin.close()
            break
        if message.get("id") != sequence:
            raise RuntimeError("RPC sequence mismatch")
        sequence += 1
        if kind == "history_request":
            reply = {"type": "history_response", "id": message["id"], "records": history}
        elif kind == "model_request":
            raw_messages = message.get("messages") or []
            if any(PROMPT in str(item.get("content", "")) for item in raw_messages):
                raise RuntimeError("participant duplicated the official prompt")
            if message.get("max_tokens") != frame["max_output_tokens"]:
                raise RuntimeError("participant did not use the expected host token budget")
            if message.get("enable_thinking") is not False:
                raise RuntimeError("participant did not disable thinking for the JSON proposal")
            if message.get("response_format") != {"type": "json_object"}:
                raise RuntimeError("participant did not request one JSON object")
            call_id = f"call-{profile}-{round_index}-{len(model_calls) + 1}"
            model_calls.append(call_id)
            reply = {
                "type": "model_response", "id": message["id"], "call_id": call_id,
                "response": _proposal(raw_messages),
            }
        elif kind == "state_request":
            next_state = run_root / f"round-{round_index:02d}-state"
            _decode_files(message.get("files") or [], next_state)
            reply = {
                "type": "state_response", "id": message["id"],
                "state_sha256": "sha256:" + _tree_sha(next_state),
            }
        elif kind == "candidate_request":
            candidate_root = run_root / f"round-{round_index:02d}-artifact"
            _decode_files(message["files"], candidate_root)
            candidate_receipt = _artifact_receipt(
                f"candidate-{profile}-{round_index}", candidate_root
            )
            reply = {
                "type": "candidate_response", "id": message["id"],
                "artifact_id": candidate_receipt["artifact_id"],
            }
        else:
            raise RuntimeError(f"unexpected host request: {kind}")
        process.stdin.write(json.dumps(reply, ensure_ascii=False) + "\n")
        process.stdin.flush()
    stderr = process.stderr.read() if process.stderr is not None else ""
    code = process.wait(timeout=600)
    if code != 0 or record is None:
        raise RuntimeError(f"container round failed ({code}): {stderr[-4000:]}")
    if not model_calls or record.get("model_call_ids") != model_calls:
        raise RuntimeError("round did not cite all real model calls")
    return record, candidate_receipt, next_state


def _predict(image: str, profile: str, artifact_root: Path, validation: Path) -> int:
    rows = []
    with validation.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                rows.append(row)
                if len(rows) == 5:
                    break
    task = TASKS[profile][0]
    context = {
        "protocol": "contest.predict-context.v1",
        "dataset_key": profile,
        "task": task,
        "artifact": {"checkpoint_paths": ["checkpoint.npz"], "code_paths": [], "predict_argv": ["python3", "/app/harness.py", "predict"]},
        "artifact_id": f"final-{profile}",
    }
    command = [
        "docker", "run", "--rm", "-i", "--network", "none", "--cpus", "4",
        "--memory", "8g", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        *_docker_mount(artifact_root, "/model", True),
        "-e", "CONTEST_ARTIFACT_PATH=/model/checkpoint.npz",
        "-e", "CONTEST_DATASET_KEY=" + profile,
        "-e", "CONTEST_TASK=" + task,
        "-e", "CONTEST_PREDICTION_CONTEXT=" + json.dumps(context, separators=(",", ":")),
        image, "predict",
    ]
    requests = "".join(
        json.dumps({"task": task, "inputs": row["inputs"]}, separators=(",", ":")) + "\n"
        for row in rows
    )
    completed = subprocess.run(command, input=requests, text=True, encoding="utf-8", capture_output=True, timeout=120)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-4000:])
    outputs = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    if len(outputs) != len(rows):
        raise RuntimeError("prediction did not return one row per input")
    return len(outputs)


def run(image: str, package_root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "format": "brace-msi.workspace-v2-acceptance.v1",
        "scope": "local_protocol_only_not_official_score",
        "image": image,
        "profiles": {},
    }
    for profile, name in PACKAGES.items():
        package = package_root / name
        profile_root = output / profile
        profile_root.mkdir()
        baseline_root = profile_root / "baseline"
        baseline_root.mkdir()
        shutil.copy2(package / "checkpoint.npz", baseline_root / "checkpoint.npz")
        parent_root = baseline_root
        parent = _artifact_receipt(f"baseline-{profile}", baseline_root)
        artifacts = [parent]
        state_root = None
        history: list[dict[str, Any]] = []
        rounds = []
        for round_index in range(1, 11):
            incoming_parent = parent
            record, candidate, next_state = _run_round(
                image=image, profile=profile, round_index=round_index, package=package,
                parent_root=parent_root, parent=parent, state_root=state_root,
                run_root=profile_root, history=history, artifacts=artifacts,
            )
            if candidate is not None:
                artifacts.append(candidate)
            selected = record["selected_artifact_id"]
            if candidate is not None and selected == candidate["artifact_id"]:
                parent = candidate
                parent_root = profile_root / f"round-{round_index:02d}-artifact"
            elif selected != parent["artifact_id"]:
                raise RuntimeError("round selected an unknown artifact")
            state_root = next_state
            history.append({"id": f"history-{profile}-{round_index}", "round_index": round_index})
            rounds.append(
                {
                    "round_index": round_index,
                    "selected_artifact_id": selected,
                    "model_call_ids": record["model_call_ids"],
                    "candidate_submitted": candidate is not None,
                    "incoming_parent_checkpoint_sha256": next(
                        item["sha256"] for item in incoming_parent["files"] if item["path"] == "checkpoint.npz"
                    ),
                    "selected_checkpoint_sha256": next(
                        item["sha256"] for item in parent["files"] if item["path"] == "checkpoint.npz"
                    ),
                }
            )
        prediction_count = _predict(
            image, profile, parent_root, package / "public" / "validation.jsonl"
        )
        report["profiles"][profile] = {
            "rounds": rounds,
            "round_count": len(rounds),
            "model_call_count": sum(len(row["model_call_ids"]) for row in rounds),
            "prediction_smoke_rows": prediction_count,
            "final_artifact_id": parent["artifact_id"],
        }
    report["valid"] = all(
        item["round_count"] == 10
        and item["model_call_count"] >= 10
        and item["prediction_smoke_rows"] == 5
        for item in report["profiles"].values()
    )
    (output / "acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.image, args.package_root, args.output)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
