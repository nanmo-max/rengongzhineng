from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
from typing import Any


TASK_NAMES = {"A": "Gas 气体识别", "B": "Bearing 轴承RUL", "C": "Engine 发动机RUL"}


def _metric_text(metrics: dict[str, Any] | None) -> str:
    if not metrics:
        return "—"
    return " · ".join(f"{key} {float(value):.6g}" for key, value in metrics.items())


def build_report(run_root: Path, *, confirmation_exposure_index: int) -> dict[str, Any]:
    root = Path(run_root).resolve()
    tasks: dict[str, Any] = {}
    for profile in "ABC":
        summary = json.loads((root / profile / "summary.json").read_text(encoding="utf-8"))
        rounds = []
        for row in summary["rounds"]:
            receipt = row["runtime_receipt"]
            rounds.append(
                {
                    "round": row["round_index"],
                    "unseen_samples": receipt["sample_count"],
                    "prequential_metrics": row["prequential_metrics"],
                    "candidate_gate_stable": row["candidate_gate_metrics"]["stable"],
                    "candidate_gate_candidate": row["candidate_gate_metrics"]["candidate"],
                    "action": receipt["decision"]["executed_action"],
                    "candidate_trained": receipt["candidate_trained"],
                    "model_selection": "deploy" if receipt["deployed"] else "retain",
                    "gate_reason": receipt["gate_reason"],
                    "cpu_seconds": receipt["cpu_seconds"],
                    "wall_seconds": receipt["wall_seconds"],
                    "peak_rss_bytes": receipt["peak_rss_bytes"],
                    "input_tokens": receipt["input_tokens"],
                    "output_tokens": receipt["output_tokens"],
                    "data_sha256": receipt["data_sha256"],
                    "parent_checkpoint_sha256": receipt["parent_checkpoint_sha256"],
                    "checkpoint_sha256": receipt["checkpoint_sha256"],
                }
            )
        deployed = [row["round"] for row in rounds if row["model_selection"] == "deploy"]
        tasks[profile] = {
            "name": TASK_NAMES[profile],
            "rounds_completed": len(rounds),
            "candidate_count": sum(row["candidate_trained"] for row in rounds),
            "accepted_count": len(deployed),
            "final_model_origin": f"round-{deployed[-1]:02d}" if deployed else "initial_parent",
            "prequential_metrics": [row["prequential_metrics"] for row in rounds],
            "local_final_confirmation": summary["local_final_confirmation"],
            "confirmation_scope": (
                "historically_exposed_local_confirmation"
                if confirmation_exposure_index > 1
                else "single_read_local_confirmation"
            ),
            "cpu_seconds": sum(row["cpu_seconds"] for row in rounds),
            "wall_seconds": sum(row["wall_seconds"] for row in rounds),
            "peak_rss_bytes": max(row["peak_rss_bytes"] for row in rounds),
            "input_tokens": summary["input_tokens"],
            "output_tokens": summary["output_tokens"],
            "parent_chain_valid": summary["parent_chain_valid"],
            "confirmation_read_count": summary["confirmation_read_count"],
            "rounds": rounds,
        }
    return {
        "format": "brace-msi.official-flow-report.v1",
        "status": "completed",
        "hidden_test_status": "not_started_not_available",
        "evidence_scope": "local_protocol_and_task_stream_simulation_not_official_hidden_score",
        "confirmation_exposure_index": confirmation_exposure_index,
        "tasks": tasks,
    }


def render_html(report: dict[str, Any]) -> str:
    cards = []
    for profile, task in report["tasks"].items():
        rows = []
        for row in task["rounds"]:
            rows.append(
                "<tr>"
                f"<td>{row['round']}</td><td>{row['unseen_samples']:,}</td>"
                f"<td>{escape(_metric_text(row['prequential_metrics']))}</td>"
                f"<td>{escape(_metric_text(row['candidate_gate_stable']))}</td>"
                f"<td>{escape(_metric_text(row['candidate_gate_candidate']))}</td>"
                f"<td>{escape(row['action'])}</td><td>{'部署' if row['model_selection']=='deploy' else '保留'}</td>"
                f"<td>{escape(row['gate_reason'])}</td><td>{row['cpu_seconds']:.3f}s</td>"
                "</tr>"
            )
        confirmation = task["local_final_confirmation"]
        cards.append(
            f"<section><h2>{escape(task['name'])}</h2>"
            "<div class='grid'>"
            f"<div><b>完成轮次</b><span>{task['rounds_completed']}/10</span></div>"
            f"<div><b>真实候选</b><span>{task['candidate_count']}（采用 {task['accepted_count']}）</span></div>"
            f"<div><b>最终模型</b><span>{escape(task['final_model_origin'])}</span></div>"
            f"<div><b>本地确认样本</b><span>{confirmation['sample_count']:,}</span></div>"
            f"<div><b>本地确认指标</b><span>{escape(_metric_text(confirmation['metrics']))}</span></div>"
            f"<div><b>CPU / 峰值RSS</b><span>{task['cpu_seconds']:.3f}s / {task['peak_rss_bytes']/1048576:.1f}MiB</span></div>"
            "</div>"
            "<table><thead><tr><th>轮次</th><th>未见样本</th><th>Prequential</th><th>Gate稳定</th>"
            "<th>Gate候选</th><th>动作</th><th>选择</th><th>原因</th><th>CPU</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>BRACE-MSI 官方流程本地复演</title>
<style>body{{font-family:system-ui,'Microsoft YaHei',sans-serif;margin:32px;background:#f6f3ee;color:#28221d}}h1{{margin-bottom:8px}}.notice{{background:#fff3cd;border:1px solid #e5bd52;padding:14px;border-radius:10px}}section{{background:white;margin:20px 0;padding:20px;border-radius:14px;box-shadow:0 3px 16px #0001}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 18px}}.grid div{{background:#f8f6f2;padding:10px;border-radius:8px}}.grid b,.grid span{{display:block}}.grid span{{margin-top:5px}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border-bottom:1px solid #e6e0d8;padding:8px;text-align:left;vertical-align:top}}th{{background:#f4eee7}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}table{{display:block;overflow:auto}}}}</style></head>
<body><h1>BRACE-MSI 训练与评测报告（本地官方流程复演）</h1>
<p class='notice'><b>证据边界：</b>正式隐藏测试尚未开始且完全不可见。本报告使用本地任务规律流验证“先预测、后反馈、再训练门控”的生命周期；本地确认已是第 {report['confirmation_exposure_index']} 次暴露，不能作为独立隐藏成绩或继续选参。</p>
<p>隐藏测试状态：<b>{escape(report['hidden_test_status'])}</b> · Prequential指标不反馈ActionPolicy · 最终模型不按确认指标回选轮次</p>
{''.join(cards)}</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--confirmation-exposure-index", type=int, default=1)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = build_report(
        args.run_root, confirmation_exposure_index=args.confirmation_exposure_index
    )
    (output / "official-flow-report.json").write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "official-flow-report.html").write_text(render_html(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
