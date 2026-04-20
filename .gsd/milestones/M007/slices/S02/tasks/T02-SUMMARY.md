---
id: T02
parent: S02
milestone: M007
provides: []
requires: []
affects: []
key_files: ["web/src/lib/api/types.ts", "web/src/hooks/websocket/types.ts", "web/src/hooks/websocket/message-handlers.ts", "web/src/lib/session-evidence.ts", "web/src/components/practice/RightPanelContent.tsx", "web/src/app/(user)/practice/[sessionId]/page.tsx", "web/src/hooks/websocket/message-handlers.test.ts", "web/src/components/practice/RightPanelContent.test.tsx", "web/src/app/(user)/practice/[sessionId]/page.test.tsx"]
key_decisions: ["Persist a normalized `liveSessionSummary` at the websocket reducer level and render learner issue/goal/claim-truth copy from shared `session-evidence` helpers instead of deriving it from stage text or action-card prose.", "Treat absence or partial invalidation of `score_update.data.live_session_summary` as a cue-clear signal so the learner route does not retain stale prior-turn conclusions."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the exact task-plan verification command from repo root: `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'`. All three targeted suites passed (44 tests total), proving reducer-state carry-through, stable cue rendering, and page-level panel pass-through on the current learner route family."
completed_at: 2026-03-28T08:02:53.066Z
blocker_discovered: false
---

# T02: Threaded websocket `live_session_summary` into learner state and rendered a stable same-session cue on `/practice/{sessionId}`.

> Threaded websocket `live_session_summary` into learner state and rendered a stable same-session cue on `/practice/{sessionId}`.

## What Happened
---
id: T02
parent: S02
milestone: M007
key_files:
  - web/src/lib/api/types.ts
  - web/src/hooks/websocket/types.ts
  - web/src/hooks/websocket/message-handlers.ts
  - web/src/lib/session-evidence.ts
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/components/practice/RightPanelContent.test.tsx
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
key_decisions:
  - Persist a normalized `liveSessionSummary` at the websocket reducer level and render learner issue/goal/claim-truth copy from shared `session-evidence` helpers instead of deriving it from stage text or action-card prose.
  - Treat absence or partial invalidation of `score_update.data.live_session_summary` as a cue-clear signal so the learner route does not retain stale prior-turn conclusions.
duration: ""
verification_result: passed
completed_at: 2026-03-28T08:02:53.067Z
blocker_discovered: false
---

# T02: Threaded websocket `live_session_summary` into learner state and rendered a stable same-session cue on `/practice/{sessionId}`.

**Threaded websocket `live_session_summary` into learner state and rendered a stable same-session cue on `/practice/{sessionId}`.**

## What Happened

Extended the learner websocket contract so `score_update` now normalizes and stores the backend `live_session_summary` as explicit reducer state, with fail-soft clearing when the field disappears or arrives partially invalid. Reused shared `session-evidence` helpers to render main issue, next goal, and claim-truth vocabulary from backend authority inside `RightPanelContent` instead of inferring it from stage labels, score text, or action-card prose. Passed the new state through the practice page into both desktop and mobile learner panels, while preserving the existing final-transcript behavior that clears transient `actionCard` / `fuzzyDetections` but leaves the stable same-session cue intact. Added focused reducer, panel, and page tests covering cue replacement, omission/partial clear, final-transcript preservation, and learner-page prop wiring.

## Verification

Ran the exact task-plan verification command from repo root: `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'`. All three targeted suites passed (44 tests total), proving reducer-state carry-through, stable cue rendering, and page-level panel pass-through on the current learner route family.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx'` | 0 | ✅ pass | 15500ms |


## Deviations

Added shared frontend contract types in `web/src/lib/api/types.ts` so the websocket reducer, learner page, and `session-evidence` helper can reference the same live-summary payload shape without duplicating local interfaces.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/api/types.ts`
- `web/src/hooks/websocket/types.ts`
- `web/src/hooks/websocket/message-handlers.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/hooks/websocket/message-handlers.test.ts`
- `web/src/components/practice/RightPanelContent.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`


## Deviations
Added shared frontend contract types in `web/src/lib/api/types.ts` so the websocket reducer, learner page, and `session-evidence` helper can reference the same live-summary payload shape without duplicating local interfaces.

## Known Issues
None.
