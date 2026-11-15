"""Replay frozen container rounds into an official-report-shaped local audit.

This tool never trains or changes a checkpoint.  It evaluates the already frozen
round checkpoints on the historically exposed public validation files so the
platform report lifecycle can be checked before consuming another trial.
"""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
from typing import Any

from brace_msi.official_metrics import nasa_asymmetric_score
from brace_msi.platform_runtime import _NativeModel, _metrics, _read_rows


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}


def _evaluate(checkpoint: Path, validation: Path, profile: str) -> dict[str, float]:
    model = _NativeModel.load(checkpoint)
    batch = _read_rows(validation, model, require_answers=True)
    metrics = _metrics(model, batch["x"], batch["y"])
    if profile == "C":
        predicted = model.predict_raw(batch["x"])
        metrics["nasa_score"] = nasa_asymmetric_score(batch["y"], predicted)
    return metrics


def _better(profile: str, candidate: dict[str, float], best: dict[str, float]) -> bool:
    if profile == "A":
        return candidate["macro_f1"] > best["macro_f1"]
    return candidate["rmse"] < best["rmse"]


def build_report(run_root: Path, package_root: Path) -> dict[str, Any]:
    tasks: dict[str, Any] = {}
    total_samples = 0
    total_input_tokens = 0
    total_output_tokens = 0
    for profile, package_name in PACKAGES.items():
        summary_path = run_root / profile / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        validation = package_root / package_name / "public" / "validation.jsonl"
        sample_count = sum(1 for line in validation.read_text(encoding="utf-8").splitlines() if line.strip())
        total_samples += sample_count
        rounds: list[dict[str, Any]] = []
        best_metrics: dict[str, float] | None = None
        best_round = 0
        for index, receipt in enumerate(summary["rounds"], 1):
            checkpoint = run_root / profile / f"round-{index:02d}" / "checkpoint.npz"
            metrics = _evaluate(checkpoint, validation, profile)
            adopted = best_metrics is None or _better(profile, metrics, best_metrics)
            if adopted:
                best_metrics = metrics
                best_round = index
            rounds.append(
                {
                    "round": index,
                    "public_validation_metrics": metrics,
                    "model_selection": "adopt" if adopted else "retain_previous",
                    "candidate_trained": bool(receipt["candidate_trained"]),
                    "deployed_by_harness": bool(receipt["deployed"]),
                    "executed_action": receipt["decision"]["executed_action"],
                    "cpu_seconds": receipt["cpu_seconds"],
                    "wall_seconds": receipt["wall_seconds"],
                    "peak_rss_bytes": receipt["peak_rss_bytes"],
                    "input_tokens": receipt["input_tokens"],
                    "output_tokens": receipt["output_tokens"],
                }
            )
        total_input_tokens += int(summary["input_tokens"])
        total_output_tokens += int(summary["output_tokens"])
        tasks[profile] = {
            "completed_rounds": 10,
            "selected_round": best_round,
            "selected_metrics": best_metrics,
            "evaluation_samples": sample_count,
            "cpu_seconds": sum(float(row["cpu_seconds"]) for row in summary["rounds"]),
            "wall_seconds": sum(float(row["wall_seconds"]) for row in summary["rounds"]),
            "rounds": rounds,
        }
    return {
        "format": "brace-msi.local-platform-report-simulation.v1",
        "status": "completed",
        "simulation_only": True,
        "official_score": False,
        "data_scope": "historically_exposed_public_validation",
        "selection_use": "protocol_verification_only_not_release_retuning",
        "predicted_sample_total": total_samples,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "tasks": tasks,
    }


def _render_html(report: dict[str, Any]) -> str:
    sections: list[str] = []
    for profile, task in report["tasks"].items():
        rows = []
        for row in task["rounds"]:
            metrics = ", ".join(f"{key}={value:.6f}" for key, value in row["public_validation_metrics"].items())
            rows.append(
                "<tr>"
                f"<td>{row['round']}</td><td>{escape(metrics)}</td>"
                f"<td>{escape(row['model_selection'])}</td>"
                f"<td>{escape(row['executed_action'])}</td>"
                f"<td>{row['cpu_seconds']:.4f}</td><td>{row['peak_rss_bytes']}</td>"
                "</tr>"
            )
        sections.append(
            f"<h2>{profile}</h2><p>10/10 rounds; selected round {task['selected_round']}; "
            f"samples {task['evaluation_samples']}</p>"
            "<table><thead><tr><th>Round</th><th>Metrics</th><th>Selection</th>"
            "<th>Action</th><th>CPU s</th><th>Peak RSS</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    return (
        "<!doctype html><meta charset='utf-8'><title>BRACE-MSI local platform report simulation</title>"
        "<style>body{font-family:system-ui;margin:32px;max-width:1200px}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ddd;padding:7px;text-align:left}th{background:#f5f1ec}.warn{color:#9b2c2c}</style>"
        "<h1>BRACE-MSI local platform report simulation</h1>"
        "<p class='warn'>Simulation only. Historically exposed public validation; not an official score and not used for retuning.</p>"
        f"<p>Total samples: {report['predicted_sample_total']}; Token: {report['input_tokens']}/{report['output_tokens']}</p>"
        + "".join(sections)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.output_root.exists():
        raise FileExistsError("output root must be new")
    args.output_root.mkdir(parents=True)
    report = build_report(args.run_root.resolve(), args.package_root.resolve())
    (args.output_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_root / "report.html").write_text(_render_html(report), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "predicted_sample_total": report["predicted_sample_total"],
        "selected_rounds": {key: value["selected_round"] for key, value in report["tasks"].items()},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
