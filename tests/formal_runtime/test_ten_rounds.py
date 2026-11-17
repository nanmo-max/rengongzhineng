from __future__ import annotations

import json
from pathlib import Path


def test_three_task_ten_round_simulation_is_complete_and_auditable(tmp_path: Path) -> None:
    from scripts.simulate_first_principles_runtime import run_simulation

    summary = run_simulation(tmp_path / "simulation")

    assert summary["label"] == "LOCAL SYNTHETIC PROTOCOL TEST - NOT AN OFFICIAL SCORE"
    assert summary["total_rounds"] == 30
    assert summary["total_model_calls"] == 30
    assert len(summary["tasks"]) == 3
    call_ids = []
    for task in summary["tasks"]:
        assert task["completed_rounds"] == 10
        assert task["parent_chain_valid"] is True
        assert task["state_chain_valid"] is True
        assert len(task["rounds"]) == 10
        call_ids.extend(item["model_call_id"] for item in task["rounds"])
    assert len(call_ids) == len(set(call_ids)) == 30

    acceptance = tmp_path / "simulation" / "acceptance.json"
    report = tmp_path / "simulation" / "report.html"
    assert json.loads(acceptance.read_text(encoding="utf-8")) == summary
    html = report.read_text(encoding="utf-8")
    assert "非官方成绩" in html
    assert "30 / 30" in html
