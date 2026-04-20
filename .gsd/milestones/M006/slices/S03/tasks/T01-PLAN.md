---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: 抽出 ManagerIntervention write-side service

Create a dedicated write-side service under `backend/src/admin/services/` to own `manager_interventions` create/load/update/remind rules, including due-state/reminder-state transitions and latest-open lookup. Refactor `/api/v1/admin/interventions` routes to delegate to it without changing response payloads.

## Inputs

- `backend/src/admin/api/interventions.py`
- `backend/tests/integration/test_admin_interventions_api.py`

## Expected Output

- `New write-side manager intervention service`
- ``/admin/interventions` routes slimmed down to transport + authorization + service calls`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py
