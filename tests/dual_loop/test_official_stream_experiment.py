from __future__ import annotations

import json
from pathlib import Path

from brace_msi.official_package import audit_package_root
from brace_msi.official_stream_experiment import run_official_stream_policy
from brace_msi.official_trainer import OfficialTrainer


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


def _audit_a():
    config = json.loads(
        (REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8")
    )
    return audit_package_root(PACKAGE_ROOT, config)["A"]


def test_static_and_fixed_policy_share_frozen_stream_and_continue_parent(tmp_path: Path) -> None:
    package = _audit_a()
    trainer = OfficialTrainer(
        __import__("sys").executable,
        timeout_seconds=60,
        allowed_learning_rate_multipliers=(0.5, 1.0),
    )
    static = run_official_stream_policy(
        package,
        "static",
        tmp_path / "static",
        trainer,
        max_total_candidates=8,
    )
    fixed = run_official_stream_policy(
        package,
        "fixed_update",
        tmp_path / "fixed",
        trainer,
        max_total_candidates=8,
    )

    assert static["complete"] is True
    assert fixed["complete"] is True
    assert len(static["rounds"]) == len(fixed["rounds"]) == 10
    assert static["candidate_count"] == 0
    assert fixed["candidate_count"] == 3
    assert static["stream_manifest_sha256"] == fixed["stream_manifest_sha256"]
    assert fixed["rounds"][0]["candidates"][0]["parent_sha256"] == package.checkpoint_sha256
    assert all(row["prediction_submitted_before_feedback"] for row in fixed["rounds"])
    assert all(row["historically_exposed"] for row in fixed["rounds"])
    assert fixed["official_test_opportunities_used"] == 0
    assert fixed["formal_eligible"] is False
