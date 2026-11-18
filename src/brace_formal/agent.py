"""Single-call bounded Agent boundary owned by the official host gateway."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentDecision:
    action: str
    epochs: int
    learning_rate_multiplier: float
    call_id: str
    rationale: str
    parse_error: str | None = None


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
