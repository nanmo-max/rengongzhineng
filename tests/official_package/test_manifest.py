from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from brace_msi.official_package import PackageAuditError, audit_package_root, package_tree_sha256


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


def load_config() -> dict:
    return json.loads((REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8"))


def test_audit_accepts_three_immutable_official_packages() -> None:
    audits = audit_package_root(PACKAGE_ROOT, load_config())

    assert set(audits) == {"A", "B", "C"}
    assert (audits["A"].task, audits["A"].input_features, audits["A"].hidden) == (
        "classification",
        128,
        32,
    )
    assert (audits["B"].input_features, audits["B"].hidden, audits["B"].parameter_count) == (
        34,
        24,
        865,
    )
    assert (audits["C"].input_features, audits["C"].hidden, audits["C"].parameter_count) == (
        24,
        32,
        833,
    )
    assert (audits["A"].train_rows, audits["A"].validation_rows) == (445, 1244)
    assert (audits["B"].train_rows, audits["B"].validation_rows) == (7032, 1679)
    assert (audits["C"].train_rows, audits["C"].validation_rows) == (113089, 23049)
    assert audits["A"].baseline_metric == pytest.approx(0.7140297220788709)
    assert audits["B"].baseline_metric == pytest.approx(681.1598326043113)
    assert audits["C"].baseline_metric == pytest.approx(52.86857256611151)
    for audit in audits.values():
        assert audit.train_ids.isdisjoint(audit.validation_ids)
        assert audit.train_groups.isdisjoint(audit.validation_groups)
        assert audit.official_package is True
        assert audit.official_scoring_ready is False


def test_audit_rejects_tampered_checkpoint_before_training(tmp_path: Path) -> None:
    config = load_config()
    source = PACKAGE_ROOT / config["packages"]["A"]["directory"]
    isolated_root = tmp_path / "packages"
    destination = isolated_root / source.name
    shutil.copytree(source, destination)
    checkpoint = destination / "checkpoint.npz"
    checkpoint.write_bytes(checkpoint.read_bytes() + b"tampered")
    config["packages"] = {"A": config["packages"]["A"]}

    with pytest.raises(PackageAuditError, match="checkpoint.npz SHA-256"):
        audit_package_root(isolated_root, config)


def test_audit_does_not_write_cache_files_to_source_tree() -> None:
    before = sorted(path.relative_to(PACKAGE_ROOT) for path in PACKAGE_ROOT.rglob("*") if path.is_file())
    audit_package_root(PACKAGE_ROOT, load_config())
    after = sorted(path.relative_to(PACKAGE_ROOT) for path in PACKAGE_ROOT.rglob("*") if path.is_file())

    assert before == after


def test_package_tree_fingerprint_ignores_runtime_python_cache(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "source.py").write_text("value = 1\n", encoding="utf-8")
    before = package_tree_sha256(package)
    cache = package / "__pycache__"
    cache.mkdir()
    (cache / "source.cpython-312.pyc").write_bytes(b"runtime-cache")

    assert package_tree_sha256(package) == before

