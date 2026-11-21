from scripts.run_competition_release_blackbox import _requested_worse_than_applied


def test_blackbox_detects_worse_requested_artifact_in_both_metric_directions() -> None:
    base = {
        "selection": {
            "requested_artifact_id": "candidate",
            "applied_artifact_id": "parent",
        },
        "artifact_evaluations": [
            {"artifact_id": "parent", "metrics": {"score": 0.9}},
            {"artifact_id": "candidate", "metrics": {"score": 0.2}},
        ],
    }
    assert _requested_worse_than_applied({
        **base, "metric_contract": {"metric": "score", "direction": "higher"}
    })
    assert _requested_worse_than_applied({
        **base,
        "metric_contract": {"metric": "score", "direction": "lower"},
        "artifact_evaluations": [
            {"artifact_id": "parent", "metrics": {"score": 1.0}},
            {"artifact_id": "candidate", "metrics": {"score": 3.0}},
        ],
    })
