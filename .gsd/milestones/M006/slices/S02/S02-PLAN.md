# S02: 治理与 admin contract 强类型化

**Goal:** Replace weak governance/admin payload parsing with shared typed contracts for `governance_summary` and `linked_asset_changes` across backend schemas, API client normalization, and admin UI components.
**Demo:** After this: Inspect current knowledge/persona/presentation/runtime asset rows and analytics/user-detail fault sections using one typed governance / linked-asset contract from backend schema through client normalization to UI props.

## Tasks
- [ ] **T01: 硬化 backend governance / linked-asset schema** — Introduce shared backend schema models for asset governance summary and linked-asset change references, then replace current dict-typed fields on knowledge/persona/presentation/runtime/admin-support response models. Keep the payload shape backward-compatible while making the contract explicit in Python types.
  - Estimate: 0.75d
  - Files: backend/src/common/db/schemas.py, backend/src/common/knowledge/schemas.py, backend/src/agent/schemas.py, backend/src/presentation_coach/api/presentations.py, backend/src/admin/api/voice_runtime.py, backend/src/support/api/runtime_status.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py
- [ ] **T02: 收口 frontend typed governance contract** — Promote frontend admin governance and linked-asset data to shared typed interfaces in `web/src/lib/api/types.ts` and normalize them centrally in `web/src/lib/api/client.ts`. Remove page-level dependence on `Record<string, unknown>` for these contracts and update `AssetGovernanceSummaryCard` props to consume the typed shape directly.
  - Estimate: 0.75d
  - Files: web/src/lib/api/types.ts, web/src/lib/api/client.ts, web/src/components/admin/asset-governance.tsx, web/src/lib/admin/linked-assets.ts
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
- [ ] **T03: 补齐 governance contract 回归证明** — Refresh focused contract and UI coverage so governance summary and linked-asset payloads are locked end-to-end. Explicitly prove that current knowledge/persona/presentation/runtime pages and fault-linked analytics/user-detail views still render the same behavior after the type hardening.
  - Estimate: 0.5d
  - Files: backend/tests/integration/test_asset_governance_api.py, backend/tests/contract/test_analytics.py, backend/tests/contract/test_support_runtime.py, web/src/app/admin/asset-governance.test.tsx, web/src/app/admin/analytics/page.test.tsx, web/src/app/admin/users/[id]/page.test.tsx
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
