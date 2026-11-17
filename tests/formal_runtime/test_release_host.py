from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _write_candidate(root: Path) -> None:
    root.mkdir()
    params = {
        "w1": np.asarray([[0.5, -0.2], [0.1, 0.3]], dtype=np.float64),
        "b1": np.zeros(2, dtype=np.float64),
        "w2": np.asarray([[0.8, -0.8], [-0.4, 0.4]], dtype=np.float64),
        "b2": np.zeros(2, dtype=np.float64),
    }
    metadata = {
        "format": "contest.cpu-mlp.v1", "device": "cpu", "profile": "test",
        "task": "classification",
        "paths": ['[["key","features"],["index",0]]', '[["key","features"],["index",1]]'],
        "classes": ["cold", "hot"], "hidden": 2, "seed": 42,
        "epochs": 1, "steps": 1, "learning_rate": 0.01, "batch_size": 4,
        "parameter_count": sum(value.size for value in params.values()),
        "target_mean": 0.0, "target_scale": 1.0,
    }
    np.savez(
        root / "checkpoint.npz",
        **params,
        **{f"adam_first_{name}": np.zeros_like(value) for name, value in params.items()},
        **{f"adam_second_{name}": np.zeros_like(value) for name, value in params.items()},
        mean=np.zeros(2), scale=np.ones(2),
        metadata=np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":"))),
    )


def test_local_host_returns_authoritative_nonempty_candidate_metrics(tmp_path: Path) -> None:
    from scripts.verify_workspace_v2_image import _score_candidate

    artifact = tmp_path / "artifact"
    _write_candidate(artifact)
    validation = tmp_path / "validation.jsonl"
    validation.write_text(
        "".join(
            json.dumps(
                {
                    "id": f"row-{index}",
                    "inputs": {"features": [float(index), float(index % 2)]},
                    "answer": "hot" if index >= 3 else "cold",
                }
            ) + "\n"
            for index in range(6)
        ),
        encoding="utf-8",
    )

    metrics = _score_candidate(artifact, validation)

    assert set(metrics) == {"accuracy", "macro_f1"}
    assert all(np.isfinite(value) for value in metrics.values())
