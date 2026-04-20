---
id: T02
parent: S02
milestone: M017
key_files:
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D200 — treat reconnect as a fresh transport epoch: only the initial connecting handshake may replay queued outbound messages, and interrupt owns queued-outbound/local-backpressure cleanup.
duration: 
verification_result: passed
completed_at: 2026-04-11T21:34:36.620Z
blocker_discovered: false
---

# T02: Tightened practice websocket reconnect cleanup so stale queued interrupts do not replay after reconnect and interrupt clears local backpressure state.

**Tightened practice websocket reconnect cleanup so stale queued interrupts do not replay after reconnect and interrupt clears local backpressure state.**

## What Happened

I kept the work on the seam identified in T01 instead of doing another size-driven split. In `web/src/hooks/use-practice-websocket.ts`, I tightened outbound orchestration around two stale-state hazards the focused tests exposed: queued outbound messages are now only replayed during the initial `connecting` handshake, and reconnect/failed phases are treated as a fresh transport epoch so stale control/interrupt intent does not leak onto the next socket. I also made `sendInterrupt(...)` own the full local backlog cleanup path by clearing queued outbound work plus local backpressure/slow-state flags when it discards buffered audio. On the proof side, I added two focused regression tests in `web/src/hooks/use-practice-websocket.test.ts`: one locks that interrupt clears the learner-visible local backpressure state after dropping buffered audio, and the other locks that an interrupt fired against a dead socket is not replayed when reconnect opens a fresh connection. I then recorded the seam-level rule in `.gsd/DECISIONS.md` (D200), added the non-obvious reconnect-epoch gotcha to `.gsd/KNOWLEDGE.md`, and updated the safe-grow continuity files so T03 can start from the tightened contract instead of the old T01 checkpoint.

## Verification

I followed a red-green cycle on the websocket hook before widening verification. First I ran `npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts` after adding the new contract tests; it failed exactly where expected, showing that interrupt left `isBackpressureActive`/`isNetworkSlow` true after dropping buffered audio and that an interrupt triggered during reconnect was replayed on the next socket. After tightening the hook, I reran the focused hook suite and it passed 17/17. Then I ran the exact task-plan verification command `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"`; all three suites passed (30/30), confirming the reconnect/backpressure/interrupt change preserved the presentation-flow and learner-page contracts. Fresh LSP diagnostics were clean on `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/use-practice-websocket.test.ts`, and `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts` | 0 | ✅ pass | 699ms |
| 2 | `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"` | 0 | ✅ pass | 1000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
