"""Competition Core orchestration for one official autonomous training round."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Mapping

from .agent import request_deployment_decision, request_experiment_proposal
from .data import DataBatch, load_rows
from .history import HistoryArtifactRef, HistoryStore
from .metrics import MetricContract, evaluate, resolve_metric_contract
from .model import FormalModel
from .profile import build_task_profile
from .recipes import CandidateResult, RecipeRegistry, TrainingRecipe, execute_recipe
from .selection import ArtifactEvaluation, SelectionResult, select_artifact
from .workspace import create_round_paths


PREDICT_ARGV = ["python3", "/app/harness.py", "predict"]
_CHECKPOINT_LIMIT = 64 * 1024 * 1024


@dataclass(frozen=True)
class RoundOutcome:
    round_index: int
    task: str
    executed_recipe_id: str | None
    candidate_trained: bool
    requested_artifact_id: str | None
    selected_artifact_id: str
    selected_role: str
    request_honored: bool
    training_call_id: str
    deployment_call_id: str
    receipt_path: str


def _parent_checkpoint(rnd: Any) -> Path:
    descriptor = getattr(rnd.parent, "descriptor", None)
    paths = descriptor.get("checkpoint_paths") if isinstance(descriptor, Mapping) else None
    matches = [item for item in paths or () if isinstance(item, str) and item.endswith(".npz")]
    if len(matches) != 1:
        raise ValueError("parent artifact must declare exactly one NPZ checkpoint")
    checkpoint = Path(rnd.parent.path(matches[0]))
    if checkpoint.is_symlink() or not checkpoint.is_file():
        raise ValueError("parent checkpoint must be a regular file")
    observed = "sha256:" + hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if observed != str(rnd.parent.checkpoint_sha256):
        raise ValueError("parent checkpoint digest mismatch")
    return checkpoint


def _peak_rss_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _hard_failures(parent: FormalModel, checkpoint: Path, metrics: Mapping[str, float]) -> tuple[str, ...]:
    failures: list[str] = []
    if checkpoint.is_symlink() or not checkpoint.is_file():
        failures.append("artifact_missing")
        return tuple(failures)
    if checkpoint.stat().st_size > _CHECKPOINT_LIMIT:
        failures.append("checkpoint_exceeds_64_mib")
    if not metrics or any(not math.isfinite(float(value)) for value in metrics.values()):
        failures.append("candidate_metrics_nonfinite")
    try:
        loaded = FormalModel.load(checkpoint)
    except (OSError, ValueError, KeyError) as exc:
        failures.append(f"checkpoint_unloadable:{type(exc).__name__}")
    else:
        if loaded.meta["task"] != parent.meta["task"] or loaded.meta["paths"] != parent.meta["paths"]:
            failures.append("checkpoint_contract_changed")
    return tuple(failures)


def _json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    os.replace(temporary, path)


def _serializable_metrics(metrics: Mapping[str, float] | None) -> dict[str, float | None] | None:
    if metrics is None:
        return None
    result: dict[str, float | None] = {}
    for key, value in metrics.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            result[str(key)] = None
        else:
            result[str(key)] = number if math.isfinite(number) else None
    return result


def _history_summary(store: HistoryStore, official_history: list[Any]) -> dict[str, Any]:
    return {
        "completed_rounds": len(store.audit_summaries),
        "retained_round_indices": list(store.round_indices),
        "official_history_records": len(official_history),
        "retained_samples": sum(int(item.get("sample_count", 0)) for item in store.audit_summaries if item.get("retained")),
    }


def _resource_summary() -> dict[str, Any]:
    return {
        "checkpoint_byte_limit": _CHECKPOINT_LIMIT,
        "peak_rss_bytes_before_training": _peak_rss_bytes(),
    }


def _restore_history_evaluations(
    rnd: Any,
    official_history: list[Any],
    paths_root: Path,
    parent: FormalModel,
    validation: DataBatch,
    metric_contract: MetricContract,
    evaluator: Callable[..., Mapping[str, float]],
) -> tuple[list[ArtifactEvaluation], dict[str, str]]:
    evaluations: list[ArtifactEvaluation] = []
    checkpoint_digests: dict[str, str] = {}
    if not callable(getattr(rnd, "restore_artifact", None)):
        return evaluations, checkpoint_digests
    seen: set[str] = set()
    for raw in reversed(official_history):
        if not isinstance(raw, Mapping):
            continue
        try:
            reference = HistoryArtifactRef.from_history_record(raw)
        except ValueError:
            continue
        if reference.artifact_id in seen or reference.artifact_id == str(rnd.parent.artifact_id):
            continue
        seen.add(reference.artifact_id)
        destination = paths_root / "history-artifacts" / reference.history_id
        try:
            restored = reference.restore(rnd, destination)
            checkpoint = restored / "checkpoint.npz" if restored.is_dir() else restored
            model = FormalModel.load(checkpoint)
            if model.meta["task"] != parent.meta["task"] or model.meta["paths"] != parent.meta["paths"]:
                continue
            metrics = dict(evaluator(model, validation.x, validation.y, metric_contract))
            failures = _hard_failures(parent, checkpoint, metrics)
        except (OSError, ValueError, KeyError):
            continue
        evaluations.append(
            ArtifactEvaluation(
                reference.artifact_id,
                "history",
                metrics,
                validation.sha256,
                {"checkpoint_bytes": checkpoint.stat().st_size},
                failures,
            )
        )
        checkpoint_digests[reference.artifact_id] = "sha256:" + hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return evaluations, checkpoint_digests


def _candidate_attempt(
    parent: FormalModel,
    profile: Any,
    registry: RecipeRegistry,
    proposal: Any,
    history_store: HistoryStore,
    current_batch: DataBatch,
) -> tuple[CandidateResult | None, TrainingRecipe | None, list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    requested = registry.resolve(proposal.recipe_id, profile, proposal.parameters)
    recipes = [requested]
    fallback = registry.fallback(profile)
    if fallback.recipe_id != requested.recipe_id:
        recipes.append(fallback)
    for recipe in recipes:
        try:
            batch = history_store.training_batch(recipe.history_policy, current_batch)
            return execute_recipe(parent, recipe, batch), recipe, failures
        except (ArithmeticError, RuntimeError, ValueError) as exc:
            failures.append(
                {"recipe_id": recipe.recipe_id, "error": f"{type(exc).__name__}: {exc}"}
            )
    return None, None, failures


def _selection_receipt(result: SelectionResult) -> dict[str, Any]:
    return {
        "requested_artifact_id": result.requested_artifact_id,
        "applied_artifact_id": result.applied_artifact_id,
        "applied_role": result.applied_role,
        "relation_to_parent": result.relation_to_parent,
        "request_honored": result.request_honored,
        "reason": result.reason,
        "validation_sha256": result.validation_sha256,
        "comparable_artifact_ids": list(result.comparable_artifact_ids),
        "excluded_artifacts": dict(result.excluded_artifacts),
        "ranked_artifact_ids": list(result.ranked_artifact_ids),
    }


def run_competition_round(
    rnd: Any,
    *,
    evaluator: Callable[..., Mapping[str, float]] = evaluate,
    hard_gate: Callable[[FormalModel, Path, Mapping[str, float]], tuple[str, ...] | list[str]] = _hard_failures,
) -> RoundOutcome:
    """Run one official round with two model calls and one real train attempt."""

    wall_started = time.monotonic()
    official_history = rnd.history()
    if not isinstance(official_history, list):
        raise ValueError("official history must be a list")
    parent_path = _parent_checkpoint(rnd)
    parent = FormalModel.load(parent_path)
    task_contract = getattr(rnd, "task", None)
    if not isinstance(task_contract, Mapping):
        raise ValueError("official task contract must be a mapping")
    metric_contract = resolve_metric_contract(task_contract, str(parent.meta["task"]))
    training = load_rows(rnd.data.train_path, parent, require_answers=True)
    validation = load_rows(rnd.data.validation_path, parent, require_answers=True)
    profile = build_task_profile(task_contract, parent, training, validation)

    paths = create_round_paths(
        Path(os.environ.get("CONTEST_WORK", "/workspace")),
        int(rnd.round_index),
        str(getattr(rnd, "stage_id", "default")),
        str(getattr(rnd, "dataset_key", "default")),
    )
    state_root = Path(rnd.state_workspace(paths.state))
    history_store = HistoryStore.load(state_root, parent)
    registry = RecipeRegistry()

    proposal_started = time.monotonic()
    proposal = request_experiment_proposal(
        rnd,
        profile,
        registry,
        history_summary=_history_summary(history_store, official_history),
        resource_fields=_resource_summary(),
    )
    proposal_seconds = time.monotonic() - proposal_started

    training_started = time.monotonic()
    candidate_cpu_started = time.process_time()
    candidate_result, executed_recipe, training_failures = _candidate_attempt(
        parent, profile, registry, proposal, history_store, training
    )
    candidate_cpu_seconds = max(0.0, time.process_time() - candidate_cpu_started)
    training_wall_seconds = time.monotonic() - training_started

    parent_metrics = dict(evaluator(parent, validation.x, validation.y, metric_contract))
    evaluations = [
        ArtifactEvaluation(
            str(rnd.parent.artifact_id),
            "parent",
            parent_metrics,
            validation.sha256,
            {"checkpoint_bytes": parent_path.stat().st_size},
        )
    ]
    artifact_digests = {str(rnd.parent.artifact_id): str(rnd.parent.checkpoint_sha256)}
    candidate_receipt: Mapping[str, Any] | None = None
    candidate_local_id = f"candidate-{int(rnd.round_index)}"
    candidate_metrics: dict[str, float] | None = None
    candidate_checkpoint: Path | None = None
    candidate_execution: dict[str, Any] | None = None
    hard_failures: tuple[str, ...] = ()

    if candidate_result is not None and executed_recipe is not None:
        paths.candidate.mkdir(parents=True, exist_ok=False)
        candidate_checkpoint = paths.candidate / "checkpoint.npz"
        candidate_result.model.save(candidate_checkpoint)
        candidate_metrics = dict(
            evaluator(candidate_result.model, validation.x, validation.y, metric_contract)
        )
        hard_failures = tuple(hard_gate(parent, candidate_checkpoint, candidate_metrics))
        candidate_execution = dict(candidate_result.receipt)
        candidate_execution["losses"] = list(candidate_result.losses)
        if not hard_failures:
            evaluations.append(
                ArtifactEvaluation(
                    candidate_local_id,
                    "candidate",
                    candidate_metrics,
                    validation.sha256,
                    {
                        "cpu_seconds": candidate_cpu_seconds,
                        "wall_seconds": training_wall_seconds,
                        "checkpoint_bytes": candidate_checkpoint.stat().st_size,
                        "parameter_count": int(candidate_result.model.meta["parameter_count"]),
                        "peak_rss_bytes": _peak_rss_bytes(),
                    },
                )
            )
            artifact_digests[candidate_local_id] = "sha256:" + hashlib.sha256(candidate_checkpoint.read_bytes()).hexdigest()

    history_evaluations, history_digests = _restore_history_evaluations(
        rnd, official_history, paths.root, parent, validation, metric_contract, evaluator
    )
    evaluations.extend(history_evaluations)
    artifact_digests.update(history_digests)

    artifact_roles = {item.artifact_id: item.role for item in evaluations}
    deployment_context = {
        "task_profile": profile.as_dict(),
        "metric_contract": metric_contract.as_dict(),
        "artifact_metrics": {item.artifact_id: dict(item.metrics) for item in evaluations},
        "artifact_resources": {item.artifact_id: dict(item.resource_evidence) for item in evaluations},
        "artifact_roles": artifact_roles,
        "parent_artifact_id": str(rnd.parent.artifact_id),
        "experiment": {
            "recipe_id": executed_recipe.recipe_id if executed_recipe is not None else None,
            "hypothesis": proposal.hypothesis,
            "training_failures": training_failures,
            "hard_failures": list(hard_failures),
        },
        "history_summary": _history_summary(history_store, official_history),
    }
    legal_ids = tuple(item.artifact_id for item in evaluations)
    deployment_started = time.monotonic()
    deployment = request_deployment_decision(
        rnd, deployment_context, legal_artifact_ids=legal_ids
    )
    deployment_seconds = time.monotonic() - deployment_started
    selection = select_artifact(
        metric_contract, evaluations, deployment.requested_artifact_id
    )

    # Candidate registration occurs only after both Agent calls and local
    # selection.  This preserves the official request order while the local
    # candidate ID gives the deployment call one concrete legal choice.
    candidate_platform_id: str | None = None
    if candidate_checkpoint is not None and not hard_failures and executed_recipe is not None:
        candidate_receipt = rnd.submit_candidate(
            paths.candidate,
            hypothesis=proposal.hypothesis,
            change_summary="Executed one registered parent-compatible experiment and evaluated it on the current legal validation scope.",
            configuration={
                "recipe_id": executed_recipe.recipe_id,
                "proposal_call_id": proposal.call_id,
                "deployment_call_id": deployment.call_id,
                "requested_artifact_id": deployment.requested_artifact_id,
                "locally_applied_artifact_id": selection.applied_artifact_id,
                "validation_sha256": validation.sha256,
                "candidate_execution": candidate_execution,
            },
            seed=int(parent.meta["seed"]),
            checkpoint_paths=["checkpoint.npz"],
            code_paths=[],
            predict_argv=PREDICT_ARGV,
        )
        candidate_platform_id = candidate_receipt.get("artifact_id")
        if not isinstance(candidate_platform_id, str) or not candidate_platform_id:
            raise ValueError("candidate receipt returned no artifact ID")
    selected_platform_id = (
        candidate_platform_id
        if selection.applied_artifact_id == candidate_local_id
        else selection.applied_artifact_id
    )

    history_store.append(training, int(rnd.round_index))
    history_store.save(state_root)
    requested_role = artifact_roles.get(deployment.requested_artifact_id or "")
    requested_decision = {"candidate": "deploy", "parent": "retain", "history": "rollback"}.get(
        requested_role, "retain"
    )
    applied_decision = {"candidate": "deploy", "parent": "retain", "history": "rollback"}[
        selection.applied_role
    ]
    if hard_failures:
        outcome_label = "candidate_rejected_by_safety_gate"
    elif candidate_result is None:
        outcome_label = "candidate_training_failed"
    else:
        outcome_label = {
            "candidate": "candidate_selected_by_selector",
            "parent": "candidate_retained_parent_by_selector",
            "history": "historical_artifact_selected_by_selector",
        }[selection.applied_role]
    platform_metrics: dict[str, float] = {}
    summary = candidate_receipt.get("summary") if isinstance(candidate_receipt, Mapping) else None
    raw_platform_metrics = summary.get("metrics") if isinstance(summary, Mapping) else None
    if isinstance(raw_platform_metrics, Mapping):
        platform_metrics = {
            str(key): float(value)
            for key, value in raw_platform_metrics.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
        }
    record = {
        "format": "brace-msi.round-receipt.v1",
        "round_index": int(rnd.round_index),
        "stage_id": str(getattr(rnd, "stage_id", "")),
        "task_profile": profile.as_dict(),
        "metric_contract": metric_contract.as_dict(),
        "parent_artifact_id": str(rnd.parent.artifact_id),
        "parent_checkpoint_sha256": str(rnd.parent.checkpoint_sha256),
        "train_sha256": training.sha256,
        "validation_sha256": validation.sha256,
        "experiment_proposal": {
            **asdict(proposal),
            "parameters": dict(proposal.parameters),
        },
        "executed_recipe_id": executed_recipe.recipe_id if executed_recipe is not None else None,
        "candidate_trained": candidate_result is not None,
        "candidate_artifact_id": candidate_platform_id,
        "candidate_checkpoint_sha256": (
            "sha256:" + hashlib.sha256(candidate_checkpoint.read_bytes()).hexdigest()
            if candidate_checkpoint is not None
            else None
        ),
        "candidate_execution": candidate_execution,
        "training_failures": training_failures,
        "hard_failures": list(hard_failures),
        "safety_failures": list(hard_failures),
        "artifact_evaluations": [
            {
                "artifact_id": item.artifact_id,
                "role": item.role,
                "metrics": _serializable_metrics(item.metrics),
                "validation_sha256": item.validation_sha256,
                "resource_evidence": dict(item.resource_evidence),
                "hard_failures": list(item.hard_failures),
            }
            for item in evaluations
        ],
        "deployment_decision": asdict(deployment),
        "selection": _selection_receipt(selection),
        "selected_artifact_id": selected_platform_id,
        "selected_checkpoint_sha256": artifact_digests.get(selection.applied_artifact_id),
        "action": "train",
        "recipe": executed_recipe.recipe_id if executed_recipe is not None else None,
        "requested_deployment_decision": requested_decision,
        "applied_deployment_decision": applied_decision,
        "outcome": outcome_label,
        "parent_metrics": _serializable_metrics(parent_metrics),
        "candidate_metrics": _serializable_metrics(candidate_metrics),
        "platform_metrics": platform_metrics,
        "best_stable_artifact_id": None,
        "history": {
            "round_indices": list(history_store.round_indices),
            "audit_summaries": list(history_store.audit_summaries),
        },
        "timing": {
            "proposal_seconds": proposal_seconds,
            "candidate_train_eval_submit_seconds": training_wall_seconds,
            "deployment_seconds": deployment_seconds,
            "observed_seconds_before_state_rpc": time.monotonic() - wall_started,
        },
    }
    receipt_path = state_root / "round-receipt.json"
    _json_atomic(receipt_path, record)
    ledger_path = state_root / "round-ledger.json"
    prior_ledger: list[Any] = []
    if ledger_path.is_file():
        loaded = json.loads(ledger_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("rounds"), list):
            prior_ledger = loaded["rounds"]
    prior_ledger.append(record)
    _json_atomic(ledger_path, {"format": "brace-msi.round-ledger.v1", "rounds": prior_ledger})
    _json_atomic(state_root / "formal-state.json", {"format": "brace-formal-state.v2", "rounds": prior_ledger})

    rnd.save_state(state_root)
    model_call_ids = [
        call_id for call_id in (proposal.call_id, deployment.call_id) if isinstance(call_id, str) and call_id
    ]
    history_ids = [
        item["id"] for item in official_history if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    ]
    rnd.finish(
        selected_artifact_id=selected_platform_id,
        hypothesis=proposal.hypothesis,
        change_summary="Ran one real registered training experiment, evaluated legal artifacts on one scope, and applied deterministic metric-direction validation to the Agent request.",
        reason=selection.reason,
        configuration={
            "executed_recipe_id": executed_recipe.recipe_id if executed_recipe is not None else None,
            "candidate_trained": candidate_result is not None,
            "requested_artifact_id": deployment.requested_artifact_id,
            "applied_artifact_id": selected_platform_id,
            "request_honored": selection.request_honored,
            "validation_sha256": validation.sha256,
        },
        seed=int(parent.meta["seed"]),
        history_ids=history_ids,
        model_call_ids=model_call_ids,
    )
    return RoundOutcome(
        round_index=int(rnd.round_index),
        task=profile.task,
        executed_recipe_id=executed_recipe.recipe_id if executed_recipe is not None else None,
        candidate_trained=candidate_result is not None,
        requested_artifact_id=deployment.requested_artifact_id,
        selected_artifact_id=str(selected_platform_id),
        selected_role=selection.applied_role,
        request_honored=selection.request_honored,
        training_call_id=proposal.call_id,
        deployment_call_id=deployment.call_id,
        receipt_path=str(receipt_path),
    )

