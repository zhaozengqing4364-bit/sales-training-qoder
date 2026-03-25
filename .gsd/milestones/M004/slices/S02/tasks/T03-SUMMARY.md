---
id: T03
parent: S02
milestone: M004
key_files:
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/DECISIONS.md
key_decisions:
  - Consumed the report deep-link contract directly on the existing replay page via query params instead of adding a second resolver or replay-only route.
  - Made replay landing stateful in the UI with a persistent anchor banner plus turn highlighting so resolved, degraded, and missing-target cases stay visible instead of silently failing.
duration: ""
verification_result: passed
completed_at: 2026-03-25T17:13:46.550Z
blocker_discovered: false
---

# T03: Replay now honors report deep links, auto-focuses the requested turn, and keeps degraded anchor fallback visible.

**Replay now honors report deep links, auto-focuses the requested turn, and keeps degraded anchor fallback visible.**

## What Happened

Implemented T03 on the current replay page rather than introducing a new route. The page now parses the report deep-link query contract (`focus`, `message_id`, `turn`, `anchor_status`, `anchor_reason`, `marker_type`, `marker_timestamp_ms`), resolves the requested message/turn against the loaded replay payload, and looks up the referenced timeline marker when the report link represents a degraded stage fallback. When a target still exists, the replay auto-scrolls to that turn and keeps it visually highlighted. When the exact highlight or marker no longer exists, the page keeps a persistent banner visible that explains whether the user landed on a degraded stage fallback or whether the requested anchor is now missing, instead of silently dropping the request.

Locked the behavior with focused replay-page tests covering three deep-link cases in addition to the existing unified-evidence render assertions: resolved issue navigation, degraded stage-fallback navigation, and missing-target fallback visibility. I also recorded the frontend-routing decision in D066 so downstream slice work can treat the replay query contract as the stable handoff seam from the report page.

I attempted a lightweight browser proof by starting the local Next dev server and loading the replay route directly, but a frontend-only API stubbing attempt reproduced the repository's known cross-origin route-mock/CORS issue for localhost:3444. I shut the temp server down and did not count that environment-noisy attempt as product verification.

## Verification

Ran the task-plan verifier exactly as written: `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`. The focused Vitest suite passed with 12/12 tests green. That covers the replay page's resolved anchor landing, degraded stage fallback copy, missing-target fallback copy, and the existing report-page deep-link contract that produces the replay query params consumed here. I also attempted a local browser proof on `localhost:3445`, but a frontend-only fetch-mock path reproduced the known cross-origin mock/CORS noise against `localhost:3444`, so it was treated as non-authoritative environment noise rather than a product failure.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 7400ms |


## Deviations

None.

## Known Issues

A frontend-only browser proof on localhost hit the repository's known cross-origin route-mock/CORS noise when trying to stub backend replay APIs, so the passing focused Vitest suite remains the authoritative verification for this task.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `.gsd/DECISIONS.md`
