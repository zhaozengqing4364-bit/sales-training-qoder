#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="${DEV_DIR:-${ROOT_DIR}/.dev}"
LOG_DIR="${DEV_DIR}/logs"
PID_DIR="${DEV_DIR}/pids"

BACKEND_PORT="${BACKEND_PORT:-3444}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
PORTS_TO_CLEAN_RAW="${PORTS_TO_CLEAN:-}"

AUTO_START_INFRA="${AUTO_START_INFRA:-1}"

POSTGRES_USER="${POSTGRES_USER:-dev}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dev}"
POSTGRES_DB="${POSTGRES_DB:-sales_training}"

BACKEND_DATABASE_URL_DEFAULT="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
BACKEND_REDIS_URL_DEFAULT="redis://127.0.0.1:${REDIS_PORT}/0"
# Keep frontend and backend on the same loopback hostname by default.
# Using 127.0.0.1 for API while opening the frontend on localhost (or vice versa)
# creates host-only auth cookies that the Next.js app cannot read after login.
FRONTEND_API_URL_DEFAULT="http://localhost:${BACKEND_PORT}/api/v1"
FRONTEND_WS_URL_DEFAULT="ws://localhost:${BACKEND_PORT}"

EFFECTIVE_DATABASE_URL=""
EFFECTIVE_REDIS_URL=""
EFFECTIVE_FRONTEND_API_URL=""
EFFECTIVE_FRONTEND_WS_URL=""
MANAGE_POSTGRES="0"
MANAGE_REDIS="0"
PORTS_TO_CLEAN=""

_timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(_timestamp)" "$*"
}

warn() {
  printf '[%s] [WARN] %s\n' "$(_timestamp)" "$*"
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

port_pids() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

port_cleanup_pids() {
  local port="$1"
  {
    lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
    # uvicorn --reload can leave a parent process with a CLOSED fd on the
    # dev port. It is not LISTENing, but a new uvicorn bind can still fail.
    lsof -tiTCP:"${port}" -sTCP:CLOSED 2>/dev/null || true
  } | sort -u
}

is_port_busy() {
  local port="$1"
  [[ -n "$(port_pids "${port}")" ]]
}

wait_for_port() {
  local port="$1"
  local timeout_seconds="${2:-30}"
  local max_ticks=$((timeout_seconds * 2))
  local tick=0

  while (( tick < max_ticks )); do
    if is_port_busy "${port}"; then
      return 0
    fi
    sleep 0.5
    tick=$((tick + 1))
  done

  return 1
}

wait_for_port_release() {
  local port="$1"
  local timeout_seconds="${2:-5}"
  local max_ticks=$((timeout_seconds * 5))
  local tick=0

  while (( tick < max_ticks )); do
    if [[ -z "$(port_cleanup_pids "${port}")" ]]; then
      return 0
    fi
    sleep 0.2
    tick=$((tick + 1))
  done

  return 1
}

wait_for_http_ok() {
  local url="$1"
  local timeout_seconds="${2:-30}"
  local max_ticks=$((timeout_seconds * 2))
  local tick=0

  if ! command -v curl >/dev/null 2>&1; then
    warn "未检测到 curl，跳过 HTTP 健康检查：${url}"
    return 0
  fi

  while (( tick < max_ticks )); do
    if curl -fsS --max-time 2 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
    tick=$((tick + 1))
  done

  return 1
}

kill_port() {
  local port="$1"
  local pids
  pids="$(port_cleanup_pids "${port}")"

  if [[ -z "${pids}" ]]; then
    return
  fi

  log "端口 ${port} 被占用，准备释放 PID: ${pids//$'\n'/, }"
  kill ${pids} >/dev/null 2>&1 || true
  wait_for_port_release "${port}" 2 || true

  local remaining
  remaining="$(port_cleanup_pids "${port}")"
  if [[ -n "${remaining}" ]]; then
    warn "端口 ${port} 仍被占用，强制结束 PID: ${remaining//$'\n'/, }"
    kill -9 ${remaining} >/dev/null 2>&1 || true
    wait_for_port_release "${port}" 2 || true
  fi
}

brew_formula_first_match() {
  local pattern="$1"
  brew list --formula 2>/dev/null | grep -E "${pattern}" | head -n 1 || true
}

resolve_effective_env() {
  local backend_env="${ROOT_DIR}/backend/.env"
  local web_env_local="${ROOT_DIR}/web/.env.local"

  local backend_db_env
  backend_db_env="$(dotenv_get "${backend_env}" "DATABASE_URL")"
  local backend_redis_env
  backend_redis_env="$(dotenv_get "${backend_env}" "REDIS_URL")"

  local web_api_env
  web_api_env="$(dotenv_get "${web_env_local}" "NEXT_PUBLIC_API_URL")"
  local web_ws_env
  web_ws_env="$(dotenv_get "${web_env_local}" "NEXT_PUBLIC_WS_URL")"

  EFFECTIVE_DATABASE_URL="${DATABASE_URL:-${backend_db_env:-${BACKEND_DATABASE_URL_DEFAULT}}}"
  EFFECTIVE_REDIS_URL="${REDIS_URL:-${backend_redis_env:-${BACKEND_REDIS_URL_DEFAULT}}}"
  EFFECTIVE_FRONTEND_API_URL="${NEXT_PUBLIC_API_URL:-${web_api_env:-${FRONTEND_API_URL_DEFAULT}}}"
  EFFECTIVE_FRONTEND_WS_URL="${NEXT_PUBLIC_WS_URL:-${web_ws_env:-${FRONTEND_WS_URL_DEFAULT}}}"
}

resolve_infra_management_targets() {
  local postgres_host=""
  local postgres_port="${POSTGRES_PORT}"
  local redis_host=""
  local redis_port="${REDIS_PORT}"

  if [[ "${EFFECTIVE_DATABASE_URL}" =~ @([^/:?]+)(:([0-9]+))? ]]; then
    postgres_host="${BASH_REMATCH[1]}"
    postgres_port="${BASH_REMATCH[3]:-${POSTGRES_PORT}}"
  fi

  if [[ "${EFFECTIVE_REDIS_URL}" =~ ^redis://([^@/]+@)?([^:/?]+)(:([0-9]+))? ]]; then
    redis_host="${BASH_REMATCH[2]}"
    redis_port="${BASH_REMATCH[4]:-${REDIS_PORT}}"
  fi

  if [[ "${postgres_host}" =~ ^(127\.0\.0\.1|localhost|::1)$ ]] && [[ "${postgres_port}" == "${POSTGRES_PORT}" ]]; then
    MANAGE_POSTGRES="1"
  fi

  if [[ "${redis_host}" =~ ^(127\.0\.0\.1|localhost|::1)$ ]] && [[ "${redis_port}" == "${REDIS_PORT}" ]]; then
    MANAGE_REDIS="1"
  fi
}

resolve_ports_to_clean() {
  if [[ -n "${PORTS_TO_CLEAN_RAW}" ]]; then
    local configured_ports=()
    IFS=',' read -r -a configured_ports <<< "${PORTS_TO_CLEAN_RAW}"
    local port
    local resolved_ports=()
    for port in "${configured_ports[@]}"; do
      port="${port// /}"
      [[ -n "${port}" ]] || continue
      if ! [[ "${port}" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
        die "PORTS_TO_CLEAN 包含非法端口：${port}"
      fi
      resolved_ports+=("${port}")
    done
    PORTS_TO_CLEAN="$(IFS=','; printf '%s' "${resolved_ports[*]}")"
    return
  fi

  local ports=("${BACKEND_PORT}" "${FRONTEND_PORT}")

  PORTS_TO_CLEAN="$(IFS=','; printf '%s' "${ports[*]}")"
}

start_postgres_brew() {
  if [[ "${MANAGE_POSTGRES}" != "1" ]]; then
    return
  fi

  if is_port_busy "${POSTGRES_PORT}"; then
    log "PostgreSQL 端口 ${POSTGRES_PORT} 已可用。"
    return
  fi

  local formula
  formula="$(brew_formula_first_match '^postgresql(@[0-9]+)?$')"
  if [[ -z "${formula}" ]]; then
    warn "未找到 brew 安装的 PostgreSQL 公式"
    return
  fi

  log "使用 brew services 启动 ${formula}..."
  brew services start "${formula}" >/dev/null 2>&1 || warn "brew 启动 ${formula} 失败"
  wait_for_port "${POSTGRES_PORT}" 30 && log "PostgreSQL 就绪：127.0.0.1:${POSTGRES_PORT}"
}

start_redis_brew() {
  if [[ "${MANAGE_REDIS}" != "1" ]]; then
    return
  fi

  if is_port_busy "${REDIS_PORT}"; then
    log "Redis 端口 ${REDIS_PORT} 已可用。"
    return
  fi

  if ! brew list --formula redis >/dev/null 2>&1; then
    warn "未找到 brew 安装的 Redis 公式"
    return
  fi

  log "使用 brew services 启动 redis..."
  brew services start redis >/dev/null 2>&1 || warn "brew 启动 redis 失败"
  wait_for_port "${REDIS_PORT}" 20 && log "Redis 就绪：127.0.0.1:${REDIS_PORT}"
}

start_infra_services() {
  if [[ "${AUTO_START_INFRA}" != "1" ]]; then
    warn "AUTO_START_INFRA=${AUTO_START_INFRA}，跳过 PostgreSQL/Redis 自动启动"
    return
  fi

  if [[ "${MANAGE_POSTGRES}" != "1" && "${MANAGE_REDIS}" != "1" ]]; then
    log "当前 DATABASE_URL/REDIS_URL 非本机端口，跳过本机依赖服务拉起。"
    return
  fi

  if ! command -v brew >/dev/null 2>&1; then
    warn "未检测到 brew，无法自动启动 PostgreSQL/Redis"
    return
  fi

  start_postgres_brew
  start_redis_brew
}

verify_infra_ports() {
  if [[ "${MANAGE_POSTGRES}" == "1" ]] && ! is_port_busy "${POSTGRES_PORT}"; then
    die "PostgreSQL 未就绪（端口 ${POSTGRES_PORT} 不可用）。请先启动数据库，或安装 brew 后使用 AUTO_START_INFRA=1。"
  fi

  if [[ "${MANAGE_REDIS}" == "1" ]] && ! is_port_busy "${REDIS_PORT}"; then
    die "Redis 未就绪（端口 ${REDIS_PORT} 不可用）。请先启动 Redis，或安装 brew 后使用 AUTO_START_INFRA=1。"
  fi
}

ensure_env_files() {
  if [[ ! -f "${ROOT_DIR}/backend/.env" && -f "${ROOT_DIR}/backend/.env.example" ]]; then
    cp "${ROOT_DIR}/backend/.env.example" "${ROOT_DIR}/backend/.env"
    log "已创建 backend/.env（基于 .env.example）"
  fi

  if [[ ! -f "${ROOT_DIR}/web/.env.local" && -f "${ROOT_DIR}/web/.env.example" ]]; then
    cp "${ROOT_DIR}/web/.env.example" "${ROOT_DIR}/web/.env.local"
    log "已创建 web/.env.local（基于 .env.example）"
  fi
}

resolve_python_bin() {
  local override_python="${BACKEND_PYTHON:-}"
  local candidates=(
    "${ROOT_DIR}/backend/.venv/bin/python"
    "${ROOT_DIR}/backend/venv/bin/python"
  )

  if [[ -n "${override_python}" ]]; then
    candidates=("${override_python}" "${candidates[@]}")
  fi

  candidates+=("python3" "python")

  local candidate
  for candidate in "${candidates[@]}"; do
    local resolved_python=""
    if [[ -x "${candidate}" ]]; then
      resolved_python="${candidate}"
    elif command -v "${candidate}" >/dev/null 2>&1; then
      resolved_python="$(command -v "${candidate}")"
    else
      continue
    fi

    if "${resolved_python}" - <<'PY' >/dev/null 2>&1; then
import dotenv
import fastapi
import uvicorn
PY
      printf '%s\n' "${resolved_python}"
      return 0
    fi

    if [[ -n "${override_python}" && "${candidate}" == "${override_python}" ]]; then
      die "BACKEND_PYTHON=${override_python} 缺少后端运行依赖（至少需要 python-dotenv、fastapi、uvicorn）"
    fi

    warn "跳过 Python 解释器 ${resolved_python}：缺少后端运行依赖" >&2
  done

  return 1
}

start_backend() {
  local python_bin
  python_bin="$(resolve_python_bin)" || die "未找到 Python 解释器，请先配置后端环境"

  log "启动 Backend (端口 ${BACKEND_PORT})，Python: ${python_bin}"
  (
    cd "${ROOT_DIR}/backend"
    nohup env \
      DATABASE_URL="${EFFECTIVE_DATABASE_URL}" \
      REDIS_URL="${EFFECTIVE_REDIS_URL}" \
      PYTHONPATH="${ROOT_DIR}/backend/src${PYTHONPATH:+:${PYTHONPATH}}" \
      "${python_bin}" -m uvicorn src.main:app --reload --port "${BACKEND_PORT}" \
      >"${LOG_DIR}/backend.log" 2>&1 &
    echo $! > "${PID_DIR}/backend.pid"
  )

  wait_for_port "${BACKEND_PORT}" 45 && wait_for_http_ok "http://127.0.0.1:${BACKEND_PORT}/health" 45 || {
    tail -n 80 "${LOG_DIR}/backend.log" >&2 || true
    die "Backend 启动失败，请查看日志 ${LOG_DIR}/backend.log"
  }

  log "Backend 已启动：http://localhost:${BACKEND_PORT}"
}

start_frontend() {
  require_cmd npm

  log "启动 Frontend (端口 ${FRONTEND_PORT})..."
  (
    cd "${ROOT_DIR}/web"
    nohup env \
      NEXT_PUBLIC_API_URL="${EFFECTIVE_FRONTEND_API_URL}" \
      NEXT_PUBLIC_WS_URL="${EFFECTIVE_FRONTEND_WS_URL}" \
      npm exec -- next dev -p "${FRONTEND_PORT}" \
      >"${LOG_DIR}/frontend.log" 2>&1 &
    echo $! > "${PID_DIR}/frontend.pid"
  )

  wait_for_port "${FRONTEND_PORT}" 60 || {
    tail -n 80 "${LOG_DIR}/frontend.log" >&2 || true
    die "Frontend 启动失败，请查看日志 ${LOG_DIR}/frontend.log"
  }

  log "Frontend 已启动：http://localhost:${FRONTEND_PORT}"
}

print_summary() {
  cat <<SUMMARY

✅ 一键开发环境启动完成（纯本机模式，无 Docker）

- Frontend: http://localhost:${FRONTEND_PORT}
- Backend API: http://localhost:${BACKEND_PORT}/api/v1
- Backend Docs: http://localhost:${BACKEND_PORT}/docs
- DATABASE_URL: ${EFFECTIVE_DATABASE_URL}
- REDIS_URL: ${EFFECTIVE_REDIS_URL}

日志文件：
- ${LOG_DIR}/backend.log
- ${LOG_DIR}/frontend.log

常用命令：
- 查看后端日志：tail -f ${LOG_DIR}/backend.log
- 查看前端日志：tail -f ${LOG_DIR}/frontend.log
- 一键停止：bash ${ROOT_DIR}/scripts/dev-stop.sh
SUMMARY
}

main() {
  require_cmd lsof

  mkdir -p "${LOG_DIR}" "${PID_DIR}"

  ensure_env_files
  resolve_effective_env
  resolve_infra_management_targets
  resolve_ports_to_clean

  log "准备释放端口：${PORTS_TO_CLEAN}"
  IFS=',' read -r -a ports <<< "${PORTS_TO_CLEAN}"
  local port
  for port in "${ports[@]}"; do
    port="${port// /}"
    [[ -n "${port}" ]] || continue
    kill_port "${port}"
  done

  start_infra_services
  verify_infra_ports
  start_backend
  start_frontend
  print_summary
}

main "$@"
