"""Run the preregistered, one-time XJTU-SY final holdout validation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_msi.data.xjtu import (  # noqa: E402
    FROZEN_BEARING_SPLIT,
    extract_bearing_cache,
    numeric_csv_files,
)
from brace_msi.final_validation import (  # noqa: E402
    assert_sealed_not_cached,
    load_cache_batch,
    run_one_time_validation,
)


CONDITIONS = {
    "1": ("35Hz12kN", 2100.0, 12.0),
    "2": ("37.5Hz11kN", 2250.0, 11.0),
    "3": ("40Hz10kN", 2400.0, 10.0),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _source(raw_root: Path, bearing: str) -> tuple[Path, str, float, float]:
    condition_index = bearing[len("Bearing") :].split("_", 1)[0]
    condition, speed_rpm, load_kn = CONDITIONS[condition_index]
    return raw_root / condition / bearing, condition, speed_rpm, load_kn


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/final_generalization_validation.json"
    )
    parser.add_argument("--existing-cache-root", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    config_bytes = args.config.read_bytes()
    config_sha256 = hashlib.sha256(config_bytes).hexdigest()
    config = json.loads(config_bytes.decode("utf-8"))
    source_commit = _git_head()
    if args.output_root.name != config["experiment_id"]:
        parser.error("output directory name must equal experiment_id")
    for key, split_key in (
        ("initial_bearings", "initial"),
        ("development_bearings", "development"),
        ("sealed_bearings", "sealed"),
    ):
        if tuple(config[key]) != FROZEN_BEARING_SPLIT[split_key]:
            parser.error(f"{key} differs from the frozen XJTU split")
    sealed_bearings = tuple(config["sealed_bearings"])
    assert_sealed_not_cached(args.existing_cache_root, sealed_bearings)
    if args.output_root.exists():
        parser.error("output root must be new")

    initial = tuple(
        load_cache_batch(
            args.existing_cache_root / f"{bearing}.npz", expected_bearing=bearing
        )
        for bearing in config["initial_bearings"]
    )
    development = tuple(
        load_cache_batch(
            args.existing_cache_root / f"{bearing}.npz", expected_bearing=bearing
        )
        for bearing in config["development_bearings"]
    )
    input_cache_fingerprints = {
        bearing: _sha256(args.existing_cache_root / f"{bearing}.npz")
        for bearing in (*config["initial_bearings"], *config["development_bearings"])
    }
    canonical_claim = (
        args.existing_cache_root.parent
        / ".holdout-claims"
        / "xjtu-frozen-split-v1.json"
    )
    preopen_receipt = {
        "experiment_id": config["experiment_id"],
        "config_sha256": config_sha256,
        "source_commit": source_commit,
        "input_cache_fingerprints": input_cache_fingerprints,
        "sealed_split": list(sealed_bearings),
        "sealed_opened": False,
    }

    def open_sealed():
        feature_root = args.output_root / "sealed-features"
        manifest: list[dict[str, Any]] = []
        batches = []
        for bearing in sealed_bearings:
            source, condition, speed_rpm, load_kn = _source(args.raw_root, bearing)
            source_files = numeric_csv_files(source)
            cache = feature_root / f"{bearing}.npz"
            summary = extract_bearing_cache(
                source,
                cache,
                condition=condition,
                bearing_id=bearing,
                speed_rpm=speed_rpm,
                load_kn=load_kn,
            )
            manifest.append(
                {
                    "bearing": bearing,
                    "condition": condition,
                    "source_file_count": len(source_files),
                    "feature_count": summary.feature_count,
                    "cache_sha256": _sha256(cache),
                    "cache_bytes": cache.stat().st_size,
                }
            )
            batches.append(load_cache_batch(cache, expected_bearing=bearing))
        _write_json(
            args.output_root / "sealed-feature-manifest.json",
            {"experiment_id": config["experiment_id"], "bearings": manifest},
        )
        return tuple(batches)

    summary = run_one_time_validation(
        initial_batches=initial,
        development_batches=development,
        open_sealed=open_sealed,
        output_root=args.output_root,
        config=config,
        claim_path=canonical_claim,
        preopen_receipt=preopen_receipt,
    )
    evidence = {
        "experiment_id": config["experiment_id"],
        "config": str(args.config.resolve()),
        "config_sha256": config_sha256,
        "source_commit": source_commit,
        "preopen_receipt_sha256": _sha256(args.output_root / "preopen-receipt.json"),
        "sealed_feature_manifest_sha256": _sha256(
            args.output_root / "sealed-feature-manifest.json"
        ),
        "summary_sha256": _sha256(args.output_root / "summary.json"),
        "promotion_passed": summary["promotion"]["passed"],
    }
    _write_json(args.output_root / "evidence.json", evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if summary["promotion"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
