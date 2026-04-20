---
id: T03
parent: S02
milestone: M012
provides: []
requires: []
affects: []
key_files: ["web/src/components/learner/learner-route-error-state.tsx", "web/src/app/(user)/practice/[sessionId]/error.tsx", "web/src/app/(user)/practice/[sessionId]/report/error.tsx", "web/src/app/(user)/practice/[sessionId]/replay/error.tsx", "web/src/app/(user)/practice/[sessionId]/error.test.tsx", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Use a shared `LearnerRouteErrorState` presenter so practice/report/replay App Router boundaries keep one retry, logging, and diagnostic contract.", "Route the live practice fallback back to `/training`, while report and replay keep `/history`, so each boundary returns users to the nearest real recovery surface."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh focused Vitest verification passed for `src/app/(user)/practice/[sessionId]/error.test.tsx`, proving the live practice fallback renders retry + safe navigation and hides raw diagnostics in production while keeping them bounded in development. LSP diagnostics then confirmed the new shared presenter and all three learner `error.tsx` routes are clean."
completed_at: 2026-04-09T09:50:21.971Z
blocker_discovered: false
---

# T03: Added a shared learner route error presenter, wired practice/report/replay App Router boundaries to it, and locked the live practice fallback with focused Vitest coverage.

> Added a shared learner route error presenter, wired practice/report/replay App Router boundaries to it, and locked the live practice fallback with focused Vitest coverage.

## What Happened
---
id: T03
parent: S02
milestone: M012
key_files:
  - web/src/components/learner/learner-route-error-state.tsx
  - web/src/app/(user)/practice/[sessionId]/error.tsx
  - web/src/app/(user)/practice/[sessionId]/report/error.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/error.tsx
  - web/src/app/(user)/practice/[sessionId]/error.test.tsx
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Use a shared `LearnerRouteErrorState` presenter so practice/report/replay App Router boundaries keep one retry, logging, and diagnostic contract.
  - Route the live practice fallback back to `/training`, while report and replay keep `/history`, so each boundary returns users to the nearest real recovery surface.
duration: ""
verification_result: passed
completed_at: 2026-04-09T09:50:21.972Z
blocker_discovered: false
---

# T03: Added a shared learner route error presenter, wired practice/report/replay App Router boundaries to it, and locked the live practice fallback with focused Vitest coverage.

**Added a shared learner route error presenter, wired practice/report/replay App Router boundaries to it, and locked the live practice fallback with focused Vitest coverage.**

## What Happened

T03 was still incomplete in the working tree, so I finished it directly with a test-first pass. I first added `web/src/app/(user)/practice/[sessionId]/error.test.tsx` and confirmed the focused Vitest run failed because `./error` did not exist yet, which proved the live practice route still lacked the planned App Router boundary. I then introduced `web/src/components/learner/learner-route-error-state.tsx` as the shared learner fallback presenter: it logs a tagged `console.error`, keeps retry plus safe navigation actions on-screen, and only exposes a bounded `error.message` in development. With that presenter in place, I added the missing live `web/src/app/(user)/practice/[sessionId]/error.tsx` boundary and refactored the existing report/replay `error.tsx` files to reuse the same presenter instead of maintaining duplicate copy and behavior. I also recorded two future-agent gotchas in `.gsd/KNOWLEDGE.md`: dashboard degraded states can legitimately render multiple `开始训练` buttons, and route-error tests must stub `NODE_ENV=development` if they expect raw diagnostics. Fresh focused verification then passed for the live practice boundary, and diagnostics were clean for the shared presenter plus all practice/report/replay error routes.

## Verification

Fresh focused Vitest verification passed for `src/app/(user)/practice/[sessionId]/error.test.tsx`, proving the live practice fallback renders retry + safe navigation and hides raw diagnostics in production while keeping them bounded in development. LSP diagnostics then confirmed the new shared presenter and all three learner `error.tsx` routes are clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/error.test.tsx"` | 0 | ✅ pass | 534ms |
| 2 | `LSP diagnostics on web/src/app/**/error.tsx` | 0 | ✅ pass | 0ms |
| 3 | `LSP diagnostics on web/src/components/learner/learner-route-error-state.tsx and web/src/app/**/error.test.tsx` | 0 | ✅ pass | 0ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/components/learner/learner-route-error-state.tsx`
- `web/src/app/(user)/practice/[sessionId]/error.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/error.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/error.tsx`
- `web/src/app/(user)/practice/[sessionId]/error.test.tsx`
- `.gsd/KNOWLEDGE.md`


## Deviations
None.

## Known Issues
None.
