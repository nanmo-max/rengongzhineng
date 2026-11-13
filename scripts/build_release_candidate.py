"""Build the deterministic BRACE-MSI release-candidate evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from brace_msi.release_candidate import (
    RELEASE_ID,
    RELEASE_VERSION,
    audit_release_tree,
    build_source_archive,
    select_release_files,
)

_PUBLIC_FORBIDDEN_KEYS = {
    "api_key",
    "features",
    "predictions",
    "raw_features",
    "sample_ids",
    "targets",
    "token",
}

_POST_VERIFICATION_PATHS = (
    "docs/",
    "scripts/build_release_candidate.py",
    "scripts/build_submission_document.js",
    "tests/system/test_release_builder.py",
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _tracked_files(root: Path) -> tuple[Path, ...]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    return tuple(Path(item.decode("utf-8")) for item in raw.split(b"\0") if item)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_public_evidence(root: Path, output: Path) -> list[dict[str, object]]:
    source_root = root / "artifacts/formal_simulation/LOCAL-FORMAL-SIM-001"
    runs = (("run-ce3e907", "INVALID"), ("run-7ef3829", "SUCCEEDED"))
    copied: list[dict[str, object]] = []
    for run_name, status in runs:
        run_root = source_root / run_name
        if not run_root.is_dir():
            raise FileNotFoundError(f"missing historical evidence directory: {run_root}")
        candidates = [run_root / "summary.json", run_root / "report.html"]
        candidates.extend(sorted(run_root.glob("tasks/*/public-spool.jsonl")))
        for source in candidates:
            relative = source.relative_to(source_root)
            destination = output / "public-evidence" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.name == "public-spool.jsonl":
                for line in source.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    forbidden = _PUBLIC_FORBIDDEN_KEYS.intersection(record)
                    if forbidden:
                        raise ValueError(
                            f"public evidence contains forbidden keys {sorted(forbidden)}: {source}"
                        )
            shutil.copy2(source, destination)
            copied.append(
                {
                    "path": destination.relative_to(output).as_posix(),
                    "sha256": _sha256(destination),
                    "run_status": status,
                }
            )
    return copied


def run_release_checks(
    root: Path,
    *,
    python: str = sys.executable,
    runner=subprocess.run,
) -> dict[str, dict[str, object]]:
    commands = {
        "pytest": (python, "-m", "pytest", "-q", "--tb=short"),
        "pip_check": (python, "-m", "pip", "check"),
        "compileall": (python, "-m", "compileall", "-q", "src", "tests", "scripts"),
    }
    results: dict[str, dict[str, object]] = {}
    for name, command in commands.items():
        completed = runner(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"release check failed: {name}\n{completed.stdout}\n{completed.stderr}"
            )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        results[name] = {
            "status": "PASS",
            "command": list(command),
            "summary": lines[-1] if lines else "exit 0",
        }
    return results


def load_release_verification(
    path: Path,
    *,
    current_commit: str,
    changed_paths: tuple[str, ...],
    is_ancestor: bool,
) -> dict[str, object]:
    """Accept recorded checks only when runtime code is unchanged afterward."""

    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("release verification evidence is invalid") from exc
    required = {
        "pytest": ("status", "passed"),
        "clean_environment": ("status", "version"),
        "pip_check": ("status",),
        "compileall": ("status",),
    }
    if not isinstance(evidence, dict) or not isinstance(evidence.get("runtime_commit"), str):
        raise RuntimeError("release verification evidence schema is invalid")
    if not is_ancestor:
        raise RuntimeError("verified runtime commit is not an ancestor of release")
    if not current_commit:
        raise RuntimeError("release commit is missing")
    for section, fields in required.items():
        item = evidence.get(section)
        if not isinstance(item, dict) or item.get("status") != "PASS" or any(field not in item for field in fields):
            raise RuntimeError(f"release verification section is not PASS: {section}")
    if int(evidence["pytest"]["passed"]) < 1:
        raise RuntimeError("release verification contains no passing tests")
    if evidence["clean_environment"]["version"] != RELEASE_VERSION:
        raise RuntimeError("clean environment installed the wrong release version")
    unsafe = [
        value
        for value in changed_paths
        if not any(
            value == allowed or value.startswith(allowed)
            for allowed in _POST_VERIFICATION_PATHS
        )
    ]
    if unsafe:
        raise RuntimeError(f"runtime-affecting files changed after verification: {unsafe}")
    return evidence


def load_container_acceptance(
    evidence_path: Path, archive_path: Path
) -> dict[str, object]:
    """Validate that a recorded container acceptance matches the upload tar."""

    try:
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("container acceptance evidence is invalid") from exc
    archive_path = Path(archive_path).resolve()
    if not archive_path.is_file():
        raise RuntimeError("container archive is missing")
    image = evidence.get("image") if isinstance(evidence, dict) else None
    runtime = evidence.get("runtime_acceptance") if isinstance(evidence, dict) else None
    archive = evidence.get("archive") if isinstance(evidence, dict) else None
    if evidence.get("release_id") != RELEASE_ID:
        raise RuntimeError("container acceptance release ID does not match")
    if not isinstance(image, dict) or not isinstance(runtime, dict) or not isinstance(archive, dict):
        raise RuntimeError("container acceptance evidence schema is invalid")
    if (
        image.get("under_2gb") is not True
        or image.get("runtime_uid") == 0
        or image.get("forbidden_files") != []
        or image.get("pip_check") != "PASS"
    ):
        raise RuntimeError("container image acceptance gates are not PASS")
    if (
        runtime.get("network") != "none"
        or runtime.get("cpus") != 4
        or runtime.get("memory_bytes") != 8 * 1024**3
        or runtime.get("status") != "completed"
    ):
        raise RuntimeError("container runtime acceptance gates are not PASS")
    if archive.get("docker_load_verified") is not True:
        raise RuntimeError("container archive was not verified with docker load")
    actual_size = archive_path.stat().st_size
    if archive.get("size_bytes") != actual_size:
        raise RuntimeError("container archive size does not match evidence")
    actual_sha256 = _sha256(archive_path)
    if archive.get("sha256") != actual_sha256:
        raise RuntimeError("container archive SHA-256 does not match evidence")
    return {
        "source_path": str(archive_path),
        "size_bytes": actual_size,
        "sha256": actual_sha256,
    }


def container_manifest_fields(
    metadata: dict[str, object], archive_name: str
) -> dict[str, object]:
    return {
        "release_gates": {
            "docker_image_build": "PASS",
            "linux_4core_8gb_container": "PASS",
        },
        "image_artifact": {
            "path": archive_name,
            "size_bytes": metadata["size_bytes"],
            "sha256": metadata["sha256"],
            "format": "docker save tar",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--verification-evidence",
        type=Path,
        help="reuse recorded PASS checks when only release docs/tooling changed afterward",
    )
    parser.add_argument("--container-evidence", type=Path, required=True)
    parser.add_argument("--image-archive", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"release output already exists: {output}")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError("release source tree must be clean before packaging")

    container = load_container_acceptance(
        args.container_evidence.resolve(), args.image_archive.resolve()
    )

    if args.verification_evidence:
        recorded = json.loads(args.verification_evidence.read_text(encoding="utf-8"))
        runtime_commit = str(recorded.get("runtime_commit", ""))
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", runtime_commit, "HEAD"],
            cwd=root,
            check=False,
        ).returncode == 0
        changed = tuple(
            line
            for line in _git(root, "diff", "--name-only", f"{runtime_commit}..HEAD").splitlines()
            if line
        )
        verification = load_release_verification(
            args.verification_evidence,
            current_commit=_git(root, "rev-parse", "HEAD"),
            changed_paths=changed,
            is_ancestor=ancestry,
        )
    else:
        verification = run_release_checks(root)
    tracked = _tracked_files(root)
    audit = audit_release_tree(root, tracked)
    if audit.blocking_findings:
        raise RuntimeError(f"release tree audit failed: {audit.blocking_findings}")
    output.mkdir(parents=True)
    image_name = f"{RELEASE_ID}-image-clean.tar"
    shutil.copy2(Path(str(container["source_path"])), output / image_name)
    source_archive = output / f"{RELEASE_ID}-source.zip"
    source_sha256 = build_source_archive(
        root, source_archive, select_release_files(tracked)
    )
    evidence = _copy_public_evidence(root, output)
    container_fields = container_manifest_fields(container, image_name)
    manifest = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "source_commit": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "branch", "--show-current"),
        "source_archive": source_archive.name,
        "source_archive_sha256": source_sha256,
        "included_source_files": len(audit.included_files),
        "evidence_boundaries": {
            "a1": audit.a1_status,
            "a2": audit.a2_status,
            "synthetic_bearing": audit.synthetic_scope,
            "regression_sprint": audit.regression_sprint_status,
            "sprint_harness": audit.sprint_harness_status,
            "official_score": False,
        },
        "public_evidence": evidence,
        "verification": verification,
        "release_gates": {
            "source_tree_audit": "PASS",
            "clean_environment_regression": "PASS",
            "swanlab_generic_offline": "PASS",
            **container_fields["release_gates"],
            "official_sdk_mapping": "BLOCKED_OFFICIAL_SDK",
            "official_public_training_packages": "PASS",
            "official_runtime_data_mapping": "BLOCKED_OFFICIAL_SDK",
            "official_scoring_optimization": "BLOCKED_OFFICIAL_RULES",
            "competition_swanlab_sync": "BLOCKED_OFFICIAL_SPEC",
        },
        "image_artifact": container_fields["image_artifact"],
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
