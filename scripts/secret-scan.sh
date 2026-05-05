#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TARGETS=(
  "${ROOT_DIR}/.env.example"
  "${ROOT_DIR}/backend/.env.example"
  "${ROOT_DIR}/CLAUDE.md"
  "${ROOT_DIR}/docs/setup/auth-local.md"
  "${ROOT_DIR}/specs/001-ai-practice-system/quickstart.md"
)

PATTERNS=(
  'sk-[A-Za-z0-9_-]{16,}'
  'lin_api_key_[A-Za-z0-9_-]{8,}'
  'AKIA[0-9A-Z]{16}'
  'AIza[0-9A-Za-z_-]{35}'
  'replace-with-your-fernet-key'
  '<OPENAI_API_KEY>'
  '<LINEAR_API_KEY>'
)

echo "Running secret hygiene scan..."

matches=0
for pattern in "${PATTERNS[@]}"; do
  if rg -n -e "${pattern}" "${TARGETS[@]}"; then
    matches=1
  fi
done

if [[ "${matches}" -ne 0 ]]; then
  echo "Secret hygiene scan failed: one or more high-confidence secret patterns were found." >&2
  exit 1
fi

echo "Secret hygiene scan passed."
