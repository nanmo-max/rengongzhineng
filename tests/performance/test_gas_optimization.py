from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from brace_msi.gas_optimization import (
    classification_metrics,
    create_oversampled_training_file,
    freeze_stratified_development_confirmation,
    select_development_winner,
)


CLASSES = ["A", "B", "C"]


def write_rows(path: Path, counts: dict[str, int]) -> None:
    rows = []
    index = 0
    for label, count in counts.items():
        for _ in range(count):
            index += 1
            rows.append(
                {
                    "id": f"sample-{index:03d}",
                    "inputs": {"x": [float(index), float(index + 1)]},
                    "answer": label,
                    "meta": {"source_batch": 2, "source_index": index},
                }
            )
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_stratified_split_is_deterministic_disjoint_and_frozen(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    write_rows(source, {"A": 10, "B": 7, "C": 3})
    output = tmp_path / "split"

    first = freeze_stratified_development_confirmation(
        source,
        output,
        classes=CLASSES,
        development_fraction=0.7,
        salt="fixed-salt",
        exposure="historically_exposed",
    )
    second = freeze_stratified_development_confirmation(
        source,
        output,
        classes=CLASSES,
        development_fraction=0.7,
        salt="fixed-salt",
        exposure="historically_exposed",
    )

    assert first == second
    dev = read_rows(output / "development.jsonl")
    confirm = read_rows(output / "confirmation.jsonl")
    assert {row["id"] for row in dev}.isdisjoint(row["id"] for row in confirm)
    assert len(dev) + len(confirm) == 20
    assert first["development_class_counts"] == {"A": 7, "B": 5, "C": 2}
    assert first["confirmation_class_counts"] == {"A": 3, "B": 2, "C": 1}
    assert first["exposure"] == "historically_exposed"


def test_split_refuses_changed_source_or_configuration(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    write_rows(source, {"A": 4, "B": 4, "C": 4})
    output = tmp_path / "split"
    freeze_stratified_development_confirmation(
        source, output, classes=CLASSES, development_fraction=0.5, salt="one", exposure="x"
    )

    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source changed"):
        freeze_stratified_development_confirmation(
            source, output, classes=CLASSES, development_fraction=0.5, salt="one", exposure="x"
        )


def test_oversampling_only_duplicates_target_with_unique_auditable_ids(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    write_rows(source, {"A": 3, "B": 2, "C": 1})
    output = tmp_path / "derived.jsonl"

    result = create_oversampled_training_file(
        source, output, target_class="C", multiplier=4
    )

    rows = read_rows(output)
    assert len(rows) == 9
    assert len({row["id"] for row in rows}) == 9
    assert sum(row["answer"] == "C" for row in rows) == 4
    duplicates = [row for row in rows if "__oversample_" in row["id"]]
    assert len(duplicates) == 3
    assert all(row["meta"]["derived_method"] == "deterministic_random_oversampling" for row in duplicates)
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert create_oversampled_training_file(
        source, output, target_class="C", multiplier=4
    ) == result


def test_oversampling_refuses_invalid_multiplier_or_unknown_class(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    write_rows(source, {"A": 2, "B": 2, "C": 2})
    with pytest.raises(ValueError, match="multiplier"):
        create_oversampled_training_file(source, tmp_path / "bad.jsonl", target_class="C", multiplier=0)
    with pytest.raises(ValueError, match="target class"):
        create_oversampled_training_file(source, tmp_path / "unknown.jsonl", target_class="D", multiplier=2)


def test_classification_metrics_and_selection_gate_target_class() -> None:
    metrics = classification_metrics(
        ["A", "A", "B", "B", "C", "C"],
        ["A", "B", "B", "B", "C", "A"],
        CLASSES,
    )
    assert metrics["accuracy"] == pytest.approx(4 / 6)
    assert metrics["per_class_f1"]["A"] == pytest.approx(0.5)
    candidates = [
        {"id": "high-no-target", "metrics": {"macro_f1": 0.8, "per_class_f1": {"C": 0.0}}, "cpu_seconds": 1.0},
        {"id": "valid", "metrics": {"macro_f1": 0.71, "per_class_f1": {"C": 0.3}}, "cpu_seconds": 2.0},
    ]

    selected = select_development_winner(
        candidates,
        baseline_macro_f1=0.70,
        target_class="C",
        minimum_improvement=0.005,
        minimum_target_f1=0.05,
    )

    assert selected["id"] == "valid"
