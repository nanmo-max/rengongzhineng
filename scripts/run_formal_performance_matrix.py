"""Run the pre-registered parent-compatible recipe matrix on train-internal folds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from brace_formal.data import load_rows
from brace_formal.model import FormalModel
from brace_formal.portfolio import cross_validate, fit_recipe


PACKAGES = {
    "A": "cpu-a-guide-20261110-v1",
    "B": "cpu-b-rul-20261110-v1",
    "C": "cpu-c-guide-20261110-v1",
}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(package_root: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=False)
    tasks = []
    for key, package_name in PACKAGES.items():
        package = package_root / package_name
        checkpoint = package / "checkpoint.npz"
        train_path = package / "public" / "train.jsonl"
        parent = FormalModel.load(checkpoint)
        batch = load_rows(train_path, parent, require_answers=True)
        started_wall = time.perf_counter()
        started_cpu = time.process_time()
        evidence = cross_validate(parent, batch.ids, batch.x, batch.y)
        selected = fit_recipe(parent, evidence["selected_recipe"], batch.x, batch.y)
        task_output = output / key
        task_output.mkdir()
        selected_path = task_output / "checkpoint.npz"
        selected.save(selected_path)
        tasks.append(
            {
                "dataset_key": key,
                "task": parent.meta["task"],
                "samples": len(batch.ids),
                "train_sha256": batch.sha256,
                "parent_sha256": _sha(checkpoint),
                "selected_checkpoint_sha256": _sha(selected_path),
                "selected_checkpoint_bytes": selected_path.stat().st_size,
                "public_validation_reads": 0,
                "selected_recipe": evidence["selected_recipe"],
                "evidence": evidence,
                "cpu_seconds": time.process_time() - started_cpu,
                "wall_seconds": time.perf_counter() - started_wall,
            }
        )
    summary: dict[str, object] = {
        "format": "brace-formal-performance-matrix.v1",
        "experiment_id": "FORMAL-PERF-001-A1",
        "seed": 20261117,
        "scope": "official_train_internal_only_no_public_validation",
        "tasks": tasks,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args.package_root, args.output)
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
