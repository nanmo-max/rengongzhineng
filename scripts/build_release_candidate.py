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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"release output already exists: {output}")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError("release source tree must be clean before packaging")

    verification = run_release_checks(root)
    tracked = _tracked_files(root)
    audit = audit_release_tree(root, tracked)
    if audit.blocking_findings:
        raise RuntimeError(f"release tree audit failed: {audit.blocking_findings}")
    output.mkdir(parents=True)
    source_archive = output / f"{RELEASE_ID}-source.zip"
    source_sha256 = build_source_archive(
        root, source_archive, select_release_files(tracked)
    )
    evidence = _copy_public_evidence(root, output)
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
            "official_score": False,
        },
        "public_evidence": evidence,
        "verification": verification,
        "release_gates": {
            "source_tree_audit": "PASS",
            "clean_environment_regression": "PASS",
            "swanlab_generic_offline": "PASS",
            "docker_image_build": "BLOCKED_NO_RUNTIME",
            "linux_4core_8gb_container": "BLOCKED_NO_RUNTIME",
            "official_sdk_mapping": "BLOCKED_OFFICIAL_SDK",
            "official_data_adaptation": "BLOCKED_OFFICIAL_DATA",
            "official_scoring_optimization": "BLOCKED_OFFICIAL_RULES",
            "competition_swanlab_sync": "BLOCKED_OFFICIAL_SPEC",
        },
        "image_artifact": None,
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
