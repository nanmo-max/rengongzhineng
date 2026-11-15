from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "render_platform_style_report.py"
SPEC = importlib.util.spec_from_file_location("render_platform_style_report", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _report() -> dict:
    rounds = []
    for index in range(1, 11):
        deployed = index == 3
        rounds.append(
            {
                "round_index": index,
                "checkpoint_sha256": "candidate" if index >= 3 else "parent",
                "candidate_trained": index <= 5,
                "deployed": deployed,
                "gate_reason": "competitive_gate_passed" if deployed else "anchor_risk_exceeded",
                "metrics_before": {"mae": 1.0 + index / 10, "rmse": 2.0 + index / 10},
                "metrics_candidate": {"mae": 0.9, "rmse": 1.9} if index <= 5 else None,
                "cpu_seconds": float(index),
                "wall_seconds": float(index) / 2,
                "peak_rss_bytes": 1000 * index,
                "training_sample_count": 20 if index <= 5 else 0,
                "input_tokens": 10 if index <= 5 else 0,
                "output_tokens": 5 if index <= 5 else 0,
                "decision": {
                    "advisor_source": "pytrio" if index <= 5 else "not_triggered",
                    "rationale": f"hypothesis {index}",
                    "executed_action": "replay_refit" if index <= 5 else "noop",
                    "epochs": 1 if index <= 5 else 0,
                    "learning_rate": 0.003,
                },
            }
        )
    return {
        "experiment_id": "UNSEEN-SIM-001-A4",
        "official_score": False,
        "official_trial_consumed": False,
        "advisor_model": "Qwen/Qwen3.5-4B",
        "input_tokens": 50,
        "output_tokens": 25,
        "tasks": [
            {
                "task": "battery",
                "task_kind": "regression",
                "round_count": 10,
                "partition_counts": {"confirmation": 30},
                "initial_confirmation_metrics": {"mae": 1.0, "rmse": 2.0},
                "final_confirmation_metrics": {"mae": 1.2, "rmse": 2.2},
                "per_round_confirmation": [
                    {"round": 0, "checkpoint_sha256": "parent", "metrics": {"mae": 1.0, "rmse": 2.0}},
                    *[
                        {
                            "round": index,
                            "checkpoint_sha256": "candidate" if index >= 3 else "parent",
                            "metrics": {"mae": 1.2, "rmse": 2.2},
                        }
                        for index in range(1, 11)
                    ],
                ],
                "rounds": rounds,
            },
            {
                "task": "hydraulic",
                "task_kind": "classification",
                "round_count": 10,
                "partition_counts": {"confirmation": 40},
                "initial_confirmation_metrics": {"accuracy": 0.4, "macro_f1": 0.3},
                "final_confirmation_metrics": {"accuracy": 0.4, "macro_f1": 0.3},
                "per_round_confirmation": [
                    {"round": index, "checkpoint_sha256": "parent", "metrics": {"accuracy": 0.4, "macro_f1": 0.3}}
                    for index in range(0, 11)
                ],
                "rounds": [{**row, "checkpoint_sha256": "parent", "deployed": False} for row in rounds],
            },
        ],
    }


def test_build_report_contains_official_page_elements_without_claiming_hidden_score() -> None:
    result = MODULE.build_platform_style_report(_report())

    assert result["format"] == "brace-msi.platform-style-local-report.v1"
    assert result["evidence_boundary"] == "local_confirmation_not_official_hidden_test"
    battery = result["tasks"][0]
    assert battery["completed_rounds"] == 10
    assert battery["final_adopted_model"] == "第3轮模型"
    assert battery["confirmation_sample_count"] == 30
    assert battery["cpu_seconds"] == 55.0
    assert battery["runtime_seconds"] == 27.5
    assert len(battery["rounds"]) == 10
    assert battery["rounds"][2]["model_selection"] == "采用本轮模型"
    assert battery["rounds"][0]["experiment_record"]["history"] == "首轮：读取模拟父模型与当前合法批次历史"
    assert battery["rounds"][0]["experiment_record"]["hypothesis"] == "hypothesis 1"
    assert battery["rounds"][0]["experiment_record"]["modification"]["action"] == "replay_refit"
    assert result["tasks"][1]["final_adopted_model"] == "初始父模型"


def test_html_is_readable_expandable_and_explicitly_non_official() -> None:
    result = MODULE.build_platform_style_report(_report())
    output = MODULE.render_platform_style_html(result)

    for text in (
        "本地独立确认集指标（非官方）",
        "完成轮次",
        "最终采用",
        "确认集样本",
        "CPU 用时",
        "运行时间",
        "公开适应流指标",
        "模型选择",
        "实验记录",
        "读取历史",
        "实验假设",
        "本轮修改",
        "PyTRiO / Token",
    ):
        assert text in output
    assert "<details" in output
    assert "官方隐藏成绩" not in output
    assert "api_key" not in output.lower()
