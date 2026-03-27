---
estimated_steps: 1
estimated_files: 13
skills_used: []
---

# T03: 运行 full admin regression pack 并回写 seam 经验

Rerun the full current M005 admin regression pack after the adapter migration and capture any seam-level lessons in project knowledge/research artifacts so the next extension milestone starts from the new shared contract instead of rediscovering it.

## Inputs

- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/unit/test_support_runtime_service.py`
- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/integration/test_admin_interventions_api.py`
- `backend/tests/integration/test_asset_governance_api.py`
- `backend/tests/integration/test_rbac_access_control_api.py`
- `backend/tests/contract/test_analytics.py`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/asset-governance.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`

## Expected Output

- `Repo-safe full admin regression proof after the seam refactor`
- `Updated seam notes in project knowledge/research artifacts`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/unit/test_support_runtime_service.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py tests/integration/test_asset_governance_api.py tests/integration/test_rbac_access_control_api.py tests/contract/test_analytics.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
