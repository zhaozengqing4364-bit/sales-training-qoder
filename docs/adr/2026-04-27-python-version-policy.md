# ADR 2026-04-27: Backend Python version support policy

## Status
Accepted

## Context
The backend package declares `requires-python = ">=3.11"` and mypy targets Python 3.11, while local verification may run with Python 3.14. Python 3.14 currently emits upstream compatibility warnings from dependencies such as LangChain/Pydantic v1 compatibility shims and ChromaDB telemetry. The warnings do not fail the current test suite, but they are not a release signal that Python 3.14 is fully supported.

## Decision
- Development and CI support is pinned to Python 3.11 until the Pydantic/LangChain/ChromaDB dependency stack is explicitly upgraded and verified on a newer Python minor.
- Python 3.14 is allowed only as a best-effort local smoke environment; warnings from upstream packages must be documented in closeout reports and must not be hidden by test skips.
- Any future change to officially support Python 3.14 must include dependency upgrades, `backend/pyproject.toml` updates, full backend tests, `ruff`, and `pip check` evidence.

## Consequences
- CI remains aligned with `.github/workflows/*` Python 3.11 configuration and `backend/pyproject.toml` mypy settings.
- The current remediation pass treats Python 3.14 as `deferred-with-ADR`, not silently ignored.
- No dependency upgrades are made solely to silence local 3.14 warnings unless the full backend gate can be re-run safely.

## Owner
Platform/backend maintainers.

## Rollback
If Python 3.14 support is required for release, supersede this ADR with an upgrade ADR and update CI, dependency pins, and backend verification gates in one change.
