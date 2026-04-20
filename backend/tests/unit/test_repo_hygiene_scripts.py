"""Unit tests for repo hygiene helper scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT_DIR = Path(__file__).resolve().parents[3]


def _load_module(relative_path: str, module_name: str) -> ModuleType:
    script_path = ROOT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_completed_units_dedupes_and_formats_multiline_json() -> None:
    normalize_script = _load_module(
        "scripts/normalize_completed_units.py",
        "normalize_completed_units",
    )

    formatted = normalize_script.format_units(
        [
            "research-slice/M001/S01",
            "execute-task/M001/S02/T01",
            "research-slice/M001/S01",
        ]
    )

    assert (
        formatted
        == '[\n  "research-slice/M001/S01",\n  "execute-task/M001/S02/T01"\n]\n'
    )


def test_main_branch_guard_blocks_slice_paths_on_default_branch() -> None:
    guard_script = _load_module(
        "scripts/guard_main_branch_slice_writes.py",
        "guard_main_branch_slice_writes",
    )

    blocked = guard_script.blocked_slice_paths(
        current_branch="001-ai-practice-system",
        default_branch="001-ai-practice-system",
        staged_paths=[
            ".gsd/milestones/M001/slices/S02/S02-SUMMARY.md",
            "backend/src/common/api/practice.py",
        ],
    )

    assert blocked == [".gsd/milestones/M001/slices/S02/S02-SUMMARY.md"]


def test_main_branch_guard_allows_slice_paths_on_feature_branch() -> None:
    guard_script = _load_module(
        "scripts/guard_main_branch_slice_writes.py",
        "guard_main_branch_slice_writes",
    )

    blocked = guard_script.blocked_slice_paths(
        current_branch="gsd/M001/S03",
        default_branch="001-ai-practice-system",
        staged_paths=[".gsd/milestones/M001/slices/S03/S03-PLAN.md"],
    )

    assert blocked == []
