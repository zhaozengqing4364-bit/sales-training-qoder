---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: 抽出 latest-evaluable result resolver

Extract latest-evaluable intervention-result resolution from `HistoryService` into a dedicated helper/module so supervisor workflow semantics are explicit and reusable. Keep the current rule that the latest evaluable completed session after intervention creation wins over a later thin non-evaluable session.

## Inputs

- `backend/src/common/analytics/history_service.py`
- `backend/src/admin/api/users.py`
- `backend/tests/integration/test_admin_users_api.py`

## Expected Output

- `Dedicated intervention-result resolver module/service`
- ``HistoryService` delegates manager intervention result building instead of owning the detailed workflow semantics inline`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py
