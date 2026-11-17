"""Official ``contest.harness.workspace.v2`` participant boundary.

This module is intentionally thin.  The official SDK owns framing, mounted
paths, model receipts and artifact transfer.  BRACE-MSI keeps ownership of the
already-verified native checkpoint continuation, bounded policy and prediction
logic.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .platform_runtime import (
    PlatformRuntimeConfig,
    _NativeModel,
    _flatten,
    start_round,
)


TASKS = ("classification", "regression")
PREDICT_ARGV = ["python3", "/app/harness.py", "predict"]


def _bounded_int(name: str, default: int, lower: int, upper: int) -> int:
    raw = os.environ.get(name)
    value = default if raw is None else int(raw)
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be in {lower}..{upper}")
    return value


def _bounded_float(name: str, default: float, lower: float, upper: float) -> float:
    raw = os.environ.get(name)
    value = default if raw is None else float(raw)
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"{name} must be in {lower}..{upper}")
    return value


def _runtime_config() -> PlatformRuntimeConfig:
    mode = os.environ.get("BRACE_POLICY_MODE", "portfolio")
    return PlatformRuntimeConfig(
        policy_mode=mode,
        max_training_rounds=_bounded_int("BRACE_MAX_TRAINING_ROUNDS", 8, 0, 10),
        min_relative_improvement=_bounded_float(
            "BRACE_MIN_RELATIVE_IMPROVEMENT", 0.0, -1.0, 1.0
        ),
        max_replay_samples=_bounded_int("BRACE_MAX_REPLAY_SAMPLES", 4096, 0, 100000),
    )


def _checkpoint_relative(rnd: Any) -> str:
    descriptor = getattr(rnd.parent, "descriptor", None)
    paths = descriptor.get("checkpoint_paths") if isinstance(descriptor, Mapping) else None
    matches = [path for path in paths or () if isinstance(path, str) and path.endswith(".npz")]
    if len(matches) != 1:
        raise ValueError("parent artifact must declare exactly one NPZ checkpoint")
    return matches[0]


def _host_model_transport(rnd: Any, request: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(request, Mapping):
        raise TypeError("model request must be an object")
    if request.get("model") != rnd.model_name:
        raise ValueError("model request differs from the platform-bound model")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("model messages are required")
    options = {
        key: value
        for key, value in request.items()
        if key not in {"model", "messages"}
    }
    receipt = rnd.model(messages, **options)
    if not isinstance(receipt.response, Mapping):
        raise ValueError("host model response must be an object")
    return receipt.response


def _metric_value(payload: Any, metric: str) -> float | None:
    if not isinstance(payload, Mapping):
        return None
    direct = payload.get(metric)
    if isinstance(direct, (int, float)) and not isinstance(direct, bool) and math.isfinite(direct):
        return float(direct)
    for key in ("metrics", "summary", "validation", "current_validation"):
        nested = _metric_value(payload.get(key), metric)
        if nested is not None:
            return nested
    return None


def _platform_measurement_accepts(rnd: Any, submitted: Mapping[str, Any]) -> bool:
    """Reject a measured regression when both parent and candidate values exist.

    The SDK intentionally leaves the response shape extensible.  Missing values
    therefore do not invent a score; they leave the already-verified internal
    SafetyGate decision unchanged.
    """

    task = rnd.task if isinstance(getattr(rnd, "task", None), Mapping) else {}
    metric = task.get("metric")
    direction = task.get("metric_direction")
    if not isinstance(metric, str) or direction not in {"higher", "lower"}:
        return True
    candidate = _metric_value(submitted.get("summary"), metric)
    parent = _metric_value(getattr(rnd, "frame", {}).get("current_validation"), metric)
    if candidate is None or parent is None:
        return True
    return candidate >= parent if direction == "higher" else candidate <= parent


def _commit_parent_after_platform_rejection(
    state_root: Path, *, parent_sha256: str, round_index: int
) -> None:
    """Make persistent policy state agree with the artifact selected by the host.

    ``start_round`` commits its internal gate decision before the host has measured
    a submitted candidate.  If that later measurement rejects the candidate, the
    next round must see the parent hash and a non-deployed last decision.
    """

    state_path = Path(state_root) / "state.json"
    if state_path.is_symlink() or not state_path.is_file():
        raise ValueError("platform state file is missing after native round")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    rounds = payload.get("rounds") if isinstance(payload, dict) else None
    if not isinstance(rounds, list) or not rounds:
        raise ValueError("platform state has no committed round to reconcile")
    latest = rounds[-1]
    if not isinstance(latest, dict) or latest.get("round_index") != round_index:
        raise ValueError("platform state round does not match the current round")
    normalized_parent = str(parent_sha256).removeprefix("sha256:").lower()
    if len(normalized_parent) != 64 or any(
        character not in "0123456789abcdef" for character in normalized_parent
    ):
        raise ValueError("platform parent checkpoint hash is invalid")
    if latest.get("parent_checkpoint_sha256") != normalized_parent:
        raise ValueError("platform state parent hash differs from the declared parent")

    latest["deployed"] = False
    latest["gate_reason"] = "platform_measurement_rejected"
    latest["checkpoint_sha256"] = normalized_parent
    artifact = latest.get("model_artifact")
    if not isinstance(artifact, dict):
        raise ValueError("platform state model artifact is invalid")
    artifact["sha256"] = normalized_parent
    artifact["disposition"] = "retained_parent"

    temporary = state_path.with_name(state_path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, state_path)

    spool_path = Path(state_root) / "public-spool.jsonl"
    if spool_path.is_symlink():
        raise ValueError("public spool must not be a symlink")
    if spool_path.is_file():
        records = [
            json.loads(line)
            for line in spool_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        matching = next(
            (
                record
                for record in reversed(records)
                if isinstance(record, dict) and record.get("round_index") == round_index
            ),
            None,
        )
        if matching is None:
            raise ValueError("public spool has no record for the current round")
        matching["accepted"] = False
        matching["gate_reason"] = "platform_measurement_rejected"
        matching["checkpoint_sha256"] = normalized_parent
        spool_temporary = spool_path.with_name(spool_path.name + ".tmp")
        spool_temporary.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
                for record in records
            ),
            encoding="utf-8",
        )
        os.replace(spool_temporary, spool_path)

    predecessor = Path(state_root) / "shadow-predecessor.npz"
    if predecessor.is_symlink():
        raise ValueError("shadow predecessor must not be a symlink")
    if predecessor.exists():
        predecessor.unlink()


def train(rnd: Any) -> None:
    history = rnd.history()
    work = Path(os.environ.get("CONTEST_WORK", "/workspace")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    state = rnd.state_workspace(work / "state")
    candidate = work / "candidate"
    parent_relative = _checkpoint_relative(rnd)
    parent = rnd.parent.path(parent_relative)

    receipt = start_round(
        Path(rnd.data.train_path),
        parent,
        state,
        candidate,
        _runtime_config(),
        model_transport=lambda request: _host_model_transport(rnd, request),
        expected_parent_sha256=rnd.parent.checkpoint_sha256,
        expected_round_index=rnd.round_index,
    )
    rationale = str(
        (receipt.get("decision") or {}).get("rationale")
        or "bounded BRACE-MSI continuation from the declared platform parent"
    )
    hypothesis = (
        "Use the current public training projection and declared parent checkpoint "
        "to test one bounded, schema-preserving continuation decision."
    )
    change_summary = (
        "Applied the BRACE-MSI bounded native continuation policy; the platform "
        "parent remains selected unless the internal safety gate and platform "
        "measurement both permit the candidate."
    )
    configuration = {
        "round_index": rnd.round_index,
        "dataset_key": rnd.dataset_key,
        "candidate_trained": bool(receipt.get("candidate_trained")),
        "deployed_by_internal_gate": bool(receipt.get("deployed")),
        "action": (receipt.get("decision") or {}).get("executed_action"),
        "recipe": receipt.get("recipe"),
        "epochs": receipt.get("epochs"),
        "learning_rate": receipt.get("learning_rate"),
        "checkpoint_sha256": receipt.get("checkpoint_sha256"),
        "cpu_seconds": receipt.get("cpu_seconds"),
        "wall_seconds": receipt.get("wall_seconds"),
    }

    selected_artifact_id = rnd.parent.artifact_id
    measured_candidate: Mapping[str, Any] | None = None
    if receipt.get("deployed"):
        measured_candidate = rnd.submit_candidate(
            candidate,
            hypothesis=hypothesis,
            change_summary=change_summary,
            configuration=configuration,
            seed=20261117,
            checkpoint_paths=["checkpoint.npz"],
            code_paths=[],
            predict_argv=PREDICT_ARGV,
        )
        if _platform_measurement_accepts(rnd, measured_candidate):
            selected_artifact_id = measured_candidate["artifact_id"]
        else:
            _commit_parent_after_platform_rejection(
                state,
                parent_sha256=rnd.parent.checkpoint_sha256,
                round_index=rnd.round_index,
            )
            change_summary += " Platform public measurement rejected the candidate; retained parent."

    rnd.save_state(state)

    rnd.finish(
        selected_artifact_id=selected_artifact_id,
        hypothesis=hypothesis,
        change_summary=change_summary,
        reason=(
            rationale
            + (" Candidate selected after platform measurement." if selected_artifact_id != rnd.parent.artifact_id else " Parent retained by bounded safety decision.")
        ),
        configuration=configuration,
        seed=20261117,
        history_ids=[item["id"] for item in history],
        model_call_ids=list(rnd.call_ids),
    )


def _artifact_checkpoint(model_dir: Path) -> Path:
    raw = os.environ.get("CONTEST_ARTIFACT_PATH")
    if not raw:
        raise ValueError("CONTEST_ARTIFACT_PATH is required")
    root = Path(model_dir).resolve()
    path = Path(raw).resolve()
    if not path.is_relative_to(root):
        raise ValueError("artifact path must remain inside the mounted model directory")
    if path.is_symlink() or not path.is_file():
        raise ValueError("artifact checkpoint must be a regular file")
    return path


def predict(sample: Any, model_dir: Path) -> Any:
    model = _NativeModel.load(_artifact_checkpoint(Path(model_dir)))
    if sample.task != model.meta["task"]:
        raise ValueError("prediction task differs from selected checkpoint")
    paths, values = _flatten(sample.inputs)
    if paths != model.meta["paths"]:
        raise ValueError("prediction feature schema differs from selected checkpoint")
    raw = model.predict_raw(np.asarray([values], dtype=np.float64))[0]
    if sample.task == "regression":
        return {"value": float(max(0.0, raw))}

    probabilities = np.asarray(raw, dtype=np.float64)
    maximum = float(np.max(probabilities))
    tied = np.flatnonzero(probabilities == maximum)
    if len(tied) > 1:
        probabilities[int(tied[0])] += 1e-12
        probabilities /= probabilities.sum()
    return [
        {"label": label, "score": float(score)}
        for label, score in zip(model.meta["classes"], probabilities, strict=True)
    ]
