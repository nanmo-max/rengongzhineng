import json
from pathlib import Path
import sys
import types

import pytest

from brace_msi.cli import main
from brace_msi.official_sdk import (
    OfficialSdkContractError,
    OfficialSdkSpec,
    OfficialSdkUnavailable,
    load_official_adapter_factory,
)
from brace_msi.protocol import ProtocolMode, SimulatedSdkAdapter


def _spec(**overrides: object) -> OfficialSdkSpec:
    values: dict[str, object] = {
        "module": "official_sdk_plugin",
        "factory": "create_adapter",
        "sdk_version": "1.2.3",
        "sdk_sha256": "a" * 64,
    }
    values.update(overrides)
    return OfficialSdkSpec(**values)


def test_loader_fails_closed_when_official_module_is_unavailable() -> None:
    with pytest.raises(OfficialSdkUnavailable, match="official SDK module"):
        load_official_adapter_factory(_spec(module="missing_competition_sdk"))


def test_loader_injects_verified_adapter_factory_without_field_assumptions(
    monkeypatch,
) -> None:
    module = types.ModuleType("official_sdk_plugin")
    module.create_adapter = lambda mode: SimulatedSdkAdapter(mode)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "official_sdk_plugin", module)

    factory = load_official_adapter_factory(_spec())
    adapter = factory(ProtocolMode.PREDICT_THEN_FEEDBACK)
    adapter.open_task("task")

    assert adapter.history == ("task_opened",)


def test_loader_rejects_plugin_that_does_not_implement_protocol(monkeypatch) -> None:
    module = types.ModuleType("official_sdk_plugin")
    module.create_adapter = lambda mode: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "official_sdk_plugin", module)

    factory = load_official_adapter_factory(_spec())

    with pytest.raises(OfficialSdkContractError, match="EventProtocolAdapter"):
        factory(ProtocolMode.PREDICT_THEN_FEEDBACK)


def test_spec_file_rejects_secrets_and_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "sdk.json"
    path.write_text(
        json.dumps(
            {
                "module": "official_sdk_plugin",
                "factory": "create_adapter",
                "sdk_version": "1.2.3",
                "sdk_sha256": "a" * 64,
                "api_key": "must-not-be-here",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(OfficialSdkContractError, match="unknown or forbidden"):
        OfficialSdkSpec.from_json(path)


def test_cli_checks_official_plugin_contract_without_calling_platform(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = types.ModuleType("official_sdk_plugin")
    module.create_adapter = lambda mode: SimulatedSdkAdapter(mode)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "official_sdk_plugin", module)
    path = tmp_path / "sdk.json"
    path.write_text(
        json.dumps(
            {
                "module": "official_sdk_plugin",
                "factory": "create_adapter",
                "sdk_version": "1.2.3",
                "sdk_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["sdk-contract-check", "--spec", str(path)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "status": "contract_ready",
        "sdk_version": "1.2.3",
        "protocol_modes": [
            "predict_then_feedback",
            "labeled_train_then_predict",
        ],
    }
