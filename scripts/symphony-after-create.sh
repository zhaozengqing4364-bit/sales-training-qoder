#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bool_enabled() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    0|false|FALSE|no|NO|off|OFF) return 1 ;;
    *) return 1 ;;
  esac
}

log() {
  printf '[symphony-after-create] %s\n' "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '[symphony-after-create] missing command: %s\n' "$1" >&2
    return 1
  }
}

bootstrap_web() {
  bool_enabled "${SYMPHONY_BOOTSTRAP_WEB:-1}" || {
    log 'Skipping web dependency bootstrap (SYMPHONY_BOOTSTRAP_WEB=0).'
    return 0
  }

  require_cmd npm

  if [[ -f "${ROOT_DIR}/web/package-lock.json" ]]; then
    log 'Installing web dependencies with npm ci.'
    npm --prefix "${ROOT_DIR}/web" ci
  else
    log 'web/package-lock.json not found; falling back to npm install.'
    npm --prefix "${ROOT_DIR}/web" install
  fi
}

bootstrap_backend() {
  bool_enabled "${SYMPHONY_BOOTSTRAP_BACKEND:-0}" || {
    log 'Skipping backend dependency bootstrap (set SYMPHONY_BOOTSTRAP_BACKEND=1 to enable).'
    return 0
  }

  local python_bin="${SYMPHONY_BACKEND_PYTHON:-python3}"
  require_cmd "${python_bin}"

  local venv_dir="${ROOT_DIR}/backend/venv"
  local python_in_venv="${venv_dir}/bin/python"

  if [[ ! -x "${python_in_venv}" ]]; then
    log "Creating backend virtualenv at ${venv_dir}."
    "${python_bin}" -m venv "${venv_dir}"
  fi

  log 'Installing backend dependencies from backend/requirements.txt.'
  "${python_in_venv}" -m pip install --upgrade pip
  "${python_in_venv}" -m pip install -r "${ROOT_DIR}/backend/requirements.txt"
}

main() {
  cd "${ROOT_DIR}"
  git config rerere.enabled true
  git config rerere.autoupdate true

  bootstrap_web
  bootstrap_backend

  log 'Workspace bootstrap complete.'
}

main "$@"
