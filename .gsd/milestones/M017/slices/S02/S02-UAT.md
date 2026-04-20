# S02: Practice WebSocket 复杂度与重连策略收口 — UAT

**Milestone:** M017
**Written:** 2026-04-11T21:44:40.226Z

# S02 UAT — Practice WebSocket reconnect / backpressure / interrupt contract

## Preconditions
- Repository dependencies are installed and the `web` test environment can run Vitest.
- Execute all commands from the repository root: `/Users/zhaozengqing/github/销售训练qoder`.
- No live StepFun/browser session is required; this slice’s acceptance authority is the focused websocket + learner-page proof bundle.

## Test Case 1 — Hook authority seam stays explicit
1. Run:
   `rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts`
2. Confirm the output includes the hook header boundary notes plus focused tests covering binary negotiation, backpressure handling, interrupt behavior, reconnect epochs, and stale-interrupt protection.

**Expected outcome**
- Command exits 0.
- The hook documents the transport/outbound boundary and the focused test files contain reconnect/backpressure/interrupt proofs rather than only generic smoke coverage.

## Test Case 2 — Sales websocket reconnect/backpressure/interrupt contract
1. Run:
   `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts"`
2. Review the named assertions in the output/logged suite:
   - binary negotiation is owned by the hook at connect time;
   - backpressure buffers outbound audio and resumes flush when the server sends `resume`;
   - interrupt clears buffered audio plus learner-visible slow/backpressure flags;
   - an interrupt fired against a dead socket is **not** replayed when reconnect opens a fresh socket;
   - non-retry close exits the reconnect path and clears stale slow-network state.

**Expected outcome**
- Suite exits 0.
- All reconnect/backpressure/interrupt assertions pass with no failed expectations.

## Test Case 3 — Presentation stream epoch reset on reconnect
1. Run:
   `npm --prefix web test -- --run "src/hooks/use-practice-websocket.presentation-flow.test.ts"`
2. Verify the suite covers:
   - `sendControl("start")` staying outbound-only until inbound `status` advances the presentation session;
   - stale `interrupted` messages from an old stream being ignored;
   - reconnect resetting stream ownership so only the new live stream can interrupt the learner-visible state.

**Expected outcome**
- Suite exits 0.
- The presentation hook contract continues to distinguish outbound commands from inbound authority and ignores stale old-stream interrupts after reconnect.

## Test Case 4 — Learner reconnect guidance matches transport truth
1. Run:
   `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx"`
2. Confirm the `shows automatic reconnect guidance while transport recovery is still in progress` assertion passes.
3. Verify the tested UX contract:
   - `connectionState="reconnecting"` shows `连接中断，正在重连...` and `网络波动，正在自动重连...`;
   - the manual `重新连接` button is **not** shown during automatic recovery;
   - failure-only actions remain reserved for terminal failure states.

**Expected outcome**
- Suite exits 0.
- The learner page surfaces passive recovery guidance during reconnect and does not regress into premature manual-reconnect UI.

## Edge Cases To Re-check If This Slice Regresses
1. **Dead-socket interrupt:** trigger abnormal close, call `sendInterrupt("user_speaking")`, then let the retry socket open. Expected: the new socket only negotiates binary transport; it does not replay the stale interrupt.
2. **Buffered-audio interrupt:** while backpressure is active and local audio has been buffered, call `sendInterrupt(...)`. Expected: buffered audio is dropped immediately and both `isBackpressureActive` / `isNetworkSlow` become false.
3. **Non-retry close:** emit close code `1000` or `1001` after slow-network state is active. Expected: reconnect stops, connection ends in `failed`, and stale slow/backpressure state is cleared.
4. **Presentation stale interrupt:** after reconnect creates a new stream epoch, deliver an `interrupted` message from the old stream id. Expected: learner-visible speaking state does not change until the current live stream emits the interrupt.

