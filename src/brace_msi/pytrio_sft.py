"""Deterministic, secret-free SFT corpus for the BRACE proposal Agent.

The corpus teaches Qwen to emit the already versioned proposal JSON.  It does
not contain industrial samples, labels, task identities, credentials, or
official hidden-test information.  Model training remains an explicit remote
operation implemented by ``scripts/run_pytrio_sft.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import version as package_version
import json
import math
from pathlib import Path
import random
import time
from typing import Any

import numpy as np

from .policies import Action
from .pytrio_agent import (
    AgentContext,
    ExperimentProposal,
    PROPOSAL_SCHEMA_VERSION,
    build_agent_prompt,
    validate_experiment_proposal,
)


CORPUS_FORMAT = "brace-msi.pytrio-sft-corpus.v1"
FROZEN_SEED = 20261112
# Remote runs fail closed unless both values match the preregistered files.
FROZEN_TRAIN_SHA256 = "1d6763854a307ccbd10f1b2b6c49a748d8272288ff2dcf9665d9f58f3b0717c3"
FROZEN_EVALUATION_SHA256 = "5119947ed2f81b99bc32729d6e53aa7d4fa86472feb0bc4953aa8fff9c6bb824"
EXECUTABLE_ACTIONS = (
    Action.NOOP.value,
    Action.INCREMENTAL_UPDATE.value,
    Action.REPLAY_REFIT.value,
)


@dataclass(frozen=True)
class SftExample:
    scenario_id: str
    archetype: str
    task_kind: str
    prompt: str
    completion: str
    budget_cpu_seconds: float
    budget_candidate_slots: int
    evidence_safe: bool

    @property
    def messages(self) -> tuple[dict[str, str], ...]:
        return ({"role": "user", "content": self.prompt},)


@dataclass(frozen=True)
class SftCorpus:
    train: tuple[SftExample, ...]
    evaluation: tuple[SftExample, ...]


@dataclass(frozen=True)
class PyTrioSftRunConfig:
    base_model: str = "Qwen/Qwen3.5-4B"
    rank: int = 8
    epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 1e-4
    seed: int = FROZEN_SEED
    max_eval_tokens: int = 512
    weight_name: str = "brace-msi-agent-sft-v1"

    def __post_init__(self) -> None:
        if not self.base_model.strip():
            raise ValueError("base_model must not be empty")
        if self.rank not in {4, 8, 16, 32}:
            raise ValueError("rank must be one of 4, 8, 16, 32")
        if not 1 <= self.epochs <= 3:
            raise ValueError("epochs must be in [1, 3]")
        if not 1 <= self.batch_size <= 8:
            raise ValueError("batch_size must be in [1, 8]")
        if not 0 < self.learning_rate <= 1e-3:
            raise ValueError("learning_rate must be in (0, 1e-3]")
        if not 64 <= self.max_eval_tokens <= 4096:
            raise ValueError("max_eval_tokens must be in [64, 4096]")
        if not self.weight_name.strip() or len(self.weight_name) > 80:
            raise ValueError("weight_name is invalid")


def encode_sft_example(
    example: SftExample,
    tokenizer: Any,
    trio_module: Any,
) -> Any:
    """Encode one example using the official assistant-only SFT contract."""

    prompt_text = tokenizer.apply_chat_template(
        list(example.messages),
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    prompt_tokens = tokenizer.encode(prompt_text, add_special_tokens=False)
    completion_tokens = tokenizer.encode(
        example.completion, add_special_tokens=False
    )
    completion_weights = [1.0] * len(completion_tokens)
    eos_token_id = tokenizer.eos_token_id
    if eos_token_id is not None:
        completion_tokens = [*completion_tokens, eos_token_id]
        completion_weights.append(1.0)
    tokens = [*prompt_tokens, *completion_tokens]
    weights = [0.0] * len(prompt_tokens) + completion_weights
    if len(tokens) < 2 or sum(weights) <= 0:
        raise ValueError("SFT example has no trainable completion tokens")
    return trio_module.Datum(
        model_input=trio_module.ModelInput.from_ints(tokens[:-1]),
        loss_fn_inputs={
            "target_tokens": np.asarray(tokens[1:], dtype=np.int32),
            "weights": np.asarray(weights[1:], dtype=np.float32),
        },
    )


def score_proposal_response(raw: str, expected: SftExample) -> dict[str, bool]:
    """Score structure and the executable decision without retaining text."""

    from .pytrio_agent import parse_experiment_proposal

    try:
        actual = parse_experiment_proposal(raw)
        target = parse_experiment_proposal(expected.completion)
    except (ValueError, TypeError, json.JSONDecodeError):
        return {
            "schema_valid": False,
            "action_match": False,
            "tool_match": False,
            "budget_safe": False,
            "policy_match": False,
        }
    action_match = actual.action is target.action
    tool_match = actual.tool == target.tool
    no_training_required = actual.action is Action.NOOP
    budget_safe = no_training_required or (
        expected.evidence_safe
        and expected.budget_candidate_slots >= actual.max_candidates
        and expected.budget_cpu_seconds >= actual.max_cpu_seconds
    )
    if not expected.evidence_safe or expected.budget_candidate_slots <= 0:
        budget_safe = no_training_required
    return {
        "schema_valid": True,
        "action_match": action_match,
        "tool_match": tool_match,
        "budget_safe": budget_safe,
        "policy_match": action_match and tool_match and budget_safe,
    }


def run_remote_pytrio_sft(
    output_dir: Path,
    config: PyTrioSftRunConfig,
    *,
    trio_module: Any | None = None,
) -> dict[str, Any]:
    """Run the bounded remote SFT and persist a sampler checkpoint.

    Authentication is intentionally delegated to ``trio login`` / PyTRiO's
    runtime configuration.  This function never accepts or serializes a key.
    """

    root = Path(output_dir)
    if root.exists():
        raise FileExistsError("remote SFT output directory must be a new path")
    root.mkdir(parents=True, exist_ok=False)
    run_spec = {
        "format": "brace-msi.pytrio-sft-run.v1",
        "status": "started",
        "base_model": config.base_model,
        "rank": config.rank,
        "epochs": config.epochs,
        "batch_size": config.batch_size,
        "learning_rate": config.learning_rate,
        "seed": config.seed,
        "max_eval_tokens": config.max_eval_tokens,
        "weight_name": config.weight_name,
        "persistent_sampler": True,
        "credentials": "pytrio_runtime_only",
        "pytrio_version": None,
        "corpus_manifest": None,
    }
    _write_json(root / "run_spec.json", run_spec)
    stage = "preflight"
    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    forward_backward_requests_submitted = 0
    optimizer_requests_submitted = 0
    remote_steps_completed = 0
    model_path: str | None = None
    supported_models: list[str] = []
    try:
        if trio_module is None:
            import pytrio as trio_module  # type: ignore[no-redef]
        run_spec["pytrio_version"] = package_version("pytrio")
        corpus_manifest = materialize_brace_sft_corpus(
            root / "corpus", seed=config.seed
        )
        _validate_frozen_corpus(corpus_manifest, config)
        run_spec["corpus_manifest"] = corpus_manifest
        _write_json(root / "run_spec.json", run_spec)
        corpus = build_brace_sft_corpus(seed=config.seed)

        stage = "service_capabilities"
        service = trio_module.ServiceClient()
        supported_models = list(service.get_supported_models())
        if config.base_model not in supported_models:
            raise ValueError("configured base model is not supported")

        stage = "create_training_client"
        trainer = service.create_lora_training_client(
            base_model=config.base_model,
            rank=config.rank,
            seed=config.seed,
        )
        tokenizer = trainer.get_tokenizer()

        stage = "base_evaluation"
        base_sampler = service.create_sampling_client(base_model=config.base_model)
        base_evaluation = _evaluate_sampler(
            base_sampler,
            tokenizer,
            corpus.evaluation,
            trio_module,
            config,
            output_path=root / "base_evaluation.json",
        )

        stage = "encode_training_corpus"
        encoded = [
            encode_sft_example(row, tokenizer, trio_module) for row in corpus.train
        ]
        order = list(range(len(encoded)))
        rng = random.Random(config.seed)
        global_step = 0
        stage = "training"
        for epoch in range(1, config.epochs + 1):
            rng.shuffle(order)
            for batch_start in range(0, len(order), config.batch_size):
                indices = order[batch_start : batch_start + config.batch_size]
                batch = [encoded[index] for index in indices]
                step_started = time.perf_counter()
                fwdbwd = trainer.forward_backward(batch, "cross_entropy")
                forward_backward_requests_submitted += 1
                optim = trainer.optim_step(
                    trio_module.AdamParams(learning_rate=config.learning_rate)
                )
                optimizer_requests_submitted += 1
                fwdbwd_result = fwdbwd.result()
                optim.result()
                remote_steps_completed += 1
                global_step += 1
                loss = _weighted_loss(fwdbwd_result, batch)
                step = {
                    "epoch": epoch,
                    "global_step": global_step,
                    "batch_examples": len(batch),
                    "loss_per_supervised_token": loss,
                    "wall_seconds": max(0.0, time.perf_counter() - step_started),
                }
                steps.append(step)
                _write_json(
                    root / "training_progress.json",
                    {
                        "format": "brace-msi.pytrio-sft-progress.v1",
                        "status": "running",
                        "steps": steps,
                    },
                )

        stage = "save_persistent_sampler"
        saved = trainer.save_weights_for_sampler(
            name=config.weight_name,
            ttl_seconds=None,
        ).result()
        model_path = str(saved.path)
        if not model_path.startswith("trio://"):
            raise ValueError("PyTRiO did not return a persistent trio:// path")
        _write_json(
            root / "persistent_sampler.json",
            {
                "format": "brace-msi.pytrio-persistent-sampler.v1",
                "base_model": config.base_model,
                "model_path": model_path,
                "model": str(getattr(saved, "model", config.base_model)),
                "size": getattr(saved, "size", None),
            },
        )

        stage = "tuned_evaluation"
        tuned_sampler = service.create_sampling_client(
            base_model=config.base_model,
            model_path=model_path,
        )
        tuned_evaluation = _evaluate_sampler(
            tuned_sampler,
            tokenizer,
            corpus.evaluation,
            trio_module,
            config,
            output_path=root / "tuned_evaluation.json",
        )
        result = {
            **run_spec,
            "status": "succeeded",
            "supported_models": supported_models,
            "training_steps": len(steps),
            "training_steps_submitted": min(
                forward_backward_requests_submitted,
                optimizer_requests_submitted,
            ),
            "forward_backward_requests_submitted": forward_backward_requests_submitted,
            "optimizer_requests_submitted": optimizer_requests_submitted,
            "remote_steps_completed": remote_steps_completed,
            "training_examples_seen": len(corpus.train) * config.epochs,
            "final_loss_per_supervised_token": steps[-1][
                "loss_per_supervised_token"
            ],
            "base_evaluation": base_evaluation["metrics"],
            "tuned_evaluation": tuned_evaluation["metrics"],
            "sampler_model_path": model_path,
            "sampler_model": str(getattr(saved, "model", config.base_model)),
            "sampler_size": getattr(saved, "size", None),
            "wall_seconds": max(0.0, time.perf_counter() - started),
        }
        _write_json(root / "result.json", result)
        return result
    except Exception as exc:
        failure = {
            **run_spec,
            "status": "failed",
            "failed_stage": stage,
            "error_category": type(exc).__name__,
            "training_steps_completed": len(steps),
            "training_steps_submitted": min(
                forward_backward_requests_submitted,
                optimizer_requests_submitted,
            ),
            "forward_backward_requests_submitted": forward_backward_requests_submitted,
            "optimizer_requests_submitted": optimizer_requests_submitted,
            "remote_steps_completed": remote_steps_completed,
            "supported_models": supported_models,
            "sampler_model_path": model_path,
            "base_evaluation_partial": _read_evaluation_summary(
                root / "base_evaluation.json"
            ),
            "tuned_evaluation_partial": _read_evaluation_summary(
                root / "tuned_evaluation.json"
            ),
            "wall_seconds": max(0.0, time.perf_counter() - started),
        }
        _write_json(root / "failure.json", failure)
        raise


def _evaluate_sampler(
    sampler: Any,
    tokenizer: Any,
    examples: tuple[SftExample, ...],
    trio_module: Any,
    config: PyTrioSftRunConfig,
    *,
    output_path: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_input_tokens = 0
    total_output_tokens = 0
    _write_json(
        output_path,
        _evaluation_payload(rows, total_input_tokens, total_output_tokens, "running"),
    )
    for index, example in enumerate(examples):
        prompt_text = tokenizer.apply_chat_template(
            list(example.messages),
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        input_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
        response = sampler.sample(
            prompt=trio_module.ModelInput.from_ints(input_ids),
            num_samples=1,
            sampling_params=trio_module.SamplingParams(
                max_tokens=config.max_eval_tokens,
                seed=config.seed + index,
                temperature=0.0,
            ),
        ).result()
        if not response.sequences:
            raw = ""
            output_tokens = 0
        else:
            sequence = response.sequences[0]
            raw = str(sequence.text)
            output_tokens = len(sequence.tokens)
        score = score_proposal_response(raw, example)
        total_input_tokens += len(input_ids)
        total_output_tokens += output_tokens
        rows.append(
            {
                "scenario_id": example.scenario_id,
                "archetype": example.archetype,
                "task_kind": example.task_kind,
                "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "input_tokens": len(input_ids),
                "output_tokens": output_tokens,
                **score,
            }
        )
        _write_json(
            output_path,
            _evaluation_payload(
                rows, total_input_tokens, total_output_tokens, "running"
            ),
        )
    result = _evaluation_payload(
        rows, total_input_tokens, total_output_tokens, "complete"
    )
    _write_json(output_path, result)
    return result


def _evaluation_payload(
    rows: list[dict[str, Any]],
    total_input_tokens: int,
    total_output_tokens: int,
    status: str,
) -> dict[str, Any]:
    count = len(rows)
    metrics = {
        key + "_rate": (
            sum(bool(row[key]) for row in rows) / count if count else 0.0
        )
        for key in (
            "schema_valid",
            "action_match",
            "tool_match",
            "budget_safe",
            "policy_match",
        )
    }
    return {
        "format": "brace-msi.pytrio-agent-evaluation.v1",
        "status": status,
        "examples": count,
        "metrics": metrics,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "rows": rows,
    }


def _weighted_loss(result: Any, batch: list[Any]) -> float:
    logprobs = np.concatenate(
        [_numeric_array(output["logprobs"]) for output in result.loss_fn_outputs]
    )
    weights = np.concatenate(
        [_numeric_array(item.loss_fn_inputs["weights"]) for item in batch]
    )
    denominator = float(weights.sum())
    if denominator <= 0 or logprobs.shape != weights.shape:
        raise ValueError("invalid training loss arrays")
    loss = -float(np.dot(logprobs, weights) / denominator)
    if not math.isfinite(loss):
        raise ValueError("non-finite training loss")
    return loss


def _numeric_array(value: Any) -> np.ndarray:
    if hasattr(value, "to_numpy"):
        value = value.to_numpy()
    elif hasattr(value, "tolist"):
        value = value.tolist()
    return np.asarray(value, dtype=np.float64).reshape(-1)


def _validate_frozen_corpus(
    manifest: dict[str, Any], config: PyTrioSftRunConfig
) -> None:
    if config.seed != FROZEN_SEED:
        raise ValueError("remote SFT seed differs from the preregistered seed")
    if manifest.get("train_sha256") != FROZEN_TRAIN_SHA256:
        raise ValueError("training corpus hash differs from preregistration")
    if manifest.get("evaluation_sha256") != FROZEN_EVALUATION_SHA256:
        raise ValueError("evaluation corpus hash differs from preregistration")


def _read_evaluation_summary(path: Path) -> dict[str, Any] | None:
    target = Path(path)
    if not target.is_file():
        return None
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unreadable"}
    return {
        key: value.get(key)
        for key in ("status", "examples", "metrics", "input_tokens", "output_tokens")
    }


def _write_json(path: Path, value: Any) -> None:
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def build_brace_sft_corpus(*, seed: int = FROZEN_SEED) -> SftCorpus:
    """Build a fixed train/evaluation split across generic decision cases.

    Training and evaluation use disjoint archetype names and templates. Each
    training archetype has two numeric variants; evaluation holds out a
    related but unseen decision scenario. The seed is part of scenario
    identity so a changed corpus cannot silently reuse an old manifest.
    """

    train: list[SftExample] = []
    evaluation: list[SftExample] = []
    train_archetypes = (
        "budget_exhausted",
        "unsafe_evidence",
        "stable_performance",
        "first_low_cost_update",
        "failed_update_replay",
        "recovery_complete",
    )
    evaluation_archetypes = (
        "wall_budget_exhausted",
        "invalid_measurement_window",
        "small_positive_gain",
        "initial_degradation",
        "repeated_failure_replay",
        "post_replay_stable",
    )
    for task_kind in ("classification", "regression"):
        for archetype in train_archetypes:
            for variant in range(2):
                train.append(
                    _build_example(
                        seed=seed,
                        task_kind=task_kind,
                        archetype=archetype,
                        variant=variant,
                    )
                )
        for index, archetype in enumerate(evaluation_archetypes):
            evaluation.append(
                _build_example(
                    seed=seed,
                    task_kind=task_kind,
                    archetype=archetype,
                    variant=10 + index,
                )
            )
    return SftCorpus(tuple(train), tuple(evaluation))


def materialize_brace_sft_corpus(
    output_dir: Path,
    *,
    seed: int = FROZEN_SEED,
) -> dict[str, Any]:
    """Write JSONL inputs and a hash manifest without remote side effects."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    corpus = build_brace_sft_corpus(seed=seed)
    train_path = root / "train.jsonl"
    eval_path = root / "evaluation.jsonl"
    _write_jsonl(train_path, corpus.train)
    _write_jsonl(eval_path, corpus.evaluation)
    manifest: dict[str, Any] = {
        "format": CORPUS_FORMAT,
        "seed": seed,
        "data_classification": "synthetic_aggregate_policy_scenarios",
        "contains_raw_samples": False,
        "contains_credentials": False,
        "train_examples": len(corpus.train),
        "evaluation_examples": len(corpus.evaluation),
        "train_sha256": _sha256_file(train_path),
        "evaluation_sha256": _sha256_file(eval_path),
        "actions": list(EXECUTABLE_ACTIONS),
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _build_example(
    *, seed: int, task_kind: str, archetype: str, variant: int
) -> SftExample:
    metric_name = "macro_f1" if task_kind == "classification" else "rmse"
    higher_is_better = task_kind == "classification"
    baseline = 0.40 + 0.01 * variant if higher_is_better else 60.0 + variant
    stable = 0.39 + 0.005 * variant if higher_is_better else 63.0 + variant
    budget_slots = 2
    cpu_seconds = 90.0 + 15.0 * variant
    failed_candidates = 0
    data_quality_ok = True
    relative_improvement = -0.025 - 0.005 * variant
    round_index = 1 + variant
    history: tuple[dict[str, Any], ...] = ()
    action = Action.NOOP
    rationale = "no update is justified by the current evidence"
    parameters: dict[str, Any] = {}
    stop_conditions = ("no_validation_gain", "budget_exhausted")

    if archetype in {"budget_exhausted", "wall_budget_exhausted"}:
        budget_slots = 0
        cpu_seconds = 0.0
        rationale = (
            "wall-clock and candidate budgets are exhausted; preserve the stable model"
            if archetype == "wall_budget_exhausted"
            else "candidate budget is exhausted; preserve the stable model"
        )
        stop_conditions = ("budget_exhausted",)
    elif archetype in {"unsafe_evidence", "invalid_measurement_window"}:
        data_quality_ok = False
        rationale = (
            "the measurement window failed validation; do not train on it"
            if archetype == "invalid_measurement_window"
            else "evidence quality is invalid; do not train on unsafe input"
        )
        stop_conditions = ("invalid_evidence",)
    elif archetype in {"stable_performance", "small_positive_gain"}:
        relative_improvement = 0.01 + 0.005 * variant
        stable = baseline * (1.0 + relative_improvement) if higher_is_better else baseline * (1.0 - relative_improvement)
        rationale = (
            "a small positive gain does not justify spending another candidate"
            if archetype == "small_positive_gain"
            else "stable performance has not degraded enough to justify training"
        )
    elif archetype in {"first_low_cost_update", "initial_degradation"}:
        action = Action.INCREMENTAL_UPDATE
        rationale = (
            "initial degradation warrants one bounded low-cost update"
            if archetype == "initial_degradation"
            else "performance degraded and the lowest-cost candidate has not been tried"
        )
        parameters = {"epochs": 1}
    elif archetype in {"failed_update_replay", "repeated_failure_replay"}:
        action = Action.REPLAY_REFIT
        failed_candidates = 1
        round_index = 2 + variant
        history = (
            {
                "round": 1,
                "action": Action.INCREMENTAL_UPDATE.value,
                "kind": "candidate",
                "accepted": False,
                "reason": "no_validation_gain",
                "cpu_seconds": 5.0 + variant,
            },
        )
        rationale = (
            "degradation persists after a rejected candidate; use one bounded replay refit"
            if archetype == "repeated_failure_replay"
            else "one low-cost update failed while degradation persists; retry with bounded replay"
        )
        parameters = {"epochs": 3, "replay_fraction": 1.0}
    elif archetype in {"recovery_complete", "post_replay_stable"}:
        failed_candidates = 1
        relative_improvement = 0.04 + 0.005 * variant
        rationale = (
            "post-replay performance is stable; stop additional experiments"
            if archetype == "post_replay_stable"
            else "the stable model has recovered; stop further candidate spending"
        )
        history = (
            {
                "round": 1,
                "action": Action.REPLAY_REFIT.value,
                "kind": "candidate",
                "accepted": True,
                "reason": "improved",
                "cpu_seconds": 8.0 + variant,
            },
        )
    else:  # pragma: no cover - fixed internal catalogue
        raise ValueError(f"unknown archetype: {archetype}")

    context = AgentContext(
        task_kind=task_kind,
        metric_name=metric_name,
        higher_is_better=higher_is_better,
        round_index=round_index,
        evidence={
            "baseline_metric": baseline,
            "stable_metric": stable,
            "relative_improvement": relative_improvement,
            "failed_candidates": failed_candidates,
            "data_quality_ok": data_quality_ok,
        },
        history=history,
        budget={
            "candidate_slots_remaining": budget_slots,
            "cpu_seconds_remaining": cpu_seconds,
            "wall_seconds_remaining": cpu_seconds,
        },
        capabilities={
            "official_numpy_trainer": True,
            "supports_resume": True,
            "supports_partial_fit": False,
            "allowed_actions": list(EXECUTABLE_ACTIONS),
            "allowed_epochs": [1, 2, 3, 5],
            "allowed_learning_rate_multipliers": [0.25, 0.5, 1.0],
        },
    )
    proposal = ExperimentProposal(
        schema_version=PROPOSAL_SCHEMA_VERSION,
        action=action,
        tool={
            Action.NOOP: "noop",
            Action.INCREMENTAL_UPDATE: "train_incremental",
            Action.REPLAY_REFIT: "train_replay_refit",
        }[action],
        rationale=rationale,
        parameters=parameters,
        max_cpu_seconds=max(0.001, cpu_seconds),
        max_candidates=1,
        stop_conditions=stop_conditions,
    )
    validate_experiment_proposal(proposal)
    completion = json.dumps(
        {
            "schema_version": proposal.schema_version,
            "action": proposal.action.value,
            "tool": proposal.tool,
            "rationale": proposal.rationale,
            "parameters": dict(proposal.parameters),
            "max_cpu_seconds": proposal.max_cpu_seconds,
            "max_candidates": proposal.max_candidates,
            "stop_conditions": list(proposal.stop_conditions),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return SftExample(
        scenario_id=f"{seed}-{task_kind}-{archetype}-v{variant}",
        archetype=archetype,
        task_kind=task_kind,
        prompt=build_agent_prompt(context.to_payload()),
        completion=completion,
        budget_cpu_seconds=cpu_seconds,
        budget_candidate_slots=budget_slots,
        evidence_safe=data_quality_ok,
    )


def _write_jsonl(path: Path, rows: tuple[SftExample, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            record = {
                "format": CORPUS_FORMAT,
                "scenario_id": row.scenario_id,
                "archetype": row.archetype,
                "task_kind": row.task_kind,
                "messages": [
                    *row.messages,
                    {"role": "assistant", "content": row.completion},
                ],
            }
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
