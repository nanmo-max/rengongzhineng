from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts.build_release_candidate import load_release_verification, run_release_checks


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


def test_release_verification_accepts_runtime_commit_with_docs_only_followups(tmp_path: Path) -> None:
    evidence = tmp_path / "verification.json"
    evidence.write_text(
        '{"runtime_commit":"abc","pytest":{"status":"PASS","passed":221},'
        '"clean_environment":{"status":"PASS","version":"0.3.0rc3"},'
        '"pip_check":{"status":"PASS"},"compileall":{"status":"PASS"}}',
        encoding="utf-8",
    )

    result = load_release_verification(
        evidence,
        current_commit="def",
        changed_paths=("docs/STATUS.md", "scripts/build_release_candidate.py"),
        is_ancestor=True,
    )

    assert result["pytest"]["passed"] == 221


def test_release_verification_rejects_runtime_source_change(tmp_path: Path) -> None:
    evidence = tmp_path / "verification.json"
    evidence.write_text(
        '{"runtime_commit":"abc","pytest":{"status":"PASS","passed":221},'
        '"clean_environment":{"status":"PASS","version":"0.3.0rc3"},'
        '"pip_check":{"status":"PASS"},"compileall":{"status":"PASS"}}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="runtime-affecting"):
        load_release_verification(
            evidence,
            current_commit="def",
            changed_paths=("src/brace_msi/harness.py",),
            is_ancestor=True,
        )
