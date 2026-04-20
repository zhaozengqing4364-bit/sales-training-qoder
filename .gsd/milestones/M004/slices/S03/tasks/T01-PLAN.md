---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: Extend the current retry-entry contract with a structured focus intent

Extend the current retry-entry contract so it can carry a structured focus intent derived from `main_issue` / `next_goal` without inventing a second launch system. Keep the source of truth on current report/practice APIs and lock it with focused contract tests.

## Inputs

- `backend/src/common/api/practice.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`

## Expected Output

- `backend/src/common/api/practice.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
