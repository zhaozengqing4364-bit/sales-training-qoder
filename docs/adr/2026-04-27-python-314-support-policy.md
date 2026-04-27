# ADR — Python 3.14 Support Policy for Backend Runtime

Date: 2026-04-27
Status: Accepted
Owner: Backend Platform / Release Engineering
Related audit item: A-014

## Decision

The backend development and CI support target remains Python 3.11 for this release line.  The authoritative settings are:

- `backend/pyproject.toml` → `requires-python = ">=3.11"`, Ruff/Black target `py311`, mypy `python_version = "3.11"`.
- `.github/workflows/release-truth-gate.yml` → `actions/setup-python` uses `3.11`.
- `.github/workflows/nfr-performance-check.yml` → `PYTHON_VERSION: '3.11'`.
- Backend dependency authority remains `backend/requirements.txt` plus `backend/pyproject.toml`.

Python 3.14 is not a supported dev/CI runtime until a dedicated dependency-upgrade track validates Pydantic, LangChain/Haystack, Chroma/vector dependencies, ASR/TTS packages, and the full backend non-performance suite under 3.14.

## Rationale

Local Python 3.14 runs can emit upstream dependency/resource warnings outside this codebase's control.  Treating those warnings as release blockers would create noisy, non-reproducible gates while CI and project configuration explicitly run Python 3.11.  A silent ignore is also unacceptable, so this ADR pins the policy and gives release engineering an owner and upgrade path.

## Consequences

- Contributors should create/use `backend/venv` with Python 3.11 for backend tests.
- CI must continue to install Python 3.11 until this ADR is superseded.
- Any future Python 3.14 support change must include dependency upgrades, `pip check`, `ruff`, full `pytest -m 'not performance'`, and a release-truth gate run.

## Rollback / Supersedence

Supersede this ADR with a new Python 3.14 enablement ADR only after green full backend gates and an explicit dependency compatibility matrix.
