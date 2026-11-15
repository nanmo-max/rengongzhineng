"""PyTRiO proposal adapter for the native platform runtime.

The advisor produces data-only proposals.  The native runtime revalidates every
field and remains the sole owner of training, budget and deployment effects.
"""

from __future__ import annotations

from .policies import Action
from .pytrio_agent import (
    AgentContext,
    ExperimentProposal,
    PROPOSAL_SCHEMA_VERSION,
    PyTrioAgentClient,
    PyTrioAgentConfig,
    RetryingProposalAdvisor,
    SamplingTransport,
)


def deterministic_platform_proposal(context: AgentContext) -> ExperimentProposal:
    replay_count = int(context.evidence.get("replay_count", 0))
    action = Action.REPLAY_REFIT if replay_count > 0 else Action.INCREMENTAL_UPDATE
    return ExperimentProposal(
        schema_version=PROPOSAL_SCHEMA_VERSION,
        action=action,
        tool=(
            "train_replay_refit"
            if action is Action.REPLAY_REFIT
            else "train_incremental"
        ),
        rationale="bounded continuation selected by deterministic recovery policy",
        parameters={"epochs": 1},
        max_cpu_seconds=300.0,
        max_candidates=1,
        stop_conditions=("budget_exhausted", "nonfinite_training_state"),
    )


def build_platform_advisor(
    *,
    model: str = "Qwen/Qwen3.5-4B",
    model_path: str | None = None,
    timeout_seconds: float = 15.0,
    transport: SamplingTransport | None = None,
) -> RetryingProposalAdvisor:
    client = PyTrioAgentClient(
        PyTrioAgentConfig(
            model=model,
            model_path=model_path,
            max_tokens=768,
            temperature=0.0,
            timeout_seconds=timeout_seconds,
            allow_fallback=False,
        ),
        transport=transport,
        fallback=deterministic_platform_proposal,
    )
    return RetryingProposalAdvisor(
        client,
        fallback=deterministic_platform_proposal,
        max_attempts=2,
    )
