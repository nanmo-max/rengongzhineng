"""Synthetic protocol-only task used for installation and recovery smoke tests."""

from __future__ import annotations

import numpy as np

from .data.types import BatchData, TaskStream


def synthetic_bearing_stream(*, seed: int = 20261107) -> TaskStream:
    """Build a deterministic drift stream; it is not real bearing evidence."""

    rng = np.random.default_rng(seed)

    def make_batch(batch_id: str, offset: float, count: int) -> BatchData:
        half = count // 2
        health = np.concatenate(
            [rng.normal(-1.0 + offset, 0.3, half), rng.normal(1.0 + offset, 0.3, half)]
        )
        vibration = health + rng.normal(0.0, 0.15, count)
        X = np.column_stack([health, vibration, vibration**2])
        y = np.concatenate([np.zeros(half, dtype=int), np.ones(half, dtype=int)])
        return BatchData(
            batch_id,
            X,
            y,
            tuple(f"synthetic-{batch_id}-{index}" for index in range(count)),
        )

    return TaskStream(
        task_id="synthetic-bearing-protocol-only",
        task_kind="classification",
        initial=make_batch("initial", 0.0, 80),
        development=tuple(
            make_batch(f"development-{index}", index * 0.35, 48)
            for index in range(4)
        ),
        sealed=(),
        metadata={"synthetic": True, "evidence_scope": "protocol_only"},
    )
