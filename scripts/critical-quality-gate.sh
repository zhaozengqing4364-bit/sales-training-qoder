#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_DIR="${ROOT_DIR}/.sisyphus/evidence"
EVIDENCE_FILE="${EVIDENCE_DIR}/task-9-quality-gate.txt"
PLAYWRIGHT_REPORT_DIR="${EVIDENCE_DIR}/task-9-playwright-report"
PLAYWRIGHT_REPORT_HTML="${EVIDENCE_DIR}/task-9-playwright-report.html"
FOUNDATION_AI_REAL_PROVIDER_EVIDENCE="${EVIDENCE_DIR}/foundation-ai-real-provider-staging.json"
PLAYWRIGHT_LIBRARY_DIR="${PLAYWRIGHT_LIBRARY_DIR:-${ROOT_DIR}/.sisyphus/playwright-libs/root/usr/lib/x86_64-linux-gnu}"

BACKEND_PORT="${BACKEND_PORT:-3444}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_USER="${POSTGRES_USER:-dev}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dev}"
POSTGRES_DB="${POSTGRES_DB:-sales_training}"
CRITICAL_GATE_MODE="${CRITICAL_GATE_MODE:-full}"
RUN_FOUNDATION_AI_REAL_PROVIDER_GATE="${RUN_FOUNDATION_AI_REAL_PROVIDER_GATE:-0}"
FOUNDATION_AI_REAL_PROVIDER_REQUIRED="${FOUNDATION_AI_REAL_PROVIDER_REQUIRED:-0}"
FOUNDATION_AI_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED="${FOUNDATION_AI_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED:-0}"
NEWCOMER_E2E_FRESH_RUN_ID="${NEWCOMER_E2E_FRESH_RUN_ID:-fresh-$(date +%Y%m%d%H%M%S)}"
export NEWCOMER_E2E_FRESH_RUN_ID

case "${CRITICAL_GATE_MODE}" in
  foundation-ai-real-provider)
    EVIDENCE_FILE="${EVIDENCE_DIR}/task-9-foundation-ai-real-provider-gate.txt"
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

run_playwright() {
  if [[ -f "${PLAYWRIGHT_LIBRARY_DIR}/libnspr4.so" ]]; then
    env \
      LD_LIBRARY_PATH="${PLAYWRIGHT_LIBRARY_DIR}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" \
      npx playwright "$@"
    return
  fi
  npx playwright "$@"
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
  foundation-ai-real-provider)
    rm -f "${FOUNDATION_AI_REAL_PROVIDER_EVIDENCE}"
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
BACKEND_SUITE_TIMEOUT_SECONDS="${BACKEND_SUITE_TIMEOUT_SECONDS:-1500}"
VITEST_SUITE_TIMEOUT_SECONDS="${VITEST_SUITE_TIMEOUT_SECONDS:-1200}"
FOUNDATION_CAPACITY_TIMEOUT_SECONDS="${FOUNDATION_CAPACITY_TIMEOUT_SECONDS:-600}"

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

write_foundation_ai_real_provider_skip_evidence() {
  local status="$1"
  local classification="$2"
  local reason="$3"

  "${PYTHON_BIN}" - "${FOUNDATION_AI_REAL_PROVIDER_EVIDENCE}" \
    "${status}" "${classification}" "${reason}" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "contract_version": "foundation_ai_provider_staging_v1",
    "status": sys.argv[2],
    "classification": sys.argv[3],
    "reason": sys.argv[4],
    "provider": os.getenv("LLM_PROVIDER", "openai"),
    "model_configured": bool(os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")),
    "base_url_configured": bool(
        os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    ),
    "required": os.getenv("FOUNDATION_AI_REAL_PROVIDER_REQUIRED", "0") == "1",
    "credential_skip_allowed": os.getenv(
        "FOUNDATION_AI_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED", "0"
    ) == "1",
    "mode": os.getenv("CRITICAL_GATE_MODE", "full"),
    "command": (
        "CRITICAL_GATE_MODE=foundation-ai-real-provider "
        "LLM_API_KEY=... LLM_BASE_URL=... LLM_MODEL=... "
        "bash scripts/critical-quality-gate.sh"
    ),
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

is_foundation_ai_real_provider_configuration_missing() {
  local key="${LLM_API_KEY:-${OPENAI_API_KEY:-}}"
  local base_url="${LLM_BASE_URL:-${OPENAI_BASE_URL:-}}"
  local model="${LLM_MODEL:-${OPENAI_MODEL:-}}"
  [[ -z "${key}" \
    || -z "${base_url}" \
    || -z "${model}" \
    || "${key}" == "change-me" \
    || "${key}" == "test-key" \
    || "${key}" == "local-test-key" \
    || "${key}" == "replace-with-llm-api-key" \
    || "${key}" == "replace-with-openai-api-key" ]]
}

run_foundation_ai_real_provider_gate() {
  log "Foundation AI controlled real-provider staging gate"

  if is_foundation_ai_real_provider_configuration_missing; then
    write_foundation_ai_real_provider_skip_evidence \
      "skipped" \
      "provider_configuration_missing" \
      "LLM_API_KEY, LLM_BASE_URL, or LLM_MODEL is missing, or the key still uses a local/test placeholder; the Foundation AI real-provider staging gate was not executed."
    if [[ "${FOUNDATION_AI_REAL_PROVIDER_REQUIRED}" == "1" ]]; then
      die "Foundation AI real-provider gate requires non-placeholder provider credentials, base URL, and model"
    fi
    if [[ "${FOUNDATION_AI_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED}" != "1" ]]; then
      die "Foundation AI real-provider gate requires provider configuration or FOUNDATION_AI_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1"
    fi
    log "Skipped Foundation AI real-provider gate: provider_configuration_missing"
    return 0
  fi

  stop_smoke_stack
  if ! (
    cd "${ROOT_DIR}/backend"
    FOUNDATION_AI_REAL_PROVIDER_CONFIRM=1 \
      PYTHONPATH=src \
      "${PYTHON_BIN}" scripts/run_foundation_ai_provider_staging.py \
        --output "${FOUNDATION_AI_REAL_PROVIDER_EVIDENCE}"
  ); then
    die "Foundation AI real-provider staging executed but did not pass; inspect ${FOUNDATION_AI_REAL_PROVIDER_EVIDENCE}"
  fi
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
  && "${CRITICAL_GATE_MODE}" != "foundation-ai-real-provider" ]]; then
  die "Unsupported CRITICAL_GATE_MODE=${CRITICAL_GATE_MODE}"
fi

if [[ "${CRITICAL_GATE_MODE}" == "foundation-ai-real-provider" ]]; then
  run_foundation_ai_real_provider_gate
  log "Foundation AI real-provider staging gate finished"
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

log "Foundation deterministic AI gold-set quality gate"
(
  cd "${ROOT_DIR}/backend"
  PYTHONPATH=src \
    "${PYTHON_BIN}" scripts/evaluate_foundation_ai_gold_set.py \
      --output "${EVIDENCE_DIR}/foundation-ai-gold-set.json"
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
  rm -rf .next/types .next/dev/types .next-smoke/types .next-smoke/dev/types
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

log "Web production build"
(
  cd "${ROOT_DIR}/web"
  npm run build
)

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
      run_playwright test "${GENERIC_PLAYWRIGHT_TARGETS[@]}" --workers=1
  )
fi

if is_selected_playwright_target "tests/e2e/smoke.spec.ts"; then
  log "Playwright smoke E2E"
  (
    cd "${ROOT_DIR}/web"
    SMOKE_REUSE_EXISTING_STACK=1 run_playwright test tests/e2e/smoke.spec.ts
  )
fi

if is_selected_playwright_target "tests/e2e/newcomer-training-closed-loop.spec.ts"; then
  log "Playwright newcomer training closed-loop E2E"
  (
    cd "${ROOT_DIR}/web"
    SMOKE_REUSE_EXISTING_STACK=1 \
      PHASE4_E2E_PROVIDER=local \
      run_playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
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
    run_playwright test tests/e2e/presentation-phase4.spec.ts --workers=1
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
    run_playwright test tests/e2e/sales-phase4.spec.ts --workers=1
  )
fi

if [[ "${RUN_FOUNDATION_AI_REAL_PROVIDER_GATE}" == "1" ]]; then
  run_foundation_ai_real_provider_gate
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

log "Foundation capacity and concurrency baseline"
(
  cd "${ROOT_DIR}/backend"
  run_with_watchdog \
    "Foundation capacity and concurrency baseline" \
    "${FOUNDATION_CAPACITY_TIMEOUT_SECONDS}" \
    env PYTHONPATH=src \
    "${PYTHON_BIN}" -m pytest -c pyproject.toml \
      -o addopts="--import-mode=importlib" \
      tests/performance/test_foundation_capacity.py \
      -q
)
[[ -s "${EVIDENCE_DIR}/foundation-capacity-baseline.json" ]] \
  || die "Foundation capacity evidence is missing or empty"

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
