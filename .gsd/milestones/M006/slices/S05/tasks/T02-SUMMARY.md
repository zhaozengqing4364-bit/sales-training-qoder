---
id: T02
parent: S05
milestone: M006
provides: []
requires: []
affects: []
key_files: ["web/src/lib/admin/read-models.ts", "web/src/lib/admin/read-models.test.ts", "web/src/app/admin/users/page.tsx", "web/src/app/admin/users/page.test.tsx", "web/src/app/admin/users/[id]/page.tsx", ".gsd/milestones/M006/slices/S05/tasks/T02-SUMMARY.md"]
key_decisions: ["D097: Reuse `web/src/lib/admin/read-models.ts` for users-page operating-pack and display-label derivation instead of adding a new users-specific hook/store abstraction."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Focused read-model/users regressions passed after the seam migration, the exact task-plan admin regression pack passed for analytics/asset-governance/user-detail/manager-lite, focused LSP diagnostics were clean on the touched shared/users files, and a live localhost browser check passed on `/admin/users` after host-aligned dev-login with no console or failed-network entries since the successful navigation."
completed_at: 2026-03-27T11:46:54.998Z
blocker_discovered: false
---

# T02: Moved the remaining users-page admin read-model glue onto the shared seam and proved the shipped admin route family still passes regression.

> Moved the remaining users-page admin read-model glue onto the shared seam and proved the shipped admin route family still passes regression.

## What Happened
---
id: T02
parent: S05
milestone: M006
key_files:
  - web/src/lib/admin/read-models.ts
  - web/src/lib/admin/read-models.test.ts
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/page.test.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - .gsd/milestones/M006/slices/S05/tasks/T02-SUMMARY.md
key_decisions:
  - D097: Reuse `web/src/lib/admin/read-models.ts` for users-page operating-pack and display-label derivation instead of adding a new users-specific hook/store abstraction.
duration: ""
verification_result: passed
completed_at: 2026-03-27T11:46:54.998Z
blocker_discovered: false
---

# T02: Moved the remaining users-page admin read-model glue onto the shared seam and proved the shipped admin route family still passes regression.

**Moved the remaining users-page admin read-model glue onto the shared seam and proved the shipped admin route family still passes regression.**

## What Happened

Verified local reality first and found that analytics and user-detail were already on the shared seam from T01, while `web/src/app/admin/users/page.tsx` still dereferenced `manager_lists` directly and kept its own role/status/relative-time derivations inline. Added a users-page regression that reproduces the missing-`manager_lists` failure, then switched the page to consume `buildOperatingPackReadModel(operatingPack).managerLite` so it inherits the shared empty fallback instead of crashing. Extended `web/src/lib/admin/read-models.ts` with shared users-page display-label helpers, covered them in `web/src/lib/admin/read-models.test.ts`, rewired the users page to use them, and corrected the local `AdminProgressLoadState` type usage in `web/src/app/admin/users/[id]/page.tsx` so diagnostics stay aligned with the shared seam.

## Verification

Focused read-model/users regressions passed after the seam migration, the exact task-plan admin regression pack passed for analytics/asset-governance/user-detail/manager-lite, focused LSP diagnostics were clean on the touched shared/users files, and a live localhost browser check passed on `/admin/users` after host-aligned dev-login with no console or failed-network entries since the successful navigation.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/read-models.test.ts' 'src/app/admin/users/page.test.tsx'` | 0 | ✅ pass | 689ms |
| 2 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass | 1340ms |
| 3 | `lsp diagnostics: web/src/lib/admin/read-models.ts, web/src/app/admin/users/page.tsx, web/src/app/admin/users/*/page.tsx` | 0 | ✅ pass | 100ms |
| 4 | `browser runtime: localhost-aligned dev-login -> http://localhost:3445/admin/users + assertions` | 0 | ✅ pass | 4000ms |


## Deviations

Minor local adaptation only: analytics and user-detail were already migrated by T01, so this task's remaining seam work concentrated on `web/src/app/admin/users/page.tsx` and the shared helpers it consumes.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/admin/read-models.ts`
- `web/src/lib/admin/read-models.test.ts`
- `web/src/app/admin/users/page.tsx`
- `web/src/app/admin/users/page.test.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `.gsd/milestones/M006/slices/S05/tasks/T02-SUMMARY.md`


## Deviations
Minor local adaptation only: analytics and user-detail were already migrated by T01, so this task's remaining seam work concentrated on `web/src/app/admin/users/page.tsx` and the shared helpers it consumes.

## Known Issues
None.
