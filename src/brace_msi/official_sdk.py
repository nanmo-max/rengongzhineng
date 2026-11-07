"""Fail-closed plugin boundary for the not-yet-published official SDK.

The manifest names only a Python module and adapter factory. It deliberately
contains no competition data fields, credentials, endpoint names, or label
assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import re
from typing import Callable, cast

from .protocol import EventProtocolAdapter, ProtocolMode

_ALLOWED_SPEC_KEYS = frozenset({"module", "factory", "sdk_version", "sdk_sha256"})
_REQUIRED_METHODS = (
    "open_task",
    "provide_training_batch",
    "request_predictions",
    "submit_predictions",
    "provide_feedback",
    "request_batch_commit",
    "finish_task",
)


class OfficialSdkUnavailable(RuntimeError):
    """The configured official SDK module is not installed."""


class OfficialSdkContractError(ValueError):
    """The plugin manifest or returned adapter violates the internal contract."""


@dataclass(frozen=True)
class OfficialSdkSpec:
    module: str
    factory: str
    sdk_version: str
    sdk_sha256: str

    def __post_init__(self) -> None:
        if not self.module or not all(part.isidentifier() for part in self.module.split(".")):
            raise OfficialSdkContractError("module must be a dotted Python identifier")
        if not self.factory.isidentifier():
            raise OfficialSdkContractError("factory must be a Python identifier")
        if not self.sdk_version.strip():
            raise OfficialSdkContractError("sdk_version must be nonempty")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.sdk_sha256):
            raise OfficialSdkContractError("sdk_sha256 must be a 64-character hex digest")

    @classmethod
    def from_json(cls, path: Path) -> "OfficialSdkSpec":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise OfficialSdkContractError("SDK spec must be a JSON object")
        unexpected = set(payload) - _ALLOWED_SPEC_KEYS
        missing = _ALLOWED_SPEC_KEYS - set(payload)
        if unexpected:
            raise OfficialSdkContractError(
                f"unknown or forbidden SDK spec keys: {sorted(unexpected)}"
            )
        if missing:
            raise OfficialSdkContractError(f"missing SDK spec keys: {sorted(missing)}")
        if not all(isinstance(payload[key], str) for key in _ALLOWED_SPEC_KEYS):
            raise OfficialSdkContractError("all SDK spec values must be strings")
        return cls(**payload)


def _validate_adapter(adapter: object) -> EventProtocolAdapter:
    history = getattr(adapter, "history", None)
    missing = [name for name in _REQUIRED_METHODS if not callable(getattr(adapter, name, None))]
    if not isinstance(history, tuple) or missing:
        details = f"missing methods {missing}" if missing else "history must be a tuple"
        raise OfficialSdkContractError(
            f"official plugin must implement EventProtocolAdapter: {details}"
        )
    return cast(EventProtocolAdapter, adapter)


def load_official_adapter_factory(
    spec: OfficialSdkSpec,
) -> Callable[[ProtocolMode], EventProtocolAdapter]:
    try:
        module = importlib.import_module(spec.module)
    except ModuleNotFoundError as exc:
        raise OfficialSdkUnavailable(
            f"official SDK module is unavailable: {spec.module}"
        ) from exc
    factory = getattr(module, spec.factory, None)
    if not callable(factory):
        raise OfficialSdkContractError(
            f"official SDK factory is missing or not callable: {spec.factory}"
        )

    def create(mode: ProtocolMode) -> EventProtocolAdapter:
        return _validate_adapter(factory(ProtocolMode(mode)))

    return create
