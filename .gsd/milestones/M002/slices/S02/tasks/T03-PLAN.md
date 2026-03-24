---
estimated_steps: 4
estimated_files: 7
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - react-best-practices
  - vercel-react-best-practices
  - baseline-ui
  - fixing-accessibility
  - verification-before-completion
---

# T03: Clear stale turn hints and enforce action-card precedence in the practice panel

**Slice:** S02 — 提示节奏收口与单轮唯一动作卡
**Milestone:** M002

## Description

Make the visible coaching surface match the backend pacing rules. The reducer currently leaves `actionCard` and `fuzzyDetections` in state until something overwrites them, and the practice panel can render multiple textual instructions at once. This task should clear turn-bound hints on a new final transcript, keep stage/score context visible, and ensure the right panel presents `action_card` as the single primary coaching surface.

## Steps

1. Add failing reducer tests in `web/src/hooks/websocket/message-handlers.test.ts` proving that a new final `transcript` / `asr_transcript` clears stale `actionCard` and `fuzzyDetections` before the next turn’s coaching lands, while leaving score/stage context intact.
2. Extend `web/src/hooks/use-practice-websocket.test.ts` with a hook-level regression that exercises the same transcript/reset path through the practice websocket wrapper, so the slice closes at the user-facing hook boundary instead of only inside the reducer.
3. Update `web/src/hooks/websocket/message-handlers.ts`, `web/src/components/practice/RightPanelContent.tsx`, and `web/src/components/practice/ScorePanel.tsx` so `action_card` is the only primary textual coach surface, duplicate textual suggestions are suppressed when that card exists, and stage/score context remains visible.
4. Add focused component assertions in `web/src/components/practice/RightPanelContent.test.tsx` and `web/src/components/practice/ScorePanel.test.tsx`, then rerun the full focused web verification set.

## Must-Haves

- [ ] New final transcript events clear stale turn-bound hints without wiping score or stage context.
- [ ] `RightPanelContent` does not show competing textual coaching beside an active `action_card`.
- [ ] `ScorePanel` can still show sales dimensions and fallback dimensions even when duplicate suggestions are suppressed.

## Verification

- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'`

## Observability Impact

- Signals added/changed: transcript-driven state-reset assertions, right-panel precedence assertions, and hook-level regressions that prove the reset survives the practice websocket wrapper.
- How a future agent inspects this: run the focused Vitest command and inspect the reducer/component tests for the exact state transitions expected after a final transcript closes a turn.
- Failure state exposed: stale hints bleeding across turns or duplicate coaching panels fail as deterministic frontend tests instead of requiring browser debugging first.

## Inputs

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — backend pacing contract that the UI should now reflect.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun event shape and reconnect-safe pacing reference from T02.
- `web/src/hooks/websocket/message-handlers.ts` — reducer handling transcript and coaching events.
- `web/src/hooks/websocket/message-handlers.test.ts` — reducer contract coverage.
- `web/src/hooks/use-practice-websocket.test.ts` — hook-level integration coverage.
- `web/src/components/practice/RightPanelContent.tsx` — visible right-panel coaching composition.
- `web/src/components/practice/ScorePanel.tsx` — score/stage/suggestion rendering.

## Expected Output

- `web/src/hooks/websocket/message-handlers.ts` — transcript-driven clearing of stale turn hints plus preserved score/stage context.
- `web/src/hooks/websocket/message-handlers.test.ts` — reducer regressions for transcript resets and single-turn coaching precedence.
- `web/src/hooks/use-practice-websocket.test.ts` — hook-level regression for the transcript/reset path.
- `web/src/components/practice/RightPanelContent.tsx` — panel composition that treats `action_card` as the primary textual coaching surface.
- `web/src/components/practice/RightPanelContent.test.tsx` — focused panel precedence assertions.
- `web/src/components/practice/ScorePanel.tsx` — duplicate-suggestion suppression with dimension rendering preserved.
- `web/src/components/practice/ScorePanel.test.tsx` — rendering assertions for the updated precedence behavior.
