from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from brace_formal.data import DataBatch
from brace_formal.model import FormalModel
from brace_formal.profile import build_task_profile
from brace_formal.recipes import RecipeRegistry
from tests.competition_core.support import write_parent


class AgentRound:
    def __init__(self, responses: list[str | BaseException]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[list[dict[str, str]], dict[str, object]]] = []
        self.call_ids: list[str] = []

    def model(self, messages, **options):
        self.calls.append((messages, options))
        response = next(self._responses)
        if isinstance(response, BaseException):
            raise response
        call_id = f"call-{len(self.calls)}"
        self.call_ids.append(call_id)
        return SimpleNamespace(call_id=call_id, text=response, response={})


def _profile(tmp_path: Path, task: str = "classification"):
    path = tmp_path / f"{task}.npz"
    write_parent(path, task=task)
    model = FormalModel.load(path)
    x = np.asarray([[float(index), float(index % 2)] for index in range(8)], dtype=np.float64)
    y = np.asarray([0, 0, 0, 0, 1, 1, 1, 1] if task == "classification" else list(range(8)))
    batch = DataBatch(tuple(f"row-{index}" for index in range(8)), x, y, "a" * 64)
    metric = "macro_f1" if task == "classification" else "rmse"
    return build_task_profile({"task": task, "metric": metric, "dataset_key": "unknown-industrial-task"}, model, batch, batch)


def test_unknown_task_proposal_is_executable_and_uses_no_participant_token_cap(tmp_path: Path) -> None:
    from brace_formal.agent import request_experiment_proposal

    rnd = AgentRound(
        [
            json.dumps(
                {
                    "recipe_id": "class_weighted_ce",
                    "parameters": {"epochs": 3, "learning_rate_multiplier": 1.5},
                    "history_policy": "current_plus_history",
                    "hypothesis": "class weighting can improve minority recall",
                    "rationale": "the aggregate class ratio is imbalanced",
                }
            )
        ]
    )
    profile = _profile(tmp_path)

    proposal = request_experiment_proposal(
        rnd,
        profile,
        RecipeRegistry(),
        history_summary={"completed_rounds": 2, "accepted_candidates": 1},
        resource_fields={"remaining_wall_seconds": 120.0},
    )

    assert proposal.recipe_id == "class_weighted_ce"
    assert proposal.parameters == {"epochs": 3, "learning_rate_multiplier": 1.5}
    assert proposal.history_policy == "current_plus_history"
    assert proposal.call_id == "call-1"
    assert proposal.parse_error is None
    assert "max_tokens" not in rnd.calls[0][1]
    prompt = rnd.calls[0][0][0]["content"]
    assert "unknown-industrial-task" not in prompt
    assert "row-0" not in prompt
    assert '"feature_count": 2' in prompt


@pytest.mark.parametrize(
    "response",
    [
        "not-json",
        '{"recipe_id":"native_current"}{"recipe_id":"native_replay"}',
        '{"recipe_id":"not-registered","parameters":{},"history_policy":"current", "hypothesis":"x","rationale":"y"}',
    ],
)
def test_invalid_first_call_falls_back_to_real_registry_training(tmp_path: Path, response: str) -> None:
    from brace_formal.agent import request_experiment_proposal

    rnd = AgentRound([response])
    profile = _profile(tmp_path, "regression")

    proposal = request_experiment_proposal(rnd, profile, RecipeRegistry())

    assert proposal.recipe_id == "native_current"
    assert proposal.history_policy == "current"
    assert proposal.parameters == {}
    assert proposal.call_id == "call-1"
    assert proposal.parse_error is not None
    assert "retain" not in proposal.recipe_id


def test_model_service_exception_returns_real_training_fallback(tmp_path: Path) -> None:
    from brace_formal.agent import request_experiment_proposal

    proposal = request_experiment_proposal(
        AgentRound([RuntimeError("host unavailable")]),
        _profile(tmp_path),
        RecipeRegistry(),
    )

    assert proposal.recipe_id == "native_current"
    assert proposal.call_id == ""
    assert "RuntimeError" in str(proposal.parse_error)


def test_agent_rejects_raw_rows_before_calling_host(tmp_path: Path) -> None:
    from brace_formal.agent import request_experiment_proposal

    rnd = AgentRound([])
    with pytest.raises(ValueError, match="aggregate-only"):
        request_experiment_proposal(
            rnd,
            _profile(tmp_path),
            RecipeRegistry(),
            history_summary={"rows": [{"id": "private", "inputs": [1.0], "answer": 1}]},
        )
    assert rnd.calls == []


def test_deployment_decision_requests_one_legal_artifact_with_same_scope_evidence() -> None:
    from brace_formal.agent import request_deployment_decision

    rnd = AgentRound(['{"artifact_id":"candidate-1","rationale":"candidate has the best same-scope macro F1"}'])
    context = {
        "metric_contract": {"metric": "macro_f1", "direction": "higher"},
        "artifact_table": [
            {"artifact_id": "parent-1", "role": "parent", "metrics": {"macro_f1": 0.7}},
            {"artifact_id": "candidate-1", "role": "candidate", "metrics": {"macro_f1": 0.8}},
        ],
        "resource_evidence": {"candidate-1": {"cpu_seconds": 0.2}},
        "artifact_roles": {"parent-1": "parent", "candidate-1": "candidate"},
    }

    decision = request_deployment_decision(
        rnd,
        context,
        legal_artifact_ids=("parent-1", "candidate-1"),
    )

    assert decision.requested_artifact_id == "candidate-1"
    assert decision.decision == "deploy"
    assert decision.call_id == "call-1"
    prompt = rnd.calls[0][0][0]["content"]
    assert '"metric_contract"' in prompt
    assert '"artifact_table"' in prompt
    assert '"resource_evidence"' in prompt


def test_deployment_invalid_artifact_falls_back_to_parent() -> None:
    from brace_formal.agent import request_deployment_decision

    rnd = AgentRound(['{"artifact_id":"invented","rationale":"choose it"}'])
    decision = request_deployment_decision(
        rnd,
        {"parent_artifact_id": "parent-1", "artifact_roles": {"parent-1": "parent"}},
        legal_artifact_ids=("parent-1",),
    )

    assert decision.requested_artifact_id == "parent-1"
    assert decision.decision == "retain"
    assert decision.parse_error is not None
