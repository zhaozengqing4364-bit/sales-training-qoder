---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T03: 补齐 governance contract 回归证明

Refresh focused contract and UI coverage so governance summary and linked-asset payloads are locked end-to-end. Explicitly prove that current knowledge/persona/presentation/runtime pages and fault-linked analytics/user-detail views still render the same behavior after the type hardening.

## Inputs

- `backend/tests/integration/test_asset_governance_api.py`
- `backend/tests/contract/test_analytics.py`
- `backend/tests/contract/test_support_runtime.py`
- `web/src/app/admin/asset-governance.test.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`

## Expected Output

- `Updated backend contract coverage for governance/admin payloads`
- `Focused web regression covering typed governance and fault-linked asset rendering`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
