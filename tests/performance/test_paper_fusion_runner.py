from __future__ import annotations

import json
from pathlib import Path

import pytest

from brace_msi.paper_fusion_runner import (
    run_paper_fusion_sprint,
    validate_paper_fusion_output,
)


def _write_rows(path: Path, profile: str, *, validation: bool = False) -> None:
    rows = []
    if profile == "A":
        for index in range(24):
            label = "a" if index % 2 == 0 else "b"
            rows.append(
                {
                    "id": f"A-{validation}-{index}",
                    "inputs": {"features": [float(index), float(index % 3)]},
                    "answer": label,
                    "meta": {"source_batch": 2 if validation else 1, "source_index": index},
                }
            )
    elif profile == "B":
        for bearing_index in range(1, 7):
            for snapshot in range(1, 5):
                rows.append(
                    {
                        "id": f"B-{validation}-{bearing_index}-{snapshot}",
                        "inputs": {"features": [float(snapshot), float(bearing_index)]},
                        "answer": float(10 - snapshot),
                        "meta": {
                            "bearing": f"Bearing1_{bearing_index}",
                            "snapshot": snapshot,
                            "source": "fixture",
                        },
                    }
                )
    else:
        for unit in range(1, 7):
            for cycle in range(1, 5):
                rows.append(
                    {
                        "id": f"C-{validation}-{unit}-{cycle}",
                        "inputs": {"settings": [0.0], "sensors": [float(cycle)]},
                        "answer": float(10 - cycle),
                        "meta": {
                            "source_subset": "FD001",
                            "source_split": "train",
                            "unit": unit,
                            "cycle": cycle,
                            "window_size": 1,
                        },
                    }
                )
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _config(tmp_path: Path) -> Path:
    profiles = {}
    for profile in ("A", "B", "C"):
        train = tmp_path / f"{profile}-train.jsonl"
        validation = tmp_path / f"{profile}-validation.jsonl"
        _write_rows(train, profile)
        _write_rows(validation, profile, validation=True)
        profiles[profile] = {
            "train": str(train),
            "validation": str(validation),
            "baseline": 0.4 if profile == "A" else 5.0,
            "rc3": 0.45 if profile == "A" else 4.5,
        }
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "format": "brace-msi.paper-fusion-sprint.v1",
                "seed": 17,
                "n_splits": 3,
                "finalist_count": 1,
                "profiles": profiles,
                "teacher_specs": {
                    "classification": [{"family": "linear", "params": {"C": 1.0}}],
                    "regression": [{"family": "linear", "params": {"alpha": 1.0}}],
                },
            }
        ),
        encoding="utf-8",
    )
    return config


def test_development_freezes_candidates_without_opening_validation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    output = tmp_path / "run"
    for profile in ("A", "B", "C"):
        Path(json.loads(config.read_text())["profiles"][profile]["validation"]).unlink()

    first = run_paper_fusion_sprint(config, output, open_validation=False)
    resumed = run_paper_fusion_sprint(config, output, open_validation=False)

    assert first == resumed
    assert first["status"] == "candidate_frozen"
    assert first["validation_open_count"] == 0
    assert not (output / "validation-open.lock").exists()
    assert all((output / profile / "model.joblib").is_file() for profile in ("A", "B", "C"))


def test_validation_opens_once_and_machine_validator_recomputes_hashes(tmp_path: Path) -> None:
    config = _config(tmp_path)
    output = tmp_path / "run"
    run_paper_fusion_sprint(config, output, open_validation=False)

    final = run_paper_fusion_sprint(config, output, open_validation=True)
    validation = validate_paper_fusion_output(output)

    assert final["status"] == "completed"
    assert final["validation_open_count"] == 1
    assert validation["valid"] is True
    assert set(final["profiles"]) == {"A", "B", "C"}
    with pytest.raises(FileExistsError, match="already opened"):
        run_paper_fusion_sprint(config, output, open_validation=True)


def test_changed_config_cannot_resume_frozen_run(tmp_path: Path) -> None:
    config = _config(tmp_path)
    output = tmp_path / "run"
    run_paper_fusion_sprint(config, output, open_validation=False)
    payload = json.loads(config.read_text())
    payload["seed"] = 18
    config.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="configuration changed"):
        run_paper_fusion_sprint(config, output, open_validation=False)
