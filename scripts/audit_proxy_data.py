"""Create a read-only aggregate audit of local proxy datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from brace_msi.data.audit import build_proxy_audit
from brace_msi.data.cmapss import load_cmapss_fd001_stream
from brace_msi.data.gas import load_gas_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gas-root", type=Path, required=True)
    parser.add_argument("--gas-archive", type=Path, required=True)
    parser.add_argument("--cmapss-zip", type=Path, required=True)
    parser.add_argument("--cmapss-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gas = load_gas_stream(args.gas_root)
    cmapss = load_cmapss_fd001_stream(args.cmapss_zip)
    report = build_proxy_audit(
        gas,
        cmapss,
        gas_archive=args.gas_archive,
        cmapss_archive=args.cmapss_archive,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
