from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
import pytest


def _write_parent(path: Path, task: str) -> None:
    paths = ['[["key","features"],["index",0]]', '[["key","features"],["index",1]]']
    classes = ["cold", "hot"] if task == "classification" else []
    outputs = len(classes) if classes else 1
    params = {
        "w1": np.asarray([[0.5, -0.2], [0.1, 0.3]], dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.full((2, outputs), 0.2, dtype=np.float64),
        "b2": np.arange(outputs, dtype=np.float64) * 0.01,
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": "unknown-task-test",
        "task": task,
        "paths": paths,
        "classes": classes,
        "hidden": 2,
        "seed": 42,
        "epochs": 1,
        "steps": 1,
        "learning_rate": 0.01,
        "batch_size": 4,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 5.0 if task == "regression" else 0.0,
        "target_scale": 5.0 if task == "regression" else 1.0,
    }
    np.savez(
        path,
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        mean=np.zeros(2),
        scale=np.ones(2),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


def _write_rows(path: Path, task: str, prefix: str) -> None:
    rows = []
    for index in range(16):
        answer = ("hot" if index >= 8 else "cold") if task == "classification" else float(index)
        rows.append(
            {
                "id": f"{prefix}-{index}",
                "inputs": {"features": [float(index), float(index % 3)]},
                "answer": answer,
            }
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class CompetitionRound:
    def __init__(
        self,
        root: Path,
        parent: Path,
        task: str,
        responses: list[object],
        *,
        round_index: int = 1,
        persisted_state: Path | None = None,
    ) -> None:
        self.root = root
        self.round_index = round_index
        self.stage_id = "unknown-stage"
        self.dataset_key = "not-A-B-or-C"
        metric = "macro_f1" if task == "classification" else "rmse"
        direction = "higher" if task == "classification" else "lower"
        self.task = {"task": task, "metric": metric, "metric_direction": direction}
        self.data = SimpleNamespace(
            train_path=str(root / "train.jsonl"),
            validation_path=str(root / "validation.jsonl"),
        )
        self.parent = SimpleNamespace(
            artifact_id=f"parent-{round_index}",
            checkpoint_sha256="sha256:" + hashlib.sha256(parent.read_bytes()).hexdigest(),
            descriptor={"checkpoint_paths": ["checkpoint.npz"], "code_paths": []},
            path=lambda relative: parent if relative == "checkpoint.npz" else None,
        )
        self.responses = list(responses)
        self.call_ids: list[str] = []
        self.model_prompts: list[str] = []
        self.submitted: dict[str, object] | None = None
        self.finished: dict[str, object] | None = None
        self.persisted_state = persisted_state
        self.saved_state: Path | None = None

    def history(self):
        return []

    def model(self, messages, **options):
        assert "max_tokens" not in options
        self.model_prompts.append(str(messages[0]["content"]))
        call_id = f"call-{self.round_index}-{len(self.call_ids) + 1}"
        self.call_ids.append(call_id)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return SimpleNamespace(call_id=call_id, text=json.dumps(response), response={})

    def state_workspace(self, destination):
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False)
        if self.persisted_state is not None and self.persisted_state.is_dir():
            for source in self.persisted_state.iterdir():
                if source.is_file():
                    shutil.copy2(source, destination / source.name)
        return destination

    def save_state(self, directory):
        self.saved_state = Path(directory)
        if self.persisted_state is not None:
            self.persisted_state.mkdir(parents=True, exist_ok=True)
            for source in self.saved_state.iterdir():
                if source.is_file():
                    shutil.copy2(source, self.persisted_state / source.name)
        return "sha256:" + "1" * 64

    def submit_candidate(self, directory, **kwargs):
        self.submitted = {"directory": Path(directory), **kwargs}
        return {"artifact_id": f"candidate-{self.round_index}"}

    def finish(self, **kwargs):
        self.finished = kwargs
        return {"accepted": True}


def _proposal(recipe_id: str = "native_current") -> dict[str, object]:
    policies = {
        "native_current": "current",
        "native_replay": "current_plus_history",
    }
    return {
        "recipe_id": recipe_id,
        "parameters": {},
        "history_policy": policies[recipe_id],
        "hypothesis": "the selected bounded continuation may improve the current task",
        "rationale": "use the registered parent-compatible recipe",
    }


def _decision(artifact_id: str) -> dict[str, str]:
    return {"artifact_id": artifact_id, "rationale": "choose the best same-scope legal artifact"}


def _evaluator(task: str):
    calls = 0

    def evaluate_model(model, values, targets, metric_contract=None):
        nonlocal calls
        calls += 1
        candidate = calls % 2 == 0
        if task == "classification":
            return {"accuracy": 0.85 if candidate else 0.75, "macro_f1": 0.84 if candidate else 0.74}
        return {"mae": 20.0 if candidate else 30.0, "rmse": 25.0 if candidate else 40.0}

    return evaluate_model


@pytest.mark.parametrize("task", ["classification", "regression"])
def test_unknown_task_runs_two_qwen_calls_real_candidate_and_selection(
    monkeypatch, tmp_path: Path, task: str
) -> None:
    from brace_formal.round_core import run_competition_round

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, task)
    _write_rows(tmp_path / "train.jsonl", task, "train")
    _write_rows(tmp_path / "validation.jsonl", task, "validation")
    rnd = CompetitionRound(tmp_path, parent, task, [_proposal(), _decision("candidate-1")])
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    outcome = run_competition_round(rnd, evaluator=_evaluator(task))

    assert rnd.call_ids == ["call-1-1", "call-1-2"]
    assert outcome.executed_recipe_id == "native_current"
    assert outcome.selected_artifact_id == "candidate-1"
    assert outcome.candidate_trained is True
    assert rnd.submitted is not None
    assert (rnd.submitted["directory"] / "checkpoint.npz").is_file()
    assert rnd.finished is not None
    assert rnd.finished["selected_artifact_id"] == "candidate-1"
    assert "not-A-B-or-C" not in rnd.model_prompts[0]


def test_invalid_first_call_falls_back_to_prevalidated_stable_training(monkeypatch, tmp_path: Path) -> None:
    from brace_formal.round_core import run_competition_round

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, "classification")
    _write_rows(tmp_path / "train.jsonl", "classification", "train")
    _write_rows(tmp_path / "validation.jsonl", "classification", "validation")
    rnd = CompetitionRound(tmp_path, parent, "classification", [{"ambiguous": True}, _decision("candidate-1")])
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    outcome = run_competition_round(rnd, evaluator=_evaluator("classification"))

    assert outcome.executed_recipe_id == "class_weighted_current_fast"
    assert outcome.candidate_trained is True
    record = json.loads((rnd.saved_state / "round-receipt.json").read_text(encoding="utf-8"))
    assert record["experiment_proposal"]["parse_error"]


def test_failed_requested_recipe_attempts_stable_fallback_and_records_failure(
    monkeypatch, tmp_path: Path
) -> None:
    import brace_formal.round_core as core
    from brace_formal.recipes import execute_recipe as real_execute

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, "classification")
    _write_rows(tmp_path / "train.jsonl", "classification", "train")
    _write_rows(tmp_path / "validation.jsonl", "classification", "validation")
    rnd = CompetitionRound(
        tmp_path,
        parent,
        "classification",
        [_proposal("native_replay"), _decision("candidate-1")],
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    def fail_requested(parent_model, recipe, training_batch):
        if recipe.recipe_id == "native_replay":
            raise RuntimeError("injected recipe failure")
        return real_execute(parent_model, recipe, training_batch)

    monkeypatch.setattr(core, "execute_recipe", fail_requested)
    outcome = core.run_competition_round(rnd, evaluator=_evaluator("classification"))

    assert outcome.executed_recipe_id == "class_weighted_current_fast"
    assert outcome.candidate_trained is True
    receipt = json.loads((rnd.saved_state / "round-receipt.json").read_text(encoding="utf-8"))
    assert receipt["training_failures"][0]["recipe_id"] == "native_replay"


def test_all_candidate_training_failures_still_record_second_call_and_retain_parent(
    monkeypatch, tmp_path: Path
) -> None:
    import brace_formal.round_core as core

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, "classification")
    _write_rows(tmp_path / "train.jsonl", "classification", "train")
    _write_rows(tmp_path / "validation.jsonl", "classification", "validation")
    rnd = CompetitionRound(
        tmp_path,
        parent,
        "classification",
        [_proposal(), _decision("parent-1")],
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))
    monkeypatch.setattr(
        core,
        "execute_recipe",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected training failure")),
    )

    outcome = core.run_competition_round(rnd, evaluator=_evaluator("classification"))

    assert rnd.call_ids == ["call-1-1", "call-1-2"]
    assert outcome.candidate_trained is False
    assert outcome.selected_artifact_id == "parent-1"
    assert rnd.submitted is None
    receipt = json.loads((rnd.saved_state / "round-receipt.json").read_text(encoding="utf-8"))
    assert receipt["outcome"] == "candidate_training_failed"
    assert receipt["training_failures"] == [
        {"recipe_id": "native_current", "error": "RuntimeError: injected training failure"},
        {"recipe_id": "class_weighted_current_fast", "error": "RuntimeError: injected training failure"},
    ]


def test_invalid_second_call_falls_back_to_parent(monkeypatch, tmp_path: Path) -> None:
    from brace_formal.round_core import run_competition_round

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, "classification")
    _write_rows(tmp_path / "train.jsonl", "classification", "train")
    _write_rows(tmp_path / "validation.jsonl", "classification", "validation")
    rnd = CompetitionRound(tmp_path, parent, "classification", [_proposal(), {"artifact_id": "illegal"}])
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    outcome = run_competition_round(rnd, evaluator=_evaluator("classification"))

    assert outcome.requested_artifact_id == "parent-1"
    assert outcome.selected_artifact_id == "candidate-1"
    assert outcome.request_honored is False
    # The model-call parser safely requests the parent; the deterministic
    # selector still applies the objectively better same-scope candidate.


def test_qwen_metric_conflict_cannot_apply_worse_candidate(monkeypatch, tmp_path: Path) -> None:
    from brace_formal.round_core import run_competition_round

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, "regression")
    _write_rows(tmp_path / "train.jsonl", "regression", "train")
    _write_rows(tmp_path / "validation.jsonl", "regression", "validation")
    rnd = CompetitionRound(tmp_path, parent, "regression", [_proposal(), _decision("candidate-1")])
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))
    scores = iter(
        [
            {"mae": 35.0, "rmse": 52.868573},
            {"mae": 38.0, "rmse": 55.629944},
        ]
    )

    outcome = run_competition_round(rnd, evaluator=lambda *args, **kwargs: next(scores))

    assert outcome.selected_artifact_id == "parent-1"
    assert outcome.requested_artifact_id == "candidate-1"
    assert outcome.request_honored is False


def test_restored_history_is_reevaluated_on_current_scope_and_can_be_selected(
    monkeypatch, tmp_path: Path
) -> None:
    from brace_formal.round_core import run_competition_round

    parent = tmp_path / "checkpoint.npz"
    history_checkpoint = tmp_path / "history-checkpoint.npz"
    _write_parent(parent, "classification")
    _write_parent(history_checkpoint, "classification")
    _write_rows(tmp_path / "train.jsonl", "classification", "train")
    _write_rows(tmp_path / "validation.jsonl", "classification", "validation")
    rnd = CompetitionRound(
        tmp_path,
        parent,
        "classification",
        [_proposal(), _decision("history-good")],
    )
    rnd.history = lambda: [
        {"id": "history-record", "round_index": 1, "selected_artifact_id": "history-good"}
    ]

    def restore_artifact(artifact_id, destination):
        assert artifact_id == "history-good"
        destination = Path(destination)
        destination.mkdir(parents=True)
        shutil.copy2(history_checkpoint, destination / "checkpoint.npz")
        return destination

    rnd.restore_artifact = restore_artifact
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))
    scores = iter(
        [
            {"accuracy": 0.80, "macro_f1": 0.80},
            {"accuracy": 0.75, "macro_f1": 0.75},
            {"accuracy": 0.90, "macro_f1": 0.90},
        ]
    )

    outcome = run_competition_round(rnd, evaluator=lambda *args, **kwargs: next(scores))

    assert outcome.selected_artifact_id == "history-good"
    assert outcome.selected_role == "history"
    assert outcome.request_honored is True
    receipt = json.loads((rnd.saved_state / "round-receipt.json").read_text(encoding="utf-8"))
    restored = next(item for item in receipt["artifact_evaluations"] if item["role"] == "history")
    assert restored["validation_sha256"] == receipt["validation_sha256"]
    assert restored["metrics"]["macro_f1"] == 0.90


def test_round_two_replay_restores_legal_history_state(monkeypatch, tmp_path: Path) -> None:
    from brace_formal.round_core import run_competition_round

    persisted = tmp_path / "persisted-state"
    parent1 = tmp_path / "parent-1.npz"
    _write_parent(parent1, "classification")

    round1_root = tmp_path / "round-1"
    round1_root.mkdir()
    _write_rows(round1_root / "train.jsonl", "classification", "r1-train")
    _write_rows(round1_root / "validation.jsonl", "classification", "r1-validation")
    rnd1 = CompetitionRound(
        round1_root,
        parent1,
        "classification",
        [_proposal(), _decision("candidate-1")],
        persisted_state=persisted,
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work-1"))
    run_competition_round(rnd1, evaluator=_evaluator("classification"))

    parent2 = rnd1.submitted["directory"] / "checkpoint.npz"
    round2_root = tmp_path / "round-2"
    round2_root.mkdir()
    _write_rows(round2_root / "train.jsonl", "classification", "r2-train")
    _write_rows(round2_root / "validation.jsonl", "classification", "r2-validation")
    rnd2 = CompetitionRound(
        round2_root,
        parent2,
        "classification",
        [_proposal("native_replay"), _decision("candidate-2")],
        round_index=2,
        persisted_state=persisted,
    )
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work-2"))

    outcome = run_competition_round(rnd2, evaluator=_evaluator("classification"))

    assert outcome.executed_recipe_id == "native_replay"
    receipt = json.loads((rnd2.saved_state / "round-receipt.json").read_text(encoding="utf-8"))
    assert receipt["candidate_execution"]["training_samples"] == 32
    assert receipt["history"]["round_indices"] == [1, 2]


def test_interrupted_official_state_save_leaves_complete_local_receipt(
    monkeypatch, tmp_path: Path
) -> None:
    from brace_formal.round_core import run_competition_round

    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent, "classification")
    _write_rows(tmp_path / "train.jsonl", "classification", "train")
    _write_rows(tmp_path / "validation.jsonl", "classification", "validation")
    rnd = CompetitionRound(tmp_path, parent, "classification", [_proposal(), _decision("candidate-1")])
    monkeypatch.setenv("CONTEST_WORK", str(tmp_path / "work"))

    def interrupted(_directory):
        raise OSError("injected state RPC interruption")

    rnd.save_state = interrupted
    with pytest.raises(OSError, match="state RPC interruption"):
        run_competition_round(rnd, evaluator=_evaluator("classification"))

    receipts = list((tmp_path / "work").glob("dataset-*/round-*/state/round-receipt.json"))
    assert len(receipts) == 1
    receipt = receipts[0]
    assert json.loads(receipt.read_text(encoding="utf-8"))["round_index"] == 1
    assert rnd.finished is None

