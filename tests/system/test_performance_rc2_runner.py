from __future__ import annotations

import json
from pathlib import Path


def test_stream_holdout_split_has_no_overlap_and_is_group_safe() -> None:
    from scripts.run_performance_rc2_pilot import split_stream_holdout_indices

    raw = []
    for bearing in range(1, 10):
        for snapshot in range(1, 21):
            raw.append({"answer": snapshot, "meta": {"bearing": f"b{bearing}", "snapshot": snapshot}})

    rounds, holdout, audit = split_stream_holdout_indices(raw, "regression")
    stream = {index for update, gate in rounds for index in (*update, *gate)}

    assert stream.isdisjoint(holdout)
    assert stream | set(holdout) == set(range(len(raw)))
    assert sum(len(update) + len(gate) for update, gate in rounds) == len(stream)
    stream_groups = {raw[index]["meta"]["bearing"] for index in stream}
    holdout_groups = {raw[index]["meta"]["bearing"] for index in holdout}
    assert stream_groups.isdisjoint(holdout_groups)
    assert audit["group_safe"] is True


def test_smoke_runs_two_opaque_tasks_without_confirmation_feedback(tmp_path: Path) -> None:
    from scripts.run_performance_rc2_pilot import run_smoke

    config = {
        "format": "brace-msi.performance-rc2-pilot.v1",
        "experiment_id": "TEST-RC2",
        "confirmation_read_policy": "once_after_strategy_freeze",
        "rounds": 10,
        "registered_surrogates": [
            {"key": "opaque-cls", "task": "classification", "feature_count": 4, "samples_per_round": 20, "confirmation_samples": 20, "seed": 71},
            {"key": "opaque-reg", "task": "regression", "feature_count": 4, "samples_per_round": 20, "confirmation_samples": 20, "seed": 72},
        ],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    summary = run_smoke(config, tmp_path / "run")

    assert summary["valid"] is True
    assert summary["confirmation_reads"] == 0
    assert summary["tasks"] == ["opaque-cls", "opaque-reg"]
    assert summary["candidate_count"] >= 8
