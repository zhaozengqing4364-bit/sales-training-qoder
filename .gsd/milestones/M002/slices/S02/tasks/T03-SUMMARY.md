---
id: T03
parent: S02
milestone: M002
provides:
  - Practice-page coaching now clears stale turn-bound hints on final transcripts and treats `action_card` as the single primary textual coach surface while preserving stage/score context.
key_files:
  - web/src/hooks/websocket/message-handlers.ts
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/components/practice/RightPanelContent.test.tsx
  - web/src/components/practice/ScorePanel.tsx
  - web/src/components/practice/ScorePanel.test.tsx
key_decisions: []
patterns_established:
  - Final user transcript events should clear only turn-bound coaching (`actionCard`, `fuzzyDetections`) while leaving long-lived score/stage context intact, and `ScorePanel` should support suggestion suppression via props rather than forking score data.
observability_surfaces:
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/components/practice/RightPanelContent.test.tsx
  - web/src/components/practice/ScorePanel.test.tsx
  - `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'`
duration: 48m
verification_result: passed
completed_at: 2026-03-24T20:31:00+0800
blocker_discovered: false
---

# T03: Clear stale turn hints and enforce action-card precedence in the practice panel

**Practice-page coaching now drops stale turn hints on final transcripts and keeps `action_card` as the only primary text coach surface.**

## What Happened

I followed the TDD path for the client seam.

First I added red tests in four places:
- reducer coverage in `web/src/hooks/websocket/message-handlers.test.ts` for final `transcript` / `asr_transcript` resets,
- a hook-level regression in `web/src/hooks/use-practice-websocket.test.ts` that runs the same path through the real websocket wrapper,
- a new `web/src/components/practice/RightPanelContent.test.tsx` file for panel precedence,
- and a new suppression-focused assertion in `web/src/components/practice/ScorePanel.test.tsx`.

The red run failed exactly where expected: final transcripts were leaving `actionCard` and `fuzzyDetections` behind, `RightPanelContent` still rendered the fuzzy hint block beside an active action card, and `ScorePanel` still showed duplicate suggestion text.

Then I updated the reducer so final transcript events clear only the turn-bound coaching surfaces while preserving score and stage objects. I also changed the sales right panel so an active `action_card` suppresses competing fuzzy hint text and passes a `suppressSuggestions` flag down to `ScorePanel`. `ScorePanel` now hides its suggestion section when asked, but still renders ordered sales dimensions and fallback dimensions exactly as before.

## Verification

Fresh task verification passed on the exact web gate from the plan. I also reran most of the slice-level backend checks so this task lands against the current arbitration contract, not just isolated frontend assumptions.

For a real-browser smoke path, I started the local backend (`:3444`) and Next dev server (`:3445`), created a real sales practice session, and loaded `/practice/{sessionId}` in the browser. The page connected, rendered the practice shell, and exposed the expected score-panel placeholder state without console or network errors. I could not keep a Playwright-side websocket capture shim alive across reloads long enough to inject synthetic `action_card` / `fuzzy_detection` payloads into the live client, so the precise precedence/reset proof remains in deterministic reducer/hook/component tests rather than a brittle browser hack.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'` | 0 | ✅ pass | 6.8s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py` | 0 | ✅ pass | 7.2s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv` | 0 | ✅ pass | 7.3s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv` | 0 | ✅ pass | 45.7s |

## Diagnostics

Future agents can inspect the finished client contract in four places:
- `web/src/hooks/websocket/message-handlers.test.ts` for transcript-driven hint reset semantics, including the empty-final-transcript edge case.
- `web/src/hooks/use-practice-websocket.test.ts` for proof that the reducer behavior survives the real hook wrapper and mocked websocket lifecycle.
- `web/src/components/practice/RightPanelContent.test.tsx` for the visible precedence rule: active `action_card` wins, stage/score context remains, competing hint text disappears.
- `web/src/components/practice/ScorePanel.test.tsx` for suppression behavior that still preserves ordered sales dimensions and fallback dimensions.

## Deviations

None beyond minor local adaptation: `ScorePanel` gained a small `suppressSuggestions` prop instead of duplicating or mutating score payloads upstream.

## Known Issues

- I did not rerun the remaining slice verification command `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown` in this unit because the context-budget warning arrived during verification wrap-up. It was green in the previous task summary, and this task does not touch backend fuzzy cooldown logic.
- Browser verification for the exact `action_card` vs `fuzzy_detection` precedence path is covered by deterministic tests, not by a live injected websocket trace; the live browser pass here is a real-shell smoke check only.

## Files Created/Modified

- `web/src/hooks/websocket/message-handlers.ts` — final transcript events now clear stale `actionCard` / `fuzzyDetections` without wiping score or stage context.
- `web/src/hooks/websocket/message-handlers.test.ts` — added transcript-reset regressions for `transcript`, `asr_transcript`, and empty-final-text edge cases.
- `web/src/hooks/use-practice-websocket.test.ts` — added a hook-level regression that runs the transcript-reset path through the websocket wrapper.
- `web/src/components/practice/RightPanelContent.tsx` — active `action_card` now suppresses competing fuzzy hint text and suppresses score suggestions while leaving stage/score context visible.
- `web/src/components/practice/RightPanelContent.test.tsx` — new focused panel precedence coverage.
- `web/src/components/practice/ScorePanel.tsx` — added suggestion suppression support without changing dimension rendering.
- `web/src/components/practice/ScorePanel.test.tsx` — added suppression coverage that still proves sales and fallback dimensions stay visible.
