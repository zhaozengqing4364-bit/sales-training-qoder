# ADR: Backend Python Runtime Support Policy

Date: 2026-04-27
Status: Accepted
Owner: Backend platform

## Context

The remediation closeout found Python 3.14 warnings from upstream dependencies, notably LangChain/Pydantic v1 compatibility shims. Upgrading that stack safely requires a separate dependency migration and full regression pass because the backend uses FastAPI, Pydantic 2, LangChain, ChromaDB and Haystack across runtime-critical sales and presentation paths.

## Decision

Backend development and CI support Python `>=3.11,<3.14`. Python 3.11 is the primary supported version for full verification. Python 3.14 is not a supported runtime for this release train.

`backend/pyproject.toml` now declares `requires-python = ">=3.11,<3.14"`; mypy and ruff remain pinned to Python 3.11 semantics.

## Consequences

- Existing Python 3.14 local environments may still run parts of the test suite, but warnings from upstream compatibility shims are policy-blocked rather than release-blocking.
- CI/dev bootstrap should create a Python 3.11/3.12/3.13 environment, with 3.11 preferred until the dependency stack is upgraded.
- A future Python 3.14 support project must upgrade/remove Pydantic v1 compatibility shims and rerun full backend tests, ruff, mypy/typing checks, and `pip check`.

## Rollback

Revert this ADR and the `backend/pyproject.toml` upper bound only after a dedicated Python 3.14 dependency migration passes full backend verification.
