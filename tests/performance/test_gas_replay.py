from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from brace_msi.gas_replay import (
    build_replay_rows,
    convert_gas_batch,
    replay_safety_gate,
    split_feedback_rows,
)


LABELS = {1: "A", 2: "B", 3: "C"}
REAL_RAW = Path(r"C:\Users\Administrator\Desktop\官方\Dataset")
REAL_PACKAGE = Path(
    r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包\cpu-a-guide-20261110-v1\public"
)
REPLAY_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "perf_a_replay.json"


def raw_line(label: int, offset: float = 0.0) -> str:
    return " ".join(
        [str(label), *[f"{index}:{offset + index / 10}" for index in range(1, 129)]]
    )


def test_preregistered_batch_hashes_are_canonical_sha256() -> None:
    config = json.loads(REPLAY_CONFIG.read_text(encoding="utf-8"))

    assert all(
        re.fullmatch(r"[0-9a-f]{64}", value)
        for value in config["raw_batch_sha256"].values()
    )


def test_convert_batch_preserves_128_features_labels_and_identity(tmp_path: Path) -> None:
    source = tmp_path / "batch2.dat"
    source.write_text(raw_line(1) + "\n" + raw_line(2, 1.0) + "\n", encoding="utf-8")
    output = tmp_path / "batch2.jsonl"

    result = convert_gas_batch(source, output, batch_number=2, label_names=LABELS)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert result["rows"] == 2
    assert rows[0]["id"] == "gas_b02_000001"
    assert rows[1]["answer"] == "B"
    assert len(rows[0]["inputs"]["features"]) == 128
    assert rows[0]["meta"] == {"source_batch": 2, "source_index": 1}


def test_feedback_split_is_stratified_disjoint_and_deterministic(tmp_path: Path) -> None:
    rows = []
    for label in "ABC":
        for index in range(10):
            rows.append({"id": f"{label}-{index}", "inputs": {"features": [index]}, "answer": label, "meta": {}})

    first = split_feedback_rows(rows, holdout_fraction=0.2, salt="fixed")
    second = split_feedback_rows(rows, holdout_fraction=0.2, salt="fixed")

    assert first == second
    train, holdout = first
    assert len(train) == 24 and len(holdout) == 6
    assert {row["id"] for row in train}.isdisjoint(row["id"] for row in holdout)
    assert {label: sum(row["answer"] == label for row in holdout) for label in "ABC"} == {"A": 2, "B": 2, "C": 2}


def test_replay_modes_respect_capacity_and_class_balance() -> None:
    history = [
        {"id": f"A-{index}", "answer": "A"} for index in range(20)
    ] + [
        {"id": f"B-{index}", "answer": "B"} for index in range(4)
    ] + [
        {"id": f"C-{index}", "answer": "C"} for index in range(2)
    ]

    uniform = build_replay_rows(history, mode="uniform_hash", capacity=9, seed=7)
    balanced = build_replay_rows(history, mode="class_balanced_hash", capacity=9, seed=7)

    assert len(uniform) == 9
    assert len(balanced) == 8  # minority classes are never fabricated
    counts = {label: sum(row["answer"] == label for row in balanced) for label in "ABC"}
    assert counts == {"A": 3, "B": 3, "C": 2}
    assert build_replay_rows(history, mode="class_balanced_hash", capacity=9, seed=7) == balanced


def test_safety_gate_requires_current_gain_and_anchor_retention() -> None:
    assert replay_safety_gate(
        stable_current=0.4,
        candidate_current=0.5,
        stable_anchor=0.9,
        candidate_anchor=0.88,
        minimum_current_improvement=0.0,
        maximum_anchor_degradation=0.03,
    ) == (True, "current_improved_anchor_retained")
    assert replay_safety_gate(
        stable_current=0.5,
        candidate_current=0.49,
        stable_anchor=0.9,
        candidate_anchor=0.9,
        minimum_current_improvement=0.0,
        maximum_anchor_degradation=0.03,
    ) == (False, "current_holdout_not_improved")
    assert replay_safety_gate(
        stable_current=0.4,
        candidate_current=0.5,
        stable_anchor=0.9,
        candidate_anchor=0.8,
        minimum_current_improvement=0.0,
        maximum_anchor_degradation=0.03,
    ) == (False, "anchor_degradation_exceeded")


@pytest.mark.skipif(
    not REAL_RAW.is_dir() or not REAL_PACKAGE.is_dir(),
    reason="official local Gas files are unavailable",
)
def test_converter_semantically_matches_official_batch1_and_batch2(tmp_path: Path) -> None:
    labels = {
        1: "Ethanol",
        2: "Ethylene",
        3: "Ammonia",
        4: "Acetaldehyde",
        5: "Acetone",
        6: "Toluene",
    }
    for batch_number, official_name in ((1, "train.jsonl"), (2, "validation.jsonl")):
        converted = tmp_path / f"batch{batch_number}.jsonl"
        convert_gas_batch(
            REAL_RAW / f"batch{batch_number}.dat",
            converted,
            batch_number=batch_number,
            label_names=labels,
        )
        actual = [json.loads(line) for line in converted.read_text(encoding="utf-8").splitlines()]
        expected = [
            json.loads(line)
            for line in (REAL_PACKAGE / official_name).read_text(encoding="utf-8").splitlines()
        ]
        assert actual == expected
