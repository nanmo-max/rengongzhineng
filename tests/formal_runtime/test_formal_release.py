from pathlib import Path
import pytest


def test_formal_dockerfile_uses_runtime_allowlist_only() -> None:
    dockerfile = Path("Dockerfile.formal")
    assert dockerfile.is_file()
    text = dockerfile.read_text(encoding="utf-8")
    assert "COPY src/contest_harness /app/src/contest_harness" in text
    assert "COPY src/brace_formal /app/src/brace_formal" in text
    assert "COPY submission/harness.py /app/harness.py" in text
    assert "COPY submission/contest_submission.py /app/contest_submission.py" in text
    assert "COPY src ./src" not in text
    assert "pyproject.toml" not in text
    assert "requirements.lock" not in text
    forbidden = ("brace_msi", "pytrio", "swanlab", "scikit-learn", "scipy", "psutil")
    assert all(name not in text.lower() for name in forbidden)


def test_formal_requirements_are_exact_and_minimal() -> None:
    assert Path("requirements.formal.lock").read_text(encoding="utf-8").splitlines() == [
        "numpy==1.26.4"
    ]


def test_docker_context_excludes_recursive_python_caches() -> None:
    patterns = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "**/__pycache__/" in patterns
    assert "**/*.pyc" in patterns


def test_release_builder_rejects_unsafe_image_metadata() -> None:
    from scripts.build_formal_release import validate_image_metadata

    safe = {"Os": "linux", "Architecture": "amd64", "Size": 80_000_000, "Config": {"User": "10001:10001"}}
    assert validate_image_metadata(safe)["size_bytes"] == 80_000_000
    with pytest.raises(ValueError, match="nonroot"):
        validate_image_metadata({**safe, "Config": {"User": ""}})
    with pytest.raises(ValueError, match="2 GiB"):
        validate_image_metadata({**safe, "Size": 3 * 1024**3})
