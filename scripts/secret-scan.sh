#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="${SECRET_SCAN_REPORT:-${ROOT_DIR}/.sisyphus/evidence/secret-scan-report.json}"

echo "Running secret hygiene scan..."
python3 "${ROOT_DIR}/scripts/check_secret_hygiene.py" --report "${REPORT_PATH}" "$@"
echo "Secret hygiene scan report: ${REPORT_PATH}"
