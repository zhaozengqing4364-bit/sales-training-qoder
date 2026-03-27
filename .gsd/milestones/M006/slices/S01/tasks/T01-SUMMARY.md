---
id: T01
parent: S01
milestone: M006
provides: []
requires: []
affects: []
key_files: ["web/src/lib/admin/drill-in.ts", "web/src/lib/admin/drill-in.test.ts", "web/src/components/admin/manager-lite-panel.tsx", "web/src/app/admin/users/page.tsx"]
key_decisions: ["Created a shared `web/src/lib/admin/drill-in.ts` helper as the single source of truth for current admin user drill-in URL generation.", "Kept the shipped query-string contract unchanged so existing manager-lite and weekly users-list links continue to land on the same `/admin/users/[id]?focusBucket=...` surfaces."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh verification passed. The new helper contract test `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/components/admin/manager-lite-panel.test.tsx'` passed 6/6 tests, the task-plan verifier `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'` passed 2/2 tests, and LSP diagnostics reported no issues in `web/src/lib/admin/drill-in.ts`, `web/src/components/admin/manager-lite-panel.tsx`, or `web/src/app/admin/users/page.tsx`."
completed_at: 2026-03-27T02:51:06.734Z
blocker_discovered: false
---

# T01: Extracted a shared admin drill-in href builder and migrated manager-lite plus users-list launchers onto it without changing the shipped route contract.

> Extracted a shared admin drill-in href builder and migrated manager-lite plus users-list launchers onto it without changing the shipped route contract.

## What Happened
---
id: T01
parent: S01
milestone: M006
key_files:
  - web/src/lib/admin/drill-in.ts
  - web/src/lib/admin/drill-in.test.ts
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/app/admin/users/page.tsx
key_decisions:
  - Created a shared `web/src/lib/admin/drill-in.ts` helper as the single source of truth for current admin user drill-in URL generation.
  - Kept the shipped query-string contract unchanged so existing manager-lite and weekly users-list links continue to land on the same `/admin/users/[id]?focusBucket=...` surfaces.
duration: ""
verification_result: passed
completed_at: 2026-03-27T02:51:06.735Z
blocker_discovered: false
---

# T01: Extracted a shared admin drill-in href builder and migrated manager-lite plus users-list launchers onto it without changing the shipped route contract.

**Extracted a shared admin drill-in href builder and migrated manager-lite plus users-list launchers onto it without changing the shipped route contract.**

## What Happened

Executed M006/S01/T01 with test-first flow. I first added a new helper test file `web/src/lib/admin/drill-in.test.ts` that asserted the existing not-passed, inactive-streak, and improving drill-in URLs plus the shared default evidence-gap note. Running that test failed immediately because the helper module did not exist yet, which confirmed the new seam was actually under test. I then implemented `web/src/lib/admin/drill-in.ts` with the shared bucket type, default-note resolution, and href builder, and migrated both `ManagerLitePanel` and the weekly-manager-list section of `web/src/app/admin/users/page.tsx` to call that helper instead of keeping separate page-local builders. No route shape or wording changed; the work only removed duplicated builder logic and made the URL contract single-source. After the change, the new helper tests passed, the existing manager-lite regression passed unchanged, and LSP diagnostics were clean on the touched files.

## Verification

Fresh verification passed. The new helper contract test `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/components/admin/manager-lite-panel.test.tsx'` passed 6/6 tests, the task-plan verifier `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'` passed 2/2 tests, and LSP diagnostics reported no issues in `web/src/lib/admin/drill-in.ts`, `web/src/components/admin/manager-lite-panel.tsx`, or `web/src/app/admin/users/page.tsx`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass | 737ms |
| 2 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass | 1000ms |
| 3 | `lsp diagnostics: web/src/lib/admin/drill-in.ts, web/src/components/admin/manager-lite-panel.tsx, web/src/app/admin/users/page.tsx` | 0 | ✅ pass | 100ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/admin/drill-in.ts`
- `web/src/lib/admin/drill-in.test.ts`
- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/app/admin/users/page.tsx`


## Deviations
None.

## Known Issues
None.
