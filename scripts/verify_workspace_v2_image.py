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
    "opaque-classification": "cpu-a-guide-20261110-v1",
    "opaque-regression": "cpu-c-guide-20261110-v1",
}
TASKS = {
    "A": ("classification", "macro_f1", "higher"),
    "B": ("regression", "rmse", "lower"),
    "C": ("regression", "rmse", "lower"),
    "opaque-classification": ("classification", "macro_f1", "higher"),
    "opaque-regression": ("regression", "rmse", "lower"),
}
SDK_KEYS = {
    "A": "A",
    "B": "B",
    "C": "C",
    # The vendored official SDK accepts only protocol slots A/B/C.  Opaque
    # coverage changes content identity while remaining in a legal slot.
    "opaque-classification": "A",
    "opaque-regression": "C",
}


def _resolve_profiles(value: str | None) -> tuple[str, ...]:
    if value is None:
        return tuple(PACKAGES)
    profiles = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = [item for item in profiles if item not in PACKAGES]
    if not profiles or unknown:
        raise ValueError("unknown acceptance profile: " + ",".join(unknown or [str(value)]))
    if len(set(profiles)) != len(profiles):
        raise ValueError("acceptance profiles must be unique")
    return profiles
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


def _materialize_round_data(
    package: Path, destination: Path, profile: str, round_index: int
) -> Path:
    """Create one current-round view with unique legal training identities.

    The official packages provide one public development projection, not the
    platform's private ten incoming batches.  This protocol-only acceptance
    therefore reuses feature/label values but namespaces each round's training
    IDs.  Validation remains fixed and external to replay.  The result is never
    reported as a performance or hidden-data simulation.
    """

    destination.mkdir(parents=True, exist_ok=False)
    source = package / "public"
    for name in ("train.jsonl", "validation.jsonl"):
        target = destination / name
        rows = []
        with (source / name).open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                if name == "train.jsonl":
                    row["id"] = f"{profile}-round-{round_index:02d}-{row['id']}"
                rows.append(row)
        target.write_text(
            "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )
    return destination


def _proposal(
    messages: list[dict[str, Any]], *, mode: str = "best"
) -> dict[str, Any]:
    content = str(messages[0].get("content", "")) if messages else ""
    context = json.loads(content.split(" Context: ", 1)[1])
    if "Required fields: recipe_id" in content:
        recipes = context.get("available_recipes") or []
        by_id = {
            item.get("recipe_id"): item
            for item in recipes
            if isinstance(item, dict) and isinstance(item.get("recipe_id"), str)
        }
        completed = int((context.get("history_summary") or {}).get("completed_rounds", 0))
        preferred = "native_replay" if completed and "native_replay" in by_id else "native_current"
        chosen = by_id.get(preferred) or next(iter(by_id.values()))
        proposal = {
            "recipe_id": chosen["recipe_id"],
            "parameters": {},
            "history_policy": chosen["history_policy"],
            "hypothesis": "a bounded parent-compatible continuation may improve same-scope evidence",
            "rationale": "run one registered experiment and let deterministic selection verify the result",
        }
    else:
        contract = context["metric_contract"]
        metric = contract.get("metric", contract.get("name"))
        if not isinstance(metric, str):
            raise ValueError("deployment metric contract has no primary metric")
        direction = contract["direction"]
        metrics = context["artifact_metrics"]
        legal = list(context["legal_artifact_ids"])
        scored = [
            (artifact_id, float(metrics[artifact_id][metric]))
            for artifact_id in legal
            if artifact_id in metrics and metric in metrics[artifact_id]
        ]
        if not scored:
            artifact_id = legal[0]
        else:
            choose_max = (direction == "higher") != (mode == "worst")
            artifact_id = (max if choose_max else min)(scored, key=lambda item: item[1])[0]
        proposal = {
            "artifact_id": artifact_id,
            "rationale": "request the measured artifact selected by the local protocol host",
        }
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
    sdk_key = SDK_KEYS[profile]
    checkpoint = next(
        item for item in parent["files"] if item["path"] == "checkpoint.npz"
    )
    return {
        "protocol": "contest.harness.workspace.v2",
        "run_id": f"local-{profile}",
        "dataset_key": sdk_key,
        "round_index": round_index,
        "stage_id": "local-protocol-only",
        "prompt": PROMPT,
        "prompt_version": "industrial-workspace-flexible-v3",
        "rounds_per_dataset": 10,
        "parent_checkpoint_sha256": checkpoint["sha256"],
        "task_contract": {
            "dataset_key": sdk_key,
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


def _merge_round_record(
    finish_record: dict[str, Any], state_root: Path | None
) -> dict[str, Any]:
    if state_root is None:
        return dict(finish_record)
    receipt = state_root / "round-receipt.json"
    if not receipt.is_file():
        return dict(finish_record)
    detailed = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(detailed, dict):
        raise RuntimeError("round receipt in state is not an object")
    detailed.update(finish_record)
    return detailed


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
    artifact_roots: dict[str, Path],
    proposal_mode: str = "best",
) -> tuple[dict[str, Any], dict[str, Any] | None, Path | None]:
    workspace = run_root / "workspace"
    workspace.mkdir(exist_ok=True)
    round_data = _materialize_round_data(
        package, run_root / f"round-{round_index:02d}-data", profile, round_index
    )
    command = [
        "docker", "run", "--rm", "-i", "--network", "none", "--cpus", "4",
        "--memory", "4g", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        *_docker_mount(round_data, "/data", True),
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
                "response": _proposal(raw_messages, mode=proposal_mode),
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
        elif kind == "artifact_read_request":
            artifact_id = str(message["artifact_id"])
            root = artifact_roots.get(artifact_id)
            if root is None:
                raise RuntimeError(f"artifact root unavailable: {artifact_id}")
            source = root / str(message["path"])
            raw = source.read_bytes()
            offset = int(message["offset"])
            chunk = raw[offset : offset + int(message["length"])]
            reply = {
                "type": "artifact_read_response",
                "id": message["id"],
                "data_base64": base64.b64encode(chunk).decode("ascii"),
                "eof": offset + len(chunk) == len(raw),
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
    return _merge_round_record(record, next_state), candidate_receipt, next_state


def _predict(
    image: str, profile: str, artifact_root: Path, validation: Path
) -> tuple[int, str]:
    rows = []
    with validation.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                rows.append(row)
                if len(rows) == 5:
                    break
    task = TASKS[profile][0]
    sdk_key = SDK_KEYS[profile]
    context = {
        "protocol": "contest.predict-context.v1",
        "dataset_key": sdk_key,
        "task": task,
        "artifact": {"checkpoint_paths": ["checkpoint.npz"], "code_paths": [], "predict_argv": ["python3", "/app/harness.py", "predict"]},
        "artifact_id": f"final-{profile}",
    }
    command = [
        "docker", "run", "--rm", "-i", "--network", "none", "--cpus", "4",
        "--memory", "4g", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        *_docker_mount(artifact_root, "/model", True),
        "-e", "CONTEST_ARTIFACT_PATH=/model/checkpoint.npz",
        "-e", "CONTEST_DATASET_KEY=" + sdk_key,
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
    encoded = json.dumps(outputs, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return len(outputs), hashlib.sha256(encoded).hexdigest()


def run(
    image: str,
    package_root: Path,
    output: Path,
    *,
    proposal_mode: str = "best",
    profiles: tuple[str, ...] | None = None,
    round_count: int = 10,
) -> dict[str, Any]:
    if not 1 <= round_count <= 10:
        raise ValueError("round_count must be between 1 and 10")
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "format": "brace-msi.workspace-v2-acceptance.v1",
        "scope": "local_protocol_only_not_official_score",
        "image": image,
        "profiles": {},
    }
    selected_profiles = tuple(PACKAGES) if profiles is None else profiles
    for profile in selected_profiles:
        name = PACKAGES[profile]
        package = package_root / name
        profile_root = output / profile
        profile_root.mkdir()
        baseline_root = profile_root / "baseline"
        baseline_root.mkdir()
        shutil.copy2(package / "checkpoint.npz", baseline_root / "checkpoint.npz")
        parent_root = baseline_root
        parent = _artifact_receipt(f"baseline-{profile}", baseline_root)
        artifacts = [parent]
        artifact_roots = {parent["artifact_id"]: baseline_root}
        state_root = None
        history: list[dict[str, Any]] = []
        rounds = []
        for round_index in range(1, round_count + 1):
            incoming_parent = parent
            record, candidate, next_state = _run_round(
                image=image, profile=profile, round_index=round_index, package=package,
                parent_root=parent_root, parent=parent, state_root=state_root,
                run_root=profile_root, history=history, artifacts=artifacts,
                artifact_roots=artifact_roots,
                proposal_mode=proposal_mode,
            )
            if candidate is not None:
                artifacts.append(candidate)
                artifact_roots[candidate["artifact_id"]] = (
                    profile_root / f"round-{round_index:02d}-artifact"
                )
            selected = record["selected_artifact_id"]
            if candidate is not None and selected == candidate["artifact_id"]:
                parent = candidate
                parent_root = profile_root / f"round-{round_index:02d}-artifact"
            elif selected != parent["artifact_id"]:
                raise RuntimeError("round selected an unknown artifact")
            state_root = next_state
            history.append({
                "id": f"history-{profile}-{round_index}",
                "round_index": round_index,
                "selected_artifact_id": selected,
            })
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
                    "requested_artifact_id": record.get("selection", {}).get("requested_artifact_id"),
                    "locally_applied_artifact_id": record.get("selection", {}).get("applied_artifact_id"),
                    "applied_role": record.get("selection", {}).get("applied_role"),
                    "parent_metrics": record.get("parent_metrics"),
                    "candidate_metrics": record.get("candidate_metrics"),
                    "executed_recipe_id": record.get("executed_recipe_id"),
                    "selection_reason": record.get("selection", {}).get("reason"),
                    "selection": record.get("selection"),
                    "metric_contract": record.get("metric_contract"),
                    "artifact_evaluations": record.get("artifact_evaluations"),
                }
            )
        prediction_count, prediction_digest = _predict(
            image, profile, parent_root, package / "public" / "validation.jsonl"
        )
        reload_count, reload_digest = _predict(
            image, profile, parent_root, package / "public" / "validation.jsonl"
        )
        report["profiles"][profile] = {
            "rounds": rounds,
            "round_count": len(rounds),
            "model_call_count": sum(len(row["model_call_ids"]) for row in rounds),
            "prediction_smoke_rows": prediction_count,
            "prediction_sha256": prediction_digest,
            "model_reload_predictions_equal": (
                prediction_count == reload_count and prediction_digest == reload_digest
            ),
            "final_artifact_id": parent["artifact_id"],
        }
    report["valid"] = all(
        item["round_count"] == round_count
        and item["model_call_count"] == 2 * round_count
        and all(row["candidate_submitted"] for row in item["rounds"])
        and item["prediction_smoke_rows"] == 5
        and item["model_reload_predictions_equal"] is True
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
    parser.add_argument("--proposal-mode", choices=("best", "worst"), default="best")
    parser.add_argument("--profiles", help="comma-separated registered local acceptance profiles")
    parser.add_argument("--rounds", type=int, default=10)
    args = parser.parse_args()
    report = run(
        args.image, args.package_root, args.output,
        proposal_mode=args.proposal_mode,
        profiles=_resolve_profiles(args.profiles),
        round_count=args.rounds,
    )
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
