---
id: S02
parent: M002
milestone: M002
provides:
  - One shared pacing and arbitration seam across classic + StepFun sales realtime coaching, with one primary action card per turn, reconnect-safe replay suppression, and transcript-driven clearing of stale turn-bound hints on the practice page.
requires:
  - slice: S01
    provides: The canonical five-dimension sales realtime `score_update` / `stage_update` / `action_card` contract consumed by the arbiter and practice-page precedence rules.
affects:
  - S03
  - S04
  - S05
key_files:
  - backend/src/sales_bot/websocket/realtime_feedback_arbiter.py
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - web/src/hooks/websocket/message-handlers.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/components/practice/RightPanelContent.test.tsx
  - web/src/components/practice/ScorePanel.tsx
  - web/src/components/practice/ScorePanel.test.tsx
key_decisions:
  - D036
  - D037
patterns_established:
  - Realtime coaching priority must be decided once, after capability execution, by a shared arbiter that preserves fuzzy/stage/score signals as context but allows only one primary `action_card` per turn.
  - Reconnect-safe pacing state is tiny: persist the last action signature + turn number under `feedback_pacing_state`, and keep `_latest_score_snapshot` / `_latest_action_card` as read-side diagnostics only.
  - The frontend must treat `action_card` as the sole primary textual coach surface and clear turn-bound hint state on new final transcripts; otherwise backend pacing fixes still look broken to users.
observability_surfaces:
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_suppresses_duplicate_action_card_for_same_turn
  - backend/tests/unit/test_stepfun_realtime_persistence.py::test_restore_session_state_suppresses_replayed_action_card_for_same_turn
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/components/practice/RightPanelContent.test.tsx
  - persisted StepFun snapshot field `feedback_pacing_state`
drill_down_paths:
  - .gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md
duration: 45m
verification_result: passed
completed_at: 2026-03-24T20:38:55+08:00
---

# S02: 提示节奏收口与单轮唯一动作卡

**Realtime sales coaching now collapses to one primary action per turn across classic + StepFun, suppresses duplicate/replayed coach bursts, and clears stale turn-bound hints from the practice page before the next turn begins.**

## What Happened

S02 retired the second major M002 risk: the product no longer lets fuzzy detections, stage updates, score suggestions, and action cards all compete as equal coach surfaces. The slice started by adding a shared backend arbiter used after capability execution. That seam keeps the low-level fuzzy/stage/score payloads intact for context, prefers score guidance over low-severity filler detections for the primary coaching direction, and suppresses duplicate action cards only when the same signature repeats within the same turn.

With that seam in place for classic mode, StepFun was moved onto the same pacing line instead of emitting fuzzy/score/action feedback independently. The handler now runs `_run_realtime_feedback(...)` through the shared arbiter, persists only the minimum reconnect-safe pacing state under `feedback_pacing_state`, and restores replay suppression without turning `_latest_action_card` or `_latest_score_snapshot` into write-side replay inputs. T02 also had to refresh an outdated terminal-evidence test baseline that still assumed pre-S05 generic dimension keys; the current sales-rollup fallback is now the asserted contract.

The frontend then closed the visible gap that backend pacing alone could not solve. `message-handlers.ts` now clears `actionCard` and `fuzzyDetections` when a new user final transcript lands, `RightPanelContent` treats `action_card` as the only primary textual coach surface, and `ScorePanel` suppresses duplicate textual suggestions when an action card is already active while keeping stage and score context visible. That means a completed turn no longer drags old hints into the next turn, and the right panel no longer shows multiple competing instructions side by side.

The closer turn did not trust the task summaries on their own. Every slice-plan verification command was rerun fresh and passed, including the fuzzy cooldown regression that T03 had intentionally deferred. The focused diagnostic surfaces also matched the intended state: backend replay suppression, arbiter context preservation, and frontend turn-reset / precedence behavior are all pinned by explicit tests rather than broad browser symptoms.

## Verification

Fresh slice-level verification passed:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown`
- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'`

Fresh observability / diagnostic confirmation also passed:

- The arbiter diagnostic command still proves same-turn duplicate suppression and context preservation without requiring a browser reproduction.
- The StepFun replay filter still proves restore-time replay suppression instead of just happy-path emission.
- The web gate matched all four targeted files (`Test Files (4)`), so the focused practice-panel precedence coverage actually executed instead of silently skipping a missing path.

## Requirements Advanced

- R009 — S02 advanced the realtime-coaching requirement from “shared sales rubric” to “shared pacing and one-primary-action delivery”: both runtime modes now converge on the same arbitration rules, reconnect replay bursts are suppressed, and the practice page clears stale turn-bound coach state instead of visually defeating backend pacing.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The written plan gained explicit diagnostic verification commands during execution so the slice had inspectable failure-path checks for arbiter suppression and StepFun replay behavior instead of only broad suites. T02 also had to update a stale persistence expectation that still asserted generic legacy score baselines (`90/82/80`) even though the live contract already normalizes that path through sales rollups.

## Known Limitations

- S02 only proves pacing, dedupe, and single-primary-surface behavior. It does not yet unify stage progression, score delta, and action-card generation into one next-turn coaching rule; that remains S03.
- This slice does not yet prove that realtime coaching and report `main_issue` / `next_goal` stay aligned for the same session; that remains S04.
- Coach degraded / resume visibility is still open. S02 prevents replay spam and stale hints, but it does not yet distinguish “no coach because nothing is wrong” from “no coach because the coaching chain degraded”; that remains S05.
- No live multi-turn runtime UAT was required or rerun here. The slice proof remains artifact-driven by focused backend/frontend verification.

## Follow-ups

- S03 should build next-turn guidance on top of the arbiter/context boundary rather than reintroducing parallel textual heuristics in the client.
- S04 should map the surviving primary action-card direction onto report `main_issue` / `next_goal` semantics instead of adding new read-side coach fields.
- S05 should use the same pacing/reconnect seam to expose degraded vs healthy coach state explicitly.

## Files Created/Modified

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — introduced the shared backend seam for turn-level action priority, duplicate suppression, and reconnect-safe pacing state.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — routed classic sales coaching through the shared arbiter while preserving fuzzy/stage/score context messages.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — routed StepFun realtime coaching through the arbiter and persisted only minimal `feedback_pacing_state` for restore-time replay suppression.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — locked the arbiter contract around score-over-filler priority, same-turn suppression, and preserved context.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — covered shared arbiter behavior on the StepFun path, including same-turn action suppression.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — locked reconnect replay suppression and the current sales-rollup terminal-evidence fallback expectation.
- `web/src/hooks/websocket/message-handlers.ts` — cleared stale turn-bound hint state on new final transcripts.
- `web/src/hooks/websocket/message-handlers.test.ts` — covered transcript-driven hint clearing and reducer-side pacing behavior.
- `web/src/components/practice/RightPanelContent.tsx` — made `action_card` the only primary textual coach surface while leaving stage/score visible as context.
- `web/src/components/practice/RightPanelContent.test.tsx` — locked the right-panel precedence rules so competing textual coaching does not return.
- `web/src/components/practice/ScorePanel.tsx` — suppressed duplicate suggestion text when an action card is already active without hiding the scoring context.
- `web/src/components/practice/ScorePanel.test.tsx` — covered the action-card-precedence rendering behavior.
- `.gsd/REQUIREMENTS.md` — updated R009 to record the slice’s pacing / unique-action proof and remaining open work.
- `.gsd/KNOWLEDGE.md` — added the turn-reset and reconnect-state gotchas future slices are likely to hit.
- `.gsd/PROJECT.md` — refreshed the current-state doc to include shipped M002/S02 coach pacing behavior.
- `.gsd/milestones/M002/M002-ROADMAP.md` — marked S02 complete.
- `.gsd/milestones/M002/slices/S02/S02-SUMMARY.md` — recorded the slice outcome, verification, and downstream guidance.
- `.gsd/milestones/M002/slices/S02/S02-UAT.md` — captured the concrete artifact-driven UAT for this slice.

## Forward Intelligence

### What the next slice should know
- The backend now already decides “what the one primary coaching direction is” per turn. S03 should compose stage context, score delta, and next-turn rules around that seam instead of inventing a second planner in the practice page.

### What's fragile
- Replay suppression depends on both halves of the slice: minimal `feedback_pacing_state` on the backend and transcript-driven turn reset on the frontend. If either side is loosened, duplicate or stale coaching will appear again even if the other half still looks correct in isolation.

### Authoritative diagnostics
- Start with `backend/tests/unit/test_realtime_feedback_arbiter.py`, `backend/tests/unit/test_stepfun_realtime_persistence.py::test_restore_session_state_suppresses_replayed_action_card_for_same_turn`, `web/src/hooks/websocket/message-handlers.test.ts`, and `web/src/components/practice/RightPanelContent.test.tsx`. Those tests pin the exact pacing/precedence behavior S03-S05 now depend on.

### What assumptions changed
- We started with the implicit assumption that backend dedupe alone would stop coach pileups. That was false: even with correct backend pacing, stale client-side hint state can carry old coaching into the next turn and recreate the same user-visible failure. S02 had to close both the runtime seam and the panel-state seam together.
