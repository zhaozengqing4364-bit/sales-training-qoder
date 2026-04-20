---
id: T02
parent: S02
milestone: M004
provides: []
requires: []
affects: []
key_files: ["web/src/app/(user)/practice/[sessionId]/report/page.tsx", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", "web/src/lib/api/types.ts", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Reused the existing replay route and encoded report deep links as replay query params (`focus`, `message_id`, `turn`, `anchor_status`, `anchor_reason`, `marker_type`, `marker_timestamp_ms`) instead of adding a report-only resolver or a second learning page.", "Loaded replay anchor metadata from the canonical replay API only when the report already had `main_issue` or `next_goal`, so the report cards stay aligned with the same SessionEvidenceService projection that T01 extended.", "Kept report highlight deep links on the current `HighlightList` seam by routing cards into replay with `focus=learning_evidence&turn=...` until T03 consumes the query contract on the replay page."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Re-ran the required focused verifier from the task plan: `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`. The suite passed with 8/8 tests, covering the new replay deep-link CTAs, degraded anchor copy, and highlight-card replay handoff alongside the existing report regressions. I also attempted a live browser/runtime proof by starting the repo backend on `:3444` and the repo frontend on `:3445`; that attempt confirmed the correct repo route and environment host mismatch gotcha, but it did not complete a fully authenticated report→replay click-through within the task time budget."
completed_at: 2026-03-25T16:55:38.881Z
blocker_discovered: false
---

# T02: Added replay deep-link CTAs to the report page for issue, goal, and highlight evidence.

> Added replay deep-link CTAs to the report page for issue, goal, and highlight evidence.

## What Happened
---
id: T02
parent: S02
milestone: M004
key_files:
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/lib/api/types.ts
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Reused the existing replay route and encoded report deep links as replay query params (`focus`, `message_id`, `turn`, `anchor_status`, `anchor_reason`, `marker_type`, `marker_timestamp_ms`) instead of adding a report-only resolver or a second learning page.
  - Loaded replay anchor metadata from the canonical replay API only when the report already had `main_issue` or `next_goal`, so the report cards stay aligned with the same SessionEvidenceService projection that T01 extended.
  - Kept report highlight deep links on the current `HighlightList` seam by routing cards into replay with `focus=learning_evidence&turn=...` until T03 consumes the query contract on the replay page.
duration: ""
verification_result: passed
completed_at: 2026-03-25T16:55:38.883Z
blocker_discovered: false
---

# T02: Added replay deep-link CTAs to the report page for issue, goal, and highlight evidence.

**Added replay deep-link CTAs to the report page for issue, goal, and highlight evidence.**

## What Happened

Started with TDD on the current report page: added focused expectations for two new behaviors before touching production code. The new tests first failed because the report page rendered the existing issue/goal cards but had no replay-aware CTA copy, no anchor-driven buttons, and no way to hand a highlight card off to the current replay route.

Implemented the frontend anchor contract in three places. In `web/src/lib/api/types.ts` I added typed `ReplayAnchor`/`ReplayAnchorMarker` support and made the existing `SessionMainIssue` and `SessionNextGoal` shapes optionally carry `replay_anchor`, which matches the replay payload T01 already ships. In `web/src/app/(user)/practice/[sessionId]/report/page.tsx` I kept the current report route and current CTA area, loaded replay data only when the report actually exposed `main_issue` or `next_goal`, derived stable deep-link URLs from the replay anchor payload, and surfaced explicit copy for resolved vs degraded anchors instead of silently pretending every conclusion had an exact highlight. The report cards now expose `定位问题片段` / `定位目标片段`, while the existing highlight section now routes cards into replay by turn without introducing a second learning surface.

The local task plan listed `web/src/lib/api/client.ts`, but the local snapshot already had `api.sessions.getReplay(...)`, so no client-layer code change was needed. I recorded the query-param handoff decision in `.gsd/DECISIONS.md` for T03 and added a browser-proof environment note to `.gsd/KNOWLEDGE.md` after confirming this machine’s `:3000` was not this repo’s frontend.

On verification, the focused report-page Vitest was rerun cleanly after the implementation. I also attempted a live browser proof by starting the repo backend on `:3444` and this repo’s Next frontend on `:3445`; that confirmed the report route exists on the repo app, but I stopped short of a full authenticated report→replay runtime proof once the time budget warning landed. Both temporary servers were shut down before wrap-up.

## Verification

Re-ran the required focused verifier from the task plan: `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`. The suite passed with 8/8 tests, covering the new replay deep-link CTAs, degraded anchor copy, and highlight-card replay handoff alongside the existing report regressions. I also attempted a live browser/runtime proof by starting the repo backend on `:3444` and the repo frontend on `:3445`; that attempt confirmed the correct repo route and environment host mismatch gotcha, but it did not complete a fully authenticated report→replay click-through within the task time budget.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 1421ms |


## Deviations

The local snapshot already exposed `api.sessions.getReplay(...)` in `web/src/lib/api/client.ts`, so T02 did not need a client-layer code change even though the original task file list expected that file to move.

## Known Issues

A fully authenticated live browser proof on the repo web app was not completed inside this task's time budget. The focused report-page Vitest is green, and a partial runtime attempt confirmed the repo route exists on `localhost:3445`, but T03 should finish the full localhost/localhost report→replay proof once the local login/runtime path is in hand.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/lib/api/types.ts`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
The local snapshot already exposed `api.sessions.getReplay(...)` in `web/src/lib/api/client.ts`, so T02 did not need a client-layer code change even though the original task file list expected that file to move.

## Known Issues
A fully authenticated live browser proof on the repo web app was not completed inside this task's time budget. The focused report-page Vitest is green, and a partial runtime attempt confirmed the repo route exists on `localhost:3445`, but T03 should finish the full localhost/localhost report→replay proof once the local login/runtime path is in hand.
