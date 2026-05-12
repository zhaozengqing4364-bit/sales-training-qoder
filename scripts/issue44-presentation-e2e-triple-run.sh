#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRANSCRIPT_PATH="${PHASE4_E2E_PROVIDER_TRANSCRIPT:-${ROOT_DIR}/.sisyphus/evidence/issue-44-provider-transcript.jsonl}"
MANIFEST_PATH="${ISSUE44_E2E_RUN_MANIFEST:-${ROOT_DIR}/.sisyphus/evidence/issue-44-run-manifest.jsonl}"
BACKEND_LOG_PATH="${ISSUE44_BACKEND_LOG_PATH:-${ROOT_DIR}/.sisyphus/evidence/issue-44-backend.log}"
ISSUE44_DB_PATH="${ISSUE44_E2E_DB_PATH:-${ROOT_DIR}/.dev/issue44-presentation-e2e.db}"

mkdir -p "$(dirname "${ISSUE44_DB_PATH}")" "$(dirname "${MANIFEST_PATH}")"
rm -f "${ISSUE44_DB_PATH}" "${TRANSCRIPT_PATH}" "${MANIFEST_PATH}" "${BACKEND_LOG_PATH}"
touch "${BACKEND_LOG_PATH}"

copy_backend_log() {
  local smoke_backend_log="${ROOT_DIR}/.dev/logs/backend.log"
  if [[ -f "${smoke_backend_log}" ]]; then
    cp "${smoke_backend_log}" "${BACKEND_LOG_PATH}"
  fi
}

trap copy_backend_log EXIT

cd "${ROOT_DIR}/web"

DATABASE_URL="sqlite+aiosqlite:///${ISSUE44_DB_PATH}" \
PRESENTATION_REQUIRE_AGENT_PERSONA=false \
PHASE4_E2E_PROVIDER=local \
PHASE4_E2E_PROVIDER_SCRIPT=presentation-provider-script.v1.json \
PHASE4_E2E_PROVIDER_TRANSCRIPT="${TRANSCRIPT_PATH}" \
ISSUE44_E2E_RUN_MANIFEST="${MANIFEST_PATH}" \
ISSUE44_BACKEND_LOG_PATH="${BACKEND_LOG_PATH}" \
STEPFUN_API_KEY="${STEPFUN_API_KEY:-phase4-local-e2e}" \
SMOKE_EVIDENCE_PREFIX="${SMOKE_EVIDENCE_PREFIX:-issue-44-presentation-e2e}" \
npx playwright test tests/e2e/presentation-phase4.spec.ts --repeat-each=3 --workers=1 --reporter=line
