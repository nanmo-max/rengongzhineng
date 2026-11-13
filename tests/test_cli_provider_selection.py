from __future__ import annotations

import pytest

from brace_msi.cli import _parser, _validate_official_agent_selection


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


def test_formal_pytrio_selection_requires_persisted_sampler_path() -> None:
    with pytest.raises(ValueError, match="--model-path"):
        _validate_official_agent_selection("pytrio", None)

    _validate_official_agent_selection("pytrio", "trio://persisted/sampler")
    _validate_official_agent_selection("deterministic", None)
