---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: Link interventions back to later session outcomes on the current evidence line

Link the intervention state back to the current report/replay evidence chain so a manager can tell whether the targeted issue family improved after a later session. Reuse existing projection/evidence semantics and admin drill-ins instead of a bespoke result screen.

## Inputs

- `backend/src/admin/api/users.py`
- `backend/src/common/analytics/history_service.py`
- `backend/tests/integration/test_admin_users_api.py`

## Expected Output

- `backend/src/admin/api/users.py`
- `backend/src/common/analytics/history_service.py`
- `backend/tests/integration/test_admin_users_api.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py
