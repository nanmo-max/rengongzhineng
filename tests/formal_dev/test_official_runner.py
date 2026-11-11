from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brace_msi.data.types import BatchData, TaskStream
from brace_msi.formal_development import (
    FormalRunConfig,
    create_local_checkpoint,
    run_formal_development_experiment,
    validate_formal_development_output,
)
from brace_msi.budget import BudgetLimits
from brace_msi.safety import GateConfig


def _classification_stream() -> TaskStream:
    rng = np.random.default_rng(11)

    def make(batch_id: str, count: int, offset: float) -> BatchData:
        y = np.tile(np.arange(1, 7), count // 6)
        X = rng.normal(size=(len(y), 128)) + y[:, None] * 0.15 + offset
        return BatchData(
            batch_id=batch_id,
            X=X,
            y=y,
            sample_ids=tuple(f"{batch_id}:{i}" for i in range(len(y))),
        )

    return TaskStream(
        task_id="gas-official-dev",
        task_kind="classification",
        initial=make("initial", 120, 0.0),
        development=tuple(make(f"opt-{i:02d}", 24, i * 0.02) for i in range(1, 11)),
        sealed=(),
        metadata={
            "official_rules_aligned": True,
            "official_checkpoint": False,
            "primary_metric": "macro_f1",
            "published_parameter_count": 4326,
        },
    )


def _config() -> FormalRunConfig:
    return FormalRunConfig(
        seed=20261111,
        budget=BudgetLimits(20, 10000, 60.0, 60.0),
        gate=GateConfig(4, -1.0, 1.0),
        minimum_candidate_events=3,
        replay_max_samples=1000,
        performance_drop_threshold=0.0,
        update_drop_threshold=0.0,
        refit_drop_threshold=1.0,
        drift_threshold=1.0,
        high_drift_threshold=2.0,
        mlp_max_iter=8,
    )


def test_three_policies_share_checkpoint_and_brace_records_real_candidates(
    tmp_path: Path,
) -> None:
    stream = _classification_stream()
    checkpoint = create_local_checkpoint(stream, tmp_path / "checkpoint.pkl", _config())

    results = {}
    for policy in ("static", "performance_triggered", "brace"):
        results[policy] = run_formal_development_experiment(
            stream,
            policy_name=policy,
            checkpoint_path=checkpoint,
            output_dir=tmp_path / policy,
            config=_config(),
        )

    assert all(result["completed_batches"] == 10 for result in results.values())
    assert all(result["checkpoint_sha256"] == results["static"]["checkpoint_sha256"] for result in results.values())
    assert results["brace"]["real_candidate_count"] >= 3
    assert results["brace"]["official_checkpoint"] is False
    validation = validate_formal_development_output(
        tmp_path / "brace", expected_batches=10, minimum_candidates=3
    )
    assert validation["valid"] is True
    assert json.loads((tmp_path / "brace" / "result.json").read_text())["status"] == "completed"

