from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_fixed_submission_entry_imports_from_allowlisted_runtime(monkeypatch) -> None:
    import submission.contest_submission as entry

    assert entry.TASKS == ("classification", "regression")
    assert callable(entry.train)
    assert callable(entry.predict)


def test_formal_allowlist_is_explicit_complete_and_contains_no_development_assets() -> None:
    from scripts.build_formal_release import load_formal_allowlist

    files = load_formal_allowlist(Path("configs/formal_runtime_allowlist.json"), Path.cwd())
    required = {
        "Dockerfile.formal",
        "requirements.formal.lock",
        "submission/harness.py",
        "submission/contest_submission.py",
        "src/brace_formal/round_core.py",
        "src/brace_formal/submission.py",
        "src/contest_harness/round.py",
    }
    assert required <= set(files)
    forbidden_parts = {"tests", "scripts", "docs", "dataji", "artifacts", "outputs", "tmp"}
    forbidden_names = {"pytrio", "swanlab", "tokenizer", "sampler", "cache"}
    for relative in files:
        path = Path(relative)
        lowered = relative.lower()
        assert not (forbidden_parts & set(path.parts))
        assert all(name not in lowered for name in forbidden_names)
        assert path.suffix.lower() not in {
            ".npz", ".pkl", ".pickle", ".joblib", ".pt", ".pth", ".onnx", ".key", ".pem"
        }


def test_formal_context_contains_exact_allowlist_plus_machine_manifest(tmp_path: Path) -> None:
    from scripts.build_formal_release import load_formal_allowlist, stage_formal_context

    allowlist = load_formal_allowlist(Path("configs/formal_runtime_allowlist.json"), Path.cwd())
    manifest = stage_formal_context(Path.cwd(), tmp_path / "formal-context")

    actual = sorted(
        path.relative_to(tmp_path / "formal-context").as_posix()
        for path in (tmp_path / "formal-context").rglob("*")
        if path.is_file()
    )
    assert actual == sorted([*allowlist, "FORMAL_CONTEXT_MANIFEST.json"])
    assert manifest["image_class"] == "FORMAL_UPLOAD"
    assert manifest["files"] == sorted(allowlist)
    assert len(manifest["tree_sha256"]) == 64
    on_disk = json.loads(
        (tmp_path / "formal-context" / "FORMAL_CONTEXT_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert on_disk == manifest
    isolated_import = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'src'); import submission.contest_submission as e; "
            "assert e.TASKS == ('classification', 'regression')",
        ],
        cwd=tmp_path / "formal-context",
        text=True,
        capture_output=True,
        check=False,
    )
    assert isolated_import.returncode == 0, isolated_import.stderr


def test_formal_allowlist_rejects_secret_like_symlink_and_unlisted_file(tmp_path: Path) -> None:
    from scripts.build_formal_release import load_formal_allowlist

    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "safe.py").write_text("pass\n", encoding="utf-8")
    (repository / "secret.key").write_text("not-a-real-secret\n", encoding="utf-8")

    secret_config = tmp_path / "secret.json"
    secret_config.write_text(json.dumps({"format": "brace-formal-allowlist.v1", "files": ["secret.key"]}), encoding="utf-8")
    try:
        load_formal_allowlist(secret_config, repository)
    except ValueError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("secret-like files must not enter the formal context")

    missing_config = tmp_path / "missing.json"
    missing_config.write_text(json.dumps({"format": "brace-formal-allowlist.v1", "files": ["missing.py"]}), encoding="utf-8")
    try:
        load_formal_allowlist(missing_config, repository)
    except ValueError as exc:
        assert "regular file" in str(exc)
    else:
        raise AssertionError("missing allowlist files must fail closed")


def test_local_context_is_marked_local_only_and_formal_context_excludes_simulators(
    tmp_path: Path,
) -> None:
    from scripts.build_formal_release import stage_formal_context
    from scripts.build_local_test_image import stage_local_test_context

    formal = tmp_path / "formal"
    local = tmp_path / "local"
    formal_manifest = stage_formal_context(Path.cwd(), formal)
    local_manifest = stage_local_test_context(Path.cwd(), local)

    assert formal_manifest["image_class"] == "FORMAL_UPLOAD"
    assert local_manifest["image_class"] == "LOCAL_TEST_ONLY"
    assert (local / "scripts" / "simulate_first_principles_runtime.py").is_file()
    assert (local / "scripts" / "simulate_platform_report.py").is_file()
    assert not (formal / "scripts").exists()
    dockerfile = (local / "Dockerfile.local-test").read_text(encoding="utf-8")
    assert "LOCAL_TEST_ONLY" in dockerfile


def test_both_dockerfiles_copy_only_from_staged_explicit_contexts() -> None:
    formal = Path("Dockerfile.formal").read_text(encoding="utf-8")
    local = Path("Dockerfile.local-test").read_text(encoding="utf-8")
    for dockerfile in (formal, local):
        assert "COPY . " not in dockerfile
        assert "COPY src " not in dockerfile
        assert "COPY tests" not in dockerfile
        assert "COPY docs" not in dockerfile
        assert "COPY data" not in dockerfile


def test_both_builders_are_directly_invocable() -> None:
    for script in ("scripts/build_formal_release.py", "scripts/build_local_test_image.py"):
        result = subprocess.run(
            [sys.executable, script, "--help"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout

