#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export FRONTEND_MODE=production
exec bash "${ROOT_DIR}/scripts/dev-up.sh"
