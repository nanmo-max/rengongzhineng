import json
import os
from pathlib import Path
import subprocess
import sys

from brace_msi.packaging import audit_docker_context
from brace_msi.reporting import render_html_report


def _report() -> dict:
    return {
        "title": "BRACE-MSI <proxy>",
        "scope": "proxy_only",
        "tasks": [
            {
                "task_id": "gas",
                "task_kind": "classification",
                "status": "completed",
                "metrics": {"accuracy": 0.8, "macro_f1": 0.75},
                "resources": {"cpu_seconds": 1.2, "peak_rss_bytes": 1024},
                "candidates": [
                    {"action": "incremental_update", "accepted": True, "reason": "gain"}
                ],
            }
        ],
    }


def test_static_report_is_offline_self_contained_and_escapes_content() -> None:
    html = render_html_report(_report())

    assert "BRACE-MSI &lt;proxy&gt;" in html
    assert "gas" in html
    assert "incremental_update" in html
    assert "accuracy" in html
    assert "https://" not in html
    assert "<script src=" not in html


def test_repository_docker_context_excludes_data_weights_secrets_and_is_under_limit() -> None:
    root = Path(__file__).resolve().parents[2]
    audit = audit_docker_context(root)

    assert audit.forbidden_files == ()
    assert audit.total_bytes < 2_000_000_000
    assert any(path.name == "Dockerfile" for path in audit.included_files)
    assert not any("dataji" in path.parts for path in audit.included_files)
    assert not any("artifacts" in path.parts for path in audit.included_files)


def test_python312_linux_release_uses_binary_compatible_psutil_and_no_source_builds() -> None:
    root = Path(__file__).resolve().parents[2]
    requirements = (root / "requirements.lock").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert "psutil==5.9.8" in requirements
    assert "--only-binary=:all:" in dockerfile
    assert "requirements-swanlab.lock" in dockerfile
    assert "pip install --no-cache-dir -r requirements-swanlab.lock" in dockerfile


def test_cli_renders_report_without_network_or_interaction(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    output = tmp_path / "report.html"
    source.write_text(json.dumps(_report()), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "brace_msi",
            "render-report",
            "--input",
            str(source),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert completed.returncode == 0, completed.stderr
    assert output.exists()
    assert "proxy_only" in output.read_text(encoding="utf-8")
