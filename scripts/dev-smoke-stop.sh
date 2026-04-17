#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="${DEV_DIR:-${ROOT_DIR}/.dev}"
STATE_FILE="${DEV_DIR}/smoke/state.env"

BACKEND_PORT="${BACKEND_PORT:-3444}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"

SMOKE_PREEXISTING_POSTGRES="1"
SMOKE_PREEXISTING_REDIS="1"

_timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(_timestamp)" "$*"
}

warn() {
  printf '[%s] [WARN] %s\n' "$(_timestamp)" "$*"
}

port_pids() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

kill_port() {
  local port="$1"
  local pids
  pids="$(port_pids "${port}")"

  if [[ -z "${pids}" ]]; then
    return
  fi

  log "停止端口 ${port} 占用进程: ${pids//$'\n'/, }"
  kill ${pids} >/dev/null 2>&1 || true
  sleep 1

  local remaining
  remaining="$(port_pids "${port}")"
  if [[ -n "${remaining}" ]]; then
    warn "强制停止端口 ${port} 占用进程: ${remaining//$'\n'/, }"
    kill -9 ${remaining} >/dev/null 2>&1 || true
  fi
}

brew_formula_first_match() {
  local pattern="$1"
  brew list --formula 2>/dev/null | grep -E "${pattern}" | head -n 1 || true
}

stop_postgres_if_owned() {
  if [[ "${SMOKE_PREEXISTING_POSTGRES}" == "1" ]]; then
    return
  fi

  if command -v brew >/dev/null 2>&1; then
    local pg_formula
    pg_formula="$(brew_formula_first_match '^postgresql(@[0-9]+)?$')"
    if [[ -n "${pg_formula}" ]]; then
      log "停止 smoke 启动的 ${pg_formula}"
      brew services stop "${pg_formula}" >/dev/null 2>&1 || warn "停止 ${pg_formula} 失败"
    fi
  fi

  kill_port "${POSTGRES_PORT}"
}

stop_redis_if_owned() {
  if [[ "${SMOKE_PREEXISTING_REDIS}" == "1" ]]; then
    return
  fi

  if command -v brew >/dev/null 2>&1 && brew list --formula redis >/dev/null 2>&1; then
    log "停止 smoke 启动的 redis"
    brew services stop redis >/dev/null 2>&1 || warn "停止 redis 失败"
  fi

  kill_port "${REDIS_PORT}"
}

main() {
  if [[ -f "${STATE_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${STATE_FILE}"
  fi

  bash "${ROOT_DIR}/scripts/dev-stop.sh"
  stop_postgres_if_owned
  stop_redis_if_owned
  rm -f "${STATE_FILE}"
}

main "$@"
