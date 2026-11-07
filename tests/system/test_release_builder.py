from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts.build_release_candidate import run_release_checks


def test_release_checks_refuse_to_mark_failed_regression_as_passed(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command, **kwargs):
        calls.append(tuple(command))
        return CompletedProcess(command, 1, stdout="failed", stderr="boom")

    with pytest.raises(RuntimeError, match="release check failed: pytest"):
        run_release_checks(tmp_path, python="python", runner=runner)

    assert calls == [("python", "-m", "pytest", "-q", "--tb=short")]


def test_release_checks_record_only_successful_commands(tmp_path: Path) -> None:
    def runner(command, **kwargs):
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    results = run_release_checks(tmp_path, python="python", runner=runner)

    assert set(results) == {"pytest", "pip_check", "compileall"}
    assert all(result["status"] == "PASS" for result in results.values())
