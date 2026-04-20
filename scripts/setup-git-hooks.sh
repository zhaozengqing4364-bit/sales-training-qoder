#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

chmod +x .githooks/pre-commit scripts/normalize_completed_units.py scripts/guard_main_branch_slice_writes.py

git config core.hooksPath .githooks

echo "Configured core.hooksPath=.githooks"
