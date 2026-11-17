from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).parents[2] / "scripts" / "render_workspace_v2_report.py"


def _acceptance() -> dict:
    profiles = {}
    for profile in ("A", "B", "C"):
        rounds = []
        parent = f"sha256:{profile.lower() * 64}"
        for round_index in range(1, 11):
            candidate = profile == "C" and round_index in {1, 2}
            selected = f"candidate-{profile}-{round_index}" if candidate else f"baseline-{profile}"
            rounds.append(
                {
                    "round_index": round_index,
                    "selected_artifact_id": selected,
                    "model_call_ids": [f"call-{profile}-{round_index}-1"],
                    "candidate_submitted": candidate,
                    "parent_checkpoint_sha256": parent,
                }
            )
        profiles[profile] = {
            "rounds": rounds,
            "round_count": 10,
            "model_call_count": 10,
            "prediction_smoke_rows": 5,
            "final_artifact_id": rounds[-1]["selected_artifact_id"],
        }
    return {
        "format": "brace-msi.workspace-v2-acceptance.v1",
        "scope": "local_protocol_only_not_official_score",
        "image": "brace-msi:independent-test",
        "profiles": profiles,
        "valid": True,
    }


def test_cli_renders_complete_official_style_local_report(tmp_path: Path) -> None:
    """Catches a report that omits rounds or presents local evidence as official."""

    source = tmp_path / "acceptance.json"
    output = tmp_path / "report"
    source.write_text(json.dumps(_acceptance()), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    machine = json.loads((output / "platform-style-report.json").read_text(encoding="utf-8"))
    html = (output / "platform-style-report.html").read_text(encoding="utf-8")
    assert machine["scope"] == "local_protocol_only_not_official_score"
    assert machine["summary"] == {
        "completed_rounds": 30,
        "expected_rounds": 30,
        "model_calls": 30,
        "prediction_smoke_rows": 15,
        "candidate_submissions": 2,
    }
    assert len(machine["tasks"]) == 3
    assert sum(len(task["rounds"]) for task in machine["tasks"]) == 30
    assert "训练与评测报告" in html
    assert "本地协议模拟，不计正式成绩" in html
    assert "隐藏测试指标" in html
    assert "正式平台产生，本地不可获得" in html
    assert "CPU用时" in html
    assert "运行用时" in html
    assert "本地模拟未汇总" in html
    assert "官方评测通过" not in html


def test_cli_fails_closed_when_a_round_has_no_model_receipt(tmp_path: Path) -> None:
    """Catches a report that hides a missing mandatory host model call."""

    payload = _acceptance()
    payload["profiles"]["B"]["rounds"][4]["model_call_ids"] = []
    source = tmp_path / "acceptance.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(tmp_path / "out")],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "model call receipt" in completed.stderr
    assert not (tmp_path / "out" / "platform-style-report.html").exists()
