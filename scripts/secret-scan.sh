#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="${SECRET_SCAN_REPORT:-${ROOT_DIR}/.sisyphus/evidence/secret-scan-report.json}"
PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/backend/.venv/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

echo "Running secret hygiene scan..."
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/check_secret_hygiene.py" --report "${REPORT_PATH}" "$@"
echo "Secret hygiene scan report: ${REPORT_PATH}"
