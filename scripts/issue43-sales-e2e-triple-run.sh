#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRANSCRIPT_PATH="${PHASE4_E2E_PROVIDER_TRANSCRIPT:-${ROOT_DIR}/.sisyphus/evidence/issue-43-provider-transcript.jsonl}"
MANIFEST_PATH="${ISSUE43_E2E_RUN_MANIFEST:-${ROOT_DIR}/.sisyphus/evidence/issue-43-run-manifest.jsonl}"
ISSUE43_DB_PATH="${ISSUE43_E2E_DB_PATH:-${ROOT_DIR}/.dev/issue43-sales-e2e.db}"

mkdir -p "$(dirname "${ISSUE43_DB_PATH}")" "$(dirname "${MANIFEST_PATH}")"
rm -f "${ISSUE43_DB_PATH}" "${TRANSCRIPT_PATH}" "${MANIFEST_PATH}"

cd "${ROOT_DIR}/web"

DATABASE_URL="sqlite+aiosqlite:///${ISSUE43_DB_PATH}" \
PHASE4_E2E_PROVIDER=local \
PHASE4_E2E_PROVIDER_SCRIPT=sales-provider-script.v1.json \
PHASE4_E2E_PROVIDER_TRANSCRIPT="${TRANSCRIPT_PATH}" \
ISSUE43_E2E_RUN_MANIFEST="${MANIFEST_PATH}" \
STEPFUN_API_KEY="${STEPFUN_API_KEY:-phase4-local-e2e}" \
SMOKE_EVIDENCE_PREFIX="${SMOKE_EVIDENCE_PREFIX:-issue-43-sales-e2e}" \
npx playwright test tests/e2e/sales-phase4.spec.ts --repeat-each=3 --workers=1 --reporter=line
