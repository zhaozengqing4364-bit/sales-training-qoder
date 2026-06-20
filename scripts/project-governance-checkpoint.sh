#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_ROOT="${PROJECT_GOVERNANCE_EVIDENCE_ROOT:-${ROOT_DIR}/.omo/evidence/project-governance-refactor}"
QUALITY_GATE_SOURCE="${PROJECT_GOVERNANCE_QUALITY_GATE_SOURCE:-${ROOT_DIR}/.sisyphus/evidence/task-9-quality-gate.txt}"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

usage() {
  printf '%s\n' \
    "Usage:" \
    "  bash scripts/project-governance-checkpoint.sh dry-checkpoint [evidence-file]" \
    "  bash scripts/project-governance-checkpoint.sh mirror-quality-gate" \
    "" \
    "dry-checkpoint records git status and Alembic heads into .omo evidence." \
    "mirror-quality-gate copies the canonical critical-quality-gate evidence into the project-governance evidence index."
}

ensure_parent_dir() {
  local path="$1"
  mkdir -p "$(dirname "${path}")"
}

alembic_heads() {
  cd "${ROOT_DIR}/backend"
  alembic heads
}

dry_checkpoint() {
  local evidence_file="${1:-${EVIDENCE_ROOT}/checkpoints/$(date '+%Y%m%d-%H%M%S')-dry-checkpoint.txt}"
  ensure_parent_dir "${evidence_file}"

  {
    printf 'project-governance-checkpoint\n'
    printf 'gate_type=dry-checkpoint\n'
    printf 'generated_at=%s\n' "$(timestamp)"
    printf 'evidence_file=%s\n\n' "${evidence_file}"

    printf '$ git status --short\n'
    cd "${ROOT_DIR}"
    git status --short

    printf '\n$ cd backend && alembic heads\n'
    alembic_heads
  } 2>&1 | tee "${evidence_file}"
}

mirror_quality_gate() {
  if [[ ! -f "${QUALITY_GATE_SOURCE}" ]]; then
    printf 'Canonical quality gate evidence not found: %s\n' "${QUALITY_GATE_SOURCE}" >&2
    printf 'Run bash scripts/critical-quality-gate.sh first, then mirror its artifact.\n' >&2
    exit 1
  fi

  local quality_gate_dir="${EVIDENCE_ROOT}/quality-gate"
  local mirror_file="${quality_gate_dir}/task-9-quality-gate.txt"
  local index_file="${quality_gate_dir}/index.md"
  mkdir -p "${quality_gate_dir}"
  cp "${QUALITY_GATE_SOURCE}" "${mirror_file}"

  local sha256="unavailable"
  if command -v shasum >/dev/null 2>&1; then
    sha256="$(shasum -a 256 "${mirror_file}" | awk '{print $1}')"
  fi

  {
    printf '# Project Governance Quality Gate Evidence\n\n'
    printf -- '- canonical_command: `bash scripts/critical-quality-gate.sh`\n'
    printf -- '- canonical_source: `%s`\n' "${QUALITY_GATE_SOURCE}"
    printf -- '- omo_mirror: `%s`\n' "${mirror_file}"
    printf -- '- mirrored_at: `%s`\n' "$(timestamp)"
    printf -- '- sha256: `%s`\n\n' "${sha256}"
    printf 'This file is an index only. The executable release truth remains `scripts/critical-quality-gate.sh`.\n'
  } >"${index_file}"

  printf 'Mirrored quality gate evidence to %s\n' "${mirror_file}"
  printf 'Updated quality gate index at %s\n' "${index_file}"
}

main() {
  local command="${1:-}"
  case "${command}" in
    dry-checkpoint)
      shift
      dry_checkpoint "${1:-}"
      ;;
    mirror-quality-gate)
      mirror_quality_gate
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
