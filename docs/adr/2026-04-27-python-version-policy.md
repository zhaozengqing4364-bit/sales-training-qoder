# ADR: Backend Python Version Policy for Release Closeout

Date: 2026-04-27
Status: Accepted for current release gate
Owner: Backend platform / release engineering

## Context

The backend declares `requires-python >=3.11` in `backend/pyproject.toml`, while static tooling pins Ruff/Black/Mypy behavior to Python 3.11. Prior closeout evidence showed local Python 3.14 can emit upstream dependency warnings from Pydantic/LangChain/resource cleanup paths. Those warnings are not a runtime support contract.

## Decision

- Dev and CI support target is Python 3.11 for this release train.
- Python 3.12/3.13 may be used only after the full backend gate passes in that environment.
- Python 3.14 is not a supported release/runtime target until a separate dependency-upgrade lane validates Pydantic, LangChain, Chroma/Haystack, torch/funasr, and the full backend test suite.
- Dependency drift must be caught with `backend/venv/bin/python -m pip check` and the non-performance pytest gate.

## Consequences

- We do not silently treat Python 3.14 warnings as green release evidence.
- CI images and local onboarding should prefer Python 3.11.
- Any future Python 3.14 enablement must include dependency upgrade notes, full backend tests, and rollback instructions.

## Rollback / Future Change

A future ADR can supersede this policy after a clean Python 3.14 gate with upgraded dependencies and no new runtime warnings.
