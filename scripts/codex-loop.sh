#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
LOOP_DIR="$ROOT_DIR/.codex/loop"
RUNS_DIR="$LOOP_DIR/runs"
LOCK_DIR="$LOOP_DIR/.runner-lock"
PROMPT_FILE="$LOOP_DIR/run-once-prompt.md"
SCHEMA_FILE="$LOOP_DIR/output-schema.json"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found in PATH" >&2
  exit 127
fi

mkdir -p "$RUNS_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "safe-grow runner is already active; exiting." >&2
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
RUN_DIR="$RUNS_DIR/$TIMESTAMP"
mkdir -p "$RUN_DIR"

PROMPT_CONTENT="$(<"$PROMPT_FILE")"

codex exec \
  --skip-git-repo-check \
  --full-auto \
  --sandbox workspace-write \
  --json \
  --output-schema "$SCHEMA_FILE" \
  --output-last-message "$RUN_DIR/final.json" \
  "$PROMPT_CONTENT" \
  >"$RUN_DIR/events.jsonl" \
  2>"$RUN_DIR/stderr.log"
