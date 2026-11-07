"""Offline, dependency-free static HTML reporting."""

from __future__ import annotations

from html import escape
from typing import Any


def _table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html_report(report: dict[str, Any]) -> str:
    task_sections: list[str] = []
    for task in report.get("tasks", []):
        metrics = task.get("metrics", {})
        resources = task.get("resources", {})
        candidates = task.get("candidates", [])
        metric_table = _table(
            ["Metric", "Value"], [[key, value] for key, value in metrics.items()]
        )
        resource_table = _table(
            ["Resource", "Value"], [[key, value] for key, value in resources.items()]
        )
        candidate_table = _table(
            ["Action", "Accepted", "Reason"],
            [
                [item.get("action", ""), item.get("accepted", ""), item.get("reason", "")]
                for item in candidates
            ],
        )
        task_sections.append(
            f"<section><h2>{escape(str(task.get('task_id', 'unknown task')))}</h2>"
            f"<p>Kind: {escape(str(task.get('task_kind', 'unknown')))} · "
            f"Status: {escape(str(task.get('status', 'unknown')))}</p>"
            f"<h3>Metrics</h3>{metric_table}<h3>Resources</h3>{resource_table}"
            f"<h3>Candidate decisions</h3>{candidate_table}</section>"
        )
    title = escape(str(report.get("title", "BRACE-MSI report")))
    scope = escape(str(report.get("scope", "unspecified")))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#172033}}
h1,h2,h3{{color:#0f3d65}} section{{border:1px solid #d9e2ec;border-radius:10px;padding:1rem;margin:1rem 0}}
table{{border-collapse:collapse;width:100%;margin:.5rem 0 1rem}}th,td{{border:1px solid #d9e2ec;padding:.45rem;text-align:left}}
th{{background:#eef5fb}} .scope{{display:inline-block;background:#fff3cd;padding:.25rem .5rem;border-radius:4px}}
</style></head><body><h1>{title}</h1><p class="scope">Evidence scope: {scope}</p>{''.join(task_sections)}</body></html>"""
