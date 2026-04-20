---
id: S02
parent: M017
milestone: M017
provides:
  - A locked reconnect/backpressure/interrupt contract for the practice websocket layer.
  - A focused proof bundle future agents can rerun to localize transport regressions quickly.
  - A learner-shell reconnect UX baseline that distinguishes automatic recovery from terminal failure.
requires:
  []
affects:
  - S03
key_files:
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D199 — keep `use-practice-websocket` as the transport/outbound orchestrator and keep inbound protocol projection in `websocket/message-handlers`.
  - D200 — treat reconnect as a fresh transport epoch: only the initial connecting handshake may replay queued outbound messages, and interrupt owns queued-outbound/local-backpressure cleanup.
patterns_established:
  - Keep outbound transport/reconnect/backpressure/interrupt orchestration in `use-practice-websocket` while leaving inbound protocol application in `websocket/message-handlers`.
  - Treat reconnect as a fresh transport epoch; stale dead-socket intent should be dropped, not replayed.
  - Gate learner reconnect UI by `connectionState` truth: passive guidance during `reconnecting`, manual CTA only in `failed`.
observability_surfaces:
  - Focused websocket authority bundle: `web/src/hooks/use-practice-websocket.test.ts` + `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`.
  - Learner reconnect-phase diagnostic surface in `web/src/app/(user)/practice/[sessionId]/page.test.tsx`.
drill_down_paths:
  - .gsd/milestones/M017/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M017/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M017/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T21:44:40.226Z
blocker_discovered: false
---

# S02: Practice WebSocket 复杂度与重连策略收口

**Locked the practice websocket seam so reconnect/backpressure/interrupt now behave as one truthful transport epoch, with focused proof extending from the hook to the learner practice page.**

## What Happened

## Delivered
- Clarified the real `use-practice-websocket` boundary instead of doing another file-size refactor: the hook remains the transport/outbound orchestrator for connect/disconnect, reconnect budget, initial pending-outbound flush, binary negotiation, outbound audio pacing, local backpressure buffering, and interrupt pre-cleanup.
- Preserved `web/src/hooks/websocket/message-handlers.ts` as the inbound authority seam: `status`, `reconnected`, `interrupted`, and `backpressure` only become learner-visible state when the backend confirms them.
- Tightened reconnect semantics into a fresh transport epoch: only the initial `connecting` handshake may replay queued outbound messages; once the hook has moved into `reconnecting`/`failed`, stale queued control or interrupt intent is dropped instead of leaking onto the next socket.
- Made `sendInterrupt(...)` own full local cleanup by aborting in-flight flushes, clearing pending outbound work, discarding buffered audio, and resetting learner-visible `isBackpressureActive` / `isNetworkSlow` state immediately.
- Added focused proof that presentation reconnect resets stream ownership, so stale `interrupted` events from the pre-reconnect stream cannot mutate the new epoch.
- Added learner-page proof that automatic recovery and terminal failure stay distinct: `reconnecting` shows passive recovery guidance, while the manual `重新连接` CTA stays reserved for the terminal `failed` state.

## What This Slice Actually Established
1. **Reconnect/backpressure/interrupt is one seam.** The remaining complexity is not “the hook is still big”; it is the truthful coordination boundary where transport retries, queued outbound work, local audio buffering, and interrupt cleanup interact.
2. **Inbound authority remains server-confirmed.** Local `sendControl("start"|"pause"|"resume"|"end")` is only an outbound command; `sessionStatus` / `aiState` change only after inbound `status` or `reconnected` messages.
3. **Reconnect is not resume-from-everything.** A retry socket represents a fresh transport epoch, not a replay of stale dead-socket intent.
4. **Learner recovery UX now matches transport truth.** Automatic reconnect is exposed as recovery-in-progress, not as a premature manual-reconnect problem.

## Patterns Established For Future Slices
- Keep websocket outbound orchestration in `use-practice-websocket`; keep inbound protocol projection in `websocket/message-handlers`.
- When a runtime regression appears, localize it via the focused authority files first: `web/src/hooks/use-practice-websocket.test.ts`, `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`, and `web/src/app/(user)/practice/[sessionId]/page.test.tsx`.
- Treat stale reconnect behavior as an epoch/queue-cleanup bug before reaching for another state machine or a broader refactor.
- Keep learner-facing reconnect UI keyed to `connectionState` truth (`reconnecting` vs `failed`) rather than generic copy toggles.

## Downstream Notes For S03
- S03 can assume the practice websocket layer no longer replays stale interrupt/control intent across reconnects, and that local backpressure cleanup does not leave fake slow-network state behind.
- If upload/resource-race discovery uncovers “session reopened after retry” symptoms, check the transport-epoch proofs here before broadening the backend lifecycle contract again.

## Operational Readiness (Q8)
- **Health signal:** focused websocket/page proofs stay green and the learner shell continues to render automatic reconnect guidance during `connectionState="reconnecting"` while hiding the manual reconnect CTA.
- **Failure signal:** a retry socket emits stale queued interrupt/control payloads, buffered/backpressured audio survives an interrupt, or the learner page surfaces `重新连接` before the transport has actually failed.
- **Recovery procedure:** rerun the focused authority bundle first; if the failure reproduces, inspect the transport epoch cleanup inside `use-practice-websocket.ts` (pending outbound flush, `sendInterrupt(...)`, backpressure reset, reconnect close handling) before touching `message-handlers` or the practice page.
- **Monitoring gaps:** there is still no dedicated production metric separating repeated reconnect exhaustion from ordinary transient recovery; current close-out proof relies on focused tests and learner-shell state, not a shipped telemetry panel.


## Verification

## Fresh verification
- `rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts` → exit 0; the seam and proof vocabulary are present in the hook and focused tests.
- `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"` → exit 0; 3 files passed, 33/33 tests passed.
- Fresh LSP diagnostics on `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`, and `web/src/app/\(user\)/practice/\[sessionId\]/page.test.tsx` returned no diagnostics.

## Diagnostic surface confirmation
- Hook tests now explicitly lock binary negotiation ownership, backpressure resume flush, interrupt pre-cleanup, stale interrupt drop across reconnect, and reconnect exit conditions.
- Presentation-flow proof confirms stale interrupt messages from the old stream epoch do not mutate the new reconnect epoch.
- Practice page proof confirms the learner sees passive automatic reconnect guidance during recovery and only gets the manual reconnect CTA after terminal failure.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

No live browser/runtime proof was required for close-out; this slice’s authority is the focused websocket + learner-page contract bundle rather than a new localhost StepFun session.

## Follow-ups

S03 should reuse this transport-epoch contract when auditing upload/resource-race symptoms, instead of widening websocket behavior again or introducing a second client-side state machine.

## Files Created/Modified

- `web/src/hooks/use-practice-websocket.ts` — Documented the real orchestration boundary and tightened reconnect/backpressure/interrupt cleanup semantics.
- `web/src/hooks/use-practice-websocket.test.ts` — Added focused proofs for backpressure cleanup, dead-socket interrupt drop, reconnect exit, and transport-epoch behavior.
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts` — Locked presentation-specific reconnect/stream-epoch interrupt behavior.
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx` — Locked learner reconnect guidance so auto-recovery and manual reconnect remain distinct.
- `.gsd/DECISIONS.md` — Recorded D199/D200 for the websocket orchestration seam.
- `.gsd/KNOWLEDGE.md` — Captured reconnect-epoch, outbound-control authority, and learner reconnect UX gotchas for future agents.
