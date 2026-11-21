"""Execute a preregistered mirror-side Advisor SFT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_msi.formal_advisor_sft import (  # noqa: E402
    CompetitionAgentSftConfig,
    FormalAdvisorSftConfig,
    run_remote_competition_agent_sft,
    run_remote_formal_advisor_sft,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "competition_agent_sft.json")
    parser.add_argument("--legacy-deployment-only", action="store_true")
    args = parser.parse_args()
    if args.legacy_deployment_only:
        result = run_remote_formal_advisor_sft(args.output, FormalAdvisorSftConfig())
    else:
        payload = json.loads(args.config.read_text(encoding="utf-8"))
        allowed = {
            key: payload[key]
            for key in (
                "base_model", "rank", "epochs", "batch_size", "learning_rate",
                "seed", "max_eval_tokens", "weight_name",
            )
            if key in payload
        }
        result = run_remote_competition_agent_sft(
            args.output, CompetitionAgentSftConfig(**allowed)
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
                "sampler_receipt": str(args.output / "persistent_sampler.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["adoption_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
