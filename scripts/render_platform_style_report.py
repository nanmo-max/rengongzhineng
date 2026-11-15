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


def build_platform_style_report(source: dict[str, Any]) -> dict[str, Any]:
    _assert_no_secrets(source)
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
        "source_experiment_id": source["experiment_id"],
        "evidence_boundary": "local_confirmation_not_official_hidden_test",
        "official_score": False,
        "official_trial_consumed": bool(source.get("official_trial_consumed", False)),
        "advisor_model": source.get("advisor_model"),
        "input_tokens": int(source.get("input_tokens", 0)),
        "output_tokens": int(source.get("output_tokens", 0)),
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
            round_rows.append(
                "<tr>"
                f"<td class='round-number'>{row['round']}</td>"
                f"<td>{_metrics_html(row['adaptation_metrics'])}</td>"
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
            f"<div><span>确认集样本</span><strong>{task['confirmation_sample_count']:,}</strong></div>"
            f"<div><span>CPU 用时</span><strong>{task['cpu_seconds']:.6f} 秒</strong></div>"
            f"<div><span>运行时间</span><strong>{task['runtime_seconds']:.6f} 秒</strong></div>"
            "</div>"
            "<h3>本地独立确认集指标（非官方）</h3>"
            f"<div class='metrics-grid'>{_metrics_html(task['final_confirmation_metrics'])}</div>"
            "<table><thead><tr><th>轮次</th><th>公开适应流指标</th><th>模型选择</th><th>实验记录</th></tr></thead>"
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
@media(max-width:850px){.summary-grid{grid-template-columns:repeat(2,1fr)}.metrics-grid{grid-template-columns:1fr}table{display:block;overflow-x:auto}}
</style></head><body><main><header class='hero'><h1>BRACE-MSI 本地正式流程复演</h1>
<p class='boundary'><b>证据边界：</b>本报告使用冻结的本地模拟父模型与独立确认集，版式仅复用官方页面信息要素；不是官方隐藏测试、官方评分或平台试运行成绩。</p>
<p>Agent：""" + html.escape(str(report.get("advisor_model") or "未启用")) + """　|　总Token：输入 """ + str(report["input_tokens"]) + " / 输出 " + str(report["output_tokens"]) + "</p></header>" + "".join(sections) + "</main></body></html>"


def render_existing_report(input_path: Path, output_dir: Path) -> tuple[Path, Path]:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    report = build_platform_style_report(source)
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
