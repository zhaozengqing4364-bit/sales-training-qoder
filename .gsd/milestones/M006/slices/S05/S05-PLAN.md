# S05: 共享 admin read-model adapter 与全链回归证明

**Goal:** Move remaining page-level admin read-model glue into shared adapters/hooks and prove the full shipped admin route family still passes regression after the seam refactor.
**Demo:** After this: Rerun the current M005 admin regression pack after migrating analytics, users list, and user detail to shared adapters/hooks, proving the route family still behaves the same while duplication drops.

## Tasks
- [ ] **T01: 抽出 shared admin read-model adapters** — Extract shared pure adapters for current admin read models — operating-pack highlights, manager-list drill-in cards, runtime-fault linked-asset enrichment, and user-session/intervention derived view state — under `web/src/lib/admin/`. Keep them route-shaped for the current pages instead of inventing a generic dashboard framework.
  - Estimate: 0.75d
  - Files: web/src/lib/admin/read-models.ts, web/src/lib/admin/runtime-faults.ts, web/src/app/admin/analytics/page.tsx, web/src/app/admin/users/page.tsx, web/src/app/admin/users/[id]/page.tsx
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
- [ ] **T02: 迁移 current admin pages 到 shared adapters** — Migrate current admin pages to the shared adapters/hooks and delete the remaining duplicated normalize/derive code that now belongs in the shared layer. Keep the route family unchanged and resist introducing a second state-management abstraction.
  - Estimate: 0.75d
  - Files: web/src/lib/admin/read-models.ts, web/src/lib/admin/runtime-faults.ts, web/src/app/admin/analytics/page.tsx, web/src/app/admin/users/page.tsx, web/src/app/admin/users/[id]/page.tsx, web/src/components/admin/manager-lite-panel.tsx
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
- [ ] **T03: 运行 full admin regression pack 并回写 seam 经验** — Rerun the full current M005 admin regression pack after the adapter migration and capture any seam-level lessons in project knowledge/research artifacts so the next extension milestone starts from the new shared contract instead of rediscovering it.
  - Estimate: 0.5d
  - Files: backend/tests/unit/common/test_admin_analytics_service.py, backend/tests/unit/test_support_runtime_service.py, backend/tests/integration/test_admin_users_api.py, backend/tests/integration/test_admin_interventions_api.py, backend/tests/integration/test_asset_governance_api.py, backend/tests/integration/test_rbac_access_control_api.py, backend/tests/contract/test_analytics.py, web/src/app/admin/analytics/page.test.tsx, web/src/app/admin/asset-governance.test.tsx, web/src/app/admin/users/[id]/page.test.tsx, web/src/components/admin/manager-lite-panel.test.tsx, .gsd/KNOWLEDGE.md, .gsd/milestones/M006/M006-RESEARCH.md
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/unit/test_support_runtime_service.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py tests/integration/test_asset_governance_api.py tests/integration/test_rbac_access_control_api.py tests/contract/test_analytics.py
cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
