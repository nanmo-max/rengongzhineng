"""Render a local workspace-v2 acceptance result in an official-style report.

The report is intentionally presentation-only.  It never invents hidden metrics,
official billing, or an official pass/fail decision.
"""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
from typing import Any


TASK_NAMES = {
    "A": "A · 气体识别",
    "B": "B · 轴承寿命",
    "C": "C · 发动机寿命",
}


def build_report(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("format") != "brace-msi.workspace-v2-acceptance.v1":
        raise ValueError("unsupported workspace-v2 acceptance format")
    if source.get("scope") != "local_protocol_only_not_official_score":
        raise ValueError("acceptance scope is not local protocol only")
    if source.get("valid") is not True:
        raise ValueError("acceptance result is not valid")
    profiles = source.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != set(TASK_NAMES):
        raise ValueError("acceptance result must contain profiles A, B and C")

    tasks = []
    completed_rounds = 0
    model_calls = 0
    predictions = 0
    candidates = 0
    for profile in TASK_NAMES:
        raw = profiles[profile]
        rounds = raw.get("rounds")
        if not isinstance(rounds, list) or len(rounds) != 10:
            raise ValueError(f"profile {profile} must contain exactly ten rounds")
        normalized_rounds = []
        for expected, row in enumerate(rounds, start=1):
            if row.get("round_index") != expected:
                raise ValueError(f"profile {profile} round order is invalid")
            call_ids = row.get("model_call_ids")
            if not isinstance(call_ids, list):
                raise ValueError(f"profile {profile} model call ids are invalid")
            if not call_ids:
                raise ValueError(
                    f"profile {profile} round {expected} has no model call receipt"
                )
            normalized_rounds.append(
                {
                    "round_index": expected,
                    "selected_artifact_id": str(row.get("selected_artifact_id", "")),
                    "candidate_submitted": bool(row.get("candidate_submitted")),
                    "model_call_ids": [str(item) for item in call_ids],
                    "parent_checkpoint_sha256": str(row.get("parent_checkpoint_sha256", "")),
                }
            )
        task_calls = sum(len(row["model_call_ids"]) for row in normalized_rounds)
        task_candidates = sum(int(row["candidate_submitted"]) for row in normalized_rounds)
        task_predictions = int(raw.get("prediction_smoke_rows", 0))
        tasks.append(
            {
                "profile": profile,
                "name": TASK_NAMES[profile],
                "rounds_completed": len(normalized_rounds),
                "rounds_expected": 10,
                "model_calls": task_calls,
                "candidate_submissions": task_candidates,
                "retained_rounds": 10 - task_candidates,
                "prediction_smoke_rows": task_predictions,
                "final_artifact_id": str(raw.get("final_artifact_id", "")),
                "hidden_metrics": None,
                "rounds": normalized_rounds,
            }
        )
        completed_rounds += len(normalized_rounds)
        model_calls += task_calls
        predictions += task_predictions
        candidates += task_candidates

    return {
        "format": "brace-msi.workspace-v2-platform-style.v1",
        "scope": "local_protocol_only_not_official_score",
        "status": "completed_local_simulation",
        "image": str(source.get("image", "")),
        "summary": {
            "completed_rounds": completed_rounds,
            "expected_rounds": 30,
            "model_calls": model_calls,
            "prediction_smoke_rows": predictions,
            "candidate_submissions": candidates,
        },
        "official_fields": {
            "hidden_metrics": "正式平台产生，本地不可获得",
            "input_tokens": "模拟宿主未计入官方结算",
            "output_tokens": "模拟宿主未计入官方结算",
            "cpu_time": "本地模拟未汇总",
            "runtime": "本地模拟未汇总",
            "official_score": "未运行",
        },
        "tasks": tasks,
    }


def _round_rows(task: dict[str, Any]) -> str:
    rows = []
    for row in task["rounds"]:
        selected = escape(row["selected_artifact_id"])
        action = "提交候选" if row["candidate_submitted"] else "保留当前模型"
        calls = escape(", ".join(row["model_call_ids"]))
        parent = escape(row["parent_checkpoint_sha256"])
        rows.append(
            "<tr>"
            f"<td>{row['round_index']}</td><td>{action}</td><td><code>{selected}</code></td>"
            f"<td><code>{calls}</code></td><td><code class=\"hash\">{parent}</code></td>"
            "</tr>"
        )
    return "".join(rows)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    task_sections = []
    for task in report["tasks"]:
        task_sections.append(
            f"""
            <section class="task">
              <div class="task-title"><h2>{escape(task['name'])}</h2><span class="pill">记录完整</span></div>
              <div class="metrics">
                <div><span>完成轮次</span><strong>{task['rounds_completed']} / {task['rounds_expected']}</strong></div>
                <div><span>宿主模型调用</span><strong>{task['model_calls']}</strong></div>
                <div><span>候选提交</span><strong>{task['candidate_submissions']}</strong></div>
                <div><span>独立预测样本</span><strong>{task['prediction_smoke_rows']}</strong></div>
              </div>
              <div class="notice"><b>隐藏测试指标：</b>正式平台产生，本地不可获得</div>
              <p class="final">最终选择：<code>{escape(task['final_artifact_id'])}</code></p>
              <div class="table-wrap"><table><thead><tr><th>轮次</th><th>模型选择</th><th>选中产物</th><th>模型调用收据</th><th>父检查点</th></tr></thead>
              <tbody>{_round_rows(task)}</tbody></table></div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BRACE-MSI 训练与评测报告</title>
<style>
:root{{--bg:#f6f2eb;--card:#fff;--ink:#322d28;--muted:#7c736a;--line:#e5ddd3;--accent:#9f4b32;--ok:#4b7155}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 system-ui,"Microsoft YaHei",sans-serif}}
.page{{max-width:1180px;margin:30px auto;padding:0 20px 60px}}.hero,.task{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:28px;margin-bottom:20px;box-shadow:0 8px 28px #4c39220b}}
h1{{font-size:28px;margin:0 0 10px}}h2{{font-size:20px;margin:0}}.subtitle{{color:var(--muted)}}.banner{{margin:20px 0;padding:14px 18px;border-radius:9px;background:#fff3e4;border:1px solid #e8c49b;color:#7e4725;font-weight:700}}
.metrics{{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:12px;margin-top:20px}}.metrics div{{border-top:1px solid var(--line);padding-top:12px}}.metrics span{{display:block;color:var(--muted);font-size:12px}}.metrics strong{{font-size:20px}}
.task-title{{display:flex;justify-content:space-between;align-items:center}}.pill{{background:#e9f3eb;color:var(--ok);border-radius:999px;padding:5px 10px;font-size:12px}}.notice{{margin:18px 0;padding:12px;background:#f7f5f2;border-radius:8px}}.final{{color:var(--muted)}}
.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:860px}}th,td{{padding:11px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-size:12px;color:var(--muted);background:#faf8f5}}code{{font:12px/1.4 ui-monospace,Consolas,monospace}}.hash{{display:block;max-width:250px;overflow-wrap:anywhere}}
@media(max-width:760px){{.metrics{{grid-template-columns:repeat(2,1fr)}}.hero,.task{{padding:18px}}}}
</style></head><body><main class="page">
<section class="hero"><h1>训练与评测报告</h1><p class="subtitle">BRACE-MSI · contest.harness.workspace.v2 独立容器复演</p>
<div class="banner">本地协议模拟，不计正式成绩</div>
<div class="metrics">
<div><span>工业模型优化流程</span><strong>已完成</strong></div>
<div><span>完成轮次</span><strong>{summary['completed_rounds']} / {summary['expected_rounds']}</strong></div>
<div><span>宿主模型调用</span><strong>{summary['model_calls']}</strong></div>
<div><span>预测样本总数</span><strong>{summary['prediction_smoke_rows']}</strong></div>
<div><span>用量结算</span><strong>非官方</strong></div>
<div><span>CPU用时</span><strong>本地模拟未汇总</strong></div>
<div><span>运行用时</span><strong>本地模拟未汇总</strong></div>
</div><p class="subtitle">输入Token / 输出Token：模拟宿主未计入官方结算；隐藏测试指标与正式成绩须由官方平台产生。</p></section>
{''.join(task_sections)}
</main></body></html>"""


def write_report(input_path: Path, output: Path) -> tuple[Path, Path]:
    source = json.loads(Path(input_path).read_text(encoding="utf-8"))
    report = build_report(source)
    output.mkdir(parents=True, exist_ok=False)
    json_path = output / "platform-style-report.json"
    html_path = output / "platform-style-report.html"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    html_path.write_text(render_html(report), encoding="utf-8")
    return json_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    json_path, html_path = write_report(args.input, args.output)
    print(json.dumps({"json": str(json_path), "html": str(html_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
