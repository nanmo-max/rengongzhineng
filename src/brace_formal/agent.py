"""Single-call bounded Agent boundary owned by the official host gateway."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .profile import TaskProfile
from .recipes import RecipeRegistry


@dataclass(frozen=True)
class AgentDecision:
    action: str
    epochs: int
    learning_rate_multiplier: float
    call_id: str
    rationale: str
    parse_error: str | None = None


@dataclass(frozen=True)
class TrainingProposal:
    recipe: str
    call_id: str
    rationale: str
    parse_error: str | None = None


@dataclass(frozen=True)
class DeploymentDecision:
    decision: str
    call_id: str
    rationale: str
    parse_error: str | None = None
    requested_artifact_id: str | None = None


@dataclass(frozen=True)
class ExperimentProposal:
    recipe_id: str
    parameters: dict[str, Any]
    history_policy: str
    hypothesis: str
    rationale: str
    call_id: str
    parse_error: str | None = None


_TRAINING_RECIPES = {"e1_lr1", "e3_lr3", "soup_e3_alpha0.25"}
_PRIVATE_AGGREGATE_KEYS = {
    "row", "rows", "input", "inputs", "answer", "answers", "feature", "features",
    "id", "ids", "sampleid", "sampleids", "rawdata", "records",
}


def _json_object(text: str) -> Mapping[str, Any]:
    objects: list[Mapping[str, Any]] = []
    start: int | None = None
    depth = 0
    quoted = False
    escaped = False

    for index, character in enumerate(text):
        if start is None:
            if character == "{":
                start = index
                depth = 1
                quoted = False
                escaped = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : index + 1]
                try:
                    payload = json.loads(candidate)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(payload, dict):
                        objects.append(payload)
                start = None

    if len(objects) != 1:
        raise ValueError("proposal must contain exactly one JSON object")
    return objects[0]


def _parse(text: str, call_id: str) -> AgentDecision:
    payload = _json_object(text)
    action = payload.get("action")
    if action not in {"retain", "train"}:
        raise ValueError("action must be retain or train")
    rationale = payload.get("rationale", "host model supplied a bounded decision")
    if not isinstance(rationale, str) or not rationale.strip():
        rationale = "host model supplied a bounded decision"
    return AgentDecision(action, 1, 1.0, call_id, rationale.strip())


def request_proposal(rnd: Any, context: Mapping[str, Any]) -> AgentDecision:
    """Call the host model exactly once before any train/retain decision."""

    messages = [
        {
            "role": "user",
            "content": (
                "Return exactly one compact JSON object and no analysis or markdown. "
                "The first character must be {. Required fields: action "
                "(retain|train) and rationale (one short sentence). "
                "The controlled executor, not this response, selects training parameters. Context: "
                + json.dumps(dict(context), sort_keys=True, ensure_ascii=False, allow_nan=False)
            ),
        }
    ]
    receipt = rnd.model(
        messages,
        temperature=0.0,
        enable_thinking=False,
        response_format={"type": "json_object"},
    )
    call_id = getattr(receipt, "call_id", None)
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("host model returned no call ID")
    text = getattr(receipt, "text", "")
    if not isinstance(text, str):
        text = ""
    try:
        return _parse(text, call_id)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return AgentDecision(
            action="retain",
            epochs=1,
            learning_rate_multiplier=1.0,
            call_id=call_id,
            rationale="retain because the host proposal was invalid",
            parse_error=f"{type(exc).__name__}: {exc}",
        )


def _host_json(rnd: Any, instruction: str, context: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    receipt = rnd.model(
        [
            {
                "role": "user",
                "content": (
                    "Return exactly one compact JSON object and no analysis or markdown. "
                    "The first character must be {. "
                    + instruction
                    + " Context: "
                    + json.dumps(dict(context), sort_keys=True, ensure_ascii=False, allow_nan=False)
                ),
            }
        ],
        temperature=0.0,
        enable_thinking=False,
        response_format={"type": "json_object"},
    )
    call_id = getattr(receipt, "call_id", None)
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("host model returned no call ID")
    text = getattr(receipt, "text", "")
    if not isinstance(text, str):
        text = ""
    return _json_object(text), call_id


def _assert_aggregate_only(value: Any, path: str = "context") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = "".join(character for character in str(key).lower() if character.isalnum())
            if normalized in _PRIVATE_AGGREGATE_KEYS:
                raise ValueError(f"aggregate-only context cannot contain {path}.{key}")
            _assert_aggregate_only(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_aggregate_only(child, f"{path}[{index}]")
    elif value is not None and (isinstance(value, bool) or isinstance(value, (str, int, float))):
        return
    elif value is not None:
        raise ValueError(f"aggregate-only context contains unsupported value at {path}")


def _recipe_descriptors(profile: TaskProfile, registry: RecipeRegistry) -> list[dict[str, Any]]:
    return [
        {
            "recipe_id": recipe.recipe_id,
            "history_policy": recipe.history_policy,
            "epochs": recipe.epochs,
            "learning_rate_multiplier": recipe.learning_rate_multiplier,
            "loss": recipe.loss,
            "loss_parameters": recipe.parameters_dict(),
            "class_weighting": recipe.class_weighting,
            "balanced_sampling": recipe.balanced_sampling,
            "parent_average_alpha": recipe.parent_average_alpha,
        }
        for recipe in registry.available(profile)
    ]


def request_experiment_proposal(
    rnd: Any,
    profile: TaskProfile,
    registry: RecipeRegistry,
    *,
    history_summary: Mapping[str, Any] | None = None,
    resource_fields: Mapping[str, Any] | None = None,
) -> ExperimentProposal:
    """Ask Qwen for one executable registered experiment, with real-training fallback."""

    history = dict(history_summary or {})
    resources = dict(resource_fields or {})
    _assert_aggregate_only(history, "history_summary")
    _assert_aggregate_only(resources, "resource_fields")
    context = {
        "task_profile": profile.as_dict(),
        "available_recipes": _recipe_descriptors(profile, registry),
        "history_summary": history,
        "resource_fields": resources,
        "candidate_training_required": True,
    }
    try:
        payload, call_id = _host_json(
            rnd,
            "Required fields: recipe_id (one available recipe), parameters (JSON object), "
            "history_policy (the selected recipe's declared policy), hypothesis and rationale (nonempty strings). ",
            context,
        )
        recipe_id = payload.get("recipe_id")
        parameters = payload.get("parameters")
        history_policy = payload.get("history_policy")
        hypothesis = payload.get("hypothesis")
        rationale = payload.get("rationale")
        if not isinstance(recipe_id, str) or not isinstance(parameters, Mapping):
            raise ValueError("recipe_id and parameters are required")
        recipe = registry.resolve(recipe_id, profile, parameters)
        if history_policy != recipe.history_policy:
            raise ValueError("history_policy differs from the registered recipe")
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError("experiment hypothesis is required")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("experiment rationale is required")
        return ExperimentProposal(
            recipe.recipe_id,
            dict(parameters),
            recipe.history_policy,
            hypothesis.strip(),
            rationale.strip(),
            call_id,
        )
    except (Exception,) as exc:
        fallback = registry.fallback(profile)
        call_ids = getattr(rnd, "call_ids", ())
        call_id = call_ids[-1] if call_ids and isinstance(call_ids[-1], str) else ""
        return ExperimentProposal(
            fallback.recipe_id,
            {},
            fallback.history_policy,
            "run the deterministic parent-compatible fallback experiment",
            "the host proposal was unavailable or not executable",
            call_id,
            f"{type(exc).__name__}: {exc}",
        )


def request_training_proposal(rnd: Any, context: Mapping[str, Any]) -> TrainingProposal:
    """Ask Qwen to choose one executable recipe; invalid output uses the safest recipe."""

    try:
        payload, call_id = _host_json(
            rnd,
            "Required fields: recipe (e1_lr1|e3_lr3|soup_e3_alpha0.25) and rationale (one short sentence). ",
            context,
        )
        recipe = payload.get("recipe")
        if recipe not in _TRAINING_RECIPES:
            raise ValueError("recipe is not in the controlled training whitelist")
        rationale = payload.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("training rationale is required")
        return TrainingProposal(str(recipe), call_id, rationale.strip())
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        call_ids = getattr(rnd, "call_ids", ())
        call_id = call_ids[-1] if call_ids else ""
        if not isinstance(call_id, str) or not call_id:
            raise
        return TrainingProposal(
            "e1_lr1",
            call_id,
            "use the safest parent-compatible continuation because the training proposal was invalid",
            f"{type(exc).__name__}: {exc}",
        )


def request_deployment_decision(
    rnd: Any,
    context: Mapping[str, Any],
    *,
    legal_artifact_ids: tuple[str, ...] | None = None,
) -> DeploymentDecision:
    """Ask Qwen to deploy, retain, or roll back after seeing measured evidence."""

    if legal_artifact_ids is not None:
        if not legal_artifact_ids or len(set(legal_artifact_ids)) != len(legal_artifact_ids):
            raise ValueError("legal artifact IDs must be unique and nonempty")
        _assert_aggregate_only(context, "deployment_context")
        try:
            payload, call_id = _host_json(
                rnd,
                "Required fields: artifact_id (one legal artifact ID) and rationale (one short sentence). "
                "Use only same-scope metrics, resource evidence and legal artifact IDs. ",
                {**dict(context), "legal_artifact_ids": list(legal_artifact_ids)},
            )
            artifact_id = payload.get("artifact_id")
            rationale = payload.get("rationale")
            if artifact_id not in legal_artifact_ids:
                raise ValueError("requested artifact is not legal")
            if not isinstance(rationale, str) or not rationale.strip():
                raise ValueError("deployment rationale is required")
            roles = context.get("artifact_roles")
            role = roles.get(artifact_id) if isinstance(roles, Mapping) else None
            decisions = {"candidate": "deploy", "parent": "retain", "history": "rollback"}
            if role not in decisions:
                raise ValueError("requested artifact has no legal role")
            return DeploymentDecision(decisions[str(role)], call_id, rationale.strip(), None, str(artifact_id))
        except (Exception,) as exc:
            roles = context.get("artifact_roles")
            parent_id = context.get("parent_artifact_id")
            if parent_id not in legal_artifact_ids and isinstance(roles, Mapping):
                parent_id = next((item for item in legal_artifact_ids if roles.get(item) == "parent"), None)
            if parent_id not in legal_artifact_ids:
                parent_id = legal_artifact_ids[0]
            call_ids = getattr(rnd, "call_ids", ())
            call_id = call_ids[-1] if call_ids and isinstance(call_ids[-1], str) else ""
            return DeploymentDecision(
                "retain",
                call_id,
                "retain the parent because the artifact decision was invalid",
                f"{type(exc).__name__}: {exc}",
                str(parent_id),
            )

    try:
        payload, call_id = _host_json(
            rnd,
            "Required fields: decision (deploy|retain|rollback) and rationale (one short sentence). "
            "Use the supplied parent/candidate metrics, resource evidence and experiment history. ",
            context,
        )
        decision = payload.get("decision")
        if decision not in {"deploy", "retain", "rollback"}:
            raise ValueError("decision must be deploy, retain, or rollback")
        rationale = payload.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("deployment rationale is required")
        return DeploymentDecision(str(decision), call_id, rationale.strip())
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        call_ids = getattr(rnd, "call_ids", ())
        call_id = call_ids[-1] if call_ids else ""
        if not isinstance(call_id, str) or not call_id:
            raise
        return DeploymentDecision(
            "retain",
            call_id,
            "retain the parent because the deployment decision was invalid",
            f"{type(exc).__name__}: {exc}",
        )
