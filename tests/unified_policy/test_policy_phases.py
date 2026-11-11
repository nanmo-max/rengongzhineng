import json
from pathlib import Path

import pytest

from brace_msi.policy_phases import (
    ExposureClass,
    PhaseManifest,
    TerminalLock,
    validate_phase_manifest,
)


def _manifest(**overrides: object) -> PhaseManifest:
    values = {
        "task_key": "opaque-task-1",
        "bootstrap_sample_ids": ("a", "b"),
        "development_sample_ids": ("c", "d"),
        "terminal_sample_ids": ("e", "f"),
        "bootstrap_group_ids": ("g1",),
        "development_group_ids": ("g2",),
        "terminal_group_ids": ("g3",),
        "terminal_exposure": ExposureClass.VIRGIN_TERMINAL,
        "source_sha256": ("1" * 64,),
    }
    values.update(overrides)
    return PhaseManifest(**values)


def test_phase_manifest_has_three_disjoint_nonempty_phases() -> None:
    manifest = _manifest()

    result = validate_phase_manifest(manifest)

    assert result["valid"] is True
    assert result["phase_counts"] == {
        "bootstrap_train": 2,
        "policy_development": 2,
        "terminal_test": 2,
    }
    assert len(manifest.sha256) == 64


@pytest.mark.parametrize(
    "overrides",
    [
        {"terminal_sample_ids": ("d", "e")},
        {"terminal_group_ids": ("g2",)},
        {"development_sample_ids": ()},
    ],
)
def test_phase_manifest_rejects_overlap_or_empty_phase(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        validate_phase_manifest(_manifest(**overrides))


def test_terminal_lock_refuses_access_before_freeze_and_opens_once(tmp_path: Path) -> None:
    lock = TerminalLock(tmp_path / "terminal-lock.json")
    manifest = _manifest()

    with pytest.raises(PermissionError, match="not frozen"):
        lock.open_terminal(
            manifest_sha256=manifest.sha256,
            config_sha256="2" * 64,
            source_commit="abc1234",
        )

    lock.freeze(
        manifest_sha256=manifest.sha256,
        config_sha256="2" * 64,
        source_commit="abc1234",
    )
    receipt = lock.open_terminal(
        manifest_sha256=manifest.sha256,
        config_sha256="2" * 64,
        source_commit="abc1234",
    )

    assert receipt["terminal_open_count"] == 1
    with pytest.raises(PermissionError, match="already opened"):
        lock.open_terminal(
            manifest_sha256=manifest.sha256,
            config_sha256="2" * 64,
            source_commit="abc1234",
        )


def test_terminal_lock_rejects_manifest_or_config_drift(tmp_path: Path) -> None:
    path = tmp_path / "terminal-lock.json"
    lock = TerminalLock(path)
    manifest = _manifest()
    lock.freeze(
        manifest_sha256=manifest.sha256,
        config_sha256="2" * 64,
        source_commit="abc1234",
    )

    with pytest.raises(ValueError, match="frozen identity mismatch"):
        lock.open_terminal(
            manifest_sha256="3" * 64,
            config_sha256="2" * 64,
            source_commit="abc1234",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["terminal_open_count"] == 0


def test_exposure_class_cannot_upgrade_historical_data_to_virgin() -> None:
    manifest = _manifest(
        terminal_exposure=ExposureClass.HISTORICALLY_EXPOSED_TERMINAL
    )

    assert manifest.terminal_exposure is ExposureClass.HISTORICALLY_EXPOSED_TERMINAL
    assert manifest.to_dict()["terminal_exposure"] == "historically_exposed_terminal"


def test_optimization_config_has_one_shared_policy_without_task_overrides() -> None:
    config_path = Path(__file__).parents[2] / "configs" / "unified_policy_optimization.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert isinstance(config["shared_policy"], dict)
    assert isinstance(config["search_space"], dict)
    assert set(config["source_sha256"]) == {
        "gas_archive",
        "cmapss_zip",
        "xjtu_manifest",
    }
    assert "task_overrides" not in config
    assert "datasets" not in config["shared_policy"]
