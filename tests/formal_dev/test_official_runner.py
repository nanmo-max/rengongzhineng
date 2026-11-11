from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brace_msi.data.types import BatchData, TaskStream
from brace_msi.formal_development import (
    FormalRunConfig,
    bounded_hpo_candidate,
    create_local_checkpoint,
    run_formal_development_experiment,
    validate_formal_development_output,
)
from brace_msi.budget import BudgetLimits
from brace_msi.safety import GateConfig
from brace_msi.unified_policy import SharedPolicyConfig
from brace_msi.modeling import CpuModelAdapter


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


def test_unified_policies_use_shared_normalized_config(tmp_path: Path) -> None:
    stream = _classification_stream()
    shared = SharedPolicyConfig(
        update_drop_threshold=0.0,
        refit_drop_threshold=0.5,
        drift_percentile_threshold=1.0,
        high_drift_percentile_threshold=1.0,
        minimum_relative_improvement=-1.0,
        maximum_relative_anchor_degradation=1.0,
    )
    config = FormalRunConfig(
        **{**_config().__dict__, "shared_policy_config": shared}
    )
    checkpoint = create_local_checkpoint(stream, tmp_path / "checkpoint.pkl", config)

    fixed = run_formal_development_experiment(
        stream,
        policy_name="fixed_low_cost",
        checkpoint_path=checkpoint,
        output_dir=tmp_path / "fixed",
        config=config,
    )
    triggered = run_formal_development_experiment(
        stream,
        policy_name="normalized_performance_triggered",
        checkpoint_path=checkpoint,
        output_dir=tmp_path / "triggered",
        config=config,
    )
    unified = run_formal_development_experiment(
        stream,
        policy_name="unified_brace",
        checkpoint_path=checkpoint,
        output_dir=tmp_path / "unified",
        config=config,
    )

    assert fixed["real_candidate_count"] == 1
    assert triggered["real_candidate_count"] >= 1
    assert unified["real_candidate_count"] >= 1
    assert unified["shared_policy_config"] == shared.__dict__
    assert all("relative_performance_drop" in row for row in unified["batch_records"])


def test_bounded_hpo_runs_finite_trials_and_selects_recorded_best() -> None:
    rng = np.random.default_rng(29)
    X = rng.normal(size=(120, 4))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    stable = CpuModelAdapter(
        task_kind="classification",
        family="mlp",
        seed=29,
        params={"max_iter": 6},
    ).fit(X[:60], y[:60])

    candidate, trials = bounded_hpo_candidate(
        stable=stable,
        train_X=X[:90],
        train_y=y[:90],
        validation_X=X[90:],
        validation_y=y[90:],
        metric_name="macro_f1",
        search_budget_fraction=0.2,
    )

    assert len(trials) == 2
    assert sum(bool(trial["selected"]) for trial in trials) == 1
    selected = next(trial for trial in trials if trial["selected"])
    assert selected["primary_metric"] == max(
        trial["primary_metric"] for trial in trials
    )
    assert candidate.predict(X[90:]).shape == y[90:].shape

