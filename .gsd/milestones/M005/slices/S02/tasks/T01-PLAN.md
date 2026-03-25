---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Persist the minimal manager intervention record on current admin APIs

Introduce a minimal persistent intervention record on the current admin backend chain: target issue family, note, due state, reminder status, and optional resolving session linkage. Keep it small and tied to current admin users/intervention routes rather than building a general task platform.

## Inputs

- `backend/src/admin/api/interventions.py`
- `backend/src/admin/api/users.py`
- `backend/src/common/db/models.py`

## Expected Output

- `backend/src/admin/api/interventions.py`
- `backend/src/common/db/models.py`
- `backend/src/common/db/schemas.py`
- `backend/tests/integration/test_admin_interventions_api.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py
