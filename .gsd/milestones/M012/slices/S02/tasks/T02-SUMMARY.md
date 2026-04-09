---
id: T02
parent: S02
milestone: M012
provides: []
requires: []
affects: []
key_files: ["web/src/app/(dashboard)/page.test.tsx", ".gsd/milestones/M012/slices/S02/tasks/T02-SUMMARY.md"]
key_decisions: ["When the local dashboard-home runtime already satisfies the contract, preserve the existing implementation and close the task by adding the missing failure-path regression instead of rewriting live CTA behavior."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the slice-plan Vitest command fresh and confirmed all dashboard-home and history route-family assertions pass, including happy-path report links, malformed and incomplete session disabled states, presentation route-family coverage, and the new history-load failure fallback behavior. Re-ran LSP diagnostics on `web/src/app/(dashboard)/page.tsx`, `web/src/app/(dashboard)/page.test.tsx`, and `web/src/app/(dashboard)/history/page.test.tsx`; no issues were reported."
completed_at: 2026-04-09T07:35:33.260Z
blocker_discovered: false
---

# T02: Locked dashboard-home learner CTA coverage so history failures still degrade to real /history or training actions without hollow controls.

> Locked dashboard-home learner CTA coverage so history failures still degrade to real /history or training actions without hollow controls.

## What Happened
---
id: T02
parent: S02
milestone: M012
key_files:
  - web/src/app/(dashboard)/page.test.tsx
  - .gsd/milestones/M012/slices/S02/tasks/T02-SUMMARY.md
key_decisions:
  - When the local dashboard-home runtime already satisfies the contract, preserve the existing implementation and close the task by adding the missing failure-path regression instead of rewriting live CTA behavior.
duration: ""
verification_result: passed
completed_at: 2026-04-09T07:35:33.261Z
blocker_discovered: false
---

# T02: Locked dashboard-home learner CTA coverage so history failures still degrade to real /history or training actions without hollow controls.

**Locked dashboard-home learner CTA coverage so history failures still degrade to real /history or training actions without hollow controls.**

## What Happened

I verified the local dashboard-home runtime before editing and found that `web/src/app/(dashboard)/page.tsx` already met the task contract: the fake filter had been replaced with a real `/history` action, recent-history cards only exposed real `/history` or `/practice/{sessionId}/report` destinations, and malformed or incomplete sessions already rendered explicit disabled states with learner-safe copy. To avoid unnecessary churn, I kept the working runtime intact and added the missing regression coverage in `web/src/app/(dashboard)/page.test.tsx` for the dashboard-history failure path so learners still see real history/training actions and never a silent no-op CTA. My first pass at the new test failed because the page legitimately renders both the recommendation CTA and the empty-state CTA with the label `开始训练`; I narrowed the assertion to the intended behavior instead of changing product code. Fresh slice verification then passed for the dashboard/home and history route-family tests, and LSP diagnostics stayed clean.

## Verification

Ran the slice-plan Vitest command fresh and confirmed all dashboard-home and history route-family assertions pass, including happy-path report links, malformed and incomplete session disabled states, presentation route-family coverage, and the new history-load failure fallback behavior. Re-ran LSP diagnostics on `web/src/app/(dashboard)/page.tsx`, `web/src/app/(dashboard)/page.test.tsx`, and `web/src/app/(dashboard)/history/page.test.tsx`; no issues were reported.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` | 0 | ✅ pass | 1010ms |
| 2 | `LSP diagnostics on web/src/app/(dashboard)/page.tsx, web/src/app/(dashboard)/page.test.tsx, web/src/app/(dashboard)/history/page.test.tsx` | 0 | ✅ pass | 0ms |


## Deviations

The planner expected runtime edits in `web/src/app/(dashboard)/page.tsx`, but local reality already satisfied the task contract. I therefore limited execution to adding the missing degraded-path regression coverage instead of rewriting working homepage CTA logic.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(dashboard)/page.test.tsx`
- `.gsd/milestones/M012/slices/S02/tasks/T02-SUMMARY.md`


## Deviations
The planner expected runtime edits in `web/src/app/(dashboard)/page.tsx`, but local reality already satisfied the task contract. I therefore limited execution to adding the missing degraded-path regression coverage instead of rewriting working homepage CTA logic.

## Known Issues
None.
