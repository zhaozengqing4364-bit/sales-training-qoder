---
id: S01
parent: M006
milestone: M006
provides:
  - A shared frontend drill-in contract for `focusBucket`, `focusIssueFamily`, and `focusNote` across manager-lite, weekly users list, and user detail.
  - A shared frontend linked-asset helper path for analytics and user-detail runtime anomaly sections.
  - A stable seam that downstream M006 slices can type and extend without reopening page-local URL builders or asset-label parsers.
requires:
  []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - web/src/lib/admin/drill-in.ts
  - web/src/lib/admin/linked-assets.ts
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/analytics/page.tsx
  - web/src/lib/admin/drill-in.test.ts
  - web/src/lib/admin/linked-assets.test.ts
  - web/src/components/admin/manager-lite-panel.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
key_decisions:
  - D088: Centralize admin user drill-in URL generation and default-note resolution in `web/src/lib/admin/drill-in.ts`, preserving the current query-string contract for manager-lite and weekly users launchers.
  - D086: Derive missing not-passed focus notes on the user-detail read side from the shared drill-in helper whenever `focusIssueFamily` is present but `focusNote` is omitted.
  - D087: Centralize linked-asset change parsing, filtering, and label formatting in `web/src/lib/admin/linked-assets.ts`, with `/admin/analytics` and `/admin/users/[id]` consuming the same helper path.
patterns_established:
  - Admin route-family query construction and destination-side read/fallback logic should live in one shared helper so launcher and destination semantics cannot drift independently.
  - Support/runtime `linked_asset_changes` should be treated as one shared typed contract on the frontend; preserve the full payload shape in helpers and let each page decide what subset to render.
  - When a query-param contract or shared diagnostic helper changes, lock both launcher and destination semantics with focused page tests instead of relying on one-side-only coverage.
observability_surfaces:
  - web/src/lib/admin/drill-in.test.ts
  - web/src/lib/admin/linked-assets.test.ts
  - web/src/components/admin/manager-lite-panel.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
drill_down_paths:
  - .gsd/milestones/M006/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T09:22:00.000Z
blocker_discovered: false
---

# S01: 前端 drill-in 与 linked-asset 共享协议收口

**Admin weekly drill-in launchers and linked-asset diagnostics now share single frontend helpers, keeping `/admin/users/[id]?focusBucket=...` context and linked-asset rendering consistent across manager-lite, users list, analytics, and user detail.**

## What Happened

S01 closed the first frontend seam in M006 by removing page-local drift from two already-shipped admin contracts: weekly drill-in context and linked-asset runtime diagnostics.

T01 extracted `web/src/lib/admin/drill-in.ts` as the single authority for `focusBucket` URL generation, issue-family-aware default-note resolution, and the current `/admin/users/[id]?focusBucket=...` query-string shape. `ManagerLitePanel` and the weekly users list now call that helper instead of rebuilding links inline, so `not_passed`, `inactive_streak`, and `improving` launchers all stay on one route family.

T02 then carried the same seam through the destination side: `/admin/users/[id]` now reads drill-in search params through the shared helper, derives the shipped not-passed fallback note when `focusIssueFamily` is present but `focusNote` is omitted, and keeps the banner / intervention-prefill behavior aligned with the launcher contract instead of re-encoding that logic inside the page.

T03 closed the parallel linked-asset parser drift by introducing `web/src/lib/admin/linked-assets.ts` as the shared reader/label helper for `linked_asset_changes`; both `/admin/analytics` and `/admin/users/[id]` now render support/runtime-linked asset context from that helper path, while preserving the full `LinkedAssetChangeReference` payload shape for later typed contract work.

The slice intentionally stayed small and route-preserving: current admin pages keep the same shipped URLs, copy, and support/runtime semantics, but downstream slices now have one reusable frontend seam for drill-ins and one for linked assets instead of four page-local variants.

## Verification

Fresh slice verification passed on all planned surfaces.

Commands run:

- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'` — 1 file passed, 2 tests passed.
- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'` — 1 file passed, 10 tests passed.
- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` — 2 files passed, 15 tests passed.

Fresh LSP diagnostics were also clean for:

- `web/src/lib/admin/drill-in.ts`
- `web/src/lib/admin/linked-assets.ts`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`
- wildcard diagnostics covering `web/src/app/admin/users/*/page.tsx`

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

This slice only closes the frontend helper seams on existing admin routes. It does not yet harden the typed governance contract across API normalization (`S02`), extract supervisor workflow services (`S03`), or introduce the asset registry/adapter seam (`S04`).

## Follow-ups

S02 should type `governance_summary` and `linked_asset_changes` end to end through `web/src/lib/api/types.ts` and `web/src/lib/api/client.ts`, then keep these helpers consuming already-normalized contracts rather than re-parsing unknown payloads.

S03 and S04 should reuse the new drill-in and linked-asset seams when extracting workflow services and asset registry/adapter layers, instead of reopening page-local query builders or diagnostic label maps.

## Files Created/Modified

- `web/src/lib/admin/drill-in.ts` — Introduced the shared admin drill-in builder/reader that owns `focusBucket` URL generation, default-note recovery, and destination-side banner/prefill context.
- `web/src/components/admin/manager-lite-panel.tsx` — Switched manager-lite launchers to the shared drill-in helper so `not_passed`, `inactive_streak`, and `improving` links stay on one route contract.
- `web/src/app/admin/users/page.tsx` — Migrated the weekly users-list drill-in cards to the shared href builder instead of rebuilding query strings inline.
- `web/src/app/admin/users/[id]/page.tsx` — Moved user-detail drill-in parsing and linked-asset rendering onto shared helpers while preserving the existing banner and intervention-prefill behavior.
- `web/src/lib/admin/linked-assets.ts` — Introduced the shared linked-asset parser/label helper that preserves the full `LinkedAssetChangeReference` contract for admin runtime anomaly consumers.
- `web/src/app/admin/analytics/page.tsx` — Reused the shared linked-asset helper for analytics runtime anomaly rendering so asset labels and impact/status copy match user detail.
- `web/src/lib/admin/drill-in.test.ts` — Locked the shared drill-in helper contract for URL generation, fallback note resolution, and destination-side context parsing.
- `web/src/lib/admin/linked-assets.test.ts` — Locked the linked-asset helper to the full `LinkedAssetChangeReference` contract and shared label formatting.
- `web/src/components/admin/manager-lite-panel.test.tsx` — Verified manager-lite continues to generate the shipped drill-in URLs and canonical report/user-detail CTAs through the shared helper.
- `web/src/app/admin/users/[id]/page.test.tsx` — Verified the destination page recovers shared fallback notes, preserves bucket-specific banner semantics, and still shows intervention/report links.
- `web/src/app/admin/analytics/page.test.tsx` — Verified analytics renders linked asset diagnostics through the shared helper path and keeps the operating-pack reminder/export flows intact.
