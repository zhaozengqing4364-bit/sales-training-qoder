# S05: 共享 admin read-model adapter 与全链回归证明 — UAT

**Milestone:** M006
**Written:** 2026-03-27T11:57:11.705Z

# S05: 共享 admin read-model adapter 与全链回归证明 — UAT

**Milestone:** M006  
**Written:** 2026-03-27

## UAT Type

- UAT mode: focused shared-read-model seam regression + full admin route-family acceptance pack
- Why this mode is sufficient: S05 does not add a new admin page. It removes duplicated read-model glue behind the existing `/admin/analytics`, `/admin/users`, `/admin/users/[id]`, manager-lite, asset-governance, and intervention surfaces. Acceptance is therefore whether those shipped routes still behave the same after the seam extraction.

## Preconditions

- Repo root: `/Users/zhaozengqing/github/销售训练qoder`
- Backend dependencies installed in `backend/venv`; frontend dependencies installed in `web/node_modules`
- Shared seam files in scope:
  - `web/src/lib/admin/read-models.ts`
  - `web/src/lib/admin/runtime-faults.ts`
- Current admin authority surfaces in scope:
  - `/admin/analytics`
  - `/admin/users`
  - `/admin/users/[id]`
  - manager-lite cards on the admin analytics/users route family
  - `/api/v1/admin/analytics/*`
  - `/api/v1/admin/interventions/*`
  - `/api/v1/support/runtime/*` linked-governance payloads consumed by admin pages
- Planned verification commands available from repo root:
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'`
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/unit/test_support_runtime_service.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py tests/integration/test_asset_governance_api.py tests/integration/test_rbac_access_control_api.py tests/contract/test_analytics.py`

## Smoke Test

1. Run the T01 frontend regression command.
2. **Expected:** all 3 files pass, proving analytics, manager-lite, and admin user detail still render correctly while consuming the shared seam.
3. Run the T02/T03 frontend admin regression command.
4. **Expected:** all 4 files pass, proving asset-governance plus the admin route family still agree on the shared linked-asset and read-model vocabulary.
5. Run the backend full admin regression pack.
6. **Expected:** all 60 backend tests pass across admin analytics, support-runtime, users, interventions, asset governance, RBAC, and analytics contract coverage.
7. Confirm that no failing check requires restoring page-local fallback logic.
8. **Expected:** acceptance stays at the shared seam and full route family, not at one page-only hotfix.

## Test Cases

### 1. Shared operating-pack seam still drives analytics, manager-lite, and user detail

1. Run `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`.
2. Inspect the passing analytics, manager-lite, and user-detail assertions.
3. **Expected:** analytics still renders operating-pack summaries and runtime-fault-linked admin references from the shared seam.
4. **Expected:** manager-lite still shows the same bucket semantics and drill-in targets.
5. **Expected:** user detail still renders progress/session/intervention derived state without page-local reimplementation.

### 2. Users page survives sparse operating-pack payloads through the shared seam

1. Run the users-focused regression coverage inside `src/app/admin/users/page.test.tsx` together with `src/lib/admin/read-models.test.ts` when validating a local change to the seam.
2. Inspect the missing-`manager_lists` scenario.
3. **Expected:** `/admin/users` no longer crashes or renders an empty state just because `manager_lists` is missing from the payload.
4. **Expected:** the page falls back through `buildOperatingPackReadModel(...).managerLite` and keeps the same list/category semantics used by analytics/manager-lite.
5. **Expected:** role, status, and relative-time labels come from shared helper formatters rather than per-page literal maps.

### 3. Runtime-fault linked assets stay aligned across analytics and user detail

1. Run the frontend admin regression command `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'`.
2. Inspect the analytics and user-detail linked-asset assertions.
3. **Expected:** both routes still consume shared linked runtime-fault entries built from `web/src/lib/admin/runtime-faults.ts`.
4. **Expected:** linked assets keep the same current admin route fallback behavior introduced by S04.
5. **Expected:** no route has reintroduced its own runtime-fault parsing branch.

### 4. Backend authority seams remain unchanged after the frontend seam extraction

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/unit/test_support_runtime_service.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py tests/integration/test_asset_governance_api.py tests/integration/test_rbac_access_control_api.py tests/contract/test_analytics.py`.
2. Inspect the passing backend suites.
3. **Expected:** admin analytics still uses the projection-backed operating-pack semantics.
4. **Expected:** support-runtime still exposes the linked-governance and asset registry contracts consumed by the admin pages.
5. **Expected:** admin users/interventions routes still follow the manager-intervention authority seam and RBAC contract.
6. **Expected:** analytics contract tests still match the shipped route-family payload shape.

### 5. Canonical acceptance bar stays route-family wide, not helper-local

1. Make a hypothetical local seam change in `web/src/lib/admin/read-models.ts` or `web/src/lib/admin/runtime-faults.ts`.
2. Run the full backend pack and the 4-file frontend pack above.
3. **Expected:** the change is not accepted until both the backend and web route-family packs are green.
4. **Expected:** helper-only unit tests are treated as insufficient evidence for completion.

## Edge Cases

### Missing `manager_lists` must fail closed into shared fallback semantics

1. Use the users-page regression data where the operating-pack payload omits `manager_lists`.
2. **Expected:** the users page still renders manager-lite buckets through the shared seam.
3. **Expected:** no page-local `undefined` dereference or blank route state appears.

### Shared label helpers must cover users-page display copy

1. Verify the users-page regression data that exercises role/status/relative-time display labels.
2. **Expected:** labels are resolved through the shared read-model helper layer.
3. **Expected:** changing the shared helper updates the users page without a second literal map.

### Route-family proof must catch cross-page drift even when helper tests stay green

1. Consider a change where helper unit tests still pass but analytics or user-detail rendering drifts.
2. **Expected:** the full 4-file frontend pack and backend admin pack catch the regression.
3. **Expected:** release acceptance remains blocked until both packs are green again.

## Failure Signals

- `/admin/users` still reads `manager_lists` directly and crashes or goes blank on sparse payloads.
- analytics and user-detail disagree on runtime-fault linked-asset entries after a seam change.
- page-local role/status/relative-time maps reappear outside the shared helper seam.
- backend admin analytics/interventions/governance/RBAC tests fail after a frontend seam refactor, showing the route family drifted from its authority surfaces.
- a seam change is declared complete based only on helper-local tests.

## Requirements Proved By This UAT

- None directly change status in this slice. S05 proves the admin route family can now evolve through a shared read-model seam without changing the shipped authority surfaces.

## Not Proven By This UAT

- A new admin route family or global dashboard state abstraction.
- Any new asset type beyond the current registry-backed set already locked by S04.

## Notes for Tester

- Treat `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` as the only intended extension seams for current admin read-side glue.
- If a regression appears only on `/admin/users`, check for reintroduced direct `manager_lists` dereferences or page-local display-label logic before changing backend contracts.
- If helper tests pass but the full admin pack fails, trust the route-family pack; S05’s acceptance contract explicitly says the seam is only valid when the shipped admin routes stay green together.
