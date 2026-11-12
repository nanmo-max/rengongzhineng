"""Strict PyTRiO proposal boundary for the BRACE deterministic harness.

The language model can propose a versioned, allow-listed experiment. It cannot
execute tools, mutate files, spend training budget, or deploy a model. Those
effects remain owned by the deterministic harness.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import math
import re
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from .policies import Action


PROPOSAL_SCHEMA_VERSION = "brace-msi.experiment-proposal.v1"
_SECRET_KEY_PATTERN = re.compile(
    r"(^|_)(api_?key|password|passwd|secret|authorization|credential|access_?token|refresh_?token)($|_)",
    re.IGNORECASE,
)
_ALLOWED_TOOLS: dict[Action, str] = {
    Action.NOOP: "noop",
    Action.INCREMENTAL_UPDATE: "train_incremental",
    Action.REPLAY_REFIT: "train_replay_refit",
    Action.FAMILY_SWITCH: "train_family_switch",
    Action.BOUNDED_HPO: "train_bounded_hpo",
    Action.ROLLBACK: "rollback",
}
_ALLOWED_PARAMETER_KEYS = {
    "epochs",
    "learning_rate",
    "batch_size",
    "replay_fraction",
    "weight_decay",
    "patience",
    "max_candidates",
    "model_family",
    "plugin_id",
}


@dataclass(frozen=True)
class PyTrioAgentConfig:
    model: str = "Qwen/Qwen3.5-4B"
    model_path: str | None = None
    max_tokens: int = 768
    temperature: float = 0.0
    seed: int = 20261106

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not 1 <= self.max_tokens <= 4096:
            raise ValueError("max_tokens must be in [1, 4096]")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be in [0, 2]")


@dataclass(frozen=True)
class AgentContext:
    task_kind: str
    metric_name: str
    higher_is_better: bool
    round_index: int
    evidence: Mapping[str, Any]
    history: Sequence[Mapping[str, Any]]
    budget: Mapping[str, Any]
    capabilities: Mapping[str, Any]

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "task_kind": self.task_kind,
            "metric_name": self.metric_name,
            "higher_is_better": self.higher_is_better,
            "round_index": self.round_index,
            "evidence": dict(self.evidence),
            "history": [dict(item) for item in self.history],
            "budget": dict(self.budget),
            "capabilities": dict(self.capabilities),
        }
        _validate_safe_json(payload)
        return payload


@dataclass(frozen=True)
class ExperimentProposal:
    schema_version: str
    action: Action
    tool: str
    rationale: str
    parameters: Mapping[str, Any]
    max_cpu_seconds: float
    max_candidates: int
    stop_conditions: tuple[str, ...]


@dataclass(frozen=True)
class SamplingResult:
    text: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class AgentCallReceipt:
    status: str
    model: str
    model_path_configured: bool
    prompt_sha256: str
    response_sha256: str | None
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    error_category: str | None = None
    error_detail: str | None = None


@dataclass(frozen=True)
class ProposalOutcome:
    proposal: ExperimentProposal
    source: str
    receipt: AgentCallReceipt


class SamplingTransport(Protocol):
    def sample(
        self,
        prompt: str,
        *,
        model: str,
        model_path: str | None,
        max_tokens: int,
        temperature: float,
        seed: int,
    ) -> SamplingResult: ...


class PyTrioSamplingTransport:
    """Small adapter around the documented PyTRiO Sampler API.

    Import is lazy so local tests and the deterministic fallback do not require
    the optional SDK. Authentication and the service URL remain PyTRiO runtime
    configuration (normally ``PYTRIO_API_KEY`` and ``PYTRIO_BASE_URL``).
    """

    def __init__(self, *, pytrio_module: Any | None = None) -> None:
        self._module = pytrio_module

    def _pytrio(self) -> Any:
        if self._module is None:
            self._module = importlib.import_module("pytrio")
        return self._module

    def sample(
        self,
        prompt: str,
        *,
        model: str,
        model_path: str | None,
        max_tokens: int,
        temperature: float,
        seed: int,
    ) -> SamplingResult:
        trio = self._pytrio()
        service = trio.ServiceClient()
        client_kwargs: dict[str, Any] = {"base_model": model}
        if model_path:
            client_kwargs["model_path"] = model_path
        sampler = service.create_sampling_client(**client_kwargs)
        tokenizer = sampler.get_tokenizer()
        input_text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        input_ids = tokenizer.encode(input_text, add_special_tokens=False)
        params = trio.SamplingParams(
            max_tokens=max_tokens,
            seed=seed,
            temperature=temperature,
        )
        response = sampler.sample(
            prompt=trio.ModelInput.from_ints(input_ids),
            num_samples=1,
            sampling_params=params,
        ).result()
        if not response.sequences:
            raise ValueError("PyTRiO returned no sequences")
        sequence = response.sequences[0]
        return SamplingResult(
            text=str(sequence.text),
            input_tokens=len(input_ids),
            output_tokens=len(sequence.tokens),
        )


class PyTrioAgentClient:
    def __init__(
        self,
        config: PyTrioAgentConfig,
        *,
        transport: SamplingTransport | None = None,
        fallback: Callable[[AgentContext], ExperimentProposal],
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.config = config
        self.transport = transport or PyTrioSamplingTransport()
        self.fallback = fallback
        self.clock = clock

    def propose(self, context: AgentContext) -> ProposalOutcome:
        payload = context.to_payload()
        prompt = build_agent_prompt(payload)
        prompt_hash = _sha256_text(prompt)
        started = self.clock()
        try:
            sampled = self.transport.sample(
                prompt,
                model=self.config.model,
                model_path=self.config.model_path,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                seed=self.config.seed,
            )
        except Exception as exc:  # transport failures are an expected boundary
            return self._fallback_outcome(
                context,
                prompt_hash=prompt_hash,
                started=started,
                category="transport_error",
                detail=type(exc).__name__,
            )

        response_hash = _sha256_text(sampled.text)
        try:
            proposal = parse_experiment_proposal(sampled.text)
        except (ValueError, TypeError, json.JSONDecodeError):
            return self._fallback_outcome(
                context,
                prompt_hash=prompt_hash,
                response_hash=response_hash,
                input_tokens=sampled.input_tokens,
                output_tokens=sampled.output_tokens,
                started=started,
                category="invalid_response",
                detail="ProposalValidationError",
            )

        return ProposalOutcome(
            proposal=proposal,
            source="pytrio",
            receipt=AgentCallReceipt(
                status="accepted",
                model=self.config.model,
                model_path_configured=self.config.model_path is not None,
                prompt_sha256=prompt_hash,
                response_sha256=response_hash,
                input_tokens=sampled.input_tokens,
                output_tokens=sampled.output_tokens,
                latency_seconds=max(0.0, self.clock() - started),
            ),
        )

    def _fallback_outcome(
        self,
        context: AgentContext,
        *,
        prompt_hash: str,
        started: float,
        category: str,
        detail: str,
        response_hash: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> ProposalOutcome:
        proposal = self.fallback(context)
        validate_experiment_proposal(proposal)
        return ProposalOutcome(
            proposal=proposal,
            source="deterministic_fallback",
            receipt=AgentCallReceipt(
                status="fallback",
                model=self.config.model,
                model_path_configured=self.config.model_path is not None,
                prompt_sha256=prompt_hash,
                response_sha256=response_hash,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_seconds=max(0.0, self.clock() - started),
                error_category=category,
                error_detail=detail,
            ),
        )


def parse_experiment_proposal(raw: str) -> ExperimentProposal:
    cleaned = raw.strip()
    # PyTRiO/Qwen can expose the chat-template terminator in ``sequence.text``.
    # Accept only the exact observed suffix; arbitrary trailing text remains an
    # error so the model cannot smuggle instructions past the JSON boundary.
    if cleaned.endswith("<|im_end|>"):
        cleaned = cleaned[: -len("<|im_end|>")].rstrip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1])
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("proposal must be a JSON object")
    expected = {
        "schema_version",
        "action",
        "tool",
        "rationale",
        "parameters",
        "max_cpu_seconds",
        "max_candidates",
        "stop_conditions",
    }
    if set(value) != expected:
        raise ValueError("proposal fields do not match the schema")
    try:
        action = Action(value["action"])
    except (TypeError, ValueError) as exc:
        raise ValueError("unsupported action") from exc
    parameters = value["parameters"]
    conditions = value["stop_conditions"]
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    if not isinstance(conditions, list) or not all(
        isinstance(item, str) and item.strip() for item in conditions
    ):
        raise ValueError("stop_conditions must be a string list")
    proposal = ExperimentProposal(
        schema_version=value["schema_version"],
        action=action,
        tool=value["tool"],
        rationale=value["rationale"],
        parameters=parameters,
        max_cpu_seconds=value["max_cpu_seconds"],
        max_candidates=value["max_candidates"],
        stop_conditions=tuple(conditions),
    )
    validate_experiment_proposal(proposal)
    return proposal


def validate_experiment_proposal(proposal: ExperimentProposal) -> None:
    """Validate a proposal again at the effectful harness boundary."""
    if proposal.schema_version != PROPOSAL_SCHEMA_VERSION:
        raise ValueError("unsupported proposal schema")
    if _ALLOWED_TOOLS.get(proposal.action) != proposal.tool:
        raise ValueError("tool is not allowed for action")
    if not isinstance(proposal.rationale, str) or not proposal.rationale.strip():
        raise ValueError("rationale must not be empty")
    if len(proposal.rationale) > 1000:
        raise ValueError("rationale is too long")
    if not isinstance(proposal.parameters, Mapping):
        raise ValueError("parameters must be a mapping")
    unknown = set(proposal.parameters) - _ALLOWED_PARAMETER_KEYS
    if unknown:
        raise ValueError(f"unsupported parameters: {sorted(unknown)}")
    _validate_safe_json(dict(proposal.parameters))
    if isinstance(proposal.max_cpu_seconds, bool) or not isinstance(
        proposal.max_cpu_seconds, (int, float)
    ):
        raise ValueError("max_cpu_seconds must be numeric")
    if not math.isfinite(float(proposal.max_cpu_seconds)) or not 0 < float(
        proposal.max_cpu_seconds
    ) <= 3600:
        raise ValueError("max_cpu_seconds is outside the proposal limit")
    if isinstance(proposal.max_candidates, bool) or not isinstance(
        proposal.max_candidates, int
    ):
        raise ValueError("max_candidates must be an integer")
    if not 1 <= proposal.max_candidates <= 8:
        raise ValueError("max_candidates is outside the proposal limit")
    if len(proposal.stop_conditions) > 16:
        raise ValueError("too many stop conditions")


def _validate_safe_json(value: Any, *, path: str = "context") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite value at {path}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string key at {path}")
            if _SECRET_KEY_PATTERN.search(key):
                raise ValueError(f"secret-bearing key at {path}.{key}")
            _validate_safe_json(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_safe_json(child, path=f"{path}[{index}]")
        return
    raise ValueError(f"unsupported value at {path}: {type(value).__name__}")


def build_agent_prompt(payload: Mapping[str, Any]) -> str:
    """Build the exact prompt used by both runtime inference and SFT.

    A runtime may expose fewer tools than the versioned proposal schema knows
    about.  When ``capabilities.allowed_actions`` is present, only that
    executable subset is advertised to the model.  The deterministic harness
    still validates the returned proposal independently.
    """
    requested = payload.get("capabilities", {}).get("allowed_actions")
    if isinstance(requested, list):
        allowed_actions = {
            action
            for action in _ALLOWED_TOOLS
            if action.value in requested
        }
        if not allowed_actions:
            allowed_actions = {Action.NOOP}
    else:
        allowed_actions = set(_ALLOWED_TOOLS)
    schema = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "action": sorted(action.value for action in allowed_actions),
        "tool_mapping": {
            action.value: _ALLOWED_TOOLS[action]
            for action in sorted(allowed_actions, key=lambda item: item.value)
        },
        "parameters_allowed": sorted(_ALLOWED_PARAMETER_KEYS),
        "required_fields": [
            "schema_version",
            "action",
            "tool",
            "rationale",
            "parameters",
            "max_cpu_seconds",
            "max_candidates",
            "stop_conditions",
        ],
    }
    control_policy = None
    evidence = payload.get("evidence", {})
    if isinstance(evidence, Mapping) and "minimum_candidate_events_remaining" in evidence:
        remaining = evidence["minimum_candidate_events_remaining"]
        if isinstance(remaining, bool) or not isinstance(remaining, int) or remaining < 0:
            raise ValueError("minimum_candidate_events_remaining must be nonnegative")
        control_policy = {
            "minimum_candidate_events_remaining": remaining,
            "minimum_candidate_rule": {
                "first_action": Action.INCREMENTAL_UPDATE.value,
                "after_rejected_candidate": Action.REPLAY_REFIT.value,
                "noop_allowed_when_remaining": 0,
            },
            "priority": [
                "hard_budget_and_data_safety",
                "minimum_real_candidate_compliance",
                "performance_and_history_evidence",
            ],
        }
    prompt = (
        "You are the experiment-proposal component of BRACE-MSI. "
        "Return exactly one JSON object and no commentary. You may only propose; "
        "the deterministic harness independently validates budget, trains, evaluates, "
        "and deploys.\n"
        f"PROPOSAL_SCHEMA={json.dumps(schema, sort_keys=True, separators=(',', ':'))}\n"
    )
    if control_policy is not None:
        prompt += (
            "CONTROL_POLICY="
            + json.dumps(control_policy, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
    return prompt + f"TASK_STATE={json.dumps(payload, sort_keys=True, separators=(',', ':'))}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
