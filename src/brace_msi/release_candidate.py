"""Deterministic source packaging and evidence-boundary audit for the RC."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import zipfile

from .packaging import audit_docker_context

RELEASE_ID = "BRACE-MSI-0.4.1rc1"

_ROOT_FILES = frozenset(
    {
        ".dockerignore",
        ".gitignore",
        "AGENTS.md",
        "Dockerfile",
        "README.md",
        "pyproject.toml",
        "requirements.lock",
        "requirements-dev.lock",
        "requirements-pytrio.lock",
        "requirements-swanlab.lock",
        "run.ps1",
        "run.sh",
    }
)
_PREFIXES = ("configs/", "docs/", "scripts/", "src/", "tests/")
_FORBIDDEN_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf",
    ".pkl",
    ".pickle",
    ".joblib",
    ".pt",
    ".pth",
    ".onnx",
    ".key",
    ".pem",
}


@dataclass(frozen=True)
class ReleaseTreeAudit:
    release_id: str
    blocking_findings: tuple[str, ...]
    included_files: tuple[Path, ...]
    a1_status: str
    a2_status: str
    synthetic_scope: str
    regression_sprint_status: str
    sprint_harness_status: str
    docker_context_under_2gb: bool


def select_release_files(candidates: tuple[Path, ...]) -> tuple[Path, ...]:
    selected: list[Path] = []
    for candidate in candidates:
        path = Path(candidate)
        value = path.as_posix()
        if path.suffix.lower() in _FORBIDDEN_SUFFIXES:
            continue
        if value.startswith("docs/team/"):
            continue
        if path.name in _ROOT_FILES or value.startswith(_PREFIXES):
            selected.append(path)
    return tuple(sorted(set(selected), key=lambda item: item.as_posix()))


def audit_release_tree(root: Path, tracked_files: tuple[Path, ...]) -> ReleaseTreeAudit:
    root = Path(root)
    included = select_release_files(tracked_files)
    findings: list[str] = []
    required = (
        Path("Dockerfile"),
        Path("requirements.lock"),
        Path("requirements-pytrio.lock"),
        Path("requirements-swanlab.lock"),
        Path("src/brace_msi/cli.py"),
        Path("src/brace_msi/official_sdk.py"),
        Path("src/brace_msi/release_candidate.py"),
        Path("src/brace_msi/swanlab_adapter.py"),
        Path("src/brace_msi/paper_fusion.py"),
        Path("src/brace_msi/paper_fusion_runner.py"),
        Path("src/brace_msi/paper_fusion_selection.py"),
        Path("scripts/build_release_candidate.py"),
        Path("docs/RELEASE_CANDIDATE.md"),
        Path("docs/results/LOCAL-FORMAL-SIM-001.md"),
        Path("docs/results/REGRESSION-SPRINT-001.md"),
        Path("docs/results/SPRINT-HARNESS-001.md"),
        Path("docs/results/PAPER-FUSION-SPRINT-001.md"),
    )
    for path in required:
        if path not in included or not (root / path).is_file():
            findings.append(f"missing release file: {path.as_posix()}")

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    if 'version = "0.4.1rc1"' not in pyproject:
        findings.append("pyproject version is not 0.4.1rc1")

    evidence = (root / "docs/results/LOCAL-FORMAL-SIM-001.md").read_text(
        encoding="utf-8"
    )
    a1_status = "INVALID" if "A1" in evidence and "INVALID" in evidence else "UNKNOWN"
    a2_status = (
        "SUCCEEDED"
        if "A2" in evidence and "通过独立机器验收" in evidence
        else "UNKNOWN"
    )
    synthetic_scope = "protocol_only" if "`protocol_only`合成轴承流" in evidence else "UNKNOWN"
    if a1_status != "INVALID":
        findings.append("A1 INVALID history is not preserved")
    if a2_status != "SUCCEEDED":
        findings.append("A2 acceptance evidence is missing")
    if synthetic_scope != "protocol_only":
        findings.append("synthetic bearing scope is not protocol_only")

    regression_evidence = (root / "docs/results/REGRESSION-SPRINT-001.md").read_text(
        encoding="utf-8"
    )
    regression_status = (
        "SUCCEEDED"
        if "Bearing B" in regression_evidence
        and "Engine C" in regression_evidence
        and "机器证据" in regression_evidence
        else "UNKNOWN"
    )
    if regression_status != "SUCCEEDED":
        findings.append("regression sprint evidence is missing")

    harness_evidence = (root / "docs/results/SPRINT-HARNESS-001.md").read_text(
        encoding="utf-8"
    )
    harness_status = (
        "SUCCEEDED"
        if "每任务均完整执行10轮" in harness_evidence
        and "机器复算三任务均`valid=true`" in harness_evidence
        else "UNKNOWN"
    )
    if harness_status != "SUCCEEDED":
        findings.append("sprint Harness evidence is missing")

    context = audit_docker_context(root)
    under_limit = context.total_bytes < 2_000_000_000
    if not under_limit:
        findings.append("Docker build context is at least 2GB")
    if context.forbidden_files:
        findings.append("Docker build context contains forbidden files")

    return ReleaseTreeAudit(
        release_id=RELEASE_ID,
        blocking_findings=tuple(findings),
        included_files=included,
        a1_status=a1_status,
        a2_status=a2_status,
        synthetic_scope=synthetic_scope,
        regression_sprint_status=regression_status,
        sprint_harness_status=harness_status,
        docker_context_under_2gb=under_limit,
    )


def build_source_archive(root: Path, output: Path, files: tuple[Path, ...]) -> str:
    root = Path(root)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for relative in sorted(files, key=lambda item: item.as_posix()):
            data = (root / relative).read_bytes()
            info = zipfile.ZipInfo(f"{RELEASE_ID}/{relative.as_posix()}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            mode = 0o755 if relative.as_posix() == "run.sh" else 0o644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return hashlib.sha256(output.read_bytes()).hexdigest()
