from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from brace_msi.data.types import BatchData, TaskStream
from brace_msi.formal_simulation import (
    load_simulation_config,
    run_simulation_suite,
    validate_simulation_output,
)
from brace_msi.simulation import synthetic_bearing_stream


def _regression_stream() -> TaskStream:
    def batch(batch_id: str, offset: float, count: int) -> BatchData:
        X = np.column_stack(
            [np.linspace(0.0, 1.0, count), np.linspace(1.0, 2.0, count) + offset]
        )
        y = 20.0 - 4.0 * X[:, 0] + offset
        return BatchData(
            batch_id,
            X,
            y,
            tuple(f"{batch_id}-{index}" for index in range(count)),
            tuple(str(index // 8 + 1) for index in range(count)),
        )

    return TaskStream(
        "synthetic-rul-protocol-only",
        "regression",
        batch("rul-initial", 0.0, 64),
        tuple(batch(f"rul-dev-{index}", index * 0.5, 32) for index in range(4)),
        (),
        {"synthetic": True, "evidence_scope": "protocol_only"},
    )


def test_three_task_formal_simulation_produces_complete_audited_evidence(tmp_path: Path) -> None:
    config = load_simulation_config(Path("configs/formal_simulation.json"))
    bearing = synthetic_bearing_stream(seed=config.seed)
    gas_like = replace(bearing, task_id="synthetic-gas-protocol-only")
    result = run_simulation_suite(
        (gas_like, _regression_stream(), bearing),
        config=config,
        output_dir=tmp_path / "formal",
    )

    assert result["status"] == "completed"
    assert result["task_count"] == 3
    assert all(task["candidate_count"] >= 3 for task in result["tasks"])
    assert result["resource_acceptance"]["cpu_affinity_count"] <= 4
    assert result["resource_acceptance"]["rss_under_limit"] is True
    assert result["consumed_sealed_used"] is False
    assert (tmp_path / "formal" / "report.html").exists()
    synthetic = next(
        task for task in result["tasks"] if task["task_id"] == bearing.task_id
    )
    assert synthetic["rollback_count"] >= 2
    saved = json.loads((tmp_path / "formal" / "summary.json").read_text())
    assert saved["experiment_id"] == "LOCAL-FORMAL-SIM-001"
    validation = validate_simulation_output(
        tmp_path / "formal", minimum_candidates=3
    )
    assert validation["valid"] is True
    assert validation["action_counts"]["incremental_update"] >= 1
    assert validation["action_counts"]["replay_refit"] >= 1
    assert validation["action_counts"]["bounded_hpo"] >= 1
