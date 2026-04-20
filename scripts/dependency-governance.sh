#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_REQUIREMENTS="${ROOT_DIR}/backend/requirements.txt"
BACKEND_PYPROJECT="${ROOT_DIR}/backend/pyproject.toml"
WEB_DIR="${ROOT_DIR}/web"
WEB_PACKAGE_JSON="${WEB_DIR}/package.json"
WEB_LOCKFILE="${WEB_DIR}/package-lock.json"

usage() {
  cat <<'EOF'
Dependency governance baseline wrapper.

Usage:
  bash scripts/dependency-governance.sh status
  bash scripts/dependency-governance.sh web-audit
  bash scripts/dependency-governance.sh backend-audit
  bash scripts/dependency-governance.sh license-plan

Commands:
  status        Print the current governance authority files and prerequisite status.
  web-audit     Run the lockfile-backed frontend vulnerability scan.
  backend-audit Run pip_audit against backend/requirements.txt when pip_audit is installed.
  license-plan  Print the currently approved license-scan commands and their blockers.
EOF
}

log() {
  printf '%s\n' "$*"
}

fail() {
  printf '[dependency-governance] %s\n' "$*" >&2
  exit 1
}

resolve_backend_python() {
  local candidates=(
    "${ROOT_DIR}/backend/venv/bin/python"
    "${ROOT_DIR}/backend/.venv/bin/python"
    "python3"
    "python"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
    if command -v "${candidate}" >/dev/null 2>&1; then
      command -v "${candidate}"
      return 0
    fi
  done

  return 1
}

python_has_module() {
  local python_bin="$1"
  local module_name="$2"

  MODULE_NAME="${module_name}" "${python_bin}" - <<'PY' >/dev/null 2>&1
import importlib.util
import os
import sys

module_name = os.environ["MODULE_NAME"]
sys.exit(0 if importlib.util.find_spec(module_name) else 1)
PY
}

print_authority() {
  cat <<EOF
Authority files:
- frontend dependencies: web/package.json + web/package-lock.json
- backend dependencies: backend/requirements.txt
- backend packaging metadata: backend/pyproject.toml (tooling metadata only for now)

Sync rule:
- any backend dependency add/remove/upgrade is incomplete until backend/requirements.txt is updated in the same change
- do not rely on backend/pyproject.toml or CI's pip install -e .[test] as the dependency-governance source of truth until the backend package metadata defines the missing extras cleanly
EOF
}

status() {
  print_authority
  echo
  log "Prerequisite status:"

  if command -v npm >/dev/null 2>&1; then
    log "- npm: ready"
  else
    log "- npm: blocked (npm not found)"
  fi

  if [[ -f "${WEB_PACKAGE_JSON}" ]]; then
    log "- web/package.json: present"
  else
    log "- web/package.json: missing"
  fi

  if [[ -f "${WEB_LOCKFILE}" ]]; then
    log "- web/package-lock.json: present"
  else
    log "- web/package-lock.json: missing (npm audit cannot use the current lockfile baseline)"
  fi

  local backend_python=""
  if backend_python="$(resolve_backend_python 2>/dev/null)"; then
    log "- backend python: ${backend_python}"
    if python_has_module "${backend_python}" "pip_audit"; then
      log "- pip_audit: ready"
    else
      log "- pip_audit: blocked (install into backend venv before claiming backend vulnerability proof)"
    fi

    if python_has_module "${backend_python}" "piplicenses"; then
      log "- pip-licenses: ready"
    else
      log "- pip-licenses: blocked (install into backend venv before claiming backend license proof)"
    fi
  else
    log "- backend python: blocked (no backend interpreter found)"
  fi

  if command -v npx >/dev/null 2>&1; then
    log "- npx: ready (web license scan can use license-checker when network/cache is available)"
  else
    log "- npx: blocked (cannot run the suggested web license scan command)"
  fi

  if grep -q '^dependencies = \[' "${BACKEND_PYPROJECT}" && ! grep -q '^\[project.optional-dependencies\]' "${BACKEND_PYPROJECT}"; then
    log "- backend pyproject extras: drift detected (no [project.optional-dependencies] block; CI install -e .[test] is not authoritative)"
  fi

  echo
  cat <<'EOF'
Recommended next commands:
- bash scripts/dependency-governance.sh web-audit
- bash scripts/dependency-governance.sh backend-audit
- bash scripts/dependency-governance.sh license-plan
EOF
}

web_audit() {
  command -v npm >/dev/null 2>&1 || fail "npm not found"
  [[ -f "${WEB_LOCKFILE}" ]] || fail "web/package-lock.json is required for the lockfile-backed audit"
  npm audit --prefix "${WEB_DIR}"
}

backend_audit() {
  local backend_python=""
  backend_python="$(resolve_backend_python 2>/dev/null)" || fail "no backend python interpreter found"

  if ! python_has_module "${backend_python}" "pip_audit"; then
    cat <<'EOF' >&2
[dependency-governance] backend audit is blocked: pip_audit is not installed in the backend environment.
Install it into the backend venv before claiming backend vulnerability proof, for example:
  backend/venv/bin/pip install pip-audit
Then rerun:
  bash scripts/dependency-governance.sh backend-audit
EOF
    exit 2
  fi

  "${backend_python}" -m pip_audit -r "${BACKEND_REQUIREMENTS}"
}

license_plan() {
  cat <<'EOF'
Approved license-scan commands for this repo baseline:

Frontend (requires npm + npx and may need registry/network access if license-checker is not cached):
  npx --yes license-checker --start ./web --production --summary

Backend (requires pip-licenses installed into the backend venv first):
  backend/venv/bin/python -m piplicenses --from=mixed --format=json

Policy:
- do not claim license proof if these commands were not run successfully
- if a prerequisite is missing, record the blocker explicitly instead of reporting a green baseline
- review any non-permissive or unknown license before merging dependency updates
EOF
}

main() {
  local command="${1:-status}"
  case "${command}" in
    status)
      status
      ;;
    web-audit)
      web_audit
      ;;
    backend-audit)
      backend_audit
      ;;
    license-plan)
      license_plan
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
