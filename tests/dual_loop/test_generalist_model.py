from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brace_msi.cli import main
from brace_msi.generalist_model import (
    GeneralistCheckpoint,
    GeneralistSpec,
    fit_generalist_candidate,
    load_numeric_rows,
)
from brace_msi.generalist_experiment import evaluate_generalist_artifact
from brace_msi.official_package import audit_package_root
from brace_msi.official_public_stream import OfficialCheckpointPredictor


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(r"C:\Users\Administrator\Desktop\人工智能创新大赛\训练包")


def _audit_a():
    config = json.loads(
        (REPO_ROOT / "configs" / "official_package_dev.json").read_text(encoding="utf-8")
    )
    return audit_package_root(PACKAGE_ROOT, config)["A"]


def test_generalist_artifact_embeds_and_uses_parent_with_independent_roundtrip(
    tmp_path: Path,
) -> None:
    package = _audit_a()
    artifact = tmp_path / "checkpoint.npz"
    result = fit_generalist_candidate(
        package,
        artifact,
        specs=(GeneralistSpec("linear", {"regularization": 1.0}),),
        max_train_rows=600,
        seed=20261113,
    )

    assert result.parent_sha256 == package.checkpoint_sha256
    assert result.artifact_bytes < 64 * 1024 * 1024
    checkpoint = GeneralistCheckpoint.load(artifact)
    rows = load_numeric_rows(package.validation_path)[:24]
    first = checkpoint.predict_rows(rows)
    second = GeneralistCheckpoint.load(artifact).predict_rows(rows)
    assert np.array_equal(first.predictions, second.predictions)
    assert np.allclose(first.parent_raw, second.parent_raw)
    assert checkpoint.metadata["parent_sha256"] == package.checkpoint_sha256
    assert checkpoint.metadata["blend_parent_weight"] == 0.5

    official = OfficialCheckpointPredictor(package, tmp_path / "official").predict_rows(
        package.checkpoint_path, [row.raw for row in rows], stage_id="parent-equivalence"
    )
    assert np.array_equal(first.parent_predictions, official.predictions)
    assert np.allclose(first.parent_raw, official.probabilities)

    evaluation = evaluate_generalist_artifact(package, artifact, rows)
    assert set(evaluation) >= {
        "parent_metrics",
        "candidate_metrics",
        "blend_metrics",
        "accepted",
    }
    assert evaluation["parent_metrics"]["macro_f1"] >= 0.0

    requests = tmp_path / "requests.jsonl"
    outputs = tmp_path / "outputs.jsonl"
    requests.write_text(
        "".join(
            json.dumps({"inputs": row.raw["inputs"]}, separators=(",", ":")) + "\n"
            for row in rows[:3]
        ),
        encoding="utf-8",
    )
    assert main(
        [
            "generalist-predict",
            "--checkpoint",
            str(artifact),
            "--input-jsonl",
            str(requests),
            "--output-jsonl",
            str(outputs),
        ]
    ) == 0
    payloads = [json.loads(line) for line in outputs.read_text(encoding="utf-8").splitlines()]
    assert len(payloads) == 3
    assert all("outputs" in payload for payload in payloads)


def test_numeric_loader_never_adds_meta_identity_or_target_features() -> None:
    package = _audit_a()
    rows = load_numeric_rows(package.train_path)[:10]

    assert rows
    assert all("meta" not in name.lower() for name in rows[0].feature_names)
    assert all("answer" not in name.lower() for name in rows[0].feature_names)
    assert all("id" not in name.lower() for name in rows[0].feature_names)
