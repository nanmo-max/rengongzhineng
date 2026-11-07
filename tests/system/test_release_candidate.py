from pathlib import Path
import subprocess
import zipfile

from brace_msi.release_candidate import (
    RELEASE_ID,
    audit_release_tree,
    build_source_archive,
    select_release_files,
)


def _tracked_files(root: Path) -> tuple[Path, ...]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    return tuple(Path(item.decode("utf-8")) for item in output.split(b"\0") if item)


def test_release_file_selection_excludes_raw_materials_data_and_model_weights() -> None:
    candidates = (
        Path("src/brace_msi/cli.py"),
        Path("docs/RUNBOOK.md"),
        Path("configs/formal_simulation.json"),
        Path("Dockerfile"),
        Path("dataji/private.csv"),
        Path("artifacts/model.pkl"),
        Path("docs/team/private.md"),
        Path("ba80dbeca694b0030c8c4d042357407b.jpg"),
        Path("competition.pdf"),
    )

    selected = select_release_files(candidates)

    assert Path("src/brace_msi/cli.py") in selected
    assert Path("docs/RUNBOOK.md") in selected
    assert Path("configs/formal_simulation.json") in selected
    assert Path("Dockerfile") in selected
    assert not any(path.suffix in {".pkl", ".jpg", ".pdf"} for path in selected)
    assert not any(path.parts[:2] == ("docs", "team") for path in selected)


def test_repository_release_audit_preserves_evidence_boundaries() -> None:
    root = Path(__file__).resolve().parents[2]

    audit = audit_release_tree(root, _tracked_files(root))

    assert audit.release_id == RELEASE_ID == "BRACE-MSI-0.1.0rc1"
    assert audit.blocking_findings == ()
    assert audit.a1_status == "INVALID"
    assert audit.a2_status == "SUCCEEDED"
    assert audit.synthetic_scope == "protocol_only"
    assert audit.docker_context_under_2gb is True


def test_source_archive_contains_only_selected_release_files(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    selected = select_release_files(_tracked_files(root))
    archive = tmp_path / "release.zip"

    digest = build_source_archive(root, archive, selected)

    assert len(digest) == 64
    with zipfile.ZipFile(archive) as handle:
        names = set(handle.namelist())
    assert f"{RELEASE_ID}/src/brace_msi/cli.py" in names
    assert not any("dataji/" in name or name.endswith(".pkl") for name in names)
