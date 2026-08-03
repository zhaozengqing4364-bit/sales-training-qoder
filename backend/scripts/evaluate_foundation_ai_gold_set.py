#!/usr/bin/env python3
"""Evaluate the deterministic newcomer Foundation AI gold set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from foundation_ai_quality import (
    DEFAULT_FOUNDATION_AI_GOLD_SET,
    evaluate_foundation_ai_quality,
    load_foundation_ai_quality_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_FOUNDATION_AI_GOLD_SET)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_foundation_ai_quality(
        load_foundation_ai_quality_manifest(args.manifest)
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
