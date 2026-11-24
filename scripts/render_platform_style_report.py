"""Render an official-element-style local report from a frozen simulation receipt."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


TASK_NAMES = {
    "battery": "A · 电池容量预测",
    "hydraulic": "B · 液压蓄能器状态分类",
    "mill": "C · 铣削刀具磨损预测",
}
OFFICIAL_TASK_NAMES = {
    "A": "A · 气体传感器漂移分类",
    "B": "B · 轴承寿命预测",
    "C": "C · 发动机剩余寿命预测",
}
SECRET_MARKERS = ("api_key", "authorization", "trio_aq")


def _assert_no_secrets(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, default=str).lower()
    for marker in SECRET_MARKERS:
        if marker in serialized:
            raise ValueError(f"report contains forbidden secret marker: {marker}")


def _metric_rows(task_kind: str, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    order = ("accuracy", "macro_f1") if task_kind == "classification" else ("mae", "rmse")
    labels = {
        "accuracy": "Accuracy · 准确率",
        "macro_f1": "Macro-F1 · 宏平均F1",
        "mae": "MAE · 平均绝对误差",
        "rmse": "RMSE · 均方根误差",
        "nasa_score": "NASA · 非对称评分",
    }
    keys = [key for key in order if key in metrics]
    if "nasa_score" in metrics:
        keys.append("nasa_score")
    return [{"key": key, "label": labels[key], "value": float(metrics[key])} for key in keys]


def _final_adopted_model(task: dict[str, Any]) -> str:
    rounds = task["rounds"]
    per_round = task["per_round_confirmation"]
    parent_sha = per_round[0]["checkpoint_sha256"]
    final_sha = rounds[-1]["checkpoint_sha256"]
    if final_sha == parent_sha:
        return "初始父模型"
    for row in rounds:
        if row["checkpoint_sha256"] == final_sha and row.get("deployed"):
            return f"第{int(row['round_index'])}轮模型"
    for row in rounds:
        if row["checkpoint_sha256"] == final_sha:
            return f"第{int(row['round_index'])}轮模型"
    return "未记录"


def _round_record(row: dict[str, Any], task_kind: str) -> dict[str, Any]:
    index = int(row["round_index"])
    decision = row.get("decision") or {}
    candidate_trained = bool(row.get("candidate_trained"))
    deployed = bool(row.get("deployed"))
    if deployed:
        selection = "采用本轮模型"
    elif candidate_trained:
        selection = "候选未采用，保留此前模型"
    else:
        selection = "保留此前模型"
    return {
        "round": index,
        "adaptation_metrics": _metric_rows(task_kind, row.get("metrics_before") or {}),
        "candidate_metrics": _metric_rows(task_kind, row.get("metrics_candidate") or {})
        if row.get("metrics_candidate")
        else [],
        "model_selection": selection,
        "experiment_record": {
            "history": (
                "首轮：读取模拟父模型与当前合法批次历史"
                if index == 1
                else f"读取至第{index - 1}轮的合法实验历史"
            ),
            "hypothesis": str(decision.get("rationale") or "未记录"),
            "modification": {
                "action": str(decision.get("executed_action") or "noop"),
                "epochs": int(row.get("epochs", decision.get("epochs", 0)) or 0),
                "learning_rate": row.get("learning_rate", decision.get("learning_rate")),
                "training_sample_count": int(row.get("training_sample_count", 0)),
            },
            "advisor": {
                "source": str(decision.get("advisor_source") or "not_recorded"),
                "input_tokens": int(row.get("input_tokens", 0)),
                "output_tokens": int(row.get("output_tokens", 0)),
            },
            "gate": {
                "reason": str(row.get("gate_reason") or "not_recorded"),
                "deployed": deployed,
            },
            "resources": {
                "cpu_seconds": float(row.get("cpu_seconds", 0.0)),
                "runtime_seconds": float(row.get("wall_seconds", 0.0)),
                "peak_rss_bytes": int(row.get("peak_rss_bytes", 0)),
            },
        },
    }


def _historical_round_record(profile: str, row: dict[str, Any]) -> dict[str, Any]:
    index = int(row["round"])
    adopted = row.get("model_selection") == "adopt"
    return {
        "round": index,
        "adaptation_metrics": _metric_rows(
            "classification" if profile == "A" else "regression",
            row.get("public_validation_metrics") or {},
        ),
        "candidate_metrics": [],
        "model_selection": "采用本轮模型" if adopted else "保留此前模型",
        "experiment_record": {
            "history": (
                "首轮：读取官方父模型与冻结运行历史"
                if index == 1
                else f"读取至第{index - 1}轮的冻结实验历史"
            ),
            "hypothesis": "历史冻结运行未记录结构化实验假设",
            "modification": {
                "action": str(row.get("executed_action") or "noop"),
                "epochs": "未记录",
                "learning_rate": "未记录",
                "training_sample_count": "未记录",
            },
            "advisor": {
                "source": "historical_report",
                "input_tokens": int(row.get("input_tokens", 0)),
                "output_tokens": int(row.get("output_tokens", 0)),
            },
            "gate": {
                "reason": "历史报告未记录门控原因",
                "deployed": bool(row.get("deployed_by_harness")),
            },
            "resources": {
                "cpu_seconds": float(row.get("cpu_seconds", 0.0)),
                "runtime_seconds": float(row.get("wall_seconds", 0.0)),
                "peak_rss_bytes": int(row.get("peak_rss_bytes", 0)),
            },
        },
    }


def _corrected_round_record(profile: str, row: dict[str, Any]) -> dict[str, Any]:
    index = int(row["round"])
    deployed = bool(row.get("deployed_by_harness"))
    candidate_trained = bool(row.get("candidate_trained"))
    return {
        "round": index,
        "adaptation_metrics": _metric_rows(
            "classification" if profile == "A" else "regression",
            row.get("gate_metrics_before") or {},
        ),
        "candidate_metrics": _metric_rows(
            "classification" if profile == "A" else "regression",
            row.get("gate_metrics_candidate") or {},
        ),
        "model_selection": (
            "采用本轮模型"
            if deployed
            else "候选未采用，保留此前模型"
            if candidate_trained
            else "保留此前模型"
        ),
        "experiment_record": {
            "history": (
                "首轮：读取官方父模型与当前合法批次"
                if index == 1
                else f"读取至第{index - 1}轮的冻结实验历史"
            ),
            "hypothesis": "历史冻结运行未记录结构化实验假设",
            "modification": {
                "action": str(row.get("executed_action") or "noop"),
                "epochs": "未记录",
                "learning_rate": "未记录",
                "training_sample_count": "未记录",
            },
            "advisor": {
                "source": "historical_report",
                "input_tokens": int(row.get("input_tokens", 0)),
                "output_tokens": int(row.get("output_tokens", 0)),
            },
            "gate": {
                "reason": str(row.get("gate_reason") or "未记录"),
                "deployed": deployed,
            },
            "resources": {
                "cpu_seconds": float(row.get("cpu_seconds", 0.0)),
                "runtime_seconds": float(row.get("wall_seconds", 0.0)),
                "peak_rss_bytes": int(row.get("peak_rss_bytes", 0)),
            },
        },
    }


def _build_historical_tasks(source: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    for profile, task in source["tasks"].items():
        if int(task["completed_rounds"]) != 10 or len(task["rounds"]) != 10:
            raise ValueError("platform-style report requires exactly ten completed rounds")
        task_kind = "classification" if profile == "A" else "regression"
        tasks.append(
            {
                "task_id": profile,
                "display_name": OFFICIAL_TASK_NAMES.get(profile, profile),
                "task_kind": task_kind,
                "status": "记录完整",
                "completed_rounds": 10,
                "total_rounds": 10,
                "final_adopted_model": (
                    f"历史validation选择：第{int(task['selected_round'])}轮（不可作泛化证据）"
                ),
                "confirmation_sample_count": int(task["evaluation_samples"]),
                "evaluation_sample_label": "公开验证样本",
                "metric_heading": "重复公开validation结果（选择污染，仅界面演示）",
                "round_metric_heading": "重复公开validation指标（受污染）",
                "cpu_seconds": float(task["cpu_seconds"]),
                "runtime_seconds": float(task["wall_seconds"]),
                "final_confirmation_metrics": _metric_rows(task_kind, task["selected_metrics"]),
                "initial_confirmation_metrics": _metric_rows(
                    task_kind, task["rounds"][0]["public_validation_metrics"]
                ),
                "rounds": [_historical_round_record(profile, row) for row in task["rounds"]],
            }
        )
    return tasks


def _build_corrected_tasks(source: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    for profile, task in source["tasks"].items():
        if int(task["completed_rounds"]) != 10 or len(task["rounds"]) != 10:
            raise ValueError("platform-style report requires exactly ten completed rounds")
        if int(task.get("public_validation_evaluations", 0)) != 1:
            raise ValueError("corrected report requires exactly one frozen public validation read")
        task_kind = "classification" if profile == "A" else "regression"
        deployed_round = task.get("last_deployed_round")
        tasks.append(
            {
                "task_id": profile,
                "display_name": OFFICIAL_TASK_NAMES.get(profile, profile),
                "task_kind": task_kind,
                "status": "记录完整",
                "completed_rounds": 10,
                "total_rounds": 10,
                "final_adopted_model": (
                    f"第{int(deployed_round)}轮部署的稳定模型"
                    if deployed_round is not None
                    else "初始父模型"
                ),
                "confirmation_sample_count": int(task["evaluation_samples"]),
                "evaluation_sample_label": "冻结后公开validation样本",
                "metric_heading": "冻结后单次公开validation指标（非独立测试）",
                "round_metric_heading": "当前批次Gate指标",
                "cpu_seconds": float(task["cpu_seconds"]),
                "runtime_seconds": float(task["wall_seconds"]),
                "final_confirmation_metrics": _metric_rows(
                    task_kind, task["final_validation_metrics"]
                ),
                "initial_confirmation_metrics": [],
                "rounds": [_corrected_round_record(profile, row) for row in task["rounds"]],
            }
        )
    return tasks


def _workspace_receipt(source_root: Path | None, profile: str, round_index: int) -> dict[str, Any]:
    if source_root is None:
        return {}
    path = source_root / profile / f"round-{round_index:02d}-state" / "round-receipt.json"
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _workspace_round_record(
    profile: str,
    row: dict[str, Any],
    receipt: dict[str, Any],
    model_provider: str,
) -> dict[str, Any]:
    task_kind = "classification" if profile == "A" else "regression"
    role = str(row.get("applied_role") or "parent")
    resources = {}
    for evaluation in receipt.get("artifact_evaluations", ()):
        if isinstance(evaluation, dict) and evaluation.get("role") == "candidate":
            candidate_resources = evaluation.get("resource_evidence")
            if isinstance(candidate_resources, dict):
                resources = candidate_resources
            break
    timing = receipt.get("timing") if isinstance(receipt.get("timing"), dict) else {}
    proposal = (
        receipt.get("experiment_proposal")
        if isinstance(receipt.get("experiment_proposal"), dict)
        else {}
    )
    execution = (
        receipt.get("candidate_execution")
        if isinstance(receipt.get("candidate_execution"), dict)
        else {}
    )
    model_receipts = row.get("host_model_receipts")
    if model_receipts is None:
        model_receipts = []
    if not isinstance(model_receipts, list) or any(
        not isinstance(item, dict) for item in model_receipts
    ):
        raise ValueError("workspace model receipts must be a list of mappings")
    receipt_providers = {
        str(item.get("provider")) for item in model_receipts if item.get("provider")
    }
    if receipt_providers and receipt_providers != {model_provider}:
        raise ValueError("workspace model receipt provider differs from acceptance provider")
    input_tokens = sum(max(0, int(item.get("input_tokens", 0))) for item in model_receipts)
    output_tokens = sum(max(0, int(item.get("output_tokens", 0))) for item in model_receipts)
    index = int(row["round_index"])
    return {
        "round": index,
        "adaptation_metrics": _metric_rows(task_kind, row.get("parent_metrics") or {}),
        "candidate_metrics": _metric_rows(task_kind, row.get("candidate_metrics") or {}),
        "model_selection": {
            "candidate": "采用本轮模型",
            "history": "回滚到历史稳定模型",
        }.get(role, "候选未采用，保留父模型"),
        "experiment_record": {
            "history": "首轮：读取父模型与当前合法数据" if index == 1 else f"读取至第{index - 1}轮的聚合实验历史",
            "hypothesis": str(proposal.get("hypothesis") or "本地协议宿主未记录结构化假设"),
            "modification": {
                "action": str(row.get("executed_recipe_id") or "not_recorded"),
                "epochs": int(execution.get("epochs", 0) or 0),
                "learning_rate": execution.get("effective_learning_rate"),
                "training_sample_count": int(execution.get("training_samples", 0) or 0),
            },
            "advisor": {
                "source": model_provider,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "gate": {
                "reason": str(row.get("selection_reason") or "not_recorded"),
                "deployed": role == "candidate",
            },
            "resources": {
                "cpu_seconds": float(resources.get("cpu_seconds", 0.0) or 0.0),
                "runtime_seconds": float(timing.get("observed_seconds_before_state_rpc", 0.0) or 0.0),
                "peak_rss_bytes": int(resources.get("peak_rss_bytes", 0) or 0),
            },
        },
    }


def _build_workspace_tasks(source: dict[str, Any], source_root: Path | None) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    profiles = source.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("workspace acceptance profiles are required")
    model_provider = str(source.get("model_provider") or "local_host_gateway_substitute")
    for profile, raw in sorted(profiles.items()):
        if not isinstance(raw, dict):
            continue
        rows = raw.get("rounds")
        if not isinstance(rows, list) or len(rows) != 10:
            raise ValueError("workspace report requires exactly ten completed rounds")
        receipts = [
            _workspace_receipt(source_root, str(profile), int(row["round_index"]))
            for row in rows
        ]
        first = rows[0]
        last = rows[-1]
        final_metrics = (
            last.get("candidate_metrics")
            if last.get("applied_role") == "candidate"
            else last.get("parent_metrics")
        ) or {}
        task_kind = "classification" if profile == "A" else "regression"
        round_records = [
            _workspace_round_record(str(profile), row, receipt, model_provider)
            for row, receipt in zip(rows, receipts, strict=True)
        ]
        input_tokens = sum(
            int(row["experiment_record"]["advisor"]["input_tokens"])
            for row in round_records
        )
        output_tokens = sum(
            int(row["experiment_record"]["advisor"]["output_tokens"])
            for row in round_records
        )
        if "input_tokens" in raw and int(raw["input_tokens"]) != input_tokens:
            raise ValueError("workspace profile input token total differs from model receipts")
        if "output_tokens" in raw and int(raw["output_tokens"]) != output_tokens:
            raise ValueError("workspace profile output token total differs from model receipts")
        validation_count = 0
        for receipt in receipts:
            task_profile = receipt.get("task_profile")
            if isinstance(task_profile, dict) and isinstance(task_profile.get("validation_count"), int):
                validation_count = int(task_profile["validation_count"])
                break
        tasks.append(
            {
                "task_id": str(profile),
                "display_name": OFFICIAL_TASK_NAMES.get(str(profile), str(profile)),
                "task_kind": task_kind,
                "status": "记录完整",
                "completed_rounds": 10,
                "total_rounds": 10,
                "final_adopted_model": str(raw.get("final_artifact_id") or "未记录"),
                "confirmation_sample_count": validation_count,
                "evaluation_sample_label": "重复公开validation样本",
                "metric_heading": "最终链模型公开validation指标（仅协议复演）",
                "round_metric_heading": "同一公开validation的父/候选指标",
                "cpu_seconds": sum(
                    row["experiment_record"]["resources"]["cpu_seconds"] for row in round_records
                ),
                "runtime_seconds": sum(
                    row["experiment_record"]["resources"]["runtime_seconds"] for row in round_records
                ),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "final_confirmation_metrics": _metric_rows(task_kind, final_metrics),
                "initial_confirmation_metrics": _metric_rows(task_kind, first.get("parent_metrics") or {}),
                "rounds": round_records,
            }
        )
    return tasks


def build_platform_style_report(
    source: dict[str, Any], *, source_root: Path | None = None
) -> dict[str, Any]:
    _assert_no_secrets(source)
    source_format = source.get("format")
    historical = source_format == "brace-msi.local-platform-report-simulation.v1"
    corrected = source_format == "brace-msi.local-platform-report-simulation.v2"
    workspace_acceptance = source_format == "brace-msi.workspace-v2-acceptance.v1"
    if workspace_acceptance:
        tasks = _build_workspace_tasks(source, source_root)
    elif corrected:
        tasks = _build_corrected_tasks(source)
    elif historical:
        tasks = _build_historical_tasks(source)
    else:
        tasks = []
        for task in source["tasks"]:
            if int(task["round_count"]) != 10 or len(task["rounds"]) != 10:
                raise ValueError("platform-style report requires exactly ten completed rounds")
            tasks.append(
                {
                    "task_id": task["task"],
                    "display_name": TASK_NAMES.get(task["task"], str(task["task"])),
                    "task_kind": task["task_kind"],
                    "status": "记录完整",
                    "completed_rounds": 10,
                    "total_rounds": 10,
                    "final_adopted_model": _final_adopted_model(task),
                    "confirmation_sample_count": int(task["partition_counts"]["confirmation"]),
                    "evaluation_sample_label": "确认集样本",
                    "metric_heading": "本地独立确认集指标（非官方）",
                    "round_metric_heading": "公开适应流指标",
                    "cpu_seconds": sum(float(row.get("cpu_seconds", 0.0)) for row in task["rounds"]),
                    "runtime_seconds": sum(float(row.get("wall_seconds", 0.0)) for row in task["rounds"]),
                    "final_confirmation_metrics": _metric_rows(
                        task["task_kind"], task["final_confirmation_metrics"]
                    ),
                    "initial_confirmation_metrics": _metric_rows(
                        task["task_kind"], task["initial_confirmation_metrics"]
                    ),
                    "rounds": [_round_record(row, task["task_kind"]) for row in task["rounds"]],
                }
            )
    result = {
        "format": "brace-msi.platform-style-local-report.v1",
        "source_experiment_id": source.get("experiment_id", "PLATFORM-REPORT-SIM-001"),
        "evidence_boundary": (
            "workspace_v2_protocol_acceptance_reuses_public_validation"
            if workspace_acceptance
            else "single_frozen_public_validation_not_used_for_selection"
            if corrected
            else "repeated_public_validation_selection_contaminated_interface_demo_only"
            if historical
            else "local_confirmation_not_official_hidden_test"
        ),
        "boundary_text": (
            "该报告来自精确Docker镜像的workspace v2本地协议验收。十轮重复使用同一公开validation进行接口与选择测试，数值存在选择污染，只能证明训练、选择、回滚和资源边界可运行，不能作为独立泛化、隐藏测试或官方成绩。"
            if workspace_acceptance
            else "逐轮仅展示当前批次Gate证据；公开validation仅在十轮策略冻结后评估一次，未用于选择轮次。该validation历史已暴露，因此仍不是独立测试、官方隐藏测试或官方评分。"
            if corrected
            else "旧V1报告对同一公开validation重复评估并据此挑选轮次，存在验证集选择污染；只保留为界面和协议演示，不得作为性能或泛化证据。"
            if historical
            else "本报告使用冻结的本地模拟父模型与独立确认集，版式仅复用官方页面信息要素；不是官方隐藏测试、官方评分或平台试运行成绩。"
        ),
        "official_score": False,
        "official_trial_consumed": bool(source.get("official_trial_consumed", False)),
        "advisor_model": (
            str(source.get("model_name") or source.get("model_provider") or "local_host_gateway_substitute")
            if workspace_acceptance
            else source.get("advisor_model")
        ),
        "input_tokens": (
            sum(int(task.get("input_tokens", 0)) for task in tasks)
            if workspace_acceptance
            else int(source.get("input_tokens", 0))
        ),
        "output_tokens": (
            sum(int(task.get("output_tokens", 0)) for task in tasks)
            if workspace_acceptance
            else int(source.get("output_tokens", 0))
        ),
        "tasks": tasks,
    }
    _assert_no_secrets(result)
    return result


def _format_number(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value:,.6f}"
    return f"{value:.6f}"


def _metrics_html(metrics: list[dict[str, Any]]) -> str:
    return "".join(
        "<div class='metric'><span>"
        + html.escape(row["label"])
        + "</span><strong>"
        + html.escape(_format_number(float(row["value"])))
        + "</strong></div>"
        for row in metrics
    )


def render_platform_style_html(report: dict[str, Any]) -> str:
    sections = []
    for task in report["tasks"]:
        round_rows = []
        for row in task["rounds"]:
            record = row["experiment_record"]
            modification = record["modification"]
            advisor = record["advisor"]
            gate = record["gate"]
            resources = record["resources"]
            metrics_cell = (
                "<div class='gate-metrics'><b>稳定模型Gate</b>"
                + _metrics_html(row["adaptation_metrics"])
                + "</div>"
            )
            if row["candidate_metrics"]:
                metrics_cell += (
                    "<div class='gate-metrics candidate'><b>候选模型Gate</b>"
                    + _metrics_html(row["candidate_metrics"])
                    + "</div>"
                )
            round_rows.append(
                "<tr>"
                f"<td class='round-number'>{row['round']}</td>"
                f"<td>{metrics_cell}</td>"
                f"<td><span class='choice {'adopted' if gate['deployed'] else 'retained'}'>"
                f"{html.escape(row['model_selection'])}</span></td>"
                "<td><details><summary>查看本轮记录</summary><div class='record'>"
                f"<p><b>读取历史</b><span>{html.escape(record['history'])}</span></p>"
                f"<p><b>实验假设</b><span>{html.escape(record['hypothesis'])}</span></p>"
                f"<p><b>本轮修改</b><span>动作 {html.escape(modification['action'])}；"
                f"epochs {modification['epochs']}；学习率 {html.escape(str(modification['learning_rate']))}；"
                f"训练样本 {modification['training_sample_count']}</span></p>"
                f"<p><b>PyTRiO / Token</b><span>{html.escape(advisor['source'])}；"
                f"输入 {advisor['input_tokens']} / 输出 {advisor['output_tokens']}</span></p>"
                f"<p><b>门控结果</b><span>{html.escape(gate['reason'])}</span></p>"
                f"<p><b>资源</b><span>CPU {resources['cpu_seconds']:.6f} 秒；"
                f"运行 {resources['runtime_seconds']:.6f} 秒；峰值RSS {resources['peak_rss_bytes']:,} 字节</span></p>"
                "</div></details></td></tr>"
            )
        sections.append(
            "<section class='task'>"
            f"<h2>{html.escape(task['display_name'])}</h2>"
            "<span class='status'>● 记录完整</span>"
            "<div class='summary-grid'>"
            f"<div><span>完成轮次</span><strong>{task['completed_rounds']} / {task['total_rounds']}</strong></div>"
            f"<div><span>最终采用</span><strong>{html.escape(task['final_adopted_model'])}</strong></div>"
                f"<div><span>{html.escape(task['evaluation_sample_label'])}</span><strong>{task['confirmation_sample_count']:,}</strong></div>"
            f"<div><span>CPU 用时</span><strong>{task['cpu_seconds']:.6f} 秒</strong></div>"
            f"<div><span>运行时间</span><strong>{task['runtime_seconds']:.6f} 秒</strong></div>"
            "</div>"
            f"<h3>{html.escape(task['metric_heading'])}</h3>"
            f"<div class='metrics-grid'>{_metrics_html(task['final_confirmation_metrics'])}</div>"
            f"<table><thead><tr><th>轮次</th><th>{html.escape(task['round_metric_heading'])}</th><th>模型选择</th><th>实验记录</th></tr></thead>"
            f"<tbody>{''.join(round_rows)}</tbody></table></section>"
        )
    return """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>BRACE-MSI 本地正式流程复演</title>
<style>
:root{--ink:#2c241f;--muted:#746a62;--line:#ded7cf;--paper:#fffdfa;--soft:#f7f3ed;--green:#1f7250;--orange:#a75232}
*{box-sizing:border-box}body{margin:0;background:#f3efe9;color:var(--ink);font:14px/1.55 system-ui,"Microsoft YaHei",sans-serif}
main{max-width:1180px;margin:32px auto;padding:0 22px}.hero,.task{background:var(--paper);border:1px solid #e5ded6;border-radius:14px;box-shadow:0 8px 24px #4a352512;padding:26px;margin-bottom:24px}
h1{margin:0 0 8px;font-size:26px}h2{margin:0 0 8px;font-size:21px}h3{margin:28px 0 12px;font-size:16px}.boundary{padding:13px 16px;border-left:4px solid var(--orange);background:#fff4ed;color:#71351f}.status{display:inline-block;color:var(--green);background:#e9f4ee;border-radius:999px;padding:4px 10px;font-size:12px}
.summary-grid{display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:18px;margin:24px 0}.summary-grid div,.metric{display:flex;flex-direction:column;gap:5px}.summary-grid span,.metric span{color:var(--muted);font-size:12px}.summary-grid strong,.metric strong{font-weight:600}.metrics-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;background:var(--soft);padding:16px;border-radius:10px}
table{width:100%;border-collapse:collapse;margin-top:22px}th{background:#eee9e1;text-align:left;font-weight:600}th,td{padding:14px 12px;border-bottom:1px solid var(--line);vertical-align:top}.round-number{width:54px;text-align:center;font-weight:700}.choice{display:inline-block;border-radius:999px;padding:5px 10px;font-size:12px}.adopted{background:#e6f2ea;color:var(--green)}.retained{background:#f0ece6;color:#665d55}
details summary{cursor:pointer;font-weight:600}.record{margin-top:12px;padding:12px 14px;background:var(--soft);border-radius:8px}.record p{display:grid;grid-template-columns:110px 1fr;gap:12px;margin:8px 0}.record b{font-size:12px}.record span{overflow-wrap:anywhere}
.gate-metrics{padding:6px 0}.gate-metrics+.gate-metrics{margin-top:8px;padding-top:10px;border-top:1px dashed var(--line)}.gate-metrics>b{display:block;color:var(--muted);font-size:12px;margin-bottom:4px}.gate-metrics .metric{display:inline-flex;min-width:150px;margin-right:14px}.gate-metrics.candidate{background:#fbf8f3;padding:9px;border-radius:7px}
@media(max-width:850px){.summary-grid{grid-template-columns:repeat(2,1fr)}.metrics-grid{grid-template-columns:1fr}table{display:block;overflow-x:auto}}
</style></head><body><main><header class='hero'><h1>BRACE-MSI 本地正式流程复演</h1>
<p class='boundary'><b>证据边界：</b>""" + html.escape(report["boundary_text"]) + """</p>
<p>Agent：""" + html.escape(str(report.get("advisor_model") or "未启用")) + """　|　总Token：输入 """ + str(report["input_tokens"]) + " / 输出 " + str(report["output_tokens"]) + "</p></header>" + "".join(sections) + "</main></body></html>"


def render_existing_report(input_path: Path, output_dir: Path) -> tuple[Path, Path]:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    report = build_platform_style_report(source, source_root=input_path.parent)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "platform-style-report.json"
    html_path = output_dir / "platform-style-report.html"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    html_path.write_text(render_platform_style_html(report), encoding="utf-8")
    return json_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    json_path, html_path = render_existing_report(args.input, args.output_dir)
    print(json.dumps({"json": str(json_path), "html": str(html_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
