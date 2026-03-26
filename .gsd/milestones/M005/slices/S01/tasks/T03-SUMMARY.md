---
id: T03
parent: S01
milestone: M005
provides: []
requires: []
affects: []
key_files: ["web/src/components/admin/manager-lite-panel.tsx", "web/src/components/admin/manager-lite-panel.test.tsx", "web/src/app/admin/users/[id]/page.tsx", "web/src/app/admin/users/[id]/page.test.tsx", "web/src/lib/api/types.ts"]
key_decisions: ["Kept the existing manager-lite panel and admin user detail route, but made both surfaces explicitly name the unified evidence score basis and report CTA semantics instead of introducing a new manager workflow shell.", "Extended the existing user statistics type with evaluability and score-basis fields so the drill-in page can render the backend truth line without local casts or duplicate normalization."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the exact task-plan verifier fresh: `cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`. The focused Vitest suite passed all 4 assertions, covering the manager-lite evidence copy, unified-report CTA wording, the user drill-in score-basis/evaluability summary, and the aligned report CTA on the session table. Browser-proof scaffolding was attempted but not counted as acceptance evidence because the local browser automation environment is broken."
completed_at: 2026-03-26T06:35:02.453Z
blocker_discovered: false
---

# T03: Align admin drill-in and manager-lite copy with unified evidence score semantics.

> Align admin drill-in and manager-lite copy with unified evidence score semantics.

## What Happened
---
id: T03
parent: S01
milestone: M005
key_files:
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/lib/api/types.ts
key_decisions:
  - Kept the existing manager-lite panel and admin user detail route, but made both surfaces explicitly name the unified evidence score basis and report CTA semantics instead of introducing a new manager workflow shell.
  - Extended the existing user statistics type with evaluability and score-basis fields so the drill-in page can render the backend truth line without local casts or duplicate normalization.
duration: ""
verification_result: passed
completed_at: 2026-03-26T06:35:02.455Z
blocker_discovered: false
---

# T03: Align admin drill-in and manager-lite copy with unified evidence score semantics.

**Align admin drill-in and manager-lite copy with unified evidence score semantics.**

## What Happened

Aligned the existing manager-lite panel and `/admin/users/[id]` page with the projection-backed admin truth line established in T01/T02. Manager-lite now explains that not-passed and improving lists only count completed evaluable sessions, uses normalized fail-result wording, and renames the report CTA to `查看统一报告` so reminder/report actions stay on the same vocabulary as analytics. The admin user drill-in now surfaces the score-basis label plus evaluable/not-evaluable counts in the top score card, renames the session preview column to `统一训练证据预览`, and uses the same `查看统一报告` CTA in the session table. I also extended the frontend `UserStatistics` type so the page can consume the backend's existing evaluability metadata directly. During verification I briefly started local backend/frontend servers and confirmed a real browser session could reach the admin user detail route through temporary dev-login scaffolding, then removed that scaffolding and shut the servers down; because browser automation itself is broken on this machine, the acceptance gate remained the focused Vitest suite.

## Verification

Ran the exact task-plan verifier fresh: `cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`. The focused Vitest suite passed all 4 assertions, covering the manager-lite evidence copy, unified-report CTA wording, the user drill-in score-basis/evaluability summary, and the aligned report CTA on the session table. Browser-proof scaffolding was attempted but not counted as acceptance evidence because the local browser automation environment is broken.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1559ms |


## Deviations

Updated `web/src/lib/api/types.ts` in addition to the four planned UI files because the existing frontend `UserStatistics` contract did not expose the backend's `evaluable_sessions`, `not_evaluable_sessions`, or `score_basis` fields.

## Known Issues

Local browser automation remains unreliable in this environment: the built-in browser tool fails before navigation because its Playwright install cannot resolve `./registry`, and both Safari and Chrome have Apple-event JavaScript execution disabled. Focused Vitest is the durable verifier for this task.

## Files Created/Modified

- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/lib/api/types.ts`


## Deviations
Updated `web/src/lib/api/types.ts` in addition to the four planned UI files because the existing frontend `UserStatistics` contract did not expose the backend's `evaluable_sessions`, `not_evaluable_sessions`, or `score_basis` fields.

## Known Issues
Local browser automation remains unreliable in this environment: the built-in browser tool fails before navigation because its Playwright install cannot resolve `./registry`, and both Safari and Chrome have Apple-event JavaScript execution disabled. Focused Vitest is the durable verifier for this task.
