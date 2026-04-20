---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: 回归证明 current supervisor workflow 无漂移

Run the current supervisor workflow regression path end-to-end after the service extraction and update the user-detail focused UI assertions if any copy or ordering assumptions need to be anchored more explicitly. The goal is zero behavior drift on the shipped `/admin/users/[id]` authority surface.

## Inputs

- `backend/tests/integration/test_admin_interventions_api.py`
- `backend/tests/integration/test_admin_users_api.py`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Expected Output

- `Backend regression proof for current intervention/user-session routes`
- `Focused user-detail UI proof that the authority surface still behaves the same after service extraction`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py tests/integration/test_admin_users_api.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'
