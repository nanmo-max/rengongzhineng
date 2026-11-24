"""Sanitized SFT corpus for the formal deployment-decision call.

This research-only module mirrors the production prompt by invoking the same
``request_deployment_decision`` function through an in-memory capture round.
It contains aggregate synthetic metrics only.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import random
from types import SimpleNamespace
import time
from typing import Any, Mapping

from brace_formal.agent import _json_object, request_deployment_decision, request_experiment_proposal
from brace_formal.profile import TaskProfile
from brace_formal.recipes import RecipeRegistry

from .pytrio_sft import SftCorpus, SftExample, _weighted_loss, encode_sft_example


FORMAL_ADVISOR_FORMAT = "brace-msi.formal-advisor-sft.v1"
FORMAL_ADVISOR_SEED = 20261120
FORMAL_ADVISOR_TRAIN_SHA256 = "70b6de4c673733b68bffcfda8d9e353040a4853bd3574de27b163705678e2844"
FORMAL_ADVISOR_EVALUATION_SHA256 = "a41aabeb37e8e2642cf10eeba1d3a91c308cb67dbbbe0e1c8ee9e04a43e9b37c"

COMPETITION_AGENT_FORMAT = "brace-msi.competition-agent-sft.v1"
COMPETITION_AGENT_SEED = 20261121
COMPETITION_AGENT_TRAIN_SHA256 = "a763a6b5efa7973bca31ceb8ee773d384bd6e8931bf8ea381c26e666c32c5c5d"
COMPETITION_AGENT_EVALUATION_SHA256 = "3e5921d13d4f09887e9570b00d13e7bb635055944f18bf390c6e3f447d327643"
COMPETITION_SOURCE_SUMMARIES = (
    (
        "core-a1",
        Path("D:/brace-msi-competition/COMPETITION-CORE-EXP-001/summary.json"),
        "9f1cecc4aedbb6af25e6d42e97319c0a123e3e9791fa752438757fd4a86df47a",
    ),
    (
        "core-a2",
        Path("D:/brace-msi-competition/COMPETITION-CORE-EXP-001-A2/summary.json"),
        "67d54094a76bd8b39248b2827bbc7b834be44b3a39f155cb083f092382449de6",
    ),
    (
        "core-a3",
        Path("D:/brace-msi-competition/COMPETITION-CORE-EXP-001-A3/summary.json"),
        "fec09c59ed727ec3192eb180da7d7598410f4ab5bd125e1b7c6dd997a91266d0",
    ),
)


@dataclass(frozen=True)
class FormalAdvisorSftConfig:
    base_model: str = "Qwen/Qwen3.5-4B"
    rank: int = 8
    epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 1e-4
    seed: int = FORMAL_ADVISOR_SEED
    max_eval_tokens: int = 512
    weight_name: str = "brace-msi-formal-deployment-v1"


@dataclass(frozen=True)
class CompetitionAgentExample:
    scenario_id: str
    scenario_family: str
    archetype: str
    task_kind: str
    phase: str
    prompt: str
    completion: str
    legal_choices: tuple[str, ...]
    expected_history_policy: str | None
    expected_role: str | None
    budget_cpu_seconds: float = 0.0
    budget_candidate_slots: int = 1
    evidence_safe: bool = True

    @property
    def messages(self) -> tuple[dict[str, str], ...]:
        return ({"role": "user", "content": self.prompt},)


@dataclass(frozen=True)
class CompetitionAgentSftConfig:
    base_model: str = "Qwen/Qwen3.5-4B"
    rank: int = 8
    epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 1e-4
    seed: int = COMPETITION_AGENT_SEED
    max_eval_tokens: int = 768
    weight_name: str = "brace-msi-competition-agent-v1"


class _CaptureRound:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompt: str | None = None
        self.call_ids: list[str] = []

    def model(self, messages: list[Mapping[str, Any]], **_: Any) -> Any:
        self.prompt = str(messages[0]["content"])
        self.call_ids.append("capture-call")
        return SimpleNamespace(call_id="capture-call", text=self.response)


def build_competition_agent_corpus(
    *, seed: int = COMPETITION_AGENT_SEED,
) -> SftCorpus:
    """Build identity-blind proposal and deployment examples.

    The numbers encode the positive and negative aggregate trajectory shapes
    observed in Task 10; no source row, task identity or public-confirmation
    value is copied into the corpus.
    """

    train: list[CompetitionAgentExample] = []
    evaluation: list[CompetitionAgentExample] = []
    train_families = (
        "current_shift",
        "history_recovery",
        "imbalance_or_outlier",
        "mechanism_failure",
        "candidate_regression",
        "history_best",
    )
    holdout_families = (
        "unseen_current_shift",
        "unseen_history_recovery",
        "unseen_imbalance_or_outlier",
        "unseen_mechanism_failure",
        "unseen_candidate_regression",
        "unseen_history_best",
    )
    for task_kind in ("classification", "regression"):
        for index, family in enumerate(train_families):
            for variant in range(2):
                train.append(_competition_proposal_example(seed, "train", task_kind, family, index, variant))
                train.append(_competition_deployment_example(seed, "train", task_kind, family, index, variant))
        for index, family in enumerate(holdout_families):
            evaluation.append(_competition_proposal_example(seed, "evaluation", task_kind, family, index, 10 + index))
            evaluation.append(_competition_deployment_example(seed, "evaluation", task_kind, family, index, 10 + index))
    return SftCorpus(tuple(train), tuple(evaluation))


def materialize_competition_agent_corpus(
    output_dir: Path,
    *,
    seed: int = COMPETITION_AGENT_SEED,
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, Any]] = []
    for source_id, path, expected in COMPETITION_SOURCE_SUMMARIES:
        actual = _sha256_file(path) if path.is_file() else None
        if actual != expected:
            raise ValueError(f"competition trajectory source hash mismatch: {source_id}")
        sources.append({"source_id": source_id, "sha256": expected, "verified": True})
    corpus = build_competition_agent_corpus(seed=seed)
    train_path = root / "train.jsonl"
    evaluation_path = root / "evaluation.jsonl"
    _write_competition_examples(train_path, corpus.train)
    _write_competition_examples(evaluation_path, corpus.evaluation)
    manifest = {
        "format": COMPETITION_AGENT_FORMAT,
        "seed": seed,
        "contains_raw_samples": False,
        "contains_credentials": False,
        "contains_sampler_path": False,
        "train_examples": len(corpus.train),
        "evaluation_examples": len(corpus.evaluation),
        "train_sha256": _sha256_file(train_path),
        "evaluation_sha256": _sha256_file(evaluation_path),
        "source_summaries": sources,
    }
    _write_json(root / "manifest.json", manifest)
    return manifest


def validate_competition_agent_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("seed") != COMPETITION_AGENT_SEED:
        raise ValueError("competition Agent corpus seed differs from preregistration")
    if manifest.get("train_sha256") != COMPETITION_AGENT_TRAIN_SHA256:
        raise ValueError("competition Agent training hash differs from preregistration")
    if manifest.get("evaluation_sha256") != COMPETITION_AGENT_EVALUATION_SHA256:
        raise ValueError("competition Agent evaluation hash differs from preregistration")
    if not all(bool(item.get("verified")) for item in manifest.get("source_summaries", [])):
        raise ValueError("competition trajectory source was not verified")


def score_competition_agent_response(
    raw: str, expected: CompetitionAgentExample
) -> dict[str, bool]:
    try:
        payload = _json_object(str(raw).removesuffix("<|im_end|>"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"schema_valid": False, "structure_match": False, "policy_match": False, "numeric_safe": False}
    if not isinstance(payload, dict):
        return {"schema_valid": False, "structure_match": False, "policy_match": False, "numeric_safe": False}
    target = json.loads(expected.completion)
    if expected.phase == "proposal":
        required = {"recipe_id", "parameters", "history_policy", "hypothesis", "rationale"}
        schema = (
            required.issubset(payload)
            and payload.get("recipe_id") in expected.legal_choices
            and isinstance(payload.get("parameters"), dict)
            and payload.get("history_policy") == expected.expected_history_policy
            and isinstance(payload.get("hypothesis"), str)
            and bool(payload.get("hypothesis", "").strip())
            and isinstance(payload.get("rationale"), str)
            and bool(payload.get("rationale", "").strip())
        )
        policy = bool(schema and payload.get("recipe_id") == target["recipe_id"])
    else:
        required = {"artifact_id", "rationale"}
        schema = (
            required.issubset(payload)
            and payload.get("artifact_id") in expected.legal_choices
            and isinstance(payload.get("rationale"), str)
            and bool(payload.get("rationale", "").strip())
        )
        policy = bool(schema and payload.get("artifact_id") == target["artifact_id"])
    return {
        "schema_valid": bool(schema),
        "structure_match": bool(schema),
        "policy_match": policy,
        "numeric_safe": policy,
    }


def run_remote_competition_agent_sft(
    output_dir: Path,
    config: CompetitionAgentSftConfig = CompetitionAgentSftConfig(),
    *,
    trio_module: Any | None = None,
) -> dict[str, Any]:
    """Run the preregistered mixed proposal/deployment SFT and reload test."""

    root = Path(output_dir)
    if root.exists():
        raise FileExistsError("competition Agent SFT output directory must be new")
    root.mkdir(parents=True, exist_ok=False)
    run_spec: dict[str, Any] = {
        "format": "brace-msi.competition-agent-sft-run.v1",
        "status": "started",
        "base_model": config.base_model,
        "rank": config.rank,
        "epochs": config.epochs,
        "batch_size": config.batch_size,
        "learning_rate": config.learning_rate,
        "seed": config.seed,
        "max_eval_tokens": config.max_eval_tokens,
        "weight_name": config.weight_name,
        "credentials": "pytrio_runtime_only",
        "formal_image_dependency": False,
    }
    _write_json(root / "run_spec.json", run_spec)
    started = time.perf_counter()
    stage = "preflight"
    steps: list[dict[str, Any]] = []
    model_path: str | None = None
    try:
        if config.seed != COMPETITION_AGENT_SEED:
            raise ValueError("competition Agent SFT seed differs from preregistration")
        if trio_module is None:
            import pytrio as trio_module  # type: ignore[no-redef]
        try:
            run_spec["pytrio_version"] = package_version("pytrio")
        except Exception:
            run_spec["pytrio_version"] = "injected-test-double"
        corpus = build_competition_agent_corpus(seed=config.seed)
        manifest = materialize_competition_agent_corpus(root / "corpus", seed=config.seed)
        validate_competition_agent_manifest(manifest)
        run_spec["corpus_manifest"] = manifest
        _write_json(root / "run_spec.json", run_spec)

        stage = "service_capabilities"
        service = trio_module.ServiceClient()
        if config.base_model not in list(service.get_supported_models()):
            raise ValueError("configured base model is not supported")
        stage = "create_training_client"
        trainer = service.create_lora_training_client(
            base_model=config.base_model, rank=config.rank, seed=config.seed
        )
        tokenizer = trainer.get_tokenizer()

        stage = "base_evaluation"
        base = _evaluate_competition_sampler(
            service.create_sampling_client(base_model=config.base_model),
            tokenizer, corpus.evaluation, trio_module, config,
            root / "base_evaluation.json",
        )

        stage = "training"
        encoded = [encode_sft_example(row, tokenizer, trio_module) for row in corpus.train]
        order = list(range(len(encoded)))
        rng = random.Random(config.seed)
        for epoch in range(1, config.epochs + 1):
            rng.shuffle(order)
            for start in range(0, len(order), config.batch_size):
                batch = [encoded[index] for index in order[start : start + config.batch_size]]
                step_started = time.perf_counter()
                forward = trainer.forward_backward(batch, "cross_entropy").result()
                trainer.optim_step(trio_module.AdamParams(learning_rate=config.learning_rate)).result()
                steps.append({
                    "epoch": epoch,
                    "global_step": len(steps) + 1,
                    "batch_examples": len(batch),
                    "loss_per_supervised_token": _weighted_loss(forward, batch),
                    "wall_seconds": time.perf_counter() - step_started,
                })
                _write_json(root / "training_progress.json", {"status": "running", "steps": steps})

        stage = "save_persistent_sampler"
        saved = trainer.save_weights_for_sampler(name=config.weight_name, ttl_seconds=None).result()
        model_path = str(saved.path)
        if not model_path.startswith("trio://"):
            raise ValueError("PyTRiO did not return a persistent trio:// path")
        _write_json(root / "persistent_sampler.json", {
            "format": "brace-msi.competition-agent-persistent-sampler.v1",
            "base_model": config.base_model,
            "model_path": model_path,
            "model": str(getattr(saved, "model", config.base_model)),
            "size": getattr(saved, "size", None),
        })

        stage = "tuned_evaluation"
        tuned = _evaluate_competition_sampler(
            service.create_sampling_client(base_model=config.base_model, model_path=model_path),
            tokenizer, corpus.evaluation, trio_module, config,
            root / "tuned_evaluation.json",
        )
        stage = "reload_evaluation"
        reload_result = _evaluate_competition_sampler(
            service.create_sampling_client(base_model=config.base_model, model_path=model_path),
            tokenizer, corpus.evaluation, trio_module, config,
            root / "reload_evaluation.json",
        )
        base_metrics = base["metrics"]
        tuned_metrics = tuned["metrics"]
        reload_metrics = reload_result["metrics"]
        adoption = bool(
            reload_metrics["schema_valid_rate"] == 1.0
            and reload_metrics["numeric_safe_rate"] == 1.0
            and reload_metrics["policy_match_rate"] >= 0.90
            and reload_metrics == tuned_metrics
            and reload_metrics["policy_match_rate"] > base_metrics["policy_match_rate"]
        )
        result = {
            **run_spec,
            "status": "succeeded",
            "training_steps": len(steps),
            "training_examples_seen": len(corpus.train) * config.epochs,
            "final_loss_per_supervised_token": steps[-1]["loss_per_supervised_token"],
            "base_evaluation": base_metrics,
            "tuned_evaluation": tuned_metrics,
            "reload_evaluation": reload_metrics,
            "sampler_model_path": model_path,
            "sampler_model": str(getattr(saved, "model", config.base_model)),
            "sampler_size": getattr(saved, "size", None),
            "adoption_gate_passed": adoption,
            "wall_seconds": time.perf_counter() - started,
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
            "sampler_saved": model_path is not None,
            "wall_seconds": time.perf_counter() - started,
        }
        _write_json(root / "failure.json", failure)
        raise


def _evaluate_competition_sampler(
    sampler: Any,
    tokenizer: Any,
    examples: tuple[Any, ...],
    trio_module: Any,
    config: CompetitionAgentSftConfig,
    output_path: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    input_tokens = 0
    output_tokens = 0
    for index, example in enumerate(examples):
        prompt_text = tokenizer.apply_chat_template(
            list(example.messages), tokenize=False, add_generation_prompt=True,
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
        raw = str(response.sequences[0].text) if response.sequences else ""
        emitted = len(response.sequences[0].tokens) if response.sequences else 0
        score = score_competition_agent_response(raw, example)
        rows.append({
            "scenario_id": example.scenario_id,
            "scenario_family": example.scenario_family,
            "phase": example.phase,
            "task_kind": example.task_kind,
            "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "input_tokens": len(input_ids),
            "output_tokens": emitted,
            **score,
        })
        input_tokens += len(input_ids)
        output_tokens += emitted
        _write_json(output_path, _competition_evaluation_payload(rows, input_tokens, output_tokens, "running"))
    result = _competition_evaluation_payload(rows, input_tokens, output_tokens, "complete")
    _write_json(output_path, result)
    return result


def _competition_evaluation_payload(
    rows: list[dict[str, Any]], input_tokens: int, output_tokens: int, status: str
) -> dict[str, Any]:
    count = len(rows)
    metrics = {
        key + "_rate": sum(bool(row[key]) for row in rows) / count if count else 0.0
        for key in ("schema_valid", "structure_match", "policy_match", "numeric_safe")
    }
    for phase in ("proposal", "deployment"):
        subset = [row for row in rows if row["phase"] == phase]
        metrics[f"{phase}_policy_match_rate"] = (
            sum(bool(row["policy_match"]) for row in subset) / len(subset) if subset else 0.0
        )
    return {
        "format": "brace-msi.competition-agent-evaluation.v1",
        "status": status,
        "examples": count,
        "metrics": metrics,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "rows": rows,
    }


def build_competition_agent_swanlab_spool(run_dir: Path, output_path: Path) -> dict[str, Any]:
    """Export aggregate training/evaluation evidence without prompts or Sampler IDs."""

    root = Path(run_dir)
    progress = json.loads((root / "training_progress.json").read_text(encoding="utf-8"))
    result = json.loads((root / "result.json").read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for step in progress.get("steps", []):
        records.append({
            "schema_version": 1,
            "event": "competition_agent_training",
            "sync_status": "pending",
            "task_kind": "agent_sft",
            "phase": "training",
            "batch_index": int(step["global_step"]),
            "training_steps": int(step["global_step"]),
            "loss": float(step["loss_per_supervised_token"]),
            "wall_seconds": float(step["wall_seconds"]),
            "status": "complete",
        })
    for phase, key in (
        ("base_evaluation", "base_evaluation"),
        ("tuned_evaluation", "tuned_evaluation"),
        ("reload_evaluation", "reload_evaluation"),
    ):
        metrics = result[key]
        evaluation = json.loads((root / f"{phase}.json").read_text(encoding="utf-8"))
        records.append({
            "schema_version": 1,
            "event": "competition_agent_evaluation",
            "sync_status": "pending",
            "task_kind": "agent_sft",
            "phase": phase,
            "schema_valid_rate": float(metrics["schema_valid_rate"]),
            "decision_match_rate": float(metrics["structure_match_rate"]),
            "safety_safe_rate": float(metrics["numeric_safe_rate"]),
            "policy_match_rate": float(metrics["policy_match_rate"]),
            "input_tokens": int(evaluation["input_tokens"]),
            "output_tokens": int(evaluation["output_tokens"]),
            "status": "complete",
        })
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records)
    lowered = encoded.lower()
    forbidden = ("trio://", "api_key", "authorization", "prompt", "response_sha256", "model_path")
    if any(token in lowered for token in forbidden):
        raise ValueError("competition Agent SwanLab spool contains a forbidden field")
    output.write_text(encoded, encoding="utf-8")
    return {"output": str(output), "record_count": len(records), "sha256": _sha256_file(output)}


def _competition_profile(task_kind: str, variant: int) -> TaskProfile:
    classification = task_kind == "classification"
    return TaskProfile(
        task=task_kind,
        primary_metric="macro_f1" if classification else "rmse",
        metric_direction="higher" if classification else "lower",
        auxiliary_metrics=("accuracy",) if classification else ("mae",),
        feature_count=6 + variant % 4,
        class_count=3 + variant % 3 if classification else 0,
        sample_count=80 + variant,
        validation_count=20 + variant % 5,
        label_summary=(
            {"minority_to_majority_ratio": 0.25 + 0.03 * (variant % 4)}
            if classification
            else {"minimum": 0.0, "maximum": 100.0 + variant, "mean": 42.0 + variant}
        ),
        data_quality={"training_finite_fraction": 1.0, "validation_finite_fraction": 1.0},
        group_hints=("group",),
        time_hints=("order",),
        contract_fingerprint=hashlib.sha256(f"{task_kind}-{variant}".encode()).hexdigest(),
    )


def _proposal_recipe(task_kind: str, family_index: int) -> str:
    if task_kind == "classification":
        return (
            "native_current", "native_replay", "class_weighted_ce",
            "class_balanced_sample", "averaged_native", "native_replay",
        )[family_index]
    return (
        "regression_mse", "native_replay", "regression_huber",
        "regression_asymmetric", "averaged_native", "native_replay",
    )[family_index]


def _competition_proposal_example(
    seed: int, split: str, task_kind: str, family: str, family_index: int, variant: int
) -> CompetitionAgentExample:
    profile = _competition_profile(task_kind, variant)
    registry = RecipeRegistry()
    recipe = registry.resolve(_proposal_recipe(task_kind, family_index), profile, {})
    completion = json.dumps(
        {
            "recipe_id": recipe.recipe_id,
            "parameters": {},
            "history_policy": recipe.history_policy,
            "hypothesis": f"the aggregate evidence supports {recipe.loss} with {recipe.history_policy}",
            "rationale": "this registered experiment tests a distinct bounded mechanism",
        },
        separators=(",", ":"), sort_keys=True,
    )
    capture = _CaptureRound(completion)
    mechanism_evidence = (
        "large current-batch shift with low history similarity",
        "high history similarity and positive prior replay gain",
        "severe class imbalance" if task_kind == "classification" else "heavy-tailed residuals with stable history",
        "previous current-only mechanism failed; test a distinct robust mechanism",
        "recent aggressive candidate overshot; use conservative parent averaging",
        "historical replay recipe has the best repeated same-scope gain",
    )[family_index]
    request_experiment_proposal(
        capture,
        profile,
        registry,
        history_summary={
            "completed_rounds": variant,
            "accepted_candidates": variant % 3,
            "previous_recipe_failed": family_index == 3,
            "mechanism_evidence": mechanism_evidence,
            "history_similarity": (0.15, 0.90, 0.65, 0.55, 0.45, 0.95)[family_index],
            "prior_same_scope_gain": (-0.05, 0.08, 0.02, -0.04, -0.03, 0.11)[family_index],
        },
        resource_fields={"remaining_wall_seconds": 240.0 - variant, "peak_rss_bytes": 100000000},
    )
    assert capture.prompt is not None
    legal = tuple(recipe.recipe_id for recipe in registry.available(profile))
    return CompetitionAgentExample(
        scenario_id=f"{seed}-{split}-{task_kind}-proposal-{family}-v{variant}",
        scenario_family=f"{split}:{family}", archetype=family, task_kind=task_kind,
        phase="proposal", prompt=capture.prompt, completion=completion,
        legal_choices=legal, expected_history_policy=recipe.history_policy, expected_role=None,
    )


def _competition_deployment_example(
    seed: int, split: str, task_kind: str, family: str, family_index: int, variant: int
) -> CompetitionAgentExample:
    higher = task_kind == "classification"
    parent = 0.70 + 0.002 * variant if higher else 60.0 + variant
    step = 0.015 + 0.001 * (variant % 3) if higher else 2.0 + 0.1 * (variant % 3)
    expected_role = ("candidate", "candidate", "parent", "parent", "parent", "history")[family_index]
    candidate = parent + step if higher else parent - step
    history = parent - step / 2 if higher else parent + step / 2
    hard_failures: list[str] = []
    if expected_role == "parent":
        candidate = parent - step if higher else parent + step
        if family_index == 3:
            hard_failures = ["candidate_artifact_invalid"]
    elif expected_role == "history":
        history = parent + 2 * step if higher else parent - 2 * step
    roles = {"parent": "parent", "candidate": "candidate", "history": "history"}
    context = {
        "metric_contract": {"metric": "macro_f1" if higher else "rmse", "direction": "higher" if higher else "lower"},
        "artifact_table": [
            {"artifact_id": "parent", "role": "parent", "metrics": {"primary": parent}},
            {"artifact_id": "candidate", "role": "candidate", "metrics": {"primary": candidate}, "hard_failures": hard_failures},
            {"artifact_id": "history", "role": "history", "metrics": {"primary": history}},
        ],
        "artifact_roles": roles,
        "parent_artifact_id": "parent",
        "resource_evidence": {"candidate": {"cpu_seconds": 1.0 + variant / 10.0}},
        "experiment_history": {"completed_rounds": variant, "last_outcome": "accepted" if family_index < 2 else "rejected"},
    }
    completion = json.dumps(
        {"artifact_id": expected_role, "rationale": f"select the legal {expected_role} artifact from same-scope evidence"},
        separators=(",", ":"), sort_keys=True,
    )
    capture = _CaptureRound(completion)
    request_deployment_decision(capture, context, legal_artifact_ids=("parent", "candidate", "history"))
    assert capture.prompt is not None
    return CompetitionAgentExample(
        scenario_id=f"{seed}-{split}-{task_kind}-deployment-{family}-v{variant}",
        scenario_family=f"{split}:{family}", archetype=family, task_kind=task_kind,
        phase="deployment", prompt=capture.prompt, completion=completion,
        legal_choices=("parent", "candidate", "history"), expected_history_policy=None,
        expected_role=expected_role,
    )


def _write_competition_examples(path: Path, rows: tuple[Any, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps({
                "format": COMPETITION_AGENT_FORMAT,
                "scenario_id": row.scenario_id,
                "scenario_family": row.scenario_family,
                "phase": row.phase,
                "task_kind": row.task_kind,
                "messages": [*row.messages, {"role": "assistant", "content": row.completion}],
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def build_formal_advisor_corpus(
    *, seed: int = FORMAL_ADVISOR_SEED,
) -> SftCorpus:
    train: list[SftExample] = []
    evaluation: list[SftExample] = []
    for task_kind in ("classification", "regression"):
        for archetype, variants in (
            ("improved", range(4)),
            ("regressed", range(4)),
            ("tied", range(2)),
            ("hard_risk", range(2)),
        ):
            train.extend(
                _build_example(seed, "train", task_kind, archetype, variant)
                for variant in variants
            )
        for archetype, variants in (
            ("improved", range(1)),
            ("regressed", range(1)),
            ("tied", range(1)),
            ("hard_risk", range(1)),
            ("history_improved", range(1)),
            ("history_regressed", range(1)),
        ):
            evaluation.extend(
                _build_example(seed, "evaluation", task_kind, archetype, variant)
                for variant in variants
            )
    return SftCorpus(tuple(train), tuple(evaluation))


def materialize_formal_advisor_corpus(
    output_dir: Path,
    *,
    seed: int = FORMAL_ADVISOR_SEED,
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    corpus = build_formal_advisor_corpus(seed=seed)
    train_path = root / "train.jsonl"
    evaluation_path = root / "evaluation.jsonl"
    _write_examples(train_path, corpus.train)
    _write_examples(evaluation_path, corpus.evaluation)
    manifest = {
        "format": FORMAL_ADVISOR_FORMAT,
        "seed": seed,
        "data_classification": "synthetic_aggregate_deployment_scenarios",
        "contains_raw_samples": False,
        "contains_credentials": False,
        "train_examples": len(corpus.train),
        "evaluation_examples": len(corpus.evaluation),
        "train_sha256": _sha256_file(train_path),
        "evaluation_sha256": _sha256_file(evaluation_path),
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def score_formal_deployment_response(
    raw: str,
    expected: SftExample,
) -> dict[str, bool]:
    round_stub = _CaptureRound(str(raw))
    decision = request_deployment_decision(round_stub, {})
    schema_valid = decision.parse_error is None
    expected_decision = json.loads(expected.completion)["decision"]
    decision_match = bool(schema_valid and decision.decision == expected_decision)
    unsafe_deploy = decision.decision == "deploy" and expected_decision != "deploy"
    safety_safe = not unsafe_deploy
    return {
        "schema_valid": schema_valid,
        "decision_match": decision_match,
        "safety_safe": safety_safe,
        "policy_match": decision_match and safety_safe,
    }


def validate_formal_advisor_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("seed") != FORMAL_ADVISOR_SEED:
        raise ValueError("formal advisor corpus seed differs from preregistration")
    if manifest.get("train_sha256") != FORMAL_ADVISOR_TRAIN_SHA256:
        raise ValueError("formal advisor training hash differs from preregistration")
    if manifest.get("evaluation_sha256") != FORMAL_ADVISOR_EVALUATION_SHA256:
        raise ValueError("formal advisor evaluation hash differs from preregistration")


def run_remote_formal_advisor_sft(
    output_dir: Path,
    config: FormalAdvisorSftConfig = FormalAdvisorSftConfig(),
    *,
    trio_module: Any | None = None,
) -> dict[str, Any]:
    """Run the single preregistered mirror-side SFT and paired evaluation."""

    root = Path(output_dir)
    if root.exists():
        raise FileExistsError("formal advisor SFT output directory must be new")
    root.mkdir(parents=True, exist_ok=False)
    run_spec: dict[str, Any] = {
        "format": "brace-msi.formal-advisor-sft-run.v1",
        "status": "started",
        "base_model": config.base_model,
        "rank": config.rank,
        "epochs": config.epochs,
        "batch_size": config.batch_size,
        "learning_rate": config.learning_rate,
        "seed": config.seed,
        "max_eval_tokens": config.max_eval_tokens,
        "weight_name": config.weight_name,
        "credentials": "pytrio_runtime_only",
        "formal_image_dependency": False,
    }
    _write_json(root / "run_spec.json", run_spec)
    started = time.perf_counter()
    stage = "preflight"
    steps: list[dict[str, Any]] = []
    model_path: str | None = None
    base_evaluation: dict[str, Any] | None = None
    tuned_evaluation: dict[str, Any] | None = None
    try:
        if config.seed != FORMAL_ADVISOR_SEED:
            raise ValueError("formal advisor SFT seed differs from preregistration")
        if trio_module is None:
            import pytrio as trio_module  # type: ignore[no-redef]
        run_spec["pytrio_version"] = package_version("pytrio")
        corpus = build_formal_advisor_corpus(seed=config.seed)
        manifest = materialize_formal_advisor_corpus(root / "corpus", seed=config.seed)
        validate_formal_advisor_manifest(manifest)
        run_spec["corpus_manifest"] = manifest
        _write_json(root / "run_spec.json", run_spec)

        stage = "service_capabilities"
        service = trio_module.ServiceClient()
        supported = list(service.get_supported_models())
        if config.base_model not in supported:
            raise ValueError("configured base model is not supported")

        stage = "create_training_client"
        trainer = service.create_lora_training_client(
            base_model=config.base_model, rank=config.rank, seed=config.seed
        )
        tokenizer = trainer.get_tokenizer()

        stage = "base_evaluation"
        base_evaluation = _evaluate_formal_sampler(
            service.create_sampling_client(base_model=config.base_model),
            tokenizer,
            corpus.evaluation,
            trio_module,
            config,
            root / "base_evaluation.json",
        )

        stage = "encode_training_corpus"
        encoded = [encode_sft_example(row, tokenizer, trio_module) for row in corpus.train]
        order = list(range(len(encoded)))
        rng = random.Random(config.seed)
        stage = "training"
        for epoch in range(1, config.epochs + 1):
            rng.shuffle(order)
            for batch_start in range(0, len(order), config.batch_size):
                batch_indices = order[batch_start : batch_start + config.batch_size]
                batch = [encoded[index] for index in batch_indices]
                step_started = time.perf_counter()
                result = trainer.forward_backward(batch, "cross_entropy").result()
                trainer.optim_step(
                    trio_module.AdamParams(learning_rate=config.learning_rate)
                ).result()
                steps.append(
                    {
                        "epoch": epoch,
                        "global_step": len(steps) + 1,
                        "batch_examples": len(batch),
                        "loss_per_supervised_token": _weighted_loss(result, batch),
                        "wall_seconds": time.perf_counter() - step_started,
                    }
                )
                _write_json(
                    root / "training_progress.json",
                    {"status": "running", "steps": steps},
                )

        stage = "save_persistent_sampler"
        saved = trainer.save_weights_for_sampler(
            name=config.weight_name, ttl_seconds=None
        ).result()
        model_path = str(saved.path)
        if not model_path.startswith("trio://"):
            raise ValueError("PyTRiO did not return a persistent trio:// path")
        _write_json(
            root / "persistent_sampler.json",
            {
                "format": "brace-msi.formal-advisor-persistent-sampler.v1",
                "base_model": config.base_model,
                "model_path": model_path,
                "model": str(getattr(saved, "model", config.base_model)),
                "size": getattr(saved, "size", None),
            },
        )

        stage = "tuned_evaluation"
        tuned_evaluation = _evaluate_formal_sampler(
            service.create_sampling_client(
                base_model=config.base_model, model_path=model_path
            ),
            tokenizer,
            corpus.evaluation,
            trio_module,
            config,
            root / "tuned_evaluation.json",
        )
        base_metrics = base_evaluation["metrics"]
        tuned_metrics = tuned_evaluation["metrics"]
        adoption_gate = bool(
            tuned_metrics["schema_valid_rate"] == 1.0
            and tuned_metrics["safety_safe_rate"] == 1.0
            and tuned_metrics["decision_match_rate"] >= 0.90
            and tuned_metrics["policy_match_rate"] > base_metrics["policy_match_rate"]
        )
        result = {
            **run_spec,
            "status": "succeeded",
            "training_steps": len(steps),
            "training_examples_seen": len(corpus.train) * config.epochs,
            "final_loss_per_supervised_token": steps[-1]["loss_per_supervised_token"],
            "base_evaluation": base_metrics,
            "tuned_evaluation": tuned_metrics,
            "sampler_model_path": model_path,
            "sampler_model": str(getattr(saved, "model", config.base_model)),
            "sampler_size": getattr(saved, "size", None),
            "adoption_gate_passed": adoption_gate,
            "wall_seconds": time.perf_counter() - started,
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
            "sampler_model_path": model_path,
            "base_evaluation_partial": None if base_evaluation is None else base_evaluation.get("metrics"),
            "tuned_evaluation_partial": None if tuned_evaluation is None else tuned_evaluation.get("metrics"),
            "wall_seconds": time.perf_counter() - started,
        }
        _write_json(root / "failure.json", failure)
        raise


def _evaluate_formal_sampler(
    sampler: Any,
    tokenizer: Any,
    examples: tuple[SftExample, ...],
    trio_module: Any,
    config: FormalAdvisorSftConfig,
    output_path: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    input_tokens = 0
    output_tokens = 0
    for index, example in enumerate(examples):
        prompt_text = tokenizer.apply_chat_template(
            list(example.messages), tokenize=False, add_generation_prompt=True,
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
        raw = str(response.sequences[0].text) if response.sequences else ""
        emitted = len(response.sequences[0].tokens) if response.sequences else 0
        score = score_formal_deployment_response(raw, example)
        rows.append(
            {
                "scenario_id": example.scenario_id,
                "archetype": example.archetype,
                "task_kind": example.task_kind,
                "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "input_tokens": len(input_ids),
                "output_tokens": emitted,
                **score,
            }
        )
        input_tokens += len(input_ids)
        output_tokens += emitted
        _write_json(
            output_path,
            _formal_evaluation_payload(rows, input_tokens, output_tokens, "running"),
        )
    result = _formal_evaluation_payload(rows, input_tokens, output_tokens, "complete")
    _write_json(output_path, result)
    return result


def _formal_evaluation_payload(
    rows: list[dict[str, Any]], input_tokens: int, output_tokens: int, status: str
) -> dict[str, Any]:
    count = len(rows)
    metrics = {
        key + "_rate": sum(bool(row[key]) for row in rows) / count if count else 0.0
        for key in ("schema_valid", "decision_match", "safety_safe", "policy_match")
    }
    return {
        "format": "brace-msi.formal-advisor-evaluation.v1",
        "status": status,
        "examples": count,
        "metrics": metrics,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "rows": rows,
    }


def _write_json(path: Path, value: Any) -> None:
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _build_example(
    seed: int,
    split: str,
    task_kind: str,
    archetype: str,
    variant: int,
) -> SftExample:
    offset = variant + (100 if split == "evaluation" else 0)
    classification = task_kind == "classification"
    metric = "macro_f1" if classification else "rmse"
    direction = "higher" if classification else "lower"
    parent = (0.55 + 0.011 * offset) if classification else (45.0 + 1.7 * offset)
    delta = (0.012 + 0.002 * (variant % 3)) if classification else (1.5 + 0.4 * (variant % 3))
    hard_failures: list[str] = []
    if archetype in {"improved", "history_improved"}:
        candidate = parent + delta if classification else parent - delta
        relation = "improved"
        expected = "deploy"
    elif archetype in {"regressed", "history_regressed"}:
        candidate = parent - delta if classification else parent + delta
        relation = "regressed"
        expected = "retain"
    elif archetype == "tied":
        candidate = parent
        relation = "tied"
        expected = "retain"
    elif archetype == "hard_risk":
        candidate = parent + delta if classification else parent - delta
        relation = "improved"
        expected = "retain"
        if split == "evaluation":
            hard_failures = ["checkpoint_size_exceeded"]
        else:
            hard_failures = [
                "candidate_metrics_nonfinite"
                if variant % 2 == 0
                else "parent_checkpoint_mismatch"
            ]
    else:
        raise ValueError(f"unknown formal advisor archetype: {archetype}")

    allowed = (
        ["deploy", "retain", "rollback"]
        if relation == "improved" and not hard_failures
        else ["retain", "rollback"]
    )
    directed_gain = (
        candidate - parent if classification else parent - candidate
    )
    context = {
        "task": task_kind,
        "round_index": 3 + (variant % 7),
        "metric": metric,
        "metric_direction": direction,
        "recipe": "e3_lr3" if variant % 2 else "e1_lr1",
        "parent_metrics": {metric: parent},
        "candidate_metrics": {metric: candidate},
        "metric_directions": {metric: direction},
        "primary_evidence": {
            "metric": metric,
            "direction": direction,
            "parent": parent,
            "candidate": candidate,
            "directed_gain": directed_gain,
            "relation": relation,
            "same_scope": True,
        },
        "metric_evidence": {
            metric: {
                "direction": direction,
                "parent": parent,
                "candidate": candidate,
            }
        },
        "allowed_decisions": allowed,
        "resource_evidence": {
            "cpu_seconds": 1.0 + 0.1 * variant,
            "checkpoint_bytes": 1_000_000 + 100 * variant,
            "parameter_count": 1024,
            "peak_rss_bytes": 120_000_000,
        },
        "history": (
            [
                {
                    "round_index": 2,
                    "requested_decision": "deploy",
                    "applied_decision": "retain",
                    "reason": "prior candidate was not better on comparable evidence",
                }
            ]
            if archetype.startswith("history_")
            else []
        ),
        "hard_safety_failures": hard_failures,
    }
    completion = json.dumps(
        {
            "decision": expected,
            "rationale": (
                "metric_improved_no_hard_failure"
                if expected == "deploy"
                else "deployment_not_justified"
            ),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    capture = _CaptureRound(completion)
    parsed = request_deployment_decision(capture, context)
    if parsed.parse_error is not None or parsed.decision != expected or capture.prompt is None:
        raise AssertionError("generated formal advisor example is invalid")
    return SftExample(
        scenario_id=f"{seed}-{split}-{task_kind}-{archetype}-v{variant}",
        archetype=archetype,
        task_kind=task_kind,
        prompt=capture.prompt,
        completion=completion,
        budget_cpu_seconds=60.0,
        budget_candidate_slots=1,
        evidence_safe=not hard_failures,
    )


def _write_examples(path: Path, examples: tuple[SftExample, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in examples:
            stream.write(
                json.dumps(
                    {
                        "format": FORMAL_ADVISOR_FORMAT,
                        "scenario_id": row.scenario_id,
                        "archetype": row.archetype,
                        "task_kind": row.task_kind,
                        "prompt": row.prompt,
                        "completion": row.completion,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
