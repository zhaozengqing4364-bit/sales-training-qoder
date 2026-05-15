#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="${DEV_DIR:-${ROOT_DIR}/.dev}"
STATE_DIR="${DEV_DIR}/smoke"
STATE_FILE="${STATE_DIR}/state.env"

BACKEND_PORT="${BACKEND_PORT:-3444}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_USER="${POSTGRES_USER:-dev}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dev}"
POSTGRES_DB="${POSTGRES_DB:-sales_training}"

BACKEND_ENV_FILE="${ROOT_DIR}/backend/.env"
DEFAULT_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
EFFECTIVE_DATABASE_URL=""

SMOKE_ADMIN_EMAIL="${SMOKE_ADMIN_EMAIL:-admin@qoder.ai}"
SMOKE_ADMIN_NAME="${SMOKE_ADMIN_NAME:-管理员}"
SMOKE_ADMIN_PASSWORD="${SMOKE_ADMIN_PASSWORD:-change-me}"

_timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(_timestamp)" "$*"
}

die() {
  printf '[%s] [ERROR] %s\n' "$(_timestamp)" "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
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

resolve_effective_database_url() {
  local backend_db_env
  backend_db_env="$(dotenv_get "${BACKEND_ENV_FILE}" "DATABASE_URL")"
  EFFECTIVE_DATABASE_URL="${DATABASE_URL:-${backend_db_env:-${DEFAULT_DATABASE_URL}}}"
}

port_pids() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

is_port_busy() {
  local port="$1"
  [[ -n "$(port_pids "${port}")" ]]
}

wait_for_url() {
  local url="$1"
  local timeout_seconds="${2:-60}"
  local max_ticks=$((timeout_seconds * 2))
  local tick=0

  while (( tick < max_ticks )); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
    tick=$((tick + 1))
  done

  return 1
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

    if "${resolved}" - <<'PY' >/dev/null 2>&1; then
import sqlalchemy
import dotenv
PY
      printf '%s\n' "${resolved}"
      return 0
    fi
  done

  return 1
}

record_prior_state() {
  mkdir -p "${STATE_DIR}"

  local postgres_busy="0"
  local redis_busy="0"

  if is_port_busy "${POSTGRES_PORT}"; then
    postgres_busy="1"
  fi

  if is_port_busy "${REDIS_PORT}"; then
    redis_busy="1"
  fi

  cat > "${STATE_FILE}" <<EOF
SMOKE_PREEXISTING_POSTGRES=${postgres_busy}
SMOKE_PREEXISTING_REDIS=${redis_busy}
POSTGRES_PORT=${POSTGRES_PORT}
REDIS_PORT=${REDIS_PORT}
EOF
}

append_state_entry() {
  local key="$1"
  local value="$2"
  printf '%s=%s\n' "${key}" "${value}" >> "${STATE_FILE}"
}

bootstrap_smoke_admin() {
  local python_bin
  python_bin="$(resolve_python_bin)" || die "未找到 Python 解释器，无法引导 smoke 管理员账号"

  "${python_bin}" "${ROOT_DIR}/backend/scripts/bootstrap_auth_admin.py" \
    --email "${SMOKE_ADMIN_EMAIL}" \
    --name "${SMOKE_ADMIN_NAME}" \
    --role admin
}

bootstrap_smoke_practice_evidence() {
  local python_bin
  python_bin="$(resolve_python_bin)" || die "未找到 Python 解释器，无法引导 smoke 报告/回放证据"

  local seed_output
  seed_output="$(${python_bin} "${ROOT_DIR}/backend/scripts/bootstrap_smoke_practice_evidence.py" --email "${SMOKE_ADMIN_EMAIL}")"
  printf '%s\n' "${seed_output}"

  while IFS='=' read -r key value; do
    case "${key}" in
      SMOKE_REPORT_SESSION_ID|SMOKE_REPORT_PATH|SMOKE_REPLAY_PATH)
        append_state_entry "${key}" "${value}"
        ;;
    esac
  done <<< "${seed_output}"
}

run_alembic_upgrade_head() {
  local python_bin
  python_bin="$(resolve_python_bin)" || die "未找到 Python 解释器，无法执行 Alembic 迁移"

  log "[smoke] Running alembic upgrade head before bootstrap..."
  (
    cd "${ROOT_DIR}/backend"
    DATABASE_URL="${EFFECTIVE_DATABASE_URL}" "${python_bin}" -m alembic upgrade head
  )
}

main() {
  require_cmd curl
  require_cmd lsof

  local default_auth_user_passwords_json
  default_auth_user_passwords_json="$(printf '{"%s":"%s"}' "${SMOKE_ADMIN_EMAIL}" "${SMOKE_ADMIN_PASSWORD}")"

  export AUTH_SHARED_PASSWORD="${AUTH_SHARED_PASSWORD:-${SMOKE_ADMIN_PASSWORD}}"
  export AUTH_USER_PASSWORDS_JSON="${AUTH_USER_PASSWORDS_JSON:-${default_auth_user_passwords_json}}"

  resolve_effective_database_url
  export DATABASE_URL="${EFFECTIVE_DATABASE_URL}"

  record_prior_state

  log "使用 smoke 启动约定拉起本地全栈环境"
  bash "${ROOT_DIR}/scripts/dev-up.sh"

  run_alembic_upgrade_head

  wait_for_url "http://localhost:${BACKEND_PORT}/health" 45 || die "Backend health 检查失败"
  wait_for_url "http://localhost:${FRONTEND_PORT}/login" 60 || die "Frontend login 页面未就绪"

  bootstrap_smoke_admin
  bootstrap_smoke_practice_evidence

  cat <<SUMMARY

✅ Smoke baseline 已就绪

- Frontend: http://localhost:${FRONTEND_PORT}
- Backend health: http://localhost:${BACKEND_PORT}/health
- Smoke admin: ${SMOKE_ADMIN_EMAIL}
- Smoke password: ${SMOKE_ADMIN_PASSWORD}
- Smoke report route: $(grep -E '^SMOKE_REPORT_PATH=' "${STATE_FILE}" | tail -n 1 | cut -d'=' -f2-)
- Smoke replay route: $(grep -E '^SMOKE_REPLAY_PATH=' "${STATE_FILE}" | tail -n 1 | cut -d'=' -f2-)
- 停止命令: bash ${ROOT_DIR}/scripts/dev-smoke-stop.sh
SUMMARY
}

main "$@"
