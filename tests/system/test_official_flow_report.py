from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "render_official_flow_report.py"
SPEC = importlib.util.spec_from_file_location("render_official_flow_report", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_report_separates_prequential_gate_confirmation_and_hidden(tmp_path: Path) -> None:
    for profile in "ABC":
        root = tmp_path / profile
        root.mkdir()
        rounds = []
        for index in range(1, 11):
            rounds.append(
                {
                    "round_index": index,
                    "prequential_metrics": {"macro_f1": 0.5} if profile == "A" else {"rmse": 10.0},
                    "candidate_gate_metrics": {"stable": {"rmse": 11.0}, "candidate": None},
                    "runtime_receipt": {
                        "sample_count": 10,
                        "candidate_trained": index == 1,
                        "deployed": False,
                        "decision": {"executed_action": "noop"},
                        "gate_reason": "retain_no_candidate",
                        "cpu_seconds": 1.0,
                        "wall_seconds": 2.0,
                        "peak_rss_bytes": 1024,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "data_sha256": "a" * 64,
                        "parent_checkpoint_sha256": "b" * 64,
                        "checkpoint_sha256": "c" * 64,
                    },
                }
            )
        (root / "summary.json").write_text(
            json.dumps(
                {
                    "rounds": rounds,
                    "local_final_confirmation": {"sample_count": 5, "metrics": {"rmse": 9.0}},
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "parent_chain_valid": True,
                    "confirmation_read_count": 1,
                }
            ),
            encoding="utf-8",
        )

    report = MODULE.build_report(tmp_path, confirmation_exposure_index=2)
    html = MODULE.render_html(report)

    assert report["hidden_test_status"] == "not_started_not_available"
    assert report["tasks"]["A"]["rounds_completed"] == 10
    assert report["tasks"]["A"]["confirmation_scope"] == "historically_exposed_local_confirmation"
    assert "正式隐藏测试尚未开始" in html
    assert "Prequential" in html and "Gate候选" in html
