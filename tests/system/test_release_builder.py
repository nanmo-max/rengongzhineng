from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts.build_release_candidate import (
    container_manifest_fields,
    load_container_acceptance,
    load_release_verification,
    run_release_checks,
)


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


def test_container_acceptance_requires_matching_archive_hash(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    archive.write_bytes(b"verified image archive")
    evidence = tmp_path / "container.json"
    evidence.write_text(
        '{"release_id":"BRACE-MSI-0.3.0rc3",'
        '"image":{"under_2gb":true,"runtime_uid":10001,"forbidden_files":[],"pip_check":"PASS"},'
        '"runtime_acceptance":{"network":"none","cpus":4,"memory_bytes":8589934592,"status":"completed"},'
        '"archive":{"size_bytes":22,"sha256":"not-the-real-hash","docker_load_verified":true}}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="archive SHA-256"):
        load_container_acceptance(evidence, archive)


def test_container_acceptance_returns_verified_upload_metadata(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    archive.write_bytes(b"verified image archive")
    evidence = tmp_path / "container.json"
    evidence.write_text(
        '{"release_id":"BRACE-MSI-0.3.0rc3",'
        '"image":{"under_2gb":true,"runtime_uid":10001,"forbidden_files":[],"pip_check":"PASS"},'
        '"runtime_acceptance":{"network":"none","cpus":4,"memory_bytes":8589934592,"status":"completed"},'
        '"archive":{"size_bytes":22,"sha256":"08d1e8fcc548b3ddeda461474b03d0ca3091277c9314429bf69d6cc205f52695",'
        '"docker_load_verified":true}}',
        encoding="utf-8",
    )

    result = load_container_acceptance(evidence, archive)

    assert result["source_path"] == str(archive.resolve())
    assert result["sha256"] == "08d1e8fcc548b3ddeda461474b03d0ca3091277c9314429bf69d6cc205f52695"
    assert result["size_bytes"] == 22


def test_container_manifest_fields_mark_real_runtime_gates_passed() -> None:
    fields = container_manifest_fields(
        {"size_bytes": 22, "sha256": "a" * 64}, "BRACE-MSI-image.tar"
    )

    assert fields["release_gates"] == {
        "docker_image_build": "PASS",
        "linux_4core_8gb_container": "PASS",
    }
    assert fields["image_artifact"] == {
        "path": "BRACE-MSI-image.tar",
        "size_bytes": 22,
        "sha256": "a" * 64,
        "format": "docker save tar",
    }
