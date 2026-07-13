#!/usr/bin/env bash

set -euo pipefail

FRONTEND_MODE="${FRONTEND_MODE:-development}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"

case "${FRONTEND_MODE}" in
  development)
    exec npm exec -- next dev -p "${FRONTEND_PORT}"
    ;;
  production)
    npm run build
    exec npm exec -- next start -p "${FRONTEND_PORT}"
    ;;
  *)
    printf 'Unsupported FRONTEND_MODE=%s; expected development or production.\n' "${FRONTEND_MODE}" >&2
    exit 2
    ;;
esac
