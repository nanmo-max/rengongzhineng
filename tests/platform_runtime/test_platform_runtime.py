from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from brace_msi.cli import main
import brace_msi.platform_runtime as platform_runtime
from brace_msi.platform_runtime import (
    PlatformRuntimeConfig,
    describe_runtime,
    start_round,
    submit_predictions,
)
from brace_msi.platform_simulation import run_ten_round_simulation
from brace_msi.platform_advisor import build_platform_advisor
from brace_msi.policies import Action
from brace_msi.pytrio_agent import (
    AdvisorOutcome,
    AdvisorReceipt,
    ExperimentProposal,
)


PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")
PACKAGE_NAMES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}


def _load_official_model_module(profile: str) -> ModuleType:
    path = PACKAGE_ROOT / PACKAGE_NAMES[profile] / "baselines" / "model.py"
    spec = importlib.util.spec_from_file_location(f"brace_official_model_{profile}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checkpoint_arrays(model) -> dict[str, np.ndarray]:
    return {
        **{name: value for name, value in model.params.items()},
        **{f"adam_first_{name}": value for name, value in model.first.items()},
        **{f"adam_second_{name}": value for name, value in model.second.items()},
        "mean": model.mean,
        "scale": model.scale,
    }


class RecordingAdvisor:
    def __init__(self, action: Action = Action.REPLAY_REFIT) -> None:
        self.action = action
        self.contexts = []

    def advise(self, context, trigger):
        self.contexts.append((context, trigger))
        tool = {
            Action.NOOP: "noop",
            Action.REPLAY_REFIT: "train_replay_refit",
            Action.BOUNDED_HPO: "train_bounded_hpo",
        }[self.action]
        return AdvisorOutcome(
            proposal=ExperimentProposal(
                schema_version="brace-msi.experiment-proposal.v1",
                action=self.action,
                tool=tool,
                rationale="bounded test proposal",
                parameters={"epochs": 2, "learning_rate": 0.003},
                max_cpu_seconds=30.0,
                max_candidates=1,
                stop_conditions=("budget_exhausted",),
            ),
            source="pytrio",
            receipt=AdvisorReceipt(
                status="accepted",
                triggered=True,
                trigger_reasons=trigger.reasons,
                attempts=1,
                error_categories=(),
                total_input_tokens=120,
                total_output_tokens=40,
                total_latency_seconds=0.25,
            ),
        )


def _write_parent(
    path: Path, *, task: str = "classification", profile: str = "X"
) -> None:
    hidden = 2
    features = 2
    classes = ["cold", "hot"] if task == "classification" else []
    outputs = len(classes) if classes else 1
    params = {
        "w1": np.zeros((features, hidden), dtype=np.float64),
        "b1": np.zeros(hidden, dtype=np.float64),
        "w2": np.zeros((hidden, outputs), dtype=np.float64),
        "b2": np.zeros(outputs, dtype=np.float64),
    }
    meta = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": profile,
        "task": task,
        "paths": [
            '[["key","features"],["index",0]]',
            '[["key","features"],["index",1]]',
        ],
        "classes": classes,
        "hidden": hidden,
        "seed": 42,
        "epochs": 20,
        "steps": 80,
        "learning_rate": 0.01,
        "batch_size": 4,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 5.0 if task == "regression" else 0.0,
        "target_scale": 5.0 if task == "regression" else 1.0,
    }
    np.savez(
        path,
        **params,
        **{f"adam_first_{key}": np.zeros_like(value) for key, value in params.items()},
        **{f"adam_second_{key}": np.zeros_like(value) for key, value in params.items()},
        mean=np.zeros(features, dtype=np.float64),
        scale=np.ones(features, dtype=np.float64),
        metadata=np.asarray(json.dumps(meta, sort_keys=True, separators=(",", ":"))),
    )


def _write_data(path: Path, *, task: str = "classification", count: int = 20) -> None:
    rows = []
    for index in range(count):
        hot = index >= count // 2
        answer = (10.0 if hot else 0.0) if task == "regression" else ("hot" if hot else "cold")
        rows.append(
            {
                "id": f"sample-{index:03d}",
                "inputs": {"features": [float(index), float(index % 3)]},
                "answer": answer,
            }
        )
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_sequential_policy_trains_when_arrival_performance_drops(tmp_path: Path) -> None:
    parent = tmp_path / "parent.npz"
    data = tmp_path / "data.jsonl"
    _write_parent(parent)
    _write_data(data)

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(policy_mode="sequential", min_relative_improvement=-1.0),
        arrival_evidence=platform_runtime.ArrivalEvidence(
            metrics={"accuracy": 0.55, "macro_f1": 0.40},
            previous_metrics={"accuracy": 0.80, "macro_f1": 0.75},
            sample_count=20,
            delayed_gain=None,
        ),
    )

    assert receipt["decision"]["executed_action"] == "incremental_update"
    assert receipt["decision"]["arrival_evidence"]["metrics"]["macro_f1"] == 0.40
    assert receipt["decision"]["performance_drop"] > 0.4
    assert receipt["candidate_trained"] is True


def test_portfolio_policy_trains_official_schema_recipe_without_profile_routing(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent.npz"
    data = tmp_path / "data.jsonl"
    _write_parent(parent, task="regression", profile="renamed-task")
    _write_data(data, task="regression", count=60)

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(
            policy_mode="portfolio",
            min_primary_improvement=-1e9,
            min_relative_improvement=-1.0,
            max_anchor_degradation=1e9,
        ),
    )

    assert receipt["candidate_trained"] is True
    assert receipt["decision"]["recipe"] == "soup_current_e3_alpha0.25"
    candidate = platform_runtime._NativeModel.load(tmp_path / "output" / "checkpoint.npz")
    assert candidate.meta["format"] == "contest.cpu-mlp.v1"
    assert candidate.meta["profile"] == "renamed-task"
    assert receipt["candidate_checkpoint_sha256"] is not None
    assert candidate.meta["epochs"] in {20, 23}


def test_portfolio_policy_derives_arrival_evidence_inside_native_start(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent.npz"
    data = tmp_path / "data.jsonl"
    workspace = tmp_path / "workspace"
    _write_parent(parent, task="classification", profile="unknown-classifier")
    _write_data(data, task="classification", count=80)

    receipt = start_round(
        data,
        parent,
        workspace,
        tmp_path / "output",
        PlatformRuntimeConfig(policy_mode="portfolio"),
    )

    assert receipt["arrival_metrics"] == receipt["decision"]["arrival_evidence"]["metrics"]
    assert receipt["decision"]["portfolio_plan"]["primary_recipe"] == (
        "soup_current_e3_alpha0.25"
    )
    if receipt["deployed"]:
        assert (workspace / "shadow-predecessor.npz").is_file()


def test_sequential_policy_retains_when_arrival_is_stable_and_delayed_gain_positive(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent.npz"
    data = tmp_path / "data.jsonl"
    _write_parent(parent)
    _write_data(data)

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(policy_mode="sequential"),
        arrival_evidence=platform_runtime.ArrivalEvidence(
            metrics={"accuracy": 0.80, "macro_f1": 0.70},
            previous_metrics={"accuracy": 0.79, "macro_f1": 0.69},
            sample_count=20,
            delayed_gain=0.02,
        ),
    )

    assert receipt["decision"]["executed_action"] == "noop"
    assert receipt["decision"]["outcome"] == "retain"
    assert receipt["candidate_trained"] is False


def test_sequential_policy_rolls_back_direct_predecessor_after_negative_delayed_gain(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent.npz"
    predecessor = tmp_path / "predecessor.npz"
    predecessor_source = tmp_path / "predecessor-source.npz"
    data = tmp_path / "data.jsonl"
    _write_parent(parent)
    _write_parent(predecessor_source)
    predecessor_model = platform_runtime._NativeModel.load(predecessor_source)
    predecessor_model.params["b2"][0] = 1.0
    predecessor_model.save(predecessor)
    _write_data(data)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "state.json").write_text(
        json.dumps(
            {
                "format": "brace-msi.platform-state.v1",
                "rounds": [
                    {
                        "round_index": 1,
                        "checkpoint_sha256": platform_runtime._sha256(parent),
                        "parent_checkpoint_sha256": platform_runtime._sha256(predecessor),
                        "candidate_trained": True,
                        "deployed": True,
                        "decision": {"executed_action": "incremental_update"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    receipt = start_round(
        data,
        parent,
        workspace,
        tmp_path / "output",
        PlatformRuntimeConfig(policy_mode="sequential"),
        arrival_evidence=platform_runtime.ArrivalEvidence(
            metrics={"accuracy": 0.50, "macro_f1": 0.40},
            previous_metrics={"accuracy": 0.50, "macro_f1": 0.40},
            sample_count=20,
            delayed_gain=-0.20,
        ),
        rollback_checkpoint=predecessor,
    )

    assert receipt["decision"]["executed_action"] == "rollback"
    assert receipt["decision"]["outcome"] == "rollback"
    assert receipt["candidate_trained"] is False
    assert receipt["deployed"] is True
    assert receipt["gate_reason"] == "negative_delayed_gain_rollback"
    assert receipt["checkpoint_sha256"] == platform_runtime._sha256(predecessor)


def test_sequential_policy_rejects_rollback_that_is_not_the_direct_predecessor(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent.npz"
    direct_predecessor = tmp_path / "direct-predecessor.npz"
    unrelated = tmp_path / "unrelated.npz"
    unrelated_source = tmp_path / "unrelated-source.npz"
    data = tmp_path / "data.jsonl"
    _write_parent(parent)
    _write_parent(direct_predecessor)
    _write_parent(unrelated_source)
    unrelated_model = platform_runtime._NativeModel.load(unrelated_source)
    unrelated_model.params["b2"][0] = 2.0
    unrelated_model.save(unrelated)
    _write_data(data)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "state.json").write_text(
        json.dumps(
            {
                "format": "brace-msi.platform-state.v1",
                "rounds": [
                    {
                        "checkpoint_sha256": platform_runtime._sha256(parent),
                        "parent_checkpoint_sha256": platform_runtime._sha256(
                            direct_predecessor
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="direct predecessor"):
        start_round(
            data,
            parent,
            workspace,
            tmp_path / "output",
            PlatformRuntimeConfig(policy_mode="sequential"),
            arrival_evidence=platform_runtime.ArrivalEvidence(
                metrics={"accuracy": 0.50, "macro_f1": 0.40},
                previous_metrics={"accuracy": 0.50, "macro_f1": 0.40},
                sample_count=20,
                delayed_gain=-0.20,
            ),
            rollback_checkpoint=unrelated,
        )


@pytest.mark.parametrize("profile", ["A", "B", "C"])
def test_native_fit_exactly_matches_official_model_state(profile: str) -> None:
    package = PACKAGE_ROOT / PACKAGE_NAMES[profile]
    checkpoint = package / "checkpoint.npz"
    native = platform_runtime._NativeModel.load(checkpoint)
    batch = platform_runtime._read_rows(
        package / "public" / "train.jsonl", native, require_answers=True
    )
    official_module = _load_official_model_module(profile)
    official = official_module.Model.load(checkpoint)

    native_losses = native.fit(batch["x"], batch["y"], 1)
    official_losses = official.fit(batch["x"], batch["y"], 1)

    np.testing.assert_array_equal(native_losses, official_losses)
    assert native.meta == official.meta
    for name, expected in _checkpoint_arrays(official).items():
        np.testing.assert_array_equal(_checkpoint_arrays(native)[name], expected)
    np.testing.assert_array_equal(native.predict_raw(batch["x"]), official.predict(batch["x"]))


@pytest.mark.parametrize("profile", ["A", "B", "C"])
def test_native_split_resume_exactly_matches_continuous_two_epochs(profile: str) -> None:
    package = PACKAGE_ROOT / PACKAGE_NAMES[profile]
    checkpoint = package / "checkpoint.npz"
    continuous = platform_runtime._NativeModel.load(checkpoint)
    split = platform_runtime._NativeModel.load(checkpoint)
    batch = platform_runtime._read_rows(
        package / "public" / "train.jsonl", continuous, require_answers=True
    )

    continuous.fit(batch["x"], batch["y"], 2)
    split.fit(batch["x"], batch["y"], 1)
    split.fit(batch["x"], batch["y"], 1)

    assert continuous.meta == split.meta
    for name, expected in _checkpoint_arrays(continuous).items():
        np.testing.assert_array_equal(_checkpoint_arrays(split)[name], expected)


def test_native_rejects_negative_adam_second_moment(tmp_path: Path) -> None:
    source = PACKAGE_ROOT / PACKAGE_NAMES["A"] / "checkpoint.npz"
    with np.load(source, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    arrays["adam_second_w1"][0, 0] = -1.0
    invalid = tmp_path / "invalid-negative-second-moment.npz"
    np.savez(invalid, **arrays)

    with pytest.raises(ValueError, match="Adam second moment"):
        platform_runtime._NativeModel.load(invalid)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda metadata: metadata.update(device="gpu"), "unsupported parent checkpoint"),
        (lambda metadata: metadata.update(batch_size=0), "checkpoint architecture"),
        (lambda metadata: metadata.update(parameter_count=1), "parameter count"),
        (lambda metadata: metadata.update(learning_rate=0.0), "optimizer/scaler"),
    ],
)
def test_native_rejects_metadata_the_official_model_rejects(
    tmp_path: Path, mutation, message: str
) -> None:
    source = PACKAGE_ROOT / PACKAGE_NAMES["A"] / "checkpoint.npz"
    with np.load(source, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    metadata = json.loads(str(arrays["metadata"].item()))
    mutation(metadata)
    arrays["metadata"] = np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":")))
    invalid = tmp_path / f"invalid-{message.replace('/', '-')}.npz"
    np.savez(invalid, **arrays)

    with pytest.raises(ValueError, match=message):
        platform_runtime._NativeModel.load(invalid)


def test_describe_declares_native_mount_contract_without_package_root() -> None:
    description = describe_runtime()

    assert description["data_root"] == "/data"
    assert description["parent_checkpoint"] == "/previous/checkpoint.npz"
    assert description["workspace_root"] == "/workspace"
    assert description["output_root"] == "/output"
    assert "package_root" not in description
    assert description["checkpoint_format"] == "contest.cpu-mlp.v1"


def test_start_round_continues_parent_without_official_package_tree(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    _write_data(data)
    _write_parent(parent)

    receipt = start_round(
        data,
        parent,
        workspace,
        output,
        PlatformRuntimeConfig(
            epochs=1,
            min_primary_improvement=-1.0,
            min_relative_improvement=-1.0,
        ),
    )

    assert receipt["status"] == "completed"
    assert receipt["round_index"] == 1
    assert receipt["candidate_trained"] is True
    assert receipt["parent_loaded"] is True
    assert receipt["deployed"] is True
    assert (output / "checkpoint.npz").is_file()
    assert (output / "training.json").is_file()
    assert (workspace / "state.json").is_file()
    with np.load(output / "checkpoint.npz", allow_pickle=False) as child:
        metadata = json.loads(str(child["metadata"].item()))
    assert metadata["epochs"] == 21
    assert metadata["steps"] > 80
    assert receipt["parent_checkpoint_sha256"] != receipt["checkpoint_sha256"]
    assert not (tmp_path / "baseline-info.json").exists()
    assert not (tmp_path / "baselines").exists()


def test_partitioned_round_never_trains_or_builds_buffers_from_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    update = tmp_path / "update.jsonl"
    gate = tmp_path / "gate.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_parent(parent)
    _write_data(update, count=20)
    gate_rows = []
    for index in range(6):
        gate_rows.append(
            {
                "id": f"gate-{index:03d}",
                "inputs": {"features": [9999.0 + index, 9999.0]},
                "answer": "cold" if index < 3 else "hot",
            }
        )
    gate.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in gate_rows),
        encoding="utf-8",
    )
    observed_training: list[np.ndarray] = []
    original_fit = platform_runtime._NativeModel.fit

    def recording_fit(model, values: np.ndarray, targets: np.ndarray, epochs: int):
        observed_training.append(values.copy())
        return original_fit(model, values, targets, epochs)

    monkeypatch.setattr(platform_runtime._NativeModel, "fit", recording_fit)

    receipt = start_round(
        update,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(min_primary_improvement=-1.0, min_relative_improvement=-1.0),
        gate_data_path=gate,
    )

    assert receipt["partition_mode"] == "explicit_update_gate"
    assert receipt["feedback_update_sample_count"] == 20
    assert receipt["gate_count"] == 6
    assert observed_training and float(observed_training[0].max()) < 9999.0
    with np.load(tmp_path / "workspace" / "anchor.npz", allow_pickle=False) as anchor:
        assert float(anchor["x"].max()) < 9999.0
    with np.load(tmp_path / "workspace" / "replay.npz", allow_pickle=False) as replay:
        assert float(replay["x"].max()) < 9999.0


def test_start_round_accepts_existing_empty_output_mount(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    output = tmp_path / "output"
    output.mkdir()
    _write_data(data)
    _write_parent(parent)

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        output,
        PlatformRuntimeConfig(
            min_primary_improvement=-1.0,
            min_relative_improvement=-1.0,
        ),
    )

    assert receipt["status"] == "completed"
    assert (output / "checkpoint.npz").is_file()


def test_start_round_refuses_nonempty_output_mount(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    output = tmp_path / "output"
    output.mkdir()
    (output / "foreign.txt").write_text("do not overwrite", encoding="utf-8")
    _write_data(data)
    _write_parent(parent)

    with pytest.raises(FileExistsError, match="empty"):
        start_round(data, parent, tmp_path / "workspace", output)


def test_start_round_stages_inside_existing_output_mount_to_avoid_cross_device_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    workspace = tmp_path / "workspace"
    output_parent = tmp_path / "read-only-root"
    output = output_parent / "output"
    output.mkdir(parents=True)
    _write_data(data)
    _write_parent(parent)
    original = platform_runtime.tempfile.mkdtemp

    def checked_mkdtemp(*, prefix: str, dir: Path) -> str:
        assert Path(dir).resolve() == output.resolve()
        return original(prefix=prefix, dir=dir)

    monkeypatch.setattr(platform_runtime.tempfile, "mkdtemp", checked_mkdtemp)

    receipt = start_round(
        data,
        parent,
        workspace,
        output,
        PlatformRuntimeConfig(
            min_primary_improvement=-1.0,
            min_relative_improvement=-1.0,
        ),
    )
    assert receipt["status"] == "completed"


def test_submit_predictions_uses_checkpoint_schema_and_never_requires_answers(tmp_path: Path) -> None:
    parent = tmp_path / "checkpoint.npz"
    requests = tmp_path / "requests.jsonl"
    output = tmp_path / "predictions.jsonl"
    _write_parent(parent)
    requests.write_text(
        json.dumps({"id": "q-1", "inputs": {"features": [1.0, 2.0]}}) + "\n",
        encoding="utf-8",
    )

    receipt = submit_predictions(parent, requests, output)

    assert receipt == {"status": "completed", "sample_count": 1, "task": "classification"}
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["id"] == "q-1"
    assert [item["label"] for item in row["outputs"]] == ["cold", "hot"]
    assert sum(item["score"] for item in row["outputs"]) == pytest.approx(1.0)


def test_second_round_uses_platform_parent_and_appends_atomic_history(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    first_parent = tmp_path / "checkpoint.npz"
    workspace = tmp_path / "workspace"
    _write_data(data, task="regression")
    _write_parent(first_parent, task="regression")

    first_output = tmp_path / "round-1"
    first = start_round(
        data,
        first_parent,
        workspace,
        first_output,
        PlatformRuntimeConfig(
            epochs=1,
            min_primary_improvement=-1e9,
            min_relative_improvement=-1.0,
        ),
    )
    second_output = tmp_path / "round-2"
    second = start_round(
        data,
        first_output / "checkpoint.npz",
        workspace,
        second_output,
        PlatformRuntimeConfig(
            epochs=1,
            min_primary_improvement=-1e9,
            min_relative_improvement=-1.0,
        ),
    )

    assert first["round_index"] == 1
    assert second["round_index"] == 2
    assert second["parent_checkpoint_sha256"] == first["checkpoint_sha256"]
    assert first["anchor_count"] > 0
    assert first["replay_count"] == 0
    assert second["replay_count"] > 0
    assert second["training_sample_count"] > second["update_count"]
    assert set(second["anchor_metrics_before"]) == {"mae", "rmse"}
    assert set(second["anchor_metrics_candidate"]) == {"mae", "rmse"}
    assert "anchor_degradation" in second
    assert "relative_improvement" in second
    assert (workspace / "anchor.npz").is_file()
    assert (workspace / "replay.npz").is_file()
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    assert [row["round_index"] for row in state["rounds"]] == [1, 2]
    assert (workspace / "public-spool.jsonl").read_text(encoding="utf-8").count("\n") == 2


def test_start_fails_closed_when_parent_schema_does_not_match_data(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data)
    _write_parent(parent)
    rows = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines()]
    rows[0]["inputs"]["features"].append(99.0)
    data.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="feature schema"):
        start_round(
            data,
            parent,
            tmp_path / "workspace",
            tmp_path / "output",
            PlatformRuntimeConfig(),
        )


def test_cli_exposes_describe_start_and_submit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    predictions = tmp_path / "predictions.jsonl"
    _write_data(data)
    _write_parent(parent)

    assert main(["describe"]) == 0
    description = json.loads(capsys.readouterr().out)
    assert description["format"] == "brace-msi.platform-native.v1"

    assert main(
        [
            "start",
            "--data",
            str(data),
            "--previous-checkpoint",
            str(parent),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
            "--min-primary-improvement",
            "-1",
        ]
    ) == 0
    start_receipt = json.loads(capsys.readouterr().out)
    assert start_receipt["round_index"] == 1

    requests = tmp_path / "requests.jsonl"
    requests.write_text(
        json.dumps({"id": "q-1", "inputs": {"features": [1.0, 2.0]}}) + "\n",
        encoding="utf-8",
    )
    assert main(
        [
            "submit",
            "--checkpoint",
            str(output / "checkpoint.npz"),
            "--requests",
            str(requests),
            "--output",
            str(predictions),
        ]
    ) == 0
    submit_receipt = json.loads(capsys.readouterr().out)
    assert submit_receipt["sample_count"] == 1
    assert predictions.is_file()


def test_ten_round_simulation_preserves_parent_chain_and_ten_real_candidates(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data.jsonl"
    validation = tmp_path / "validation.jsonl"
    parent = tmp_path / "checkpoint.npz"
    run_root = tmp_path / "simulation"
    _write_data(data, count=100)
    _write_data(validation, count=20)
    _write_parent(parent)

    summary = run_ten_round_simulation(
        data,
        parent,
        run_root,
        prediction_data_path=validation,
        config=PlatformRuntimeConfig(
            epochs=1,
            min_primary_improvement=-1.0,
            min_relative_improvement=-1.0,
            max_training_rounds=10,
        ),
        export_swanlab=False,
    )

    assert summary["status"] == "completed"
    assert summary["round_count"] == 10
    assert summary["candidate_count"] == 10
    assert summary["noop_count"] == 0
    assert summary["parent_chain_valid"] is True
    assert (run_root / "round-10" / "checkpoint.npz").is_file()
    assert (run_root / "predictions.jsonl").is_file()
    assert summary["prediction_sample_count"] == 20
    assert set(summary["initial_metrics"]) == {"accuracy", "macro_f1"}
    assert set(summary["final_metrics"]) == {"accuracy", "macro_f1"}
    state = json.loads((run_root / "workspace" / "state.json").read_text(encoding="utf-8"))
    assert len(state["rounds"]) == 10


def test_formal_runtime_defaults_to_real_candidate_in_all_ten_rounds() -> None:
    assert PlatformRuntimeConfig().max_training_rounds == 10
    assert PlatformRuntimeConfig().max_anchor_degradation == 0.0
    assert PlatformRuntimeConfig().min_relative_improvement == 0.05


def test_container_defaults_to_native_start_command() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["python3", "-m", "brace_msi"]' in dockerfile
    assert 'CMD ["start"]' in dockerfile
    assert 'ENV BRACE_ADVISOR=pytrio' in dockerfile
    assert 'BRACE_POLICY_MODE=portfolio' in dockerfile
    assert 'BRACE_PROTOCOL_PROFILES=' not in dockerfile
    assert 'BRACE_MAX_REPLAY_SAMPLES=100000' in dockerfile


def test_release_version_matches_competitive_candidate() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.8.0rc1"' in pyproject


def test_pytrio_advice_is_bounded_and_recorded_without_bypassing_gate(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    advisor = RecordingAdvisor()
    _write_data(data, count=60)
    _write_parent(parent)

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(
            epochs=1,
            min_primary_improvement=1.0,
            min_relative_improvement=1.0,
        ),
        advisor=advisor,
    )

    assert len(advisor.contexts) == 1
    assert receipt["decision"]["source"] == "pytrio"
    assert receipt["decision"]["proposed_action"] == "replay_refit"
    assert receipt["decision"]["executed_action"] == "incremental_update"
    assert receipt["decision"]["proposal_accepted"] is True
    assert receipt["epochs"] == 1
    assert receipt["learning_rate"] == pytest.approx(0.01)
    assert set(receipt["decision"]["policy_constraints_applied"]) == {
        "action",
        "epochs",
        "learning_rate",
    }
    assert receipt["input_tokens"] == 120
    assert receipt["output_tokens"] == 40
    assert receipt["deployed"] is False


def test_unsupported_advisor_action_falls_back_to_safe_real_candidate(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, count=60)
    _write_parent(parent)

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(min_primary_improvement=-1.0, min_relative_improvement=-1.0),
        advisor=RecordingAdvisor(Action.BOUNDED_HPO),
    )

    assert receipt["candidate_trained"] is True
    assert receipt["decision"]["proposed_action"] == "bounded_hpo"
    assert receipt["decision"]["proposal_accepted"] is False
    assert receipt["decision"]["executed_action"] == "incremental_update"
    assert receipt["decision"]["fallback_reason"] == "unsupported_platform_action"


def test_all_ten_rounds_have_decision_and_execution_receipts(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    validation = tmp_path / "validation.jsonl"
    parent = tmp_path / "checkpoint.npz"
    advisor = RecordingAdvisor()
    _write_data(data, count=100)
    _write_data(validation, count=20)
    _write_parent(parent)

    summary = run_ten_round_simulation(
        data,
        parent,
        tmp_path / "simulation",
        prediction_data_path=validation,
        config=PlatformRuntimeConfig(
            min_primary_improvement=-1.0,
            min_relative_improvement=-1.0,
        ),
        export_swanlab=False,
        advisor=advisor,
    )

    assert len(advisor.contexts) == 10
    assert summary["round_count"] == 10
    assert summary["decision_count"] == 10
    assert summary["candidate_count"] == 10
    assert summary["complete_ten_rounds"] is True
    assert summary["input_tokens"] == 1200
    assert summary["output_tokens"] == 400
    assert [row["round_index"] for row in summary["rounds"]] == list(range(1, 11))
    assert all("decision" in row for row in summary["rounds"])
    assert all(row["candidate_trained"] for row in summary["rounds"])


def test_competitive_mode_spreads_b_schedule_across_stream_then_retains(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    validation = tmp_path / "validation.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, task="regression", count=100)
    _write_data(validation, task="regression", count=20)
    _write_parent(parent, task="regression", profile="B")

    summary = run_ten_round_simulation(
        data,
        parent,
        tmp_path / "simulation",
        prediction_data_path=validation,
        config=PlatformRuntimeConfig(
            policy_mode="competitive",
            max_training_rounds=3,
            min_primary_improvement=-1e9,
            min_relative_improvement=-1.0,
            max_anchor_degradation=1e9,
        ),
        export_swanlab=False,
    )

    assert summary["complete_ten_rounds"] is True
    assert summary["candidate_count"] == 3
    assert summary["noop_count"] == 7
    trained = [row for row in summary["rounds"] if row["candidate_trained"]]
    assert [row["round_index"] for row in trained] == [1, 5, 9]
    assert [row["epochs"] for row in trained] == [1, 1, 5]
    assert [row["learning_rate"] for row in trained] == pytest.approx(
        [0.01, 0.003, 0.03]
    )
    assert all(
        row["decision"]["executed_action"] == "noop"
        and row["decision"]["outcome"] == "retain"
        and not row["candidate_trained"]
        for row in summary["rounds"]
        if row["round_index"] not in {1, 5, 9}
    )


def test_competitive_gate_accepts_small_safe_c_gain() -> None:
    result = platform_runtime._competitive_gate(
        profile="C",
        task="regression",
        before={"rmse": 50.0, "mae": 35.0},
        candidate={"rmse": 49.5, "mae": 34.8},
        anchor_before={"rmse": 40.0, "mae": 30.0},
        anchor_candidate={"rmse": 40.4, "mae": 30.2},
    )

    assert result.accepted is True
    assert result.relative_improvement == pytest.approx(0.01)
    assert result.relative_anchor_degradation == pytest.approx(0.01)
    assert result.reason == "competitive_gate_passed"


def test_competitive_first_round_trains_but_cannot_deploy_without_history(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, task="regression", count=60)
    _write_parent(parent, task="regression", profile="B")

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=3),
    )

    assert receipt["candidate_trained"] is True
    assert receipt["deployed"] is False
    assert receipt["gate_reason"] == "insufficient_history_for_deployment"


def test_competitive_gate_rejects_regression_secondary_metric_loss() -> None:
    result = platform_runtime._competitive_gate(
        profile="B",
        task="regression",
        before={"rmse": 100.0, "mae": 50.0},
        candidate={"rmse": 95.0, "mae": 51.0},
        anchor_before={"rmse": 100.0, "mae": 50.0},
        anchor_candidate={"rmse": 100.5, "mae": 50.2},
    )

    assert result.accepted is False
    assert result.reason == "secondary_metric_regressed"


def test_competitive_gate_rejects_historical_replay_regression() -> None:
    result = platform_runtime._competitive_gate(
        profile="C",
        task="regression",
        before={"rmse": 50.0, "mae": 35.0},
        candidate={"rmse": 49.0, "mae": 34.5},
        anchor_before={"rmse": 40.0, "mae": 30.0},
        anchor_candidate={"rmse": 40.2, "mae": 30.1},
        replay_before={"rmse": 45.0, "mae": 32.0},
        replay_candidate={"rmse": 47.0, "mae": 33.0},
    )

    assert result.accepted is False
    assert result.reason == "replay_history_regressed"


def test_competitive_gate_accepts_current_tie_with_safe_replay_gain() -> None:
    result = platform_runtime._competitive_gate(
        profile="A",
        task="classification",
        before={"macro_f1": 1.0, "accuracy": 1.0},
        candidate={"macro_f1": 1.0, "accuracy": 1.0},
        anchor_before={"macro_f1": 0.95, "accuracy": 0.97},
        anchor_candidate={"macro_f1": 0.95, "accuracy": 0.97},
        replay_before={"macro_f1": 0.78, "accuracy": 0.96},
        replay_candidate={"macro_f1": 0.98, "accuracy": 0.99},
    )

    assert result.accepted is True
    assert result.reason == "safe_replay_gain"


def test_competitive_gate_accepts_small_mae_tradeoff_when_history_improves() -> None:
    result = platform_runtime._competitive_gate(
        profile="C",
        task="regression",
        before={"rmse": 50.0, "mae": 40.0},
        candidate={"rmse": 49.9, "mae": 40.2},
        anchor_before={"rmse": 45.0, "mae": 35.0},
        anchor_candidate={"rmse": 44.0, "mae": 34.0},
        replay_before={"rmse": 52.0, "mae": 39.0},
        replay_candidate={"rmse": 51.0, "mae": 38.0},
    )

    assert result.accepted is True
    assert result.reason == "safe_replay_gain"


def test_pytrio_noop_is_recorded_as_retain_without_training(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, count=60)
    _write_parent(parent, profile="A")

    first = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "round-1",
        PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=3),
    )
    receipt = start_round(
        data,
        tmp_path / "round-1" / "checkpoint.npz",
        tmp_path / "workspace",
        tmp_path / "round-2",
        PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=3),
        advisor=RecordingAdvisor(Action.NOOP),
    )

    assert first["candidate_trained"] is True
    assert receipt["decision"]["source"] == "pytrio"
    assert receipt["decision"]["outcome"] == "retain"
    assert receipt["candidate_trained"] is False
    assert receipt["deployed"] is False
    assert receipt["checkpoint_sha256"] == receipt["parent_checkpoint_sha256"]


def test_pytrio_cannot_escape_frozen_competitive_candidate_schedule(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, count=60)
    _write_parent(parent, profile="A")

    first = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "round-1",
        PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=3),
    )
    second = start_round(
        data,
        tmp_path / "round-1" / "checkpoint.npz",
        tmp_path / "workspace",
        tmp_path / "round-2",
        PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=3),
        advisor=RecordingAdvisor(Action.REPLAY_REFIT),
    )

    assert first["candidate_trained"] is True
    assert second["candidate_trained"] is False
    assert second["decision"]["executed_action"] == "noop"
    assert second["decision"]["proposal_accepted"] is False
    assert second["decision"]["fallback_reason"] == "outside_frozen_candidate_schedule"


def test_pytrio_training_intent_cannot_override_frozen_action_or_parameters(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, count=60)
    _write_parent(parent, profile="A")

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "round-1",
        PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=3),
        advisor=RecordingAdvisor(Action.REPLAY_REFIT),
    )

    assert receipt["candidate_trained"] is True
    assert receipt["decision"]["source"] == "pytrio"
    assert receipt["decision"]["proposed_action"] == "replay_refit"
    assert receipt["decision"]["executed_action"] == "incremental_update"
    assert receipt["epochs"] == 1
    assert receipt["learning_rate"] == pytest.approx(0.01)
    assert set(receipt["decision"]["policy_constraints_applied"]) == {
        "action",
        "epochs",
        "learning_rate",
    }


def test_pytrio_noop_cannot_cancel_frozen_candidate_round(tmp_path: Path) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, count=60)
    _write_parent(parent, profile="A")

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "round-1",
        PlatformRuntimeConfig(policy_mode="competitive", max_training_rounds=3),
        advisor=RecordingAdvisor(Action.NOOP),
    )

    assert receipt["candidate_trained"] is True
    assert receipt["decision"]["source"] == "deterministic_policy"
    assert receipt["decision"]["proposed_action"] == "noop"
    assert receipt["decision"]["executed_action"] == "incremental_update"
    assert receipt["decision"]["proposal_accepted"] is False
    assert receipt["decision"]["fallback_reason"] == "frozen_candidate_required"


def test_competitive_mode_can_reuse_verified_protocol_for_declared_profile(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, task="regression", count=100)
    _write_parent(parent, task="regression", profile="B")

    routed = run_ten_round_simulation(
        data,
        parent,
        tmp_path / "routed",
        prediction_data_path=data,
        config=PlatformRuntimeConfig(
            policy_mode="competitive",
            protocol_profiles=("B",),
            min_relative_improvement=0.05,
        ),
        export_swanlab=False,
    )
    legacy = run_ten_round_simulation(
        data,
        parent,
        tmp_path / "legacy",
        prediction_data_path=data,
        config=PlatformRuntimeConfig(
            policy_mode="protocol",
            min_relative_improvement=0.05,
        ),
        export_swanlab=False,
    )

    assert routed["candidate_count"] == legacy["candidate_count"] == 10
    assert routed["accepted_count"] == legacy["accepted_count"]
    assert routed["final_metrics"] == legacy["final_metrics"]
    assert routed["final_checkpoint_sha256"] == legacy["final_checkpoint_sha256"]


@pytest.mark.parametrize(
    ("profile", "task", "expected_candidates"),
    (("A", "classification", 3), ("B", "regression", 10), ("C", "regression", 3)),
)
def test_pytrio_training_intents_preserve_frozen_release_policy(
    tmp_path: Path, profile: str, task: str, expected_candidates: int
) -> None:
    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, task=task, count=100)
    _write_parent(parent, task=task, profile=profile)
    config = PlatformRuntimeConfig(
        policy_mode="competitive",
        protocol_profiles=("B",),
        max_training_rounds=10,
        min_primary_improvement=-1e9,
        min_relative_improvement=-1.0,
        max_anchor_degradation=1e9,
    )

    deterministic = run_ten_round_simulation(
        data,
        parent,
        tmp_path / "deterministic",
        prediction_data_path=data,
        config=config,
        export_swanlab=False,
    )
    advised = run_ten_round_simulation(
        data,
        parent,
        tmp_path / "advised",
        prediction_data_path=data,
        config=config,
        export_swanlab=False,
        advisor=RecordingAdvisor(Action.REPLAY_REFIT),
    )

    assert advised["candidate_count"] == deterministic["candidate_count"] == expected_candidates
    assert advised["accepted_count"] == deterministic["accepted_count"]
    assert advised["final_metrics"] == deterministic["final_metrics"]
    assert advised["final_checkpoint_sha256"] == deterministic["final_checkpoint_sha256"]


def test_pytrio_failure_retains_without_training(tmp_path: Path) -> None:
    class FailingTransport:
        def sample(self, prompt: str, **kwargs: object):
            raise TimeoutError("offline")

    data = tmp_path / "data.jsonl"
    parent = tmp_path / "checkpoint.npz"
    _write_data(data, count=60)
    _write_parent(parent, profile="A")

    receipt = start_round(
        data,
        parent,
        tmp_path / "workspace",
        tmp_path / "output",
        PlatformRuntimeConfig(policy_mode="competitive"),
        advisor=build_platform_advisor(transport=FailingTransport()),
    )

    assert receipt["decision"]["advisor_source"] == "deterministic_recovery"
    assert receipt["decision"]["advisor_receipt"]["status"] == "fallback_after_retry"
    assert receipt["decision"]["executed_action"] == "noop"
    assert receipt["candidate_trained"] is False
    assert receipt["input_tokens"] == 0
    assert receipt["output_tokens"] == 0

