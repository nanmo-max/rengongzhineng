from __future__ import annotations

import numpy as np


def test_build_evidence_handles_higher_is_better_metric() -> None:
    from brace_msi.evidence import build_evidence

    reference = np.zeros((20, 2))
    current = np.ones((20, 2)) * 4

    evidence = build_evidence(
        reference,
        current,
        current_metric=0.60,
        reference_metric=0.85,
        higher_is_better=True,
    )

    assert evidence.performance_drop == 0.25
    assert evidence.drift_score > 0.9
    assert evidence.sample_count == 20


def test_build_evidence_handles_lower_is_better_metric() -> None:
    from brace_msi.evidence import build_evidence

    evidence = build_evidence(
        np.zeros((10, 1)),
        np.zeros((10, 1)),
        current_metric=30.0,
        reference_metric=20.0,
        higher_is_better=False,
    )

    assert evidence.performance_drop == 10.0
    assert evidence.drift_score == 0.0
