"""Run the preregistered base-Qwen advisor evaluation on PyTRiO."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brace_msi.advisor_evaluation import run_base_advisor_evaluation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="Qwen/Qwen3.5-4B")
    args = parser.parse_args()

    import pytrio as trio

    service = trio.ServiceClient()
    supported = tuple(service.get_supported_models())
    if args.model not in supported:
        raise RuntimeError(f"model is not supported by PyTRiO: {args.model}")
    sampler = service.create_sampling_client(base_model=args.model)
    tokenizer = sampler.get_tokenizer()

    def call(prompt: str, call_index: int):
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        tokens = tokenizer.encode(text, add_special_tokens=False)
        started = time.perf_counter()
        response = sampler.sample(
            prompt=trio.ModelInput.from_ints(tokens),
            num_samples=1,
            sampling_params=trio.SamplingParams(
                max_tokens=512,
                temperature=0.0,
                seed=20261120 + call_index,
            ),
        ).result()
        if not response.sequences:
            raise RuntimeError("PyTRiO returned no sequence")
        sequence = response.sequences[0]
        return (
            str(sequence.text),
            len(tokens),
            len(sequence.tokens),
            time.perf_counter() - started,
        )

    result = run_base_advisor_evaluation(args.output, call)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0 if result["summary"]["base_model_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
