#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="${DEV_DIR:-${ROOT_DIR}/.dev}"
PID_DIR="${DEV_DIR}/pids"

BACKEND_PORT="${BACKEND_PORT:-3444}"
FRONTEND_PORT="${FRONTEND_PORT:-3445}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"

PORTS_TO_CLEAN="${PORTS_TO_CLEAN:-${BACKEND_PORT},${FRONTEND_PORT}}"
STOP_INFRA="${STOP_INFRA:-0}"

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

stop_pid_file() {
  local name="$1"
  local pid_file="${PID_DIR}/${name}.pid"

  if [[ ! -f "${pid_file}" ]]; then
    return
  fi

  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    rm -f "${pid_file}"
    return
  fi

  if kill -0 "${pid}" >/dev/null 2>&1; then
    log "停止 ${name} 进程 PID=${pid}"
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "${pid}" >/dev/null 2>&1; then
      warn "强制停止 ${name} 进程 PID=${pid}"
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
  fi

  rm -f "${pid_file}"
}

brew_formula_first_match() {
  local pattern="$1"
  brew list --formula 2>/dev/null | grep -E "${pattern}" | head -n 1 || true
}

stop_infra_with_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    warn "未检测到 brew，跳过基础服务停止"
    return
  fi

  if brew list --formula redis >/dev/null 2>&1; then
    log "停止 brew redis"
    brew services stop redis >/dev/null 2>&1 || warn "停止 redis 失败"
  fi

  local pg_formula
  pg_formula="$(brew_formula_first_match '^postgresql(@[0-9]+)?$')"
  if [[ -n "${pg_formula}" ]]; then
    log "停止 brew ${pg_formula}"
    brew services stop "${pg_formula}" >/dev/null 2>&1 || warn "停止 ${pg_formula} 失败"
  fi
}

main() {
  if ! command -v lsof >/dev/null 2>&1; then
    echo "[ERROR] 缺少命令: lsof" >&2
    exit 1
  fi

  stop_pid_file "backend"
  stop_pid_file "frontend"

  IFS=',' read -r -a ports <<< "${PORTS_TO_CLEAN}"
  local port
  for port in "${ports[@]}"; do
    port="${port// /}"
    [[ -n "${port}" ]] || continue
    kill_port "${port}"
  done

  if [[ "${STOP_INFRA}" == "1" ]]; then
    stop_infra_with_brew
    kill_port "${POSTGRES_PORT}"
    kill_port "${REDIS_PORT}"
  fi

  log "开发环境停止完成"
}

main "$@"
