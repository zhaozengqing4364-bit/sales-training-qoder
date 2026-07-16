#!/usr/bin/env bash

set -euo pipefail

FRONTEND_MODE="${FRONTEND_MODE:-development}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"

case "${FRONTEND_MODE}" in
  development)
    # Stale Turbopack cache under .next/dev (often mixed with prior production
    # build artifacts under .next/) can make `next dev` serve /login as 404
    # even when the App Router page exists. Always clear the dev cache before
    # starting so readiness checks against /login stay reliable.
    rm -rf .next/dev
    if [[ "${NEXT_CLEAN_CACHE:-0}" == "1" ]]; then
      rm -rf .next
    fi
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
