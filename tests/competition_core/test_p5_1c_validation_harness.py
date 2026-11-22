from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "p5_drift_targeted_repair.json"


def test_p5_1c_config_uses_only_new_development_seeds() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    development = set(
        range(payload["generation_seed_start"], payload["generation_seed_end"] + 1)
    ) | set(range(payload["permutation_seed_start"], payload["permutation_seed_end"] + 1))
    sealed = set(range(510001, 510005)) | set(range(520001, 520005))
    sealed |= set(range(530001, 530041)) | set(range(540001, 540009))
    sealed |= set(range(550001, 550009)) | set(range(560001, 560007))
    sealed |= {570001, 580001}

    assert not development.intersection(sealed)
    assert payload["scope"] == "development_only_not_final_validation"
    assert payload["permutations"] == 2047


def test_p5_1c_job_matrix_is_complete_and_deterministic() -> None:
    from scripts.run_p5_1c_targeted_validation import build_jobs, load_config

    first = build_jobs(load_config(CONFIG))
    second = build_jobs(load_config(CONFIG))

    assert first == second
    assert len(first) == 72
    assert {item["dimension"] for item in first} == {24, 34, 128}
    assert {item["scenario"] for item in first} == {
        "no_drift",
        "medium_variance",
        "noise_increase",
        "group_composition",
        "sparse_outlier",
        "persistent_drift_recovery",
    }
    assert len({item["generation_seed"] for item in first}) == len(first)
    assert len({item["permutation_seed"] for item in first}) == len(first)
