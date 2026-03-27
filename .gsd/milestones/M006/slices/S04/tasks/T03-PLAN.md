---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T03: 补齐 asset registry 扩展与回归证明

Lock the registry seam with regression coverage that proves all current four asset types still render correct governance labels, admin links, and linked-change metadata, and that adding a new asset type is reduced to a registry-focused change path plus tests.

## Inputs

- `backend/tests/unit/test_support_runtime_service.py`
- `backend/tests/integration/test_asset_governance_api.py`
- `backend/tests/contract/test_support_runtime.py`
- `web/src/app/admin/asset-governance.test.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Expected Output

- `Registry-focused backend/frontend regression proof across current asset types`
- `Documented extension rule for future asset-type additions`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/integration/test_asset_governance_api.py tests/contract/test_support_runtime.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
