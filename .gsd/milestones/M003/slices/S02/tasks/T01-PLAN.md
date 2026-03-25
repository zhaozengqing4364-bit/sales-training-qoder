---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Turn Persona policy into a structured customer-pressure model

Extend the existing Persona policy schema and normalization logic so Persona behavior is described as a structured pressure model instead of only loose sales-focus strings. Add or update focused tests around `persona_policy.py` and Persona service audit behavior, and make sure old records normalize safely rather than silently dropping to generic defaults.

## Inputs

- `backend/src/agent/services/persona_policy.py`
- `backend/src/agent/services/persona_service.py`
- `backend/src/agent/api/personas.py`

## Expected Output

- `backend/src/agent/services/persona_policy.py`
- `backend/src/agent/services/persona_service.py`
- `backend/tests/unit/test_persona_policy.py`
- `backend/tests/integration/test_persona_api.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py
