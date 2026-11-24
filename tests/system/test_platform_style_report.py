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


def test_original_three_task_report_is_adapted_without_inventing_missing_hypotheses() -> None:
    rounds = [
        {
            "round": index,
            "public_validation_metrics": {"mae": 40.0 - index, "rmse": 50.0 - index, "nasa_score": 1000.0 - index},
            "model_selection": "adopt" if index in {1, 9} else "retain_previous",
            "candidate_trained": index in {1, 5, 9},
            "deployed_by_harness": index == 9,
            "executed_action": "replay_refit" if index in {5, 9} else ("incremental_update" if index == 1 else "noop"),
            "cpu_seconds": 1.0,
            "wall_seconds": 2.0,
            "peak_rss_bytes": 1000,
            "input_tokens": 0,
            "output_tokens": 0,
        }
        for index in range(1, 11)
    ]
    source = {
        "format": "brace-msi.local-platform-report-simulation.v1",
        "official_score": False,
        "simulation_only": True,
        "data_scope": "historically_exposed_public_validation",
        "input_tokens": 0,
        "output_tokens": 0,
        "tasks": {
            "C": {
                "completed_rounds": 10,
                "selected_round": 9,
                "selected_metrics": {"mae": 31.0, "rmse": 41.0, "nasa_score": 991.0},
                "evaluation_samples": 9687,
                "cpu_seconds": 10.0,
                "wall_seconds": 20.0,
                "rounds": rounds,
            }
        },
    }

    result = MODULE.build_platform_style_report(source)
    task = result["tasks"][0]

    assert result["evidence_boundary"] == "repeated_public_validation_selection_contaminated_interface_demo_only"
    assert task["display_name"] == "C · 发动机剩余寿命预测"
    assert task["final_adopted_model"] == "历史validation选择：第9轮（不可作泛化证据）"
    assert task["evaluation_sample_label"] == "公开验证样本"
    assert task["metric_heading"] == "重复公开validation结果（选择污染，仅界面演示）"
    assert task["final_confirmation_metrics"][2] == {
        "key": "nasa_score",
        "label": "NASA · 非对称评分",
        "value": 991.0,
    }
    assert task["rounds"][0]["experiment_record"]["hypothesis"] == "历史冻结运行未记录结构化实验假设"
    assert task["rounds"][0]["experiment_record"]["gate"]["reason"] == "历史报告未记录门控原因"


def test_original_report_html_uses_public_validation_boundary() -> None:
    source = {
        "format": "brace-msi.local-platform-report-simulation.v1",
        "official_score": False,
        "simulation_only": True,
        "data_scope": "historically_exposed_public_validation",
        "input_tokens": 0,
        "output_tokens": 0,
        "tasks": {
            "A": {
                "completed_rounds": 10,
                "selected_round": 1,
                "selected_metrics": {"accuracy": 0.8, "macro_f1": 0.7},
                "evaluation_samples": 100,
                "cpu_seconds": 1.0,
                "wall_seconds": 2.0,
                "rounds": [
                    {
                        "round": index,
                        "public_validation_metrics": {"accuracy": 0.8, "macro_f1": 0.7},
                        "model_selection": "adopt" if index == 1 else "retain_previous",
                        "candidate_trained": index == 1,
                        "deployed_by_harness": index == 1,
                        "executed_action": "incremental_update" if index == 1 else "noop",
                        "cpu_seconds": 0.1,
                        "wall_seconds": 0.2,
                        "peak_rss_bytes": 1000,
                        "input_tokens": 0,
                        "output_tokens": 0,
                    }
                    for index in range(1, 11)
                ],
            }
        },
    }

    output = MODULE.render_platform_style_html(MODULE.build_platform_style_report(source))

    assert "A · 气体传感器漂移分类" in output
    assert "公开验证样本" in output
    assert "重复公开validation结果（选择污染，仅界面演示）" in output
    assert "存在验证集选择污染" in output
    assert "本地独立确认集指标（非官方）" not in output


def test_corrected_report_uses_gate_metrics_and_single_frozen_confirmation() -> None:
    source = {
        "format": "brace-msi.local-platform-report-simulation.v2",
        "official_score": False,
        "simulation_only": True,
        "data_scope": "per_round_gate_plus_single_frozen_public_validation",
        "selection_use": "harness_gate_only_public_validation_not_used_for_selection",
        "input_tokens": 0,
        "output_tokens": 0,
        "tasks": {
            "A": {
                "completed_rounds": 10,
                "final_checkpoint_round": 10,
                "last_deployed_round": 9,
                "final_model_origin": "round_9_deployment",
                "final_validation_metrics": {"accuracy": 0.8, "macro_f1": 0.7},
                "evaluation_samples": 100,
                "public_validation_evaluations": 1,
                "cpu_seconds": 1.0,
                "wall_seconds": 2.0,
                "rounds": [
                    {
                        "round": index,
                        "gate_metrics_before": {"accuracy": 0.5, "macro_f1": 0.4},
                        "gate_metrics_candidate": {"accuracy": 0.6, "macro_f1": 0.5},
                        "model_selection": "adopt" if index == 9 else "retain_previous",
                        "candidate_trained": True,
                        "deployed_by_harness": index == 9,
                        "gate_reason": "safe_gain" if index == 9 else "candidate_rejected",
                        "executed_action": "replay_refit",
                        "cpu_seconds": 0.1,
                        "wall_seconds": 0.2,
                        "peak_rss_bytes": 1000,
                        "input_tokens": 0,
                        "output_tokens": 0,
                    }
                    for index in range(1, 11)
                ],
            }
        },
    }

    result = MODULE.build_platform_style_report(source)
    task = result["tasks"][0]
    output = MODULE.render_platform_style_html(result)

    assert result["evidence_boundary"] == "single_frozen_public_validation_not_used_for_selection"
    assert task["final_adopted_model"] == "第9轮部署的稳定模型"
    assert task["metric_heading"] == "冻结后单次公开validation指标（非独立测试）"
    assert task["round_metric_heading"] == "当前批次Gate指标"
    assert task["rounds"][0]["adaptation_metrics"][1]["value"] == 0.4
    assert "当前批次Gate指标" in output
    assert "稳定模型Gate" in output
    assert "候选模型Gate" in output
    assert "0.500000" in output
    assert "公开validation仅在十轮策略冻结后评估一次，未用于选择轮次" in output


def test_workspace_v2_acceptance_renders_each_round_from_machine_receipts(tmp_path: Path) -> None:
    import json

    rounds = []
    profile_root = tmp_path / "A"
    for index in range(1, 11):
        final_parent = index == 10
        rounds.append(
            {
                "round_index": index,
                "selected_artifact_id": f"candidate-A-{index}",
                "model_call_ids": [f"proposal-{index}", f"deploy-{index}"],
                "candidate_submitted": True,
                "parent_metrics": (
                    {"accuracy": 0.83, "macro_f1": 0.73}
                    if final_parent
                    else {"accuracy": 0.80, "macro_f1": 0.70}
                ),
                "candidate_metrics": (
                    {"accuracy": 0.81, "macro_f1": 0.71}
                    if final_parent
                    else {"accuracy": 0.82, "macro_f1": 0.72}
                ),
                "executed_recipe_id": "class_weighted_current_fast",
                "applied_role": "parent" if final_parent else "candidate",
                "selection_reason": "candidate is better on the same scope",
            }
        )
        state = profile_root / f"round-{index:02d}-state"
        state.mkdir(parents=True)
        (state / "round-receipt.json").write_text(
            json.dumps(
                {
                    "round_index": index,
                    "task_profile": {"validation_count": 100},
                    "experiment_proposal": {"hypothesis": f"hypothesis-{index}"},
                    "timing": {
                        "candidate_train_eval_submit_seconds": 0.25,
                        "observed_seconds_before_state_rpc": 1.5,
                    },
                    "artifact_evaluations": [
                        {
                            "role": "candidate",
                            "resource_evidence": {
                                "cpu_seconds": 0.20,
                                "wall_seconds": 0.25,
                                "peak_rss_bytes": 1024,
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    source = {
        "format": "brace-msi.workspace-v2-acceptance.v1",
        "scope": "local_protocol_only_not_official_score",
        "image": "brace-msi:test",
        "valid": True,
        "profiles": {
            "A": {
                "rounds": rounds,
                "round_count": 10,
                "model_call_count": 20,
                "prediction_smoke_rows": 5,
                "final_artifact_id": "candidate-A-10",
            }
        },
    }

    result = MODULE.build_platform_style_report(source, source_root=tmp_path)

    assert result["evidence_boundary"] == "workspace_v2_protocol_acceptance_reuses_public_validation"
    task = result["tasks"][0]
    assert task["display_name"] == "A · 气体传感器漂移分类"
    assert task["completed_rounds"] == 10
    assert task["runtime_seconds"] == 15.0
    assert task["cpu_seconds"] == 2.0
    assert task["rounds"][0]["experiment_record"]["hypothesis"] == "hypothesis-1"
    assert task["rounds"][0]["experiment_record"]["advisor"]["source"] == "local_host_gateway_substitute"
    assert task["final_confirmation_metrics"] == [
        {"key": "accuracy", "label": "Accuracy · 准确率", "value": 0.83},
        {"key": "macro_f1", "label": "Macro-F1 · 宏平均F1", "value": 0.73},
    ]
