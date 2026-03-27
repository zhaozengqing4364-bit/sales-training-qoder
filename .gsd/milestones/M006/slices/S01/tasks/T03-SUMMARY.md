---
id: T03
parent: S01
milestone: M006
provides: []
requires: []
affects: []
key_files: ["web/src/lib/admin/linked-assets.ts", "web/src/lib/admin/linked-assets.test.ts", "web/src/app/admin/analytics/page.tsx", "web/src/app/admin/analytics/page.test.tsx", "web/src/app/admin/users/[id]/page.tsx", "web/src/app/admin/users/[id]/page.test.tsx", ".gsd/DECISIONS.md"]
key_decisions: ["Centralized linked-asset change parsing, filtering, and labels in `web/src/lib/admin/linked-assets.ts` so admin pages stop owning duplicate support/runtime coercion code.", "Kept the shipped frontend contract by continuing to discard incomplete linked-asset entries unless they include `asset_name`, `admin_path`, and `latest_change_label`."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh focused verification passed after the extraction. `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/linked-assets.test.ts' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` passed 17/17 tests, the task-plan verifier `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` passed 15/15 tests, and LSP diagnostics reported no issues on the new helper plus the touched analytics and user-detail files."
completed_at: 2026-03-27T04:13:51.711Z
blocker_discovered: false
---

# T03: Centralized admin linked-asset parsing so analytics and user-detail pages share one runtime-diagnostics helper.

> Centralized admin linked-asset parsing so analytics and user-detail pages share one runtime-diagnostics helper.

## What Happened
---
id: T03
parent: S01
milestone: M006
key_files:
  - web/src/lib/admin/linked-assets.ts
  - web/src/lib/admin/linked-assets.test.ts
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - .gsd/DECISIONS.md
key_decisions:
  - Centralized linked-asset change parsing, filtering, and labels in `web/src/lib/admin/linked-assets.ts` so admin pages stop owning duplicate support/runtime coercion code.
  - Kept the shipped frontend contract by continuing to discard incomplete linked-asset entries unless they include `asset_name`, `admin_path`, and `latest_change_label`.
duration: ""
verification_result: passed
completed_at: 2026-03-27T04:13:51.712Z
blocker_discovered: false
---

# T03: Centralized admin linked-asset parsing so analytics and user-detail pages share one runtime-diagnostics helper.

**Centralized admin linked-asset parsing so analytics and user-detail pages share one runtime-diagnostics helper.**

## What Happened

I executed T03 as a narrow helper extraction. I started by adding `web/src/lib/admin/linked-assets.test.ts` and running it in isolation so the new seam failed on the missing module instead of on page noise. Then I created `web/src/lib/admin/linked-assets.ts` with the shared `LinkedAssetChange` type, parsing/filtering for `SupportRuntimeFaultItem.diagnostics.linked_asset_changes`, and shared asset / impact / health label formatters. After that I removed the duplicated linked-asset parser blocks from `web/src/app/admin/analytics/page.tsx` and `web/src/app/admin/users/[id]/page.tsx`, rewiring both pages to import the helper. I tightened the focused page tests to keep the linked-asset render contract pinned on both surfaces, and I recorded the shared-helper seam in D087 for downstream admin work.

## Verification

Fresh focused verification passed after the extraction. `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/linked-assets.test.ts' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` passed 17/17 tests, the task-plan verifier `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` passed 15/15 tests, and LSP diagnostics reported no issues on the new helper plus the touched analytics and user-detail files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/linked-assets.test.ts' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1060ms |
| 2 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 862ms |
| 3 | `lsp diagnostics: web/src/lib/admin/linked-assets.ts, web/src/lib/admin/linked-assets.test.ts, web/src/app/admin/analytics/page.tsx, web/src/app/admin/analytics/page.test.tsx, web/src/app/admin/users/[id]/page.tsx, web/src/app/admin/users/[id]/page.test.tsx` | 0 | ✅ pass | 100ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/admin/linked-assets.ts`
- `web/src/lib/admin/linked-assets.test.ts`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `.gsd/DECISIONS.md`


## Deviations
None.

## Known Issues
None.
