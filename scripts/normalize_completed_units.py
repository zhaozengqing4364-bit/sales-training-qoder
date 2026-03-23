#!/usr/bin/env python3
"""Normalize .gsd/completed-units.json into a stable, low-conflict layout."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable


DEFAULT_PATH = Path(".gsd/completed-units.json")


def dedupe_preserve_order(units: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for unit in units:
        if unit in seen:
            continue
        seen.add(unit)
        ordered.append(unit)
    return ordered


def format_units(units: Iterable[str]) -> str:
    return json.dumps(
        dedupe_preserve_order(units),
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def load_units(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"{path} must contain a JSON array of strings")
    return dedupe_preserve_order(payload)


def normalize_file(path: Path) -> int:
    if not path.exists():
        return 0
    path.write_text(format_units(load_units(path)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    raise SystemExit(normalize_file(target))
