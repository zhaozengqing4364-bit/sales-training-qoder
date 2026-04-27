# ADR: Backend Python Version Support Policy

Date: 2026-04-27

## Status

Accepted for the 2026-04-27 closeout.

## Context

The backend dependency set is validated on Python 3.11 semantics (`backend/pyproject.toml` mypy `python_version = "3.11"`). Local Python 3.14 runs have emitted upstream Pydantic/LangChain/resource warnings that are outside a safe patch-level closeout.

## Decision

- Development and CI support Python `>=3.11,<3.14` until the AI dependency stack is upgraded and re-certified.
- Python 3.14 is not a supported runtime for this release line.
- `backend/pyproject.toml` constrains `requires-python` to `>=3.11,<3.14` while retaining mypy `python_version = "3.11"`.

## Owner

Platform/backend owner.

## Rollback / Forward Plan

To support Python 3.14, upgrade and re-test Pydantic/LangChain/Haystack/audio/runtime dependencies, then run full backend ruff, non-performance pytest, and `pip check` before widening `requires-python`.
