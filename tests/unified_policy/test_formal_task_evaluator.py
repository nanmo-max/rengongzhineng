from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from brace_msi.data.types import BatchData, TaskStream
from brace_msi.formal_task_evaluator import FormalTaskEvaluator
from brace_msi.unified_policy import SharedPolicyConfig


def _stream() -> TaskStream:
    rng = np.random.default_rng(17)

    def batch(name: str, count: int, offset: float) -> BatchData:
        y = np.tile(np.arange(1, 7), count // 6)
        X = rng.normal(size=(len(y), 128)) + y[:, None] * 0.1 + offset
        return BatchData(
            batch_id=name,
            X=X,
            y=y,
            sample_ids=tuple(f"{name}:{index}" for index in range(len(y))),
        )

    return TaskStream(
        task_id="opaque-classification-task",
        task_kind="classification",
        initial=batch("initial", 120, 0.0),
        development=tuple(
            batch(f"development-{index:02d}", 24, index * 0.03)
            for index in range(1, 11)
        ),
        sealed=(),
        metadata={
            "official_rules_aligned": True,
            "official_checkpoint": False,
            "primary_metric": "macro_f1",
            "published_parameter_count": 4326,
        },
    )


def _shared() -> SharedPolicyConfig:
    return SharedPolicyConfig(
        update_drop_threshold=0.0,
        refit_drop_threshold=0.5,
        drift_percentile_threshold=1.0,
        high_drift_percentile_threshold=1.0,
        minimum_relative_improvement=-1.0,
        maximum_relative_anchor_degradation=1.0,
    )


def test_formal_evaluator_runs_four_fair_policies_from_one_checkpoint(tmp_path: Path) -> None:
    evaluator = FormalTaskEvaluator(
        streams={"opaque-1": _stream()},
        runtime_root=tmp_path,
        seed=20261112,
        baseline_shared_config=_shared(),
        mlp_max_iter=6,
    )

    results = {
        policy: evaluator.evaluate(
            task_key="opaque-1",
            policy_name=policy,
            candidate_id="candidate" if policy == "brace" else None,
            shared_config=_shared() if policy == "brace" else None,
        )
        for policy in (
            "static",
            "fixed_low_cost",
            "performance_triggered",
            "brace",
        )
    }

    assert len({item.initial_state_sha256 for item in results.values()}) == 1
    assert len({item.phase_manifest_sha256 for item in results.values()}) == 1
    assert results["static"].training_samples == 0
    assert results["fixed_low_cost"].training_samples > 0
    assert all(item.hard_constraints_passed for item in results.values())


def test_formal_evaluator_refuses_loaded_terminal_data(tmp_path: Path) -> None:
    source = _stream()
    unsafe = replace(source, sealed=(source.development[-1],))

    with pytest.raises(ValueError, match="terminal"):
        FormalTaskEvaluator(
            streams={"opaque-1": unsafe},
            runtime_root=tmp_path,
            seed=1,
            baseline_shared_config=_shared(),
            mlp_max_iter=4,
        )
