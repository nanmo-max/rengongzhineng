from __future__ import annotations

import json
from pathlib import Path

import pytest
import brace_msi.official_flow_simulation as flow_simulation

from brace_msi.official_flow_simulation import (
    ScoreVault,
    StreamRound,
    TaskStreamPlan,
    build_bearing_stream_plan,
    build_engine_stream_plan,
    build_gas_stream_plan,
    materialize_stream_plan,
    run_official_flow_simulation,
)
from brace_msi.platform_runtime import PlatformRuntimeConfig
import numpy as np


LABELS = ["Ethanol", "Ethylene", "Ammonia", "Acetaldehyde", "Acetone", "Toluene"]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _gas_raw(path: Path, batch: int, rows_per_class: int = 12) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for label in range(1, 7):
        for index in range(rows_per_class):
            values = " ".join(
                f"{feature}:{batch * 1000 + label * 100 + index + feature / 1000:.6f}"
                for feature in range(1, 129)
            )
            lines.append(f"{label} {values}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_gas_uses_unseen_natural_batches_and_reserves_batch_ten(tmp_path: Path) -> None:
    parent = tmp_path / "parent.jsonl"
    _write_jsonl(
        parent,
        [
            {
                "id": "gas_b01_000001",
                "inputs": {"features": [float(index) for index in range(128)]},
                "answer": "Ethanol",
                "meta": {"source_batch": 1, "source_index": 1},
            }
        ],
    )
    raw = tmp_path / "Dataset"
    for batch in range(2, 11):
        _gas_raw(raw / f"batch{batch}.dat", batch)

    plan = build_gas_stream_plan(parent, raw)

    assert len(plan.rounds) == 10
    assert {row["meta"]["source_batch"] for round_ in plan.rounds for row in round_.rows} == set(
        range(2, 10)
    )
    assert {row["meta"]["source_batch"] for row in plan.confirmation_rows} == {10}
    assert all(set(round_.update_ids).isdisjoint(round_.gate_ids) for round_ in plan.rounds)
    assert all(set(row["answer"] for row in round_.rows) == set(LABELS) for round_ in plan.rounds)
    assert plan.audit["parent_stream_id_overlap"] == 0
    assert plan.audit["parent_confirmation_id_overlap"] == 0
    assert plan.audit["stream_confirmation_id_overlap"] == 0


def _bearing_rows(names: list[str], count: int) -> list[dict]:
    rows = []
    for bearing_index, name in enumerate(names):
        for snapshot in range(1, count + bearing_index + 1):
            rows.append(
                {
                    "id": f"{name}-{snapshot}",
                    "inputs": {"features": [float(bearing_index), float(snapshot)]},
                    "answer": count + bearing_index - snapshot,
                    "meta": {"bearing": name, "snapshot": snapshot},
                }
            )
    return rows


def test_bearing_uses_life_progress_and_keeps_future_snapshots_out(tmp_path: Path) -> None:
    parent = tmp_path / "parent.jsonl"
    validation = tmp_path / "validation.jsonl"
    parent_rows = _bearing_rows(["Seen"], 20)
    for row in parent_rows:
        row["inputs"]["features"][0] += 1000.0
    _write_jsonl(parent, parent_rows)
    rows = _bearing_rows(["Bearing1_4", "Bearing2_4", "Bearing3_4"], 30)
    _write_jsonl(validation, list(reversed(rows)))

    plan = build_bearing_stream_plan(parent, validation)

    assert len(plan.rounds) == 10
    confirmation_groups = {row["meta"]["bearing"] for row in plan.confirmation_rows}
    assert len(confirmation_groups) == 1
    stream_groups = {row["meta"]["bearing"] for round_ in plan.rounds for row in round_.rows}
    assert confirmation_groups.isdisjoint(stream_groups)
    for round_index, round_ in enumerate(plan.rounds, 1):
        for row in round_.rows:
            bearing = row["meta"]["bearing"]
            total = max(item["meta"]["snapshot"] for item in rows if item["meta"]["bearing"] == bearing)
            expected = min(9, int((row["meta"]["snapshot"] - 1) / max(1, total - 1) * 10)) + 1
            assert expected == round_index
        assert set(round_.update_groups).isdisjoint(round_.gate_groups)

    ordered = tmp_path / "ordered.jsonl"
    _write_jsonl(ordered, rows)
    reordered_plan = build_bearing_stream_plan(parent, ordered)
    assert plan.assignment_digest == reordered_plan.assignment_digest


def _engine_rows(unit_count: int, cycles: int = 3) -> list[dict]:
    rows = []
    for unit in range(1, unit_count + 1):
        for cycle in range(1, cycles + 1):
            rows.append(
                {
                    "id": f"fd001_u{unit:04d}_c{cycle:05d}",
                    "inputs": {"settings": [float(unit)], "sensors": [float(cycle)]},
                    "answer": cycles - cycle,
                    "meta": {"source_subset": "FD001", "unit": unit, "cycle": cycle},
                }
            )
    return rows


def test_engine_units_never_cross_round_gate_or_confirmation(tmp_path: Path) -> None:
    parent = tmp_path / "parent.jsonl"
    validation = tmp_path / "validation.jsonl"
    parent_rows = _engine_rows(5)
    for row in parent_rows:
        row["id"] = "parent-" + row["id"]
        row["inputs"]["settings"][0] += 1000.0
    _write_jsonl(parent, parent_rows)
    rows = _engine_rows(40)
    _write_jsonl(validation, rows)

    plan = build_engine_stream_plan(parent, validation)

    assert len(plan.rounds) == 10
    seen: set[str] = set()
    confirmation = {f"{row['meta']['source_subset']}:{row['meta']['unit']}" for row in plan.confirmation_rows}
    for round_ in plan.rounds:
        groups = set(round_.update_groups) | set(round_.gate_groups)
        assert set(round_.update_groups).isdisjoint(round_.gate_groups)
        assert groups.isdisjoint(seen)
        assert groups.isdisjoint(confirmation)
        seen.update(groups)
    assert plan.audit["parent_stream_id_overlap"] == 0
    assert plan.audit["stream_confirmation_id_overlap"] == 0

    reversed_path = tmp_path / "reversed.jsonl"
    _write_jsonl(reversed_path, list(reversed(rows)))
    assert plan.assignment_digest == build_engine_stream_plan(parent, reversed_path).assignment_digest


def test_feature_overlap_with_parent_fails_closed(tmp_path: Path) -> None:
    parent = tmp_path / "parent.jsonl"
    validation = tmp_path / "validation.jsonl"
    parent_rows = _engine_rows(1)
    for row in parent_rows:
        row["id"] = "parent-" + row["id"]
    candidate_rows = _engine_rows(40)
    candidate_rows[0]["inputs"] = parent_rows[0]["inputs"]
    _write_jsonl(parent, parent_rows)
    _write_jsonl(validation, candidate_rows)

    with pytest.raises(ValueError, match="parent.*feature"):
        build_engine_stream_plan(parent, validation)


def _write_parent_checkpoint(path: Path) -> None:
    params = {
        "w1": np.zeros((2, 2), dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.zeros((2, 2), dtype=np.float64),
        "b2": np.zeros(2, dtype=np.float64),
    }
    metadata = {
        "format": "contest.cpu-mlp.v1",
        "device": "cpu",
        "profile": "X",
        "task": "classification",
        "paths": [
            '[["key","features"],["index",0]]',
            '[["key","features"],["index",1]]',
        ],
        "classes": ["cold", "hot"],
        "hidden": 2,
        "seed": 42,
        "epochs": 1,
        "steps": 1,
        "learning_rate": 0.01,
        "batch_size": 4,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 0.0,
        "target_scale": 1.0,
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


def _small_plan() -> TaskStreamPlan:
    rounds = []
    for round_index in range(1, 11):
        rows = []
        for sample_index in range(8):
            rows.append(
                {
                    "id": f"round-{round_index:02d}-{sample_index:02d}",
                    "inputs": {"features": [float(round_index), float(sample_index)]},
                    "answer": "cold" if sample_index < 4 else "hot",
                    "meta": {"group": f"g-{round_index}-{sample_index // 2}"},
                }
            )
        rounds.append(
            StreamRound(
                index=round_index,
                rows=tuple(rows),
                update_ids=tuple(row["id"] for row in rows[:6]),
                gate_ids=tuple(row["id"] for row in rows[6:]),
                update_groups=(f"update-{round_index}",),
                gate_groups=(f"gate-{round_index}",),
                source_groups=(f"round-{round_index}",),
            )
        )
    confirmation = tuple(
        {
            "id": f"confirmation-{index}",
            "inputs": {"features": [100.0, float(index)]},
            "answer": "cold" if index < 3 else "hot",
            "meta": {"group": "confirmation"},
        }
        for index in range(6)
    )
    return TaskStreamPlan(
        profile="X",
        task="classification",
        rounds=tuple(rounds),
        confirmation_rows=confirmation,
        parent_ids=("parent",),
        source_sha256=(("synthetic", "0" * 64),),
        audit={
            "parent_stream_id_overlap": 0,
            "parent_confirmation_id_overlap": 0,
            "stream_confirmation_id_overlap": 0,
            "parent_stream_feature_overlap": 0,
            "parent_confirmation_feature_overlap": 0,
            "stream_confirmation_feature_overlap": 0,
        },
        assignment_digest="1" * 64,
    )


def test_materialized_prediction_views_never_contain_answers(tmp_path: Path) -> None:
    manifest = materialize_stream_plan(_small_plan(), tmp_path / "stream")

    assert manifest["round_count"] == 10
    first = json.loads((tmp_path / "stream" / "rounds" / "round-01" / "prediction.jsonl").read_text().splitlines()[0])
    assert "answer" not in first
    assert (tmp_path / "stream" / "rounds" / "round-01" / "update.jsonl").is_file()
    assert (tmp_path / "stream" / "rounds" / "round-01" / "gate.jsonl").is_file()


def test_score_vault_rejects_feedback_before_prediction_seal(tmp_path: Path) -> None:
    feedback = tmp_path / "feedback.jsonl"
    _write_jsonl(feedback, list(_small_plan().rounds[0].rows))
    vault = ScoreVault(tmp_path / "vault")

    with pytest.raises(ValueError, match="sealed prediction"):
        vault.score_feedback(1, feedback, task="classification", confirmation=False)


def test_official_flow_predicts_before_feedback_and_confirms_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint = tmp_path / "checkpoint.npz"
    _write_parent_checkpoint(checkpoint)
    original_submit = flow_simulation.submit_predictions
    original_start = flow_simulation.start_round
    submitted_rounds: list[int] = []

    def guarded_submit(parent: Path, request: Path, output: Path):
        request = Path(request)
        if request.parent.name.startswith("round-"):
            round_index = int(request.parent.name.split("-")[-1])
            submitted_rounds.append(round_index)
            assert not (request.parent / "feedback.jsonl").exists()
            assert not (request.parent / "update.jsonl").exists()
            assert not (request.parent / "gate.jsonl").exists()
        return original_submit(parent, request, output)

    def guarded_start(data: Path, *args, **kwargs):
        data = Path(data)
        round_index = int(data.parent.name.split("-")[-1])
        runtime_inputs = data.parents[1]
        assert sorted(path.name for path in runtime_inputs.glob("round-*")) == [
            f"round-{index:02d}" for index in range(1, round_index + 1)
        ]
        assert not (runtime_inputs / "confirmation").exists()
        return original_start(data, *args, **kwargs)

    monkeypatch.setattr(flow_simulation, "submit_predictions", guarded_submit)
    monkeypatch.setattr(flow_simulation, "start_round", guarded_start)

    summary = run_official_flow_simulation(
        _small_plan(),
        checkpoint,
        tmp_path / "run",
        config=PlatformRuntimeConfig(max_training_rounds=0),
        export_swanlab=False,
    )

    assert summary["format"] == "brace-msi.official-flow-simulation.v1"
    assert summary["round_count"] == 10
    assert summary["confirmation_read_count"] == 1
    assert summary["prequential_metrics_visible_to_policy"] is False
    assert all(row["prediction_sealed_before_feedback"] for row in summary["rounds"])
    assert all(row["runtime_receipt"]["partition_mode"] == "explicit_update_gate" for row in summary["rounds"])
    assert all("prequential_metrics" not in row["runtime_receipt"] for row in summary["rounds"])
    events = [json.loads(line)["event"] for line in (tmp_path / "run" / "score-vault" / "events.jsonl").read_text().splitlines()]
    assert events[:2] == ["prediction_sealed", "feedback_scored"]
    assert events[-2:] == ["prediction_sealed", "confirmation_scored"]
    assert submitted_rounds == list(range(1, 11))
