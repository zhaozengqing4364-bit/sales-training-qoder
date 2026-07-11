#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_DIR="${ROOT_DIR}/.sisyphus/evidence"
EVIDENCE_FILE="${EVIDENCE_DIR}/task-9-quality-gate.txt"
PLAYWRIGHT_REPORT_DIR="${EVIDENCE_DIR}/task-9-playwright-report"
PLAYWRIGHT_REPORT_HTML="${EVIDENCE_DIR}/task-9-playwright-report.html"
NEWCOMER_REAL_PROVIDER_EVIDENCE="${EVIDENCE_DIR}/newcomer-real-provider-gate.json"
NEWCOMER_AI_COACH_REAL_PROVIDER_EVIDENCE="${EVIDENCE_DIR}/newcomer-ai-coach-real-provider-gate.json"
NEWCOMER_AI_COACH_REAL_PROVIDER_RUNTIME_AUDIT="${EVIDENCE_DIR}/newcomer-ai-coach-real-provider-runtime-audit.json"

BACKEND_PORT="${BACKEND_PORT:-3444}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_USER="${POSTGRES_USER:-dev}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dev}"
POSTGRES_DB="${POSTGRES_DB:-sales_training}"
CRITICAL_GATE_MODE="${CRITICAL_GATE_MODE:-full}"
RUN_NEWCOMER_REAL_PROVIDER_GATE="${RUN_NEWCOMER_REAL_PROVIDER_GATE:-0}"
NEWCOMER_REAL_PROVIDER_NAME="${NEWCOMER_REAL_PROVIDER_NAME:-stepfun_realtime}"
NEWCOMER_REAL_PROVIDER_REQUIRED="${NEWCOMER_REAL_PROVIDER_REQUIRED:-0}"
NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED="${NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED:-0}"
RUN_NEWCOMER_AI_COACH_REAL_PROVIDER_GATE="${RUN_NEWCOMER_AI_COACH_REAL_PROVIDER_GATE:-0}"
NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED="${NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED:-0}"
NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED="${NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED:-0}"
NEWCOMER_E2E_FRESH_RUN_ID="${NEWCOMER_E2E_FRESH_RUN_ID:-fresh-$(date +%Y%m%d%H%M%S)}"
export NEWCOMER_E2E_FRESH_RUN_ID

case "${CRITICAL_GATE_MODE}" in
  newcomer-real-provider)
    EVIDENCE_FILE="${EVIDENCE_DIR}/task-9-newcomer-real-provider-gate.txt"
    ;;
  newcomer-ai-coach-real-provider)
    EVIDENCE_FILE="${EVIDENCE_DIR}/task-9-newcomer-ai-coach-real-provider-gate.txt"
    ;;
esac

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
    "${ROOT_DIR}/backend/.venv/bin/python"
    "${ROOT_DIR}/backend/venv/bin/python"
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

start_smoke_stack() {
  PHASE4_E2E_PROVIDER="${PHASE4_E2E_PROVIDER:-local}" \
    STEPFUN_API_KEY="${STEPFUN_API_KEY:-phase4-local-e2e}" \
    bash "${ROOT_DIR}/scripts/dev-smoke-up.sh"
  STACK_STARTED="1"
}

stop_smoke_stack() {
  if [[ "${STACK_STARTED}" == "1" ]]; then
    bash "${ROOT_DIR}/scripts/dev-smoke-stop.sh" || true
    STACK_STARTED="0"
  fi
}

trap finalize EXIT

mkdir -p "${EVIDENCE_DIR}"
rm -rf \
  "${PLAYWRIGHT_REPORT_DIR}" \
  "${PLAYWRIGHT_REPORT_HTML}"
case "${CRITICAL_GATE_MODE}" in
  newcomer-real-provider)
    rm -f "${NEWCOMER_REAL_PROVIDER_EVIDENCE}"
    ;;
  newcomer-ai-coach-real-provider)
    rm -f \
      "${NEWCOMER_AI_COACH_REAL_PROVIDER_EVIDENCE}" \
      "${NEWCOMER_AI_COACH_REAL_PROVIDER_RUNTIME_AUDIT}"
    ;;
esac
exec > >(tee "${EVIDENCE_FILE}") 2>&1

PYTHON_BIN="$(resolve_python_bin)" || die "Could not find a backend Python interpreter"

BACKEND_ENV_FILE="${ROOT_DIR}/backend/.env"
DEFAULT_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
DEFAULT_REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
QUALITY_SELECTION_MANIFEST="${EVIDENCE_DIR}/quality-test-selection.json"
BACKEND_COVERAGE_REPORT="${EVIDENCE_DIR}/backend-coverage.json"
CHANGED_COVERAGE_REPORT="${EVIDENCE_DIR}/changed-coverage-report.json"
BACKEND_INTEGRATION_TARGET_FILE="${EVIDENCE_DIR}/backend-integration-targets.txt"
BACKEND_E2E_TARGET_FILE="${EVIDENCE_DIR}/backend-e2e-targets.txt"
PLAYWRIGHT_TARGET_FILE="${EVIDENCE_DIR}/playwright-targets.txt"
QUALITY_GATE_SELECTION_MODE="${QUALITY_GATE_SELECTION_MODE:-local}"
QUALITY_GATE_BASE_SHA="${QUALITY_GATE_BASE_SHA:-}"
QUALITY_GATE_HEAD_SHA="${QUALITY_GATE_HEAD_SHA:-HEAD}"
BACKEND_SUITE_TIMEOUT_SECONDS="${BACKEND_SUITE_TIMEOUT_SECONDS:-1200}"
VITEST_SUITE_TIMEOUT_SECONDS="${VITEST_SUITE_TIMEOUT_SECONDS:-1200}"

export DATABASE_URL="${DATABASE_URL:-$(dotenv_get "${BACKEND_ENV_FILE}" "DATABASE_URL")}" 
DATABASE_URL="${DATABASE_URL:-${DEFAULT_DATABASE_URL}}"
export REDIS_URL="${REDIS_URL:-$(dotenv_get "${BACKEND_ENV_FILE}" "REDIS_URL")}" 
REDIS_URL="${REDIS_URL:-${DEFAULT_REDIS_URL}}"
export AUTH_SHARED_PASSWORD="${AUTH_SHARED_PASSWORD:-$(dotenv_get "${BACKEND_ENV_FILE}" "AUTH_SHARED_PASSWORD")}"
export AUTH_USER_PASSWORDS_JSON="${AUTH_USER_PASSWORDS_JSON:-$(dotenv_get "${BACKEND_ENV_FILE}" "AUTH_USER_PASSWORDS_JSON")}"
export SMOKE_ADMIN_PASSWORD="${SMOKE_ADMIN_PASSWORD:-${AUTH_SHARED_PASSWORD:-change-me}}"
export STEPFUN_API_KEY="${STEPFUN_API_KEY:-$(dotenv_get "${BACKEND_ENV_FILE}" "STEPFUN_API_KEY")}"
export STEPFUN_REALTIME_URL="${STEPFUN_REALTIME_URL:-$(dotenv_get "${BACKEND_ENV_FILE}" "STEPFUN_REALTIME_URL")}"
export STEPFUN_REALTIME_MODEL="${STEPFUN_REALTIME_MODEL:-$(dotenv_get "${BACKEND_ENV_FILE}" "STEPFUN_REALTIME_MODEL")}"
export LLM_API_KEY="${LLM_API_KEY:-$(dotenv_get "${BACKEND_ENV_FILE}" "LLM_API_KEY")}"
export LLM_BASE_URL="${LLM_BASE_URL:-$(dotenv_get "${BACKEND_ENV_FILE}" "LLM_BASE_URL")}"
export LLM_MODEL="${LLM_MODEL:-$(dotenv_get "${BACKEND_ENV_FILE}" "LLM_MODEL")}"

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

write_newcomer_real_provider_evidence() {
  local status="$1"
  local classification="$2"
  local reason="$3"
  local http_status="${4:-}"

  "${PYTHON_BIN}" - "${NEWCOMER_REAL_PROVIDER_EVIDENCE}" \
    "${status}" "${classification}" "${reason}" "${http_status}" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
http_status = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] else None
payload = {
    "status": sys.argv[2],
    "classification": sys.argv[3],
    "reason": sys.argv[4],
    "http_status": http_status,
    "provider": os.getenv("NEWCOMER_REAL_PROVIDER_NAME", "stepfun_realtime"),
    "model": os.getenv("STEPFUN_REALTIME_MODEL", "stepaudio-2.5-realtime"),
    "realtime_url_configured": bool(os.getenv("STEPFUN_REALTIME_URL")),
    "required": os.getenv("NEWCOMER_REAL_PROVIDER_REQUIRED", "0") == "1",
    "credential_skip_allowed": os.getenv(
        "NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED", "0"
    ) == "1",
    "mode": os.getenv("CRITICAL_GATE_MODE", "full"),
    "command": (
        "CRITICAL_GATE_MODE=newcomer-real-provider "
        "NEWCOMER_REAL_PROVIDER_NAME=stepfun_realtime "
        "bash scripts/critical-quality-gate.sh"
    ),
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

infer_newcomer_real_provider_failure_classification() {
  if grep -q "\\[STEPFUN_UPSTREAM_REJECTED\\].*HTTP 401\\|HTTP 401.*\\[STEPFUN_UPSTREAM_REJECTED\\]" "${EVIDENCE_FILE}" 2>/dev/null; then
    printf '%s\n' "upstream_auth_rejected"
    return 0
  fi
  if grep -q "\\[STEPFUN_UPSTREAM_REJECTED\\]" "${EVIDENCE_FILE}" 2>/dev/null; then
    printf '%s\n' "upstream_rejected"
    return 0
  fi
  if grep -q "\\[STEPFUN_API_ERROR\\]" "${EVIDENCE_FILE}" 2>/dev/null; then
    printf '%s\n' "upstream_api_error"
    return 0
  fi
  if grep -q "\\[STEPFUN_CONNECTION_ERROR\\]\\|timed out during opening handshake" "${EVIDENCE_FILE}" 2>/dev/null; then
    printf '%s\n' "upstream_connection_error"
    return 0
  fi
  printf '%s\n' "executed_failed"
}

infer_newcomer_real_provider_http_status() {
  grep -Eo "HTTP [0-9]{3}" "${EVIDENCE_FILE}" 2>/dev/null \
    | tail -1 \
    | sed -E 's/^HTTP //' \
    || true
}

newcomer_real_provider_failure_reason() {
  local classification="$1"
  case "${classification}" in
    upstream_auth_rejected)
      printf '%s\n' "StepFun realtime provider gate executed and reached upstream, but StepFun rejected the handshake with HTTP 401. The local auth/seed/path flow passed; check that STEPFUN_API_KEY is valid and authorized for STEPFUN_REALTIME_MODEL."
      ;;
    upstream_rejected)
      printf '%s\n' "StepFun realtime provider gate executed and reached upstream, but StepFun rejected the handshake. Inspect .sisyphus/evidence/task-9-quality-gate.txt for status code and provider detail."
      ;;
    upstream_api_error)
      printf '%s\n' "StepFun realtime provider gate executed, reached upstream, and completed the WebSocket handshake, but StepFun returned an application-level API error during the session. Inspect .sisyphus/evidence/task-9-newcomer-real-provider-gate.txt for provider detail."
      ;;
    upstream_connection_error)
      printf '%s\n' "StepFun realtime provider gate executed but the upstream WebSocket connection failed before a completed realtime session. Inspect .sisyphus/evidence/task-9-newcomer-real-provider-gate.txt for provider detail."
      ;;
    *)
      printf '%s\n' "Newcomer realtime real provider gate executed but did not pass. Inspect .sisyphus/evidence/task-9-newcomer-real-provider-gate.txt for the upstream error and Playwright trace."
      ;;
  esac
}

write_newcomer_ai_coach_real_provider_evidence() {
  local status="$1"
  local classification="$2"
  local reason="$3"

  "${PYTHON_BIN}" - "${NEWCOMER_AI_COACH_REAL_PROVIDER_EVIDENCE}" \
    "${NEWCOMER_AI_COACH_REAL_PROVIDER_RUNTIME_AUDIT}" \
    "${status}" "${classification}" "${reason}" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
runtime_audit_path = Path(sys.argv[2])
runtime_audit = {}
if runtime_audit_path.exists():
    raw = json.loads(runtime_audit_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        runtime_audit = raw
actual_llm_runtime = {}
if isinstance(runtime_audit.get("llm_runtime"), dict):
    actual_llm_runtime = runtime_audit["llm_runtime"]
payload = {
    "status": sys.argv[3],
    "classification": sys.argv[4],
    "reason": sys.argv[5],
    "provider": actual_llm_runtime.get("provider") or os.getenv("LLM_PROVIDER", "openai"),
    "model": actual_llm_runtime.get("model_name")
    or os.getenv("LLM_MODEL")
    or os.getenv("OPENAI_MODEL")
    or "",
    "base_url_configured": bool(
        actual_llm_runtime.get("base_url")
        or os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
    ),
    "required": os.getenv("NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED", "0") == "1",
    "credential_skip_allowed": os.getenv(
        "NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED", "0"
    ) == "1",
    "mode": os.getenv("CRITICAL_GATE_MODE", "full"),
    "command": (
        "CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider "
        "LLM_API_KEY=... bash scripts/critical-quality-gate.sh"
    ),
    "actual_runtime_audit": runtime_audit,
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

is_placeholder_stepfun_key() {
  local key="${STEPFUN_API_KEY:-}"
  [[ -z "${key}" || "${key}" == "phase4-local-e2e" || "${key}" == "replace-with-stepfun-api-key" ]]
}

is_placeholder_llm_key() {
  local key="${LLM_API_KEY:-${OPENAI_API_KEY:-}}"
  [[ -z "${key}" \
    || "${key}" == "change-me" \
    || "${key}" == "test-key" \
    || "${key}" == "local-test-key" \
    || "${key}" == "replace-with-llm-api-key" \
    || "${key}" == "replace-with-openai-api-key" ]]
}

run_newcomer_real_provider_gate() {
  log "Newcomer realtime real provider gate"

  if is_placeholder_stepfun_key; then
    write_newcomer_real_provider_evidence \
      "skipped" \
      "credential_missing" \
      "STEPFUN_API_KEY is empty or still uses a local/test placeholder; real provider gate was not executed."
    if [[ "${NEWCOMER_REAL_PROVIDER_REQUIRED}" == "1" ]]; then
      die "Newcomer real provider gate requires a non-placeholder STEPFUN_API_KEY"
    fi
    if [[ "${NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED}" != "1" ]]; then
      die "Newcomer real provider gate requires STEPFUN_API_KEY or NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1"
    fi
    log "Skipped newcomer real provider gate: credential_missing"
    return 0
  fi

  stop_smoke_stack
  export PHASE4_E2E_PROVIDER="${NEWCOMER_REAL_PROVIDER_NAME}"
  export NEWCOMER_E2E_EXPECT_REAL_PROVIDER="1"
  start_smoke_stack

  if ! (
    cd "${ROOT_DIR}/web"
    SMOKE_REUSE_EXISTING_STACK=1 \
      PHASE4_E2E_PROVIDER="${NEWCOMER_REAL_PROVIDER_NAME}" \
      NEWCOMER_E2E_EXPECT_REAL_PROVIDER=1 \
      npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts \
        --grep "realtime roleplay starts from active path" \
        --workers=1
  ); then
    local failure_classification
    local failure_reason
    local failure_http_status
    failure_classification="$(infer_newcomer_real_provider_failure_classification)"
    failure_reason="$(newcomer_real_provider_failure_reason "${failure_classification}")"
    failure_http_status="$(infer_newcomer_real_provider_http_status)"
    write_newcomer_real_provider_evidence \
      "failed" \
      "${failure_classification}" \
      "${failure_reason}" \
      "${failure_http_status}"
    return 1
  fi

  write_newcomer_real_provider_evidence \
    "passed" \
    "executed" \
    "Newcomer realtime roleplay start, /ws/sales session lifecycle, Journey outcome, and admin record projection passed against the configured non-local provider."
}

run_newcomer_ai_coach_real_provider_gate() {
  log "Newcomer AI Coach real provider stream gate"

  if is_placeholder_llm_key; then
    write_newcomer_ai_coach_real_provider_evidence \
      "skipped" \
      "credential_missing" \
      "LLM_API_KEY/OPENAI_API_KEY is empty or still uses a local/test placeholder; AI Coach real provider stream gate was not executed."
    if [[ "${NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED}" == "1" ]]; then
      die "Newcomer AI Coach real provider gate requires a non-placeholder LLM_API_KEY or OPENAI_API_KEY"
    fi
    if [[ "${NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED}" != "1" ]]; then
      die "Newcomer AI Coach real provider gate requires LLM_API_KEY/OPENAI_API_KEY or NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1"
    fi
    log "Skipped newcomer AI Coach real provider gate: credential_missing"
    return 0
  fi

  stop_smoke_stack
  export NEWCOMER_AI_COACH_EXPECT_REAL_PROVIDER="1"
  start_smoke_stack

	  if ! (
	    cd "${ROOT_DIR}/web"
	    SMOKE_REUSE_EXISTING_STACK=1 \
	      NEWCOMER_AI_COACH_EXPECT_REAL_PROVIDER=1 \
	      NEWCOMER_AI_COACH_REAL_PROVIDER_AUDIT_FILE="${NEWCOMER_AI_COACH_REAL_PROVIDER_RUNTIME_AUDIT}" \
	      npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts \
	        --grep "AI Coach real provider stream creates a governed first-card after learner choice" \
	        --workers=1
  ); then
    write_newcomer_ai_coach_real_provider_evidence \
      "failed" \
      "executed_failed" \
      "AI Coach real provider stream gate executed but did not pass. Inspect .sisyphus/evidence/task-9-quality-gate.txt for the provider error and Playwright trace."
    return 1
  fi

  write_newcomer_ai_coach_real_provider_evidence \
    "passed" \
    "executed" \
    "AI Coach /chat/sessions/stream and /messages/stream created a governed first-card after learner choice against the configured real LLM provider without fallback error events."
}

run_with_watchdog() {
  local label="$1"
  local timeout_seconds="$2"
  shift 2

  local exit_code=0
  set +e
  timeout --foreground -k 30s "${timeout_seconds}s" "$@"
  exit_code=$?
  set -e
  if [[ ${exit_code} -eq 124 || ${exit_code} -eq 137 ]]; then
    die "${label} timed out after ${timeout_seconds}s (exit=${exit_code})"
  fi
  if [[ ${exit_code} -ne 0 ]]; then
    die "${label} failed (exit=${exit_code})"
  fi
}

is_selected_playwright_target() {
  local expected="$1"
  local target
  for target in "${PLAYWRIGHT_TARGETS[@]}"; do
    if [[ "${target}" == "${expected}" ]]; then
      return 0
    fi
  done
  return 1
}

if [[ "${CRITICAL_GATE_MODE}" != "full" \
  && "${CRITICAL_GATE_MODE}" != "newcomer-real-provider" \
  && "${CRITICAL_GATE_MODE}" != "newcomer-ai-coach-real-provider" ]]; then
  die "Unsupported CRITICAL_GATE_MODE=${CRITICAL_GATE_MODE}"
fi

if [[ "${CRITICAL_GATE_MODE}" == "newcomer-real-provider" ]]; then
  run_newcomer_real_provider_gate
  log "Newcomer real provider gate finished"
  exit 0
fi

if [[ "${CRITICAL_GATE_MODE}" == "newcomer-ai-coach-real-provider" ]]; then
  run_newcomer_ai_coach_real_provider_gate
  log "Newcomer AI Coach real provider gate finished"
  exit 0
fi

log "Select policy-governed slow test families"
SELECTOR_ARGS=(
  --mode "${QUALITY_GATE_SELECTION_MODE}"
  --head "${QUALITY_GATE_HEAD_SHA}"
  --output "${QUALITY_SELECTION_MANIFEST}"
)
if [[ -n "${QUALITY_GATE_BASE_SHA}" ]]; then
  SELECTOR_ARGS+=(--base "${QUALITY_GATE_BASE_SHA}")
fi
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/select_quality_tests.py" "${SELECTOR_ARGS[@]}"
[[ -s "${QUALITY_SELECTION_MANIFEST}" ]] || die "Selector manifest is missing or empty"

"${PYTHON_BIN}" "${ROOT_DIR}/scripts/select_quality_tests.py" \
  --output "${QUALITY_SELECTION_MANIFEST}" --emit-family backend_integration \
  > "${BACKEND_INTEGRATION_TARGET_FILE}"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/select_quality_tests.py" \
  --output "${QUALITY_SELECTION_MANIFEST}" --emit-family backend_e2e \
  > "${BACKEND_E2E_TARGET_FILE}"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/select_quality_tests.py" \
  --output "${QUALITY_SELECTION_MANIFEST}" --emit-family playwright \
  > "${PLAYWRIGHT_TARGET_FILE}"
mapfile -t BACKEND_INTEGRATION_TARGETS < "${BACKEND_INTEGRATION_TARGET_FILE}"
mapfile -t BACKEND_E2E_TARGETS < "${BACKEND_E2E_TARGET_FILE}"
mapfile -t PLAYWRIGHT_TARGETS < "${PLAYWRIGHT_TARGET_FILE}"
BACKEND_SLOW_TARGETS=("${BACKEND_INTEGRATION_TARGETS[@]}" "${BACKEND_E2E_TARGETS[@]}")

log "Backend ruff"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" -m ruff check src
)

log "Backend architecture dependency guard"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" scripts/architecture_dependency_guard.py --check
)

log "OpenAPI contract parity"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" scripts/generate_openapi_contract.py --check
)

log "Backend full mypy"
(
  cd "${ROOT_DIR}/backend"
  "${PYTHON_BIN}" -m mypy --config-file pyproject.toml src
)

log "Backend full unit + contract branch coverage"
(
  cd "${ROOT_DIR}/backend"
  rm -f .coverage "${BACKEND_COVERAGE_REPORT}"
  run_with_watchdog \
    "Backend unit + contract branch coverage" \
    "${BACKEND_SUITE_TIMEOUT_SECONDS}" \
    env PHASE4_E2E_PROVIDER= NEWCOMER_E2E_EXPECT_REAL_PROVIDER= \
    "${PYTHON_BIN}" -m pytest -c pyproject.toml \
      -o addopts="--import-mode=importlib" \
      tests/unit tests/contract \
      --cov=src \
      --cov-branch \
      --cov-report= \
      -q
)

log "Web typecheck"
(
  cd "${ROOT_DIR}/web"
  rm -rf .next/types .next/dev/types
  npx tsc --noEmit
)

log "Web lint"
(
  cd "${ROOT_DIR}/web"
  npm run lint
)

log "Vitest"
(
  cd "${ROOT_DIR}/web"
  rm -rf coverage
  run_with_watchdog \
    "Full Vitest coverage" \
    "${VITEST_SUITE_TIMEOUT_SECONDS}" \
    npx vitest run --coverage
)
assert_non_empty_vitest_coverage_summary
[[ -s "${ROOT_DIR}/web/coverage/coverage-final.json" ]] \
  || die "Vitest coverage-final.json is missing or empty"

log "[quality-gate] Ensuring database schema is current before smoke bootstrap and Playwright"
start_smoke_stack

GENERIC_PLAYWRIGHT_TARGETS=()
for target in "${PLAYWRIGHT_TARGETS[@]}"; do
  case "${target}" in
    tests/e2e/smoke.spec.ts|tests/e2e/newcomer-training-closed-loop.spec.ts|tests/e2e/presentation-phase4.spec.ts|tests/e2e/sales-phase4.spec.ts)
      ;;
    *)
      GENERIC_PLAYWRIGHT_TARGETS+=("${target}")
      ;;
  esac
done

if [[ ${#GENERIC_PLAYWRIGHT_TARGETS[@]} -gt 0 ]]; then
  log "Policy-selected generic Playwright E2E"
  (
    cd "${ROOT_DIR}/web"
    SMOKE_REUSE_EXISTING_STACK=1 \
      npx playwright test "${GENERIC_PLAYWRIGHT_TARGETS[@]}" --workers=1
  )
fi

if is_selected_playwright_target "tests/e2e/smoke.spec.ts"; then
  log "Playwright smoke E2E"
  (
    cd "${ROOT_DIR}/web"
    SMOKE_REUSE_EXISTING_STACK=1 npx playwright test tests/e2e/smoke.spec.ts
  )
fi

if is_selected_playwright_target "tests/e2e/newcomer-training-closed-loop.spec.ts"; then
  log "Playwright newcomer training closed-loop E2E"
  (
    cd "${ROOT_DIR}/web"
    SMOKE_REUSE_EXISTING_STACK=1 \
      PHASE4_E2E_PROVIDER=local \
      npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
  )
fi

if is_selected_playwright_target "tests/e2e/presentation-phase4.spec.ts"; then
  log "Playwright presentation Phase 4 E2E"
  stop_smoke_stack
  PHASE4_E2E_PROVIDER=local \
  PHASE4_E2E_PROVIDER_SCRIPT=presentation-provider-script.v1.json \
  PHASE4_E2E_PROVIDER_TRANSCRIPT="${ROOT_DIR}/.sisyphus/evidence/issue-44-provider-transcript.jsonl" \
  ISSUE44_E2E_RUN_MANIFEST="${ROOT_DIR}/.sisyphus/evidence/issue-44-run-manifest.jsonl" \
  ISSUE44_BACKEND_LOG_PATH="${ROOT_DIR}/.dev/logs/backend.log" \
  STEPFUN_API_KEY="${STEPFUN_API_KEY:-phase4-local-e2e}" \
  start_smoke_stack
  (
    cd "${ROOT_DIR}/web"
    PHASE4_E2E_PROVIDER=local \
    PHASE4_E2E_PROVIDER_SCRIPT=presentation-provider-script.v1.json \
    PHASE4_E2E_PROVIDER_TRANSCRIPT="${ROOT_DIR}/.sisyphus/evidence/issue-44-provider-transcript.jsonl" \
    ISSUE44_E2E_RUN_MANIFEST="${ROOT_DIR}/.sisyphus/evidence/issue-44-run-manifest.jsonl" \
    ISSUE44_BACKEND_LOG_PATH="${ROOT_DIR}/.dev/logs/backend.log" \
    STEPFUN_API_KEY="${STEPFUN_API_KEY:-phase4-local-e2e}" \
    SMOKE_REUSE_EXISTING_STACK=1 \
    npx playwright test tests/e2e/presentation-phase4.spec.ts --workers=1
  )
fi

if is_selected_playwright_target "tests/e2e/sales-phase4.spec.ts"; then
  log "Playwright sales Phase 4 E2E"
  stop_smoke_stack
  PHASE4_E2E_PROVIDER=local \
  PHASE4_E2E_PROVIDER_SCRIPT=sales-provider-script.v1.json \
  PHASE4_E2E_PROVIDER_TRANSCRIPT="${ROOT_DIR}/.sisyphus/evidence/issue-43-provider-transcript.jsonl" \
  ISSUE43_E2E_RUN_MANIFEST="${ROOT_DIR}/.sisyphus/evidence/issue-43-run-manifest.jsonl" \
  STEPFUN_API_KEY="${STEPFUN_API_KEY:-phase4-local-e2e}" \
  start_smoke_stack
  (
    cd "${ROOT_DIR}/web"
    PHASE4_E2E_PROVIDER=local \
    PHASE4_E2E_PROVIDER_SCRIPT=sales-provider-script.v1.json \
    PHASE4_E2E_PROVIDER_TRANSCRIPT="${ROOT_DIR}/.sisyphus/evidence/issue-43-provider-transcript.jsonl" \
    ISSUE43_E2E_RUN_MANIFEST="${ROOT_DIR}/.sisyphus/evidence/issue-43-run-manifest.jsonl" \
    STEPFUN_API_KEY="${STEPFUN_API_KEY:-phase4-local-e2e}" \
    SMOKE_REUSE_EXISTING_STACK=1 \
    npx playwright test tests/e2e/sales-phase4.spec.ts --workers=1
  )
fi

if [[ "${RUN_NEWCOMER_REAL_PROVIDER_GATE}" == "1" ]]; then
  run_newcomer_real_provider_gate
fi

if [[ "${RUN_NEWCOMER_AI_COACH_REAL_PROVIDER_GATE}" == "1" ]]; then
  run_newcomer_ai_coach_real_provider_gate
fi

# Playwright has finished. Release the smoke stack before the slower pytest
# families so background services cannot contend with test fixtures or retain
# avoidable CPU/memory during coverage collection.
stop_smoke_stack

[[ ${#BACKEND_SLOW_TARGETS[@]} -gt 0 ]] \
  || die "Selector returned no backend integration/e2e targets"
log "Policy-selected backend integration + e2e coverage append"
(
  cd "${ROOT_DIR}/backend"
  PHASE4_E2E_PROVIDER= \
    NEWCOMER_E2E_EXPECT_REAL_PROVIDER= \
    "${PYTHON_BIN}" -m pytest -c pyproject.toml \
      -o addopts="--import-mode=importlib" \
      "${BACKEND_SLOW_TARGETS[@]}" \
      --cov=src \
      --cov-branch \
      --cov-append \
      --cov-report=term-missing \
      --cov-report="json:${BACKEND_COVERAGE_REPORT}" \
      --cov-fail-under=48 \
      -q
)
[[ -s "${BACKEND_COVERAGE_REPORT}" ]] || die "Backend coverage report is missing or empty"

log "Changed-line and critical-branch coverage guard"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/check_changed_coverage.py" \
  --backend-report "${BACKEND_COVERAGE_REPORT}" \
  --frontend-report "${ROOT_DIR}/web/coverage/coverage-final.json" \
  --selector-manifest "${QUALITY_SELECTION_MANIFEST}" \
  --output "${CHANGED_COVERAGE_REPORT}" \
  --head "${QUALITY_GATE_HEAD_SHA}"
[[ -s "${CHANGED_COVERAGE_REPORT}" ]] || die "Changed coverage report is missing or empty"
[[ -s "${PLAYWRIGHT_REPORT_DIR}/index.html" ]] \
  || die "Playwright HTML evidence is missing or empty"

log "Critical quality gate passed"
