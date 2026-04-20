---
id: T03
parent: S02
milestone: M006
provides: []
requires: []
affects: []
key_files: ["backend/tests/integration/test_asset_governance_api.py", "backend/tests/contract/test_analytics.py", "backend/tests/contract/test_support_runtime.py", "web/src/app/admin/asset-governance.test.tsx", "web/src/app/admin/analytics/page.test.tsx", "web/src/app/admin/users/[id]/page.test.tsx", ".gsd/milestones/M006/slices/S02/tasks/T03-SUMMARY.md"]
key_decisions: ["Locked frontend fault-linked fixtures to the shared typed contract with `satisfies` so analytics and user-detail regressions now fail on contract drift instead of silently accepting loosely shaped mocks.", "Tightened backend governance and linked-asset regression checks at the field level rather than only asserting schema-ref presence, so shared contract drift is caught before the admin UI layer."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the full planned backend and web verification commands fresh after the test hardening. Backend pytest passed 24/24 and web Vitest passed 21/21. LSP diagnostics were also clean on the touched backend/web test files, so the stronger contract assertions and typed fixtures did not introduce any new errors."
completed_at: 2026-03-27T09:43:28.771Z
blocker_discovered: false
---

# T03: Locked governance and fault-linked admin regressions end-to-end with stronger backend contract assertions and shared typed admin page fixtures.

> Locked governance and fault-linked admin regressions end-to-end with stronger backend contract assertions and shared typed admin page fixtures.

## What Happened
---
id: T03
parent: S02
milestone: M006
key_files:
  - backend/tests/integration/test_asset_governance_api.py
  - backend/tests/contract/test_analytics.py
  - backend/tests/contract/test_support_runtime.py
  - web/src/app/admin/asset-governance.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - .gsd/milestones/M006/slices/S02/tasks/T03-SUMMARY.md
key_decisions:
  - Locked frontend fault-linked fixtures to the shared typed contract with `satisfies` so analytics and user-detail regressions now fail on contract drift instead of silently accepting loosely shaped mocks.
  - Tightened backend governance and linked-asset regression checks at the field level rather than only asserting schema-ref presence, so shared contract drift is caught before the admin UI layer.
duration: ""
verification_result: passed
completed_at: 2026-03-27T09:43:28.771Z
blocker_discovered: false
---

# T03: Locked governance and fault-linked admin regressions end-to-end with stronger backend contract assertions and shared typed admin page fixtures.

**Locked governance and fault-linked admin regressions end-to-end with stronger backend contract assertions and shared typed admin page fixtures.**

## What Happened

T03 only needed stronger proof, not runtime behavior changes. I tightened the backend governance regression from a few spot checks into field-level assertions over the nested impact/change/health payloads across knowledge, persona, presentation, and runtime routes, and I strengthened the support-runtime OpenAPI regression so LinkedAssetChangeReference is pinned by its concrete shared field set. I also extended the analytics operating-pack contract assertions around the weekly blocker/degradation objects that feed the admin surface. On the frontend side, I converted the governance and fault fixtures to explicit shared typed contracts with `satisfies`, then expanded analytics and user-detail coverage from a single knowledge-base asset to a multi-asset chain covering knowledge-base, persona, and runtime-profile links plus change labels. No shipped runtime code changed in this task; the delivered value is regression coverage that will now fail if the shared governance_summary or linked_asset_changes contract drifts.

## Verification

Ran the full planned backend and web verification commands fresh after the test hardening. Backend pytest passed 24/24 and web Vitest passed 21/21. LSP diagnostics were also clean on the touched backend/web test files, so the stronger contract assertions and typed fixtures did not introduce any new errors.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py` | 0 | ✅ pass | 11190ms |
| 2 | `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 2640ms |


## Deviations

None.

## Known Issues

The backend OpenAPI build still emits the pre-existing duplicate operation-id warning from backend/src/admin/api/model_configs.py; this task did not change that surface.

## Files Created/Modified

- `backend/tests/integration/test_asset_governance_api.py`
- `backend/tests/contract/test_analytics.py`
- `backend/tests/contract/test_support_runtime.py`
- `web/src/app/admin/asset-governance.test.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `.gsd/milestones/M006/slices/S02/tasks/T03-SUMMARY.md`


## Deviations
None.

## Known Issues
The backend OpenAPI build still emits the pre-existing duplicate operation-id warning from backend/src/admin/api/model_configs.py; this task did not change that surface.
