---
id: T01
parent: S02
milestone: M017
key_files:
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D199 — keep `use-practice-websocket` as the transport/outbound orchestrator and keep inbound protocol projection in `websocket/message-handlers`.
duration: 
verification_result: passed
completed_at: 2026-04-11T21:26:50.634Z
blocker_discovered: false
---

# T01: Locked the real practice websocket seam with boundary notes and focused reconnect/backpressure/interrupt proofs.

**Locked the real practice websocket seam with boundary notes and focused reconnect/backpressure/interrupt proofs.**

## What Happened

I inspected `web/src/hooks/use-practice-websocket.ts` together with its focused hook tests and the surrounding `websocket/message-handlers` module to distinguish real orchestration responsibility from superficial file-size complexity. The live code already had one important split in place: inbound protocol application (`status`, `reconnected`, `interrupted`, `backpressure`) belongs in `websocket/message-handlers`, while the hook still legitimately owns transport lifecycle, reconnect retry budget, pending outbound flush, binary negotiation on connect, outbound audio pacing/backpressure buffering, and interrupt pre-cleanup across playback refs and browser speech synthesis. I codified that boundary directly in the hook header instead of doing a fake extract-by-size refactor. I then strengthened the focused tests so future agents can see the seam in behavior: the hook suite now proves binary negotiation happens at connect time, backpressure is an inbound resume signal plus hook-owned outbound buffering/flush, and interrupt pre-cleanup stays in the hook before backend confirmation. On the presentation-focused suite, I corrected the contract proof to match the real runtime truth line: `sendControl("start")` is only an outbound command, and `sessionStatus` / `aiState` advance only after inbound backend `status` confirms the session is actually in progress.

## Verification

Ran the exact task-plan inventory command to confirm reconnect/backpressure/interrupt/binary coverage now appears directly in the hook and focused tests. Ran the impacted websocket hook suites with Vitest; both `src/hooks/use-practice-websocket.test.ts` and `src/hooks/use-practice-websocket.presentation-flow.test.ts` passed (18/18). Re-ran LSP diagnostics on `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/use-practice-websocket.test.ts`, and `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`; all were clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts` | 0 | ✅ pass | 18ms |
| 2 | `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts"` | 0 | ✅ pass | 980ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `.gsd/KNOWLEDGE.md`
