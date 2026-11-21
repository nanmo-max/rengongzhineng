from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.final_record import build_swanlab_spool
from brace_msi.formal_advisor_sft import build_competition_agent_swanlab_spool


parser = argparse.ArgumentParser()
parser.add_argument("--runtime-dir", type=Path)
parser.add_argument("--competition-agent-result", type=Path)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--task-id")
parser.add_argument("--task-kind", choices=("classification", "regression"))
parser.add_argument("--primary-metric")
parser.add_argument("--secondary-metric")
parser.add_argument("--higher-is-better", action="store_true")
args = parser.parse_args()

if args.competition_agent_result:
    result = build_competition_agent_swanlab_spool(args.competition_agent_result, args.output)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)
if not all((args.runtime_dir, args.task_id, args.task_kind, args.primary_metric)):
    parser.error("formal runtime spool requires runtime-dir, task-id, task-kind and primary-metric")
result = build_swanlab_spool(
    args.runtime_dir, args.output, task_id=args.task_id, task_kind=args.task_kind,
    primary_metric_name=args.primary_metric, secondary_metric_name=args.secondary_metric,
    higher_is_better=args.higher_is_better,
)
print(
    json.dumps(
        {"output": str(result.output_path), "record_count": result.record_count},
        ensure_ascii=False,
    )
)

