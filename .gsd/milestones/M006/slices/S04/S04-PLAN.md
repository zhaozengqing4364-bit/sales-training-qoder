# S04: 资产 registry 与 adapter seam 收口

**Goal:** Introduce a shared asset registry/adapter seam so governance summaries, linked asset changes, and admin-path labeling for current asset types are not spread across page/service-specific conditionals.
**Demo:** After this: Show the current four asset types resolving governance labels, admin paths, and linked-change references through one registry/adapter seam, with asset pages and fault-linked views still rendering correctly.

## Tasks
- [ ] **T01: 建立 backend asset registry** — Create a backend asset registry module that centralizes current asset-type metadata (label, admin path builder, reference extraction hooks) for knowledge bases, personas, presentations, and runtime profiles. Refactor `RuntimeStatusService` to consume the registry for asset-ref iteration and linked-change enrichment instead of owning asset-type conditionals inline.
  - Estimate: 0.75d
  - Files: backend/src/support/services/asset_registry.py, backend/src/support/services/runtime_status_service.py, backend/tests/unit/test_support_runtime_service.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py
- [ ] **T02: 对齐 frontend asset metadata helper** — Add a matching frontend asset metadata helper so linked-asset displays and governance surfaces stop hardcoding asset labels/admin-path assumptions in page components. Reuse the helper from the shared linked-asset utilities introduced earlier.
  - Estimate: 0.5d
  - Files: web/src/lib/admin/assets.ts, web/src/lib/admin/linked-assets.ts, web/src/app/admin/analytics/page.tsx, web/src/app/admin/users/[id]/page.tsx, web/src/components/admin/asset-governance.tsx
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/admin/asset-governance.test.tsx'
- [ ] **T03: 补齐 asset registry 扩展与回归证明** — Lock the registry seam with regression coverage that proves all current four asset types still render correct governance labels, admin links, and linked-change metadata, and that adding a new asset type is reduced to a registry-focused change path plus tests.
  - Estimate: 0.5d
  - Files: backend/tests/unit/test_support_runtime_service.py, backend/tests/integration/test_asset_governance_api.py, backend/tests/contract/test_support_runtime.py, web/src/app/admin/asset-governance.test.tsx, web/src/app/admin/analytics/page.test.tsx, web/src/app/admin/users/[id]/page.test.tsx
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/integration/test_asset_governance_api.py tests/contract/test_support_runtime.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
