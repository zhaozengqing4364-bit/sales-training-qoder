#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_DIR="${ROOT_DIR}/.sisyphus/evidence"
EVIDENCE_FILE="${EVIDENCE_DIR}/task-9-quality-gate.txt"
PLAYWRIGHT_REPORT_DIR="${EVIDENCE_DIR}/task-9-playwright-report"
PLAYWRIGHT_REPORT_HTML="${EVIDENCE_DIR}/task-9-playwright-report.html"

BACKEND_PORT="${BACKEND_PORT:-3444}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_USER="${POSTGRES_USER:-dev}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dev}"
POSTGRES_DB="${POSTGRES_DB:-sales_training}"

STACK_STARTED="0"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '\n[%s] %s\n' "$(timestamp)" "$*"
}

die() {
  printf '\n[%s] [ERROR] %s\n' "$(timestamp)" "$*" >&2
  exit 1
}

resolve_python_bin() {
  local candidates=(
    "${ROOT_DIR}/backend/venv/bin/python"
    "${ROOT_DIR}/backend/.venv/bin/python"
    "python3"
    "python"
  )

  local candidate
  local resolved
  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" ]]; then
      resolved="${candidate}"
    elif command -v "${candidate}" >/dev/null 2>&1; then
      resolved="$(command -v "${candidate}")"
    else
      continue
    fi

    if "${resolved}" -c "import pytest" >/dev/null 2>&1; then
      printf '%s\n' "${resolved}"
      return 0
    fi
  done

  return 1
}

strip_surrounding_quotes() {
  local value="$1"
  if [[ ${#value} -ge 2 ]]; then
    local first_char="${value:0:1}"
    local last_char="${value: -1}"
    if [[ "${first_char}" == '"' && "${last_char}" == '"' ]]; then
      value="${value:1:-1}"
    elif [[ "${first_char}" == "'" && "${last_char}" == "'" ]]; then
      value="${value:1:-1}"
    fi
  fi
  printf '%s' "${value}"
}

dotenv_get() {
  local file="$1"
  local key="$2"

  if [[ ! -f "${file}" ]]; then
    return 0
  fi

  local line
  line="$(grep -E "^[[:space:]]*${key}=" "${file}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    return 0
  fi

  local value="${line#*=}"
  strip_surrounding_quotes "${value}"
}

finalize() {
  local exit_code=$?

  if [[ -f "${PLAYWRIGHT_REPORT_DIR}/index.html" ]]; then
    cp "${PLAYWRIGHT_REPORT_DIR}/index.html" "${PLAYWRIGHT_REPORT_HTML}"
  fi

  if [[ "${STACK_STARTED}" == "1" ]]; then
    log "Stopping smoke stack"
    bash "${ROOT_DIR}/scripts/dev-smoke-stop.sh" || true
  fi

  exit ${exit_code}
}

trap finalize EXIT

mkdir -p "${EVIDENCE_DIR}"
rm -rf "${PLAYWRIGHT_REPORT_DIR}" "${PLAYWRIGHT_REPORT_HTML}"
exec > >(tee "${EVIDENCE_FILE}") 2>&1

PYTHON_BIN="$(resolve_python_bin)" || die "Could not find a backend Python interpreter"

BACKEND_ENV_FILE="${ROOT_DIR}/backend/.env"
DEFAULT_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
DEFAULT_REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
VITEST_GATE_TARGETS=(
  "src/app/(auth)/login/page.test.tsx"
  "src/app/(dashboard)/page.test.tsx"
  "src/app/(dashboard)/support/runtime/page.test.tsx"
  "src/app/admin/analytics/page.test.tsx"
  "src/app/admin/business-rules/_components/governed-business-rule-page.test.tsx"
  "src/app/admin/business-rules/sales-combinations/page.test.tsx"
  "src/app/admin/governance/page.test.tsx"
  "src/app/admin/scoring-rulesets/page.test.tsx"
  "src/app/admin/settings/page.test.tsx"
  "src/app/(user)/practice/[sessionId]/page.test.tsx"
  "src/app/(user)/practice/[sessionId]/report/page.test.tsx"
  "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
  "src/components/error-reporting.test.tsx"
  "src/components/ui/chat-bubble.test.tsx"
  "src/lib/admin/linked-assets.test.ts"
  "src/lib/auth-handler.test.ts"
)

BACKEND_GATE_TARGETS=(
  "tests/integration/test_auth_login_api.py"
  "tests/integration/test_history_evidence_flow.py"
  "tests/integration/test_replay_api.py"
  "tests/integration/test_support_runtime_api.py"
  "tests/contract/test_analytics.py"
  "tests/contract/test_release_verification_contract.py"
  "tests/contract/test_admin_governance_contract.py"
  "tests/integration/test_admin_business_rules_api.py"
  "tests/integration/test_admin_model_configs_api.py"
  "tests/integration/test_scoring_rulesets_api.py"
  "tests/unit/admin/test_model_config_security.py"
  "tests/unit/common/test_business_rule_config_service.py"
)

export DATABASE_URL="${DATABASE_URL:-$(dotenv_get "${BACKEND_ENV_FILE}" "DATABASE_URL")}" 
DATABASE_URL="${DATABASE_URL:-${DEFAULT_DATABASE_URL}}"
export REDIS_URL="${REDIS_URL:-$(dotenv_get "${BACKEND_ENV_FILE}" "REDIS_URL")}" 
REDIS_URL="${REDIS_URL:-${DEFAULT_REDIS_URL}}"

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:${BACKEND_PORT}/api/v1}"
export NEXT_PUBLIC_WS_URL="${NEXT_PUBLIC_WS_URL:-ws://localhost:${BACKEND_PORT}}"
export SMOKE_EVIDENCE_PREFIX="task-9"

log "Secret hygiene scan"
"${ROOT_DIR}/scripts/secret-scan.sh"

assert_non_empty_vitest_coverage_summary() {
  local summary_file="${ROOT_DIR}/web/coverage/coverage-summary.json"
  if [[ ! -s "${summary_file}" ]]; then
    die "Vitest coverage summary is missing or empty: ${summary_file}"
  fi

  node -e '
    const fs = require("fs");
    const path = process.argv[1];
    const summary = JSON.parse(fs.readFileSync(path, "utf8"));
    const total = summary.total;
    if (!total) {
      throw new Error("coverage summary missing total");
    }
    const coveredUnits = ["lines", "functions", "branches", "statements"]
      .map((key) => Number(total[key]?.total || 0))
      .reduce((sum, value) => sum + value, 0);
    if (coveredUnits <= 0) {
      throw new Error("coverage summary total is empty");
    }
  ' "${summary_file}" || die "Vitest coverage summary is not a valid non-empty summary"
}

log "Backend tests: auth + history/report/replay + admin analytics + support runtime + business rules + model config + release verification"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" -m pytest -c pyproject.toml "${BACKEND_GATE_TARGETS[@]}" --no-cov -q
)

log "Backend coverage threshold"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" -m pytest -c pyproject.toml tests/unit tests/integration tests/contract -q
)

log "Bootstrapping smoke stack for Alembic + Playwright"
bash "${ROOT_DIR}/scripts/dev-smoke-up.sh"
STACK_STARTED="1"

log "Alembic drift check"
(
  cd "${ROOT_DIR}/backend"
  DATABASE_URL="${DATABASE_URL}" "${PYTHON_BIN}" -m alembic upgrade head
)

log "Web typecheck"
(
  cd "${ROOT_DIR}/web"
  npx tsc --noEmit
)

log "Vitest"
(
  cd "${ROOT_DIR}/web"
  rm -rf coverage
  npx vitest run --coverage "${VITEST_GATE_TARGETS[@]}"
)
assert_non_empty_vitest_coverage_summary

log "Playwright smoke matrix"
(
  cd "${ROOT_DIR}/web"
  SMOKE_REUSE_EXISTING_STACK=1 npx playwright test
)

log "Critical quality gate passed"
