from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from brace_msi.official_package import audit_package_root
from brace_msi.official_trainer import (
    CandidateConfig,
    CandidateValidationError,
    OfficialTrainer,
    validate_candidate_output,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")
PYTHON = Path(r"D:\anaconda3\python.exe")


@pytest.fixture(scope="module")
def audit_a():
    config = json.loads((REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8"))
    return audit_package_root(PACKAGE_ROOT, config)["A"]


def one_epoch(audit_a) -> CandidateConfig:
    return CandidateConfig(epochs=1, learning_rate=audit_a.base_learning_rate, batch_size=audit_a.base_batch_size)


def test_run_candidate_verifies_real_state_change_and_refuses_overwrite(tmp_path: Path, audit_a) -> None:
    trainer = OfficialTrainer(python_executable=PYTHON, timeout_seconds=30)
    output = tmp_path / "candidate"

    receipt = trainer.run_candidate(audit_a, audit_a.checkpoint_path, output, one_epoch(audit_a), "unit-01")

    assert receipt.parent_sha256 == audit_a.checkpoint_sha256
    assert receipt.checkpoint_sha256 != receipt.parent_sha256
    assert receipt.initial_epochs == audit_a.initial_epochs
    assert receipt.final_epochs == audit_a.initial_epochs + 1
    assert receipt.final_steps > receipt.initial_steps
    assert receipt.model_state_changed is True
    assert receipt.optimizer_state_changed is True
    assert receipt.validation_file_reads == 1
    assert receipt.validation_metric_evaluations == 2
    assert Path(receipt.output_dir, "checkpoint.npz").is_file()
    assert Path(receipt.output_dir, "candidate-receipt.json").is_file()
    with pytest.raises(FileExistsError, match="new directory"):
        trainer.run_candidate(audit_a, audit_a.checkpoint_path, output, one_epoch(audit_a), "unit-repeat")


def test_original_trainer_resume_one_plus_one_exactly_matches_two_epochs(tmp_path: Path, audit_a) -> None:
    trainer = OfficialTrainer(python_executable=PYTHON, timeout_seconds=30)
    direct = trainer.run_candidate(
        audit_a,
        audit_a.checkpoint_path,
        tmp_path / "direct-two",
        CandidateConfig(2, audit_a.base_learning_rate, audit_a.base_batch_size),
        "direct-two",
    )
    first = trainer.run_candidate(audit_a, audit_a.checkpoint_path, tmp_path / "split-one", one_epoch(audit_a), "split-one")
    resumed = trainer.run_candidate(
        audit_a,
        Path(first.output_dir) / "checkpoint.npz",
        tmp_path / "split-two",
        one_epoch(audit_a),
        "split-two",
    )

    assert direct.checkpoint_sha256 == resumed.checkpoint_sha256
    with np.load(Path(direct.output_dir) / "checkpoint.npz", allow_pickle=False) as left, np.load(
        Path(resumed.output_dir) / "checkpoint.npz", allow_pickle=False
    ) as right:
        assert set(left.files) == set(right.files)
        for name in left.files:
            np.testing.assert_array_equal(left[name], right[name])
        metadata = json.loads(str(left["metadata"]))
        assert metadata["epochs"] == audit_a.initial_epochs + 2
        assert metadata["steps"] > audit_a.initial_steps

    request = json.loads(audit_a.validation_path.read_text(encoding="utf-8").splitlines()[0])
    stdin = json.dumps({"task": audit_a.task, "inputs": request["inputs"]}) + "\n"
    environment = os.environ.copy()
    environment.update(PYTHONDONTWRITEBYTECODE="1", BASELINE_CPU_THREADS="1")
    predictions = []
    for checkpoint in (Path(direct.output_dir) / "checkpoint.npz", Path(resumed.output_dir) / "checkpoint.npz"):
        completed = subprocess.run(
            [str(PYTHON), "-m", "baselines.predict", "--checkpoint", str(checkpoint)],
            cwd=audit_a.package_dir,
            env=environment,
            input=stdin,
            text=True,
            capture_output=True,
            check=True,
        )
        predictions.append(json.loads(completed.stdout))
    assert predictions[0] == predictions[1]


def test_validation_rejects_tampered_report_schema(tmp_path: Path, audit_a) -> None:
    trainer = OfficialTrainer(python_executable=PYTHON, timeout_seconds=30)
    receipt = trainer.run_candidate(audit_a, audit_a.checkpoint_path, tmp_path / "candidate", one_epoch(audit_a), "schema")
    report_path = Path(receipt.output_dir) / "training.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["stage_id"] = "wrong-stage"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(CandidateValidationError, match="stage_id"):
        validate_candidate_output(audit_a, audit_a.checkpoint_path, Path(receipt.output_dir), one_epoch(audit_a), "schema")


def test_timeout_preserves_failure_receipt_without_candidate_directory(tmp_path: Path, audit_a) -> None:
    trainer = OfficialTrainer(python_executable=PYTHON, timeout_seconds=0.001)
    output = tmp_path / "timeout-candidate"

    with pytest.raises(TimeoutError, match="timed out"):
        trainer.run_candidate(audit_a, audit_a.checkpoint_path, output, one_epoch(audit_a), "timeout")

    assert not output.exists()
    failure = output.with_name(output.name + ".failure.json")
    assert failure.is_file()
    payload = json.loads(failure.read_text(encoding="utf-8"))
    assert payload["stage_id"] == "timeout"
    assert payload["status"] == "failed"
    assert "timed out" in payload["error"]


def test_trainer_rejects_package_code_changed_after_audit(tmp_path: Path) -> None:
    config = json.loads((REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8"))
    config["packages"] = {"A": config["packages"]["A"]}
    copied_root = tmp_path / "packages"
    source = PACKAGE_ROOT / config["packages"]["A"]["directory"]
    destination = copied_root / source.name
    shutil.copytree(source, destination)
    audit = audit_package_root(copied_root, config)["A"]
    train_code = destination / "baselines" / "train.py"
    train_code.write_text(train_code.read_text(encoding="utf-8") + "\n# changed after audit\n", encoding="utf-8")
    trainer = OfficialTrainer(python_executable=PYTHON, timeout_seconds=30)
    output = tmp_path / "candidate"

    with pytest.raises(CandidateValidationError, match="source code changed"):
        trainer.run_candidate(audit, audit.checkpoint_path, output, one_epoch(audit), "changed-code")

    assert not output.exists()

