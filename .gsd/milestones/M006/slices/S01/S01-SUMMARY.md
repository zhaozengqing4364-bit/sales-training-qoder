---
id: S01
parent: M006
milestone: M006
provides:
  - A shared admin drill-in helper that owns current `focusBucket` / `focusIssueFamily` / `focusNote` URL generation and destination-side fallback-note parsing.
  - A shared linked-asset helper that owns `linked_asset_changes` parsing, filtering, labels, and the full normalized linked-asset shape reused by analytics and user-detail surfaces.
  - Focused helper and page regression coverage that pins the current admin drill-in and linked-asset contracts for downstream M006 slices.
requires: []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - web/src/lib/admin/drill-in.ts
  - web/src/lib/admin/drill-in.test.ts
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/lib/admin/linked-assets.ts
  - web/src/lib/admin/linked-assets.test.ts
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D088: keep admin user drill-in URL generation and default-note resolution in `web/src/lib/admin/drill-in.ts` so manager-lite and `/admin/users` launchers stay on one route-contract seam.
  - D086: derive missing `focusNote` values for `focusBucket=not_passed` on the read side from the shared drill-in helper whenever `focusIssueFamily` is present.
  - D087: centralize `linked_asset_changes` parsing, filtering, and label formatting in `web/src/lib/admin/linked-assets.ts` for `/admin/analytics` and `/admin/users/[id]`.
patterns_established:
  - Current admin route contracts should live in shared helpers under `web/src/lib/admin/*`, with launcher and destination surfaces round-tripping through the same parser/builder instead of duplicating query logic in page components.
  - Current support/runtime linked-asset references should be filtered and labeled once in a shared helper, and admin pages should render only complete `linked_asset_changes` entries rather than inventing local defaults.
  - When a frontend helper wraps a normalized API contract that downstream slices will reuse, keep the helper aligned to the full contract shape and let pages consume the subset they need; trimming fields too early creates hidden drift that only shows up in cross-surface regression tests.
observability_surfaces:
  - web/src/lib/admin/drill-in.test.ts
  - web/src/lib/admin/linked-assets.test.ts
  - web/src/components/admin/manager-lite-panel.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - LSP diagnostics on the touched helper/page/test files
drill_down_paths:
  - .gsd/milestones/M006/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T07:49:24.000Z
blocker_discovered: false
---

# S01: 前端 drill-in 与 linked-asset 共享协议收口

**Manager-lite/users drill-ins and analytics/user-detail linked assets now share one frontend helper seam, and close-out verification aligned the linked-asset helper to the full normalized contract without changing shipped admin behavior.**

## What Happened

S01 closed the remaining page-local duplication on the shipped admin drill-in and linked-asset surfaces without changing the product-facing route family. T01 extracted `web/src/lib/admin/drill-in.ts` as the single source of truth for admin user drill-in URL generation, keeping `focusBucket` / `focusIssueFamily` / `focusNote` on the exact shipped query-string shape while migrating both `ManagerLitePanel` and the `/admin/users` weekly manager list to the shared helper.

T02 finished the round-trip contract on the destination side. Instead of adding page-local fallback logic, the user-detail page kept reading drill-in context through the same helper, and `readAdminUserDrillInContext(...)` now reconstructs the shared default note for `focusBucket=not_passed` when a URL still carries an issue family but omits `focusNote`. That preserved the existing risk-bucket banner wording and supervisor-form prefill even for partial/manual URLs.

T03 extracted `web/src/lib/admin/linked-assets.ts` so `/admin/analytics` and `/admin/users/[id]` stopped owning duplicate runtime-diagnostics parsing and label maps for `linked_asset_changes`; both pages now reuse one parser/filter/formatter seam and continue to discard incomplete linked-asset entries instead of inventing page-specific fallbacks. During slice close-out, the combined helper/page regression suite also exposed one remaining seam mismatch: the shared linked-asset helper had narrowed the normalized change payload down to a page-only subset. I fixed that before acceptance by keeping the helper aligned to the full `LinkedAssetChangeReference` contract, so current pages still render the same copy while downstream typed-governance slices can safely reuse the complete linked-asset shape.

Across the slice, the code change stayed narrow and deliberately reused the shipped admin surfaces rather than adding a new route, API, or standalone governance console. The result is one frontend contract seam for admin weekly drill-ins and one frontend contract seam for linked-asset diagnostics, both ready for S02-S05 to build on instead of reintroducing page-local parsing.

## Verification

Fresh slice verification passed from the repo root after the close-out fix.

- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'` → 2/2 tests passed.
- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'` → 10/10 tests passed.
- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` → 15/15 tests passed.
- `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/lib/admin/linked-assets.test.ts' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` → 26/26 tests passed.
- LSP diagnostics were clean for `web/src/lib/admin/drill-in.ts`, `web/src/lib/admin/linked-assets.ts`, `web/src/components/admin/manager-lite-panel.tsx`, `web/src/app/admin/analytics/page.tsx`, `web/src/app/admin/users/[id]/page.tsx`, and the focused helper/page test files.

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

This slice proves the current admin route contract through focused helper/page tests rather than a fresh live browser pass. Local admin browser proof remains sensitive to dev-login session persistence across the backend/web host boundary, so future live UAT should keep frontend and backend on the same loopback host or use the shipped admin login path.

## Follow-ups

S02 should type and reuse the new frontend seams instead of reintroducing page-local query parsing or linked-asset coercion. S03-S05 should keep building on these helpers when extracting workflow services, governance contracts, and shared admin adapters. Future edits to `web/src/lib/admin/linked-assets.ts` should preserve the full normalized contract even if current pages only read a subset of fields.

## Files Created/Modified

- `web/src/lib/admin/drill-in.ts` — Centralized admin user drill-in URL generation, default-note resolution, and destination-side context parsing for the current `focusBucket` route contract.
- `web/src/lib/admin/drill-in.test.ts` — Locked the shared drill-in helper contract for not-passed, inactive-streak, and improving links plus destination-side parsing behavior.
- `web/src/components/admin/manager-lite-panel.tsx` — Switched manager-lite launchers to the shared drill-in helper while preserving the shipped copy and route shape.
- `web/src/app/admin/users/page.tsx` — Reused the shared drill-in helper for weekly users-list launchers so the list and manager-lite panel build identical `/admin/users/[id]` query strings.
- `web/src/app/admin/users/[id]/page.tsx` — Consumed shared drill-in and linked-asset helpers so banner/prefill state and linked-asset rendering stay aligned with launcher/runtime contracts.
- `web/src/lib/admin/linked-assets.ts` — Centralized `linked_asset_changes` parsing, filtering, and label formatting, and preserved the full `LinkedAssetChangeReference` field set instead of trimming the helper to a page-local subset.
- `web/src/lib/admin/linked-assets.test.ts` — Locked the shared linked-asset helper against the complete normalized contract plus the rule that incomplete entries are filtered out.
- `web/src/app/admin/analytics/page.tsx` — Reused the shared linked-asset helper so analytics fault-linked asset sections stop carrying page-local parser and label logic.
- `web/src/app/admin/analytics/page.test.tsx` — Kept the analytics linked-asset render contract pinned on the shipped page after the helper extraction.
- `web/src/app/admin/users/[id]/page.test.tsx` — Locked user-detail drill-in banner/prefill behavior and linked-asset rendering against the shared helpers.
- `.gsd/DECISIONS.md` — Recorded the slice-level frontend seam decisions D086-D088 for drill-in fallback parsing and shared linked-asset/drill-in helpers.
- `.gsd/KNOWLEDGE.md` — Captured the read-side drill-in fallback rule, the linked-asset filtering rule, and the close-out gotcha that the shared helper must preserve the full linked-asset contract.
- `.gsd/PROJECT.md` — Refreshed current project state to note that M006/S01 completed the frontend drill-in and linked-asset seam extraction and kept the linked-asset helper aligned to the normalized contract.
