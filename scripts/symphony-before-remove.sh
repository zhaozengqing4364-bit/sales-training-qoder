#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '[symphony-before-remove] %s\n' "$*"
}

cd "${ROOT_DIR}"

if [[ -x scripts/dev-smoke-stop.sh || -f scripts/dev-smoke-stop.sh ]]; then
  log 'Stopping smoke stack if it is running.'
  bash scripts/dev-smoke-stop.sh || true
fi

if [[ -x scripts/dev-stop.sh || -f scripts/dev-stop.sh ]]; then
  log 'Stopping dev stack if it is running.'
  STOP_INFRA="${SYMPHONY_STOP_INFRA_ON_REMOVE:-0}" bash scripts/dev-stop.sh || true
fi

log 'Workspace cleanup hook complete.'
