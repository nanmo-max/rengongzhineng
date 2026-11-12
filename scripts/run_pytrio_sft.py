from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from brace_msi.pytrio_sft import (
    PyTrioSftRunConfig,
    materialize_brace_sft_corpus,
    materialize_compliance_sft_corpus,
    run_remote_pytrio_sft,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or execute the bounded BRACE-MSI PyTRiO SFT run."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform remote sampling/training; omitted means prepare-only",
    )
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20261112)
    parser.add_argument("--weight-name", default="brace-msi-agent-sft-v1")
    parser.add_argument(
        "--corpus-version",
        choices=("v1", "compliance_v2"),
        default="v1",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = PyTrioSftRunConfig(
        rank=args.rank,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
        weight_name=args.weight_name,
        corpus_version=args.corpus_version,
    )
    if args.execute:
        result = run_remote_pytrio_sft(args.output_dir, config)
    else:
        result = {
            "status": "prepared_only",
            "remote_calls": 0,
            "config": {
                "base_model": config.base_model,
                "rank": config.rank,
                "epochs": config.epochs,
                "batch_size": config.batch_size,
                "learning_rate": config.learning_rate,
                "seed": config.seed,
                "weight_name": config.weight_name,
                "corpus_version": config.corpus_version,
            },
            "corpus": (
                materialize_brace_sft_corpus(
                    args.output_dir / "corpus", seed=config.seed
                )
                if config.corpus_version == "v1"
                else materialize_compliance_sft_corpus(
                    args.output_dir / "corpus", seed=config.seed
                )
            ),
        }
        (args.output_dir / "prepared.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
