---
id: T02
parent: S04
milestone: M005
provides: []
requires: []
affects: []
key_files: ["web/src/app/admin/analytics/page.tsx", "web/src/app/admin/analytics/page.test.tsx", "web/src/lib/api/types.ts", "web/src/lib/api/client.ts", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M005/slices/S04/tasks/T02-SUMMARY.md"]
key_decisions: ["Keep the weekly operating pack on a fixed 7-day `/admin/analytics/operating-pack` read while leaving overview/trends/leaderboard on the existing time-range filter.", "Feed the existing manager-lite panel from `operating_pack.manager_lists` so current risk/improving membership stays on the same projection-backed evidence line as the new weekly buckets."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the slice verification command `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'` fresh after wiring the operating-pack client and page. The suite passed with the new weekly summary assertions, the projection-backed manager-panel feed, and the existing analytics evidence assertions still green."
completed_at: 2026-03-26T11:14:51.357Z
blocker_discovered: false
---

# T02: Rendered the admin analytics weekly operating pack with projection-backed risk lists, blocker buckets, and department issue views.

> Rendered the admin analytics weekly operating pack with projection-backed risk lists, blocker buckets, and department issue views.

## What Happened
---
id: T02
parent: S04
milestone: M005
key_files:
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M005/slices/S04/tasks/T02-SUMMARY.md
key_decisions:
  - Keep the weekly operating pack on a fixed 7-day `/admin/analytics/operating-pack` read while leaving overview/trends/leaderboard on the existing time-range filter.
  - Feed the existing manager-lite panel from `operating_pack.manager_lists` so current risk/improving membership stays on the same projection-backed evidence line as the new weekly buckets.
duration: ""
verification_result: passed
completed_at: 2026-03-26T11:14:51.359Z
blocker_discovered: false
---

# T02: Rendered the admin analytics weekly operating pack with projection-backed risk lists, blocker buckets, and department issue views.

**Rendered the admin analytics weekly operating pack with projection-backed risk lists, blocker buckets, and department issue views.**

## What Happened

Extended the existing admin analytics route so it now consumes the dedicated `/api/v1/admin/analytics/operating-pack` contract instead of stitching weekly manager lists from the legacy interventions endpoint. Added typed operating-pack response models in `web/src/lib/api/types.ts`, normalized the new payload in `web/src/lib/api/client.ts`, and switched `web/src/app/admin/analytics/page.tsx` to fetch a fixed 7-day operating pack alongside the existing broader overview/trend/leaderboard filters. The page now renders a weekly operating-pack summary, repeated blocker-family cards, and a department issue panel, while the existing manager panel is fed directly from the projection-backed `manager_lists`. Updated the focused Vitest file first to assert the new contract and then implemented until the suite passed again. Recorded the fixed-7-day page contract in `.gsd/DECISIONS.md` and added a knowledge note about duplicate reason text on this page so future tests do not assume those strings only render once.

## Verification

Ran the slice verification command `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'` fresh after wiring the operating-pack client and page. The suite passed with the new weekly summary assertions, the projection-backed manager-panel feed, and the existing analytics evidence assertions still green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'` | 0 | ✅ pass | 1010ms |


## Deviations

The task plan's expected-output list omitted `web/src/lib/api/client.ts`, but the page could not safely consume `/admin/analytics/operating-pack` without adding a typed client method and normalizer there.

## Known Issues

Live browser proof against a real authenticated admin backend was not completed inside this task window; `/admin/*` uses server-side session gating, so client-side route mocks alone are not enough to render the page without a cookie-backed backend session.

## Files Created/Modified

- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M005/slices/S04/tasks/T02-SUMMARY.md`


## Deviations
The task plan's expected-output list omitted `web/src/lib/api/client.ts`, but the page could not safely consume `/admin/analytics/operating-pack` without adding a typed client method and normalizer there.

## Known Issues
Live browser proof against a real authenticated admin backend was not completed inside this task window; `/admin/*` uses server-side session gating, so client-side route mocks alone are not enough to render the page without a cookie-backed backend session.
