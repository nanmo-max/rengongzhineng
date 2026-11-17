"""Single-call bounded Agent boundary owned by the official host gateway."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
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
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1])
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("proposal must be a JSON object")
    return payload


def _parse(text: str, call_id: str) -> AgentDecision:
    payload = _json_object(text)
    action = payload.get("action")
    epochs = payload.get("epochs", 1)
    multiplier = payload.get("learning_rate_multiplier", 1.0)
    if action not in {"retain", "train"}:
        raise ValueError("action must be retain or train")
    if type(epochs) is not int or not 1 <= epochs <= 5:
        raise ValueError("epochs must be in 1..5")
    if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
        raise ValueError("learning-rate multiplier must be numeric")
    multiplier = float(multiplier)
    if not math.isfinite(multiplier) or multiplier not in {0.3, 1.0, 3.0}:
        raise ValueError("learning-rate multiplier must be 0.3, 1, or 3")
    rationale = payload.get("rationale", "host model supplied a bounded decision")
    if not isinstance(rationale, str) or not rationale.strip():
        rationale = "host model supplied a bounded decision"
    return AgentDecision(action, epochs, multiplier, call_id, rationale.strip())


def request_proposal(rnd: Any, context: Mapping[str, Any]) -> AgentDecision:
    """Call the host model exactly once before any train/retain decision."""

    messages = [
        {
            "role": "user",
            "content": (
                "Choose one safe industrial-model action. Return JSON only with "
                "action (retain|train), epochs (1..5), learning_rate_multiplier "
                "(0.3|1|3), and a short rationale. Current aggregate context: "
                + json.dumps(dict(context), sort_keys=True, ensure_ascii=False, allow_nan=False)
            ),
        }
    ]
    receipt = rnd.model(
        messages,
        max_tokens=min(256, int(rnd.max_output_tokens)),
        temperature=0.0,
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
