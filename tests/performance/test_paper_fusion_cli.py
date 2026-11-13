from __future__ import annotations

import json
from pathlib import Path

from brace_msi.cli import main


def test_paper_fusion_validate_cli_reports_machine_result(
    tmp_path: Path, capsys
) -> None:
    output = tmp_path / "run"
    output.mkdir()

    exit_code = main(["paper-fusion-run", "--output", str(output), "--validate-only"])

    result = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert result["valid"] is False
    assert result["errors"]
