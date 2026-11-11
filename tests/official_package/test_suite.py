from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from brace_msi.official_package import audit_package_root
from brace_msi.official_package_suite import (
    run_official_package_suite,
    validate_runtime_boundary,
    validate_official_package_suite,
)
from brace_msi.official_trainer import CandidateReceipt


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


class SuiteTrainer:
    def __init__(self, *, cpu_seconds: float = 0.1, wall_seconds: float = 0.2) -> None:
        self.calls: list[dict] = []
        self.per_profile: dict[str, int] = {}
        self.cpu_seconds = cpu_seconds
        self.wall_seconds = wall_seconds

    def run_candidate(self, package, parent, output_dir, config, stage_id):
        output_dir = Path(output_dir)
        if output_dir.exists():
            raise FileExistsError(output_dir)
        output_dir.mkdir(parents=True)
        checkpoint = output_dir / "checkpoint.npz"
        checkpoint.write_bytes(f"{stage_id}:{len(self.calls)}".encode())
        parent_sha = hashlib.sha256(Path(parent).read_bytes()).hexdigest()
        child_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        index = self.per_profile.get(package.profile, 0) + 1
        self.per_profile[package.profile] = index
        direction = 1.0 if package.higher_is_better else -1.0
        metric = package.baseline_metric + direction * index * 0.001
        receipt = CandidateReceipt(
            stage_id=stage_id,
            profile=package.profile,
            parent_sha256=parent_sha,
            checkpoint_sha256=child_sha,
            metrics_before={package.primary_metric: package.baseline_metric},
            metrics_after={package.primary_metric: metric},
            initial_epochs=10 + index - 1,
            final_epochs=10 + index,
            initial_steps=100 + index - 1,
            final_steps=100 + index,
            model_state_changed=True,
            optimizer_state_changed=True,
            wall_seconds=self.wall_seconds,
            cpu_seconds=self.cpu_seconds,
            peak_rss_bytes=4096,
            output_dir=str(output_dir),
            validation_file_reads=1,
            validation_metric_evaluations=config.epochs + 1,
        )
        (output_dir / "candidate-receipt.json").write_text(json.dumps(asdict(receipt)), encoding="utf-8")
        self.calls.append({"profile": package.profile, "stage_id": stage_id})
        return receipt


def load_config() -> dict:
    config = json.loads((REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8"))
    config.update(
        max_candidates_per_policy=3,
        max_cpu_seconds_per_policy=60.0,
        max_wall_seconds_per_policy=60.0,
        report_title="<BRACE-MSI official package development>",
    )
    return config


def test_suite_estimates_resources_before_smoke_then_resumes_six_policy_jobs(tmp_path: Path) -> None:
    config = load_config()
    audits = audit_package_root(PACKAGE_ROOT, config)
    trainer = SuiteTrainer()
    runtime = tmp_path / "suite"

    smoke_state = run_official_package_suite(PACKAGE_ROOT, runtime, config, max_jobs=3, trainer=trainer)

    assert smoke_state.complete is False
    assert smoke_state.completed_jobs == ["smoke:A", "smoke:B", "smoke:C"]
    estimate = json.loads((runtime / "resource-estimate.json").read_text(encoding="utf-8"))
    assert estimate["pre_smoke"]["estimated_cpu_seconds"] > 0
    assert estimate["pre_smoke"]["estimated_disk_bytes"] > 0
    assert estimate["pre_smoke"]["within_limits"] is True
    assert estimate["post_smoke"]["estimated_wall_seconds"] > 0
    assert estimate["post_smoke"]["within_limits"] is True
    assert all((runtime / "smoke" / profile / "checkpoint.npz").is_file() for profile in audits)
    manifest = json.loads((runtime / "source-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["source_commit"]) == 40
    assert isinstance(manifest["source_tree_dirty"], bool)

    complete_state = run_official_package_suite(PACKAGE_ROOT, runtime, config, trainer=trainer)

    assert complete_state.complete is True
    assert len(complete_state.completed_jobs) == 9
    assert len(trainer.calls) == 3 + (3 * 1) + (3 * 3)
    summary = json.loads((runtime / "summary.json").read_text(encoding="utf-8"))
    assert summary["official_package"] is True
    assert summary["official_scoring_ready"] is False
    assert summary["round_semantics"] == "candidate_adaptation_decision"
    assert summary["real_drift_stream"] is False
    assert set(summary["tasks"]) == {"A", "B", "C"}
    assert summary["upstream_package_tests"]["B"]["core_passed"] == 10
    assert summary["upstream_package_tests"]["B"]["packaging_tool_errors"] == 2
    assert "&lt;BRACE-MSI official package development&gt;" in (runtime / "report.html").read_text(encoding="utf-8")
    validation_rows = [
        json.loads(line)
        for line in (runtime / "validation-usage.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    candidate_rows = [row for row in validation_rows if row["purpose"] != "source_audit"]
    audit_rows = [row for row in validation_rows if row["purpose"] == "source_audit"]
    assert len(candidate_rows) == len(trainer.calls)
    assert len(audit_rows) == 6
    assert sum(row["file_reads"] for row in validation_rows) == 42
    assert all(row["used_for_training"] is False for row in validation_rows)
    assert all(row["used_for_preprocessing_fit"] is False for row in validation_rows)
    validation = validate_official_package_suite(runtime)
    assert validation["valid"] is True
    assert validation["jobs"] == 9
    assert validation["profiles"] == ["A", "B", "C"]


def test_completed_suite_resume_runs_no_duplicate_candidates(tmp_path: Path) -> None:
    config = load_config()
    trainer = SuiteTrainer()
    runtime = tmp_path / "resume"
    first = run_official_package_suite(PACKAGE_ROOT, runtime, config, trainer=trainer)
    calls = len(trainer.calls)
    state_hash = hashlib.sha256((runtime / "suite-state.json").read_bytes()).hexdigest()

    second = run_official_package_suite(PACKAGE_ROOT, runtime, config, trainer=trainer)

    assert first.complete and second.complete
    assert len(trainer.calls) == calls
    assert hashlib.sha256((runtime / "suite-state.json").read_bytes()).hexdigest() == state_hash


def test_pre_smoke_resource_limit_stops_before_any_training(tmp_path: Path) -> None:
    config = load_config()
    config["resource_limits"]["estimated_disk_bytes"] = 1
    trainer = SuiteTrainer()

    try:
        run_official_package_suite(PACKAGE_ROOT, tmp_path / "limited", config, trainer=trainer)
    except RuntimeError as exc:
        assert "resource estimate exceeds limits" in str(exc)
    else:
        raise AssertionError("resource limit did not stop the suite")

    assert trainer.calls == []
    estimate = json.loads((tmp_path / "limited" / "resource-estimate.json").read_text(encoding="utf-8"))
    assert estimate["pre_smoke"]["within_limits"] is False


def test_cli_runs_from_clean_checkout_without_editable_install() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "scripts/run_official_package_dev.py", "--help"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--package-root" in completed.stdout


def test_cli_archives_failed_status_before_restart(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "run_official_package_dev.py"
    spec = importlib.util.spec_from_file_location("official_package_dev_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._status(tmp_path, "failed", error="first failure")

    module._status(tmp_path, "running")

    history = sorted((tmp_path / "pipeline-status-history").glob("attempt-*.json"))
    assert len(history) == 1
    assert json.loads(history[0].read_text(encoding="utf-8"))["stage"] == "failed"
    assert json.loads((tmp_path / "pipeline-status.json").read_text(encoding="utf-8"))["stage"] == "running"


def test_runtime_boundary_rejects_package_overlap_before_first_write(tmp_path: Path) -> None:
    package_root = tmp_path / "packages"
    package_root.mkdir()
    runtime = package_root / "forbidden-runtime"

    try:
        validate_runtime_boundary(package_root, runtime)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("overlapping runtime was accepted")
    assert not runtime.exists()


def test_failed_post_smoke_estimate_blocks_every_resume_before_policy(tmp_path: Path) -> None:
    config = load_config()
    config["resource_limits"]["estimated_wall_seconds"] = 70.0
    runtime = tmp_path / "post-smoke-stop"
    first = SuiteTrainer(wall_seconds=1.0)
    try:
        run_official_package_suite(PACKAGE_ROOT, runtime, config, max_jobs=3, trainer=first)
    except RuntimeError as exc:
        assert "after smoke" in str(exc)
    else:
        raise AssertionError("post-smoke limit did not stop")
    assert len(first.calls) == 3

    resumed = SuiteTrainer()
    try:
        run_official_package_suite(PACKAGE_ROOT, runtime, config, trainer=resumed)
    except RuntimeError as exc:
        assert "after smoke" in str(exc)
    else:
        raise AssertionError("resume bypassed failed post-smoke limit")
    assert resumed.calls == []


def test_suite_recovers_completed_smoke_receipt_before_state_commit(tmp_path: Path) -> None:
    config = load_config()
    audits = audit_package_root(PACKAGE_ROOT, config)
    runtime = tmp_path / "smoke-recovery"
    trainer = SuiteTrainer()
    trainer.run_candidate(
        audits["A"],
        audits["A"].checkpoint_path,
        runtime / "smoke" / "A",
        __import__("brace_msi.official_trainer", fromlist=["CandidateConfig"]).CandidateConfig(
            1, audits["A"].base_learning_rate, audits["A"].base_batch_size
        ),
        "A-smoke",
    )

    state = run_official_package_suite(PACKAGE_ROOT, runtime, config, max_jobs=1, trainer=trainer)

    assert state.completed_jobs == ["smoke:A"]
    assert len(trainer.calls) == 1


def test_resume_preserves_execution_manifest_and_rejects_config_drift(tmp_path: Path) -> None:
    config = load_config()
    runtime = tmp_path / "manifest-freeze"
    run_official_package_suite(PACKAGE_ROOT, runtime, config, max_jobs=3, trainer=SuiteTrainer())
    manifest_before = (runtime / "source-manifest.json").read_bytes()
    changed = json.loads(json.dumps(config))
    changed["report_title"] = "changed after partial run"

    try:
        run_official_package_suite(PACKAGE_ROOT, runtime, changed, trainer=SuiteTrainer())
    except ValueError as exc:
        assert "configuration fingerprint" in str(exc)
    else:
        raise AssertionError("configuration drift was accepted")
    assert (runtime / "source-manifest.json").read_bytes() == manifest_before


def test_suite_validator_rejects_missing_checkpoint_and_summary_tamper(tmp_path: Path) -> None:
    config = load_config()
    missing_runtime = tmp_path / "missing"
    run_official_package_suite(PACKAGE_ROOT, missing_runtime, config, trainer=SuiteTrainer())
    checkpoint = next((missing_runtime / "policies" / "A" / "brace").rglob("checkpoint.npz"))
    checkpoint.unlink()
    try:
        validate_official_package_suite(missing_runtime)
    except ValueError as exc:
        assert "checkpoint" in str(exc)
    else:
        raise AssertionError("missing checkpoint passed validation")

    tampered_runtime = tmp_path / "tampered-summary"
    run_official_package_suite(PACKAGE_ROOT, tampered_runtime, config, trainer=SuiteTrainer())
    summary_path = tampered_runtime / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["tasks"]["C"]["brace"]["stable_metric"] = -999.0
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    try:
        validate_official_package_suite(tampered_runtime)
    except ValueError as exc:
        assert "summary" in str(exc)
    else:
        raise AssertionError("tampered summary passed validation")

