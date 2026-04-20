---
id: T02
parent: S02
milestone: M002
provides:
  - StepFun realtime coaching now reuses the shared arbiter, suppresses same-turn replayed action cards, and restores only the pacing metadata needed to stay reconnect-safe.
key_files:
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - .gsd/milestones/M002/slices/S02/S02-PLAN.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D037 — persist a nested `feedback_pacing_state` from `RealtimeFeedbackPacingState` while keeping `_latest_score_snapshot` and `_latest_action_card` as read-side diagnostics.
patterns_established:
  - StepFun reconnect snapshots should keep read-side latest score/action diagnostics and persist only `feedback_pacing_state` for same-turn action replay suppression; the arbiter remains the single source of primary-coaching selection.
observability_surfaces:
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv`
duration: 59m
verification_result: passed
completed_at: 2026-03-24T20:14:49+0800
blocker_discovered: false
---

# T02: Wire StepFun feedback pacing and reconnect-safe arbiter state

**StepFun realtime feedback now shares the backend arbiter and restores minimal pacing state so reconnects do not replay stale action cards.**

## What Happened

I started by fixing the pre-flight gap for this slice: `S02-PLAN.md` now includes a StepFun-specific diagnostic verification command (`-k 'suppress or replay' -vv`) instead of relying only on the classic-path arbiter diagnostic.

Then I followed the TDD path for the StepFun seam. I added new handler regressions for score-over-low-severity-fuzzy arbitration and same-turn duplicate suppression, plus persistence regressions that require a reconnect snapshot to carry minimal pacing state and suppress replayed action cards after restore. I ran those tests red first and confirmed the actual failures were the expected ones: StepFun still preferred fuzzy detections over score guidance when both existed, it still emitted duplicate action cards for the same turn, and `_create_state_snapshot()` / `_restore_session_state()` still ignored pacing state entirely.

The implementation wires `StepFunRealtimeHandler._run_realtime_feedback(...)` through the shared `RealtimeFeedbackArbiter`, adds `_feedback_pacing_state` to the handler, serializes only `feedback_pacing_state` into the existing reconnect snapshot, and restores that state on reconnect. `_latest_score_snapshot` and `_latest_action_card` stay intact as read-side diagnostics. I also updated one carried-forward persistence assertion so the task-level suite matches the current sales-rollup fallback that `common/api/practice.py` already applies to legacy generic dimension keys.

## Verification

I verified the new StepFun arbitration seam in three layers:
- focused red/green tests for priority, duplicate suppression, and restore-path replay suppression
- the full T02 backend command from the task plan
- the full slice verification set, including the classic-path arbiter/capability suite, the StepFun diagnostic filter, the fuzzy cooldown regression, and the existing web slice command

All backend verification commands required for this task passed fresh. The web slice command also exited 0, but Vitest only matched the three existing files; `src/components/practice/RightPanelContent.test.tsx` is still absent and remains T03 territory.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py` | 0 | ✅ pass | 6.19s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py` | 0 | ✅ pass | 5.71s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv` | 0 | ✅ pass | 6.02s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv` | 0 | ✅ pass | 5.87s |
| 5 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown` | 0 | ✅ pass | 5.82s |
| 6 | `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'` | 0 | ✅ pass | 1.22s |

## Diagnostics

Future agents can inspect this seam in four places:
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` for `_feedback_pacing_state`, arbiter-driven `_run_realtime_feedback(...)`, and the `feedback_pacing_state` snapshot restore path.
- `backend/tests/unit/test_stepfun_realtime_handler.py` for the StepFun-side priority and same-turn suppression contract.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` for `_create_state_snapshot()` / `_restore_session_state()` expectations and replay-suppression after reconnect.
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv` for the focused failure-path check.

## Deviations

I added a StepFun-specific diagnostic verification line to `S02-PLAN.md` before implementation because the pre-flight check flagged the slice verification section as lacking an explicit failure-path check for this runtime path.

I also updated the carried-forward `test_sync_sales_realtime_terminal_evidence_uses_latest_message_score_snapshot` expectation to the existing sales-rollup fallback (`88/88/88`). The runtime code was already canonical; the old assertion was a stale pre-sales-semantics baseline.

## Known Issues

`cd web && npm test -- --run '...RightPanelContent.test.tsx'` still returns 0 even though `web/src/components/practice/RightPanelContent.test.tsx` does not exist yet, because Vitest only runs the files it actually matches. T03 still needs to add/cover that right-panel test path; this task did not touch the web side.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S02/S02-PLAN.md` — added the StepFun-specific diagnostic verification command and marked T02 done.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun now uses the shared arbiter and persists/restores minimal `feedback_pacing_state` for reconnect-safe pacing.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — added StepFun arbitration regressions for single-action priority and same-turn duplicate suppression.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — added reconnect snapshot/replay suppression coverage and updated the stale legacy score expectation to the current sales-rollup fallback.
- `.gsd/DECISIONS.md` — recorded D037 for the minimal reconnect-safe StepFun pacing snapshot choice.
- `.gsd/KNOWLEDGE.md` — recorded the Vitest missing-file verification gotcha for slice gates that pass explicit file paths.
