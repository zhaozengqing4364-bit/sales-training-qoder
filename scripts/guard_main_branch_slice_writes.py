#!/usr/bin/env python3
"""Block direct slice-file commits on the repository's default branch."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


SLICE_PATH_RE = re.compile(r"^\.gsd/milestones/[^/]+/slices/S\d{2}/")
FALLBACK_PRIMARY_BRANCHES = {"main", "master", "001-ai-practice-system"}


def normalize_branch_name(name: str | None) -> str:
    if not name:
        return ""
    return name.removeprefix("origin/").strip()


def is_primary_branch(current_branch: str, default_branch: str | None) -> bool:
    current = normalize_branch_name(current_branch)
    default = normalize_branch_name(default_branch)
    if not current:
        return False
    if default:
        return current == default
    return current in FALLBACK_PRIMARY_BRANCHES


def blocked_slice_paths(
    current_branch: str,
    default_branch: str | None,
    staged_paths: Iterable[str],
) -> list[str]:
    if not is_primary_branch(current_branch, default_branch):
        return []
    return [path for path in staged_paths if SLICE_PATH_RE.match(path)]


def _run_git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def get_repo_root() -> Path:
    return Path(_run_git(["rev-parse", "--show-toplevel"], Path.cwd()))


def get_current_branch(repo_root: Path) -> str:
    return _run_git(["branch", "--show-current"], repo_root)


def get_default_branch(repo_root: Path) -> str | None:
    env_default = os.getenv("GIT_PRIMARY_BRANCH") or os.getenv("MAIN_BRANCH")
    if env_default:
        return normalize_branch_name(env_default)
    try:
        return normalize_branch_name(
            _run_git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], repo_root)
        )
    except subprocess.CalledProcessError:
        return None


def get_staged_paths(repo_root: Path) -> list[str]:
    output = _run_git(
        ["diff", "--cached", "--name-only", "--diff-filter=ACMRD"],
        repo_root,
    )
    return [line for line in output.splitlines() if line]


def main() -> int:
    repo_root = get_repo_root()
    blocked = blocked_slice_paths(
        current_branch=get_current_branch(repo_root),
        default_branch=get_default_branch(repo_root),
        staged_paths=get_staged_paths(repo_root),
    )
    if not blocked:
        return 0

    print(
        "Blocked: do not commit slice files directly on the primary branch.",
        file=sys.stderr,
    )
    print(
        "Create/use a gsd/<milestone>/<slice> branch, then merge back after completion.",
        file=sys.stderr,
    )
    for path in blocked:
        print(f" - {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
