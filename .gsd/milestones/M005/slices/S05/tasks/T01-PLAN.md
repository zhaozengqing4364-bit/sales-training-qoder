---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T01: Assemble the regression pack for the current admin operating chain

Assemble the regression pack for the current admin chain so analytics, users, interventions, manager-lite, and export stay on one evidence vocabulary. Reuse the focused backend/web suites created by earlier slices instead of a new acceptance framework.

## Inputs

- `backend/tests/contract/test_analytics.py`
- `backend/tests/integration/test_admin_users_api.py`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`

## Expected Output

- `backend/tests/contract/test_analytics.py`
- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/integration/test_admin_interventions_api.py`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_analytics.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py && cd ../web && npm test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
