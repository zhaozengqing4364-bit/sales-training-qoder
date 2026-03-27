---
id: T01
parent: S05
milestone: M006
provides: []
requires: []
affects: []
key_files: ["web/src/lib/admin/read-models.ts", "web/src/lib/admin/runtime-faults.ts", "web/src/lib/admin/read-models.test.ts", "web/src/lib/admin/runtime-faults.test.ts", "web/src/app/admin/analytics/page.tsx", "web/src/app/admin/users/page.tsx", "web/src/app/admin/users/[id]/page.tsx", ".gsd/milestones/M006/slices/S05/tasks/T01-SUMMARY.md"]
key_decisions: ["D096: keep the admin seam route-shaped by splitting shared adapters into `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` instead of introducing a generic dashboard abstraction."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh adapter tests passed for the new shared modules, the exact task-plan web regression command passed fresh for analytics/manager-lite/user-detail, focused LSP diagnostics were clean on the touched shared/admin files, and live localhost browser checks passed on `/admin/analytics` plus `/admin/users/89e31f06-6393-42b6-877e-5a007803136a` after host-aligned dev-login."
completed_at: 2026-03-27T11:33:13.087Z
blocker_discovered: false
---

# T01: Extracted shared admin read-model adapters for operating-pack, runtime-fault, and user-detail state while keeping the shipped analytics/users regressions green.

> Extracted shared admin read-model adapters for operating-pack, runtime-fault, and user-detail state while keeping the shipped analytics/users regressions green.

## What Happened
---
id: T01
parent: S05
milestone: M006
key_files:
  - web/src/lib/admin/read-models.ts
  - web/src/lib/admin/runtime-faults.ts
  - web/src/lib/admin/read-models.test.ts
  - web/src/lib/admin/runtime-faults.test.ts
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - .gsd/milestones/M006/slices/S05/tasks/T01-SUMMARY.md
key_decisions:
  - D096: keep the admin seam route-shaped by splitting shared adapters into `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` instead of introducing a generic dashboard abstraction.
duration: ""
verification_result: passed
completed_at: 2026-03-27T11:33:13.088Z
blocker_discovered: false
---

# T01: Extracted shared admin read-model adapters for operating-pack, runtime-fault, and user-detail state while keeping the shipped analytics/users regressions green.

**Extracted shared admin read-model adapters for operating-pack, runtime-fault, and user-detail state while keeping the shipped analytics/users regressions green.**

## What Happened

Created `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` as the shared route-shaped seam for the current admin route family. Moved the current operating-pack fallback logic, score-basis/degraded-reason labeling, user progress/session/intervention derivation, and linked runtime-fault enrichment into those pure adapters, then rewired `web/src/app/admin/analytics/page.tsx`, `web/src/app/admin/users/page.tsx`, and `web/src/app/admin/users/[id]/page.tsx` to consume the shared helpers instead of carrying the same branching inline. Added focused adapter regressions first, verified the planned admin page regressions stayed green, and proved the protected localhost analytics and user-detail routes still render the expected sections after host-aligned dev-login.

## Verification

Fresh adapter tests passed for the new shared modules, the exact task-plan web regression command passed fresh for analytics/manager-lite/user-detail, focused LSP diagnostics were clean on the touched shared/admin files, and live localhost browser checks passed on `/admin/analytics` plus `/admin/users/89e31f06-6393-42b6-877e-5a007803136a` after host-aligned dev-login.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/read-models.test.ts' 'src/lib/admin/runtime-faults.test.ts'` | 0 | ✅ pass | 661ms |
| 2 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/read-models.test.ts' 'src/lib/admin/runtime-faults.test.ts' 'src/app/admin/analytics/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1170ms |
| 3 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1690ms |
| 4 | `lsp diagnostics: web/src/lib/admin/read-models.ts, web/src/lib/admin/runtime-faults.ts, web/src/app/admin/analytics/page.tsx, web/src/app/admin/users/page.tsx` | 0 | ✅ pass | 100ms |
| 5 | `browser runtime: localhost dev-login -> /admin/analytics -> /admin/users/89e31f06-6393-42b6-877e-5a007803136a` | 0 | ✅ pass | 5000ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/admin/read-models.ts`
- `web/src/lib/admin/runtime-faults.ts`
- `web/src/lib/admin/read-models.test.ts`
- `web/src/lib/admin/runtime-faults.test.ts`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `.gsd/milestones/M006/slices/S05/tasks/T01-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
