#!/usr/bin/env python3
"""CLI entrypoint for the recovery drill baseline authority module."""

from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().with_name("recovery_drill_baseline.py")),
    run_name="__main__",
)
