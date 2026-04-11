---
id: T03
parent: S02
milestone: M017
key_files:
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-11T21:40:59.589Z
blocker_discovered: false
---

# T03: Added focused websocket contract proofs for reconnect exit, stale interrupt reset, and learner reconnect guidance.

**Added focused websocket contract proofs for reconnect exit, stale interrupt reset, and learner reconnect guidance.**

## What Happened

I kept this task at the proof layer instead of reopening the websocket implementation seam from T01/T02. In `web/src/hooks/use-practice-websocket.test.ts`, I added a focused transport-epoch regression that proves a close code which exits the retry path clears learner-visible slow-network/backpressure state and does not schedule another socket. In `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`, I added a presentation-specific proof that reconnect resets stream ownership, so a stale `interrupted` message from the pre-reconnect stream no longer mutates the new epoch. In `web/src/app/(user)/practice/[sessionId]/page.test.tsx`, I added a learner-shell proof that the page shows automatic reconnect guidance while recovery is still in progress and withholds the manual reconnect CTA until the transport has actually failed. The runtime code already satisfied these boundaries, so the shipped change is a tighter proof surface that future agents can use to localize regressions quickly.

## Verification

Ran the slice-plan verification command after adding the new proofs: `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"`; all three focused suites passed (33/33). Re-ran semantic checks with LSP diagnostics on the two hook test files plus the app page test glob covering `web/src/app/(user)/practice/[sessionId]/page.test.tsx`; no diagnostics were reported.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts src/hooks/use-practice-websocket.presentation-flow.test.ts src/app/(user)/practice/[sessionId]/page.test.tsx` | 0 | ✅ pass | 1371ms |
| 2 | `rg -n "transport epoch|presentation stream epoch|automatic reconnect guidance" web/src/hooks/use-practice-websocket.test.ts web/src/hooks/use-practice-websocket.presentation-flow.test.ts web/src/app/(user)/practice/[sessionId]/page.test.tsx` | 0 | ✅ pass | 15ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
