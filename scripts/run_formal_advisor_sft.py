"""Execute the single preregistered formal deployment Advisor SFT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_msi.formal_advisor_sft import (  # noqa: E402
    FormalAdvisorSftConfig,
    run_remote_formal_advisor_sft,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_remote_formal_advisor_sft(
        args.output, FormalAdvisorSftConfig()
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "training_steps": result["training_steps"],
                "final_loss_per_supervised_token": result[
                    "final_loss_per_supervised_token"
                ],
                "base_evaluation": result["base_evaluation"],
                "tuned_evaluation": result["tuned_evaluation"],
                "adoption_gate_passed": result["adoption_gate_passed"],
                "sampler_model_path": result["sampler_model_path"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["adoption_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
