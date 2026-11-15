from __future__ import annotations

import pytest

from brace_msi.cli import _parser, _validate_official_agent_selection
from brace_msi.platform_advisor import build_platform_advisor


def test_official_agent_provider_has_no_silent_default() -> None:
    args = _parser().parse_args(
        [
            "official-agent-run",
            "--config",
            "config.json",
            "--package-root",
            "package",
            "--runtime-root",
            "runtime",
            "--profile",
            "A",
        ]
    )

    assert args.provider is None
    with pytest.raises(ValueError, match="--provider"):
        _validate_official_agent_selection(None, None)


def test_formal_pytrio_selection_accepts_base_model_without_sampler_path() -> None:
    _validate_official_agent_selection("pytrio", None)
    _validate_official_agent_selection("pytrio", "trio://persisted/sampler")
    _validate_official_agent_selection("deterministic", None)


def test_native_platform_pytrio_uses_online_validated_timeout_by_default() -> None:
    args = _parser().parse_args(["start"])
    advisor = build_platform_advisor()

    assert args.agent_timeout_seconds == 60.0
    assert advisor.proposer.config.timeout_seconds == 60.0
