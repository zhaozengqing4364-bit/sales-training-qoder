---
id: T02
parent: S03
milestone: M003
key_files:
  - backend/src/sales_bot/websocket/components/objection_ledger_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - backend/tests/unit/test_capability_processor.py
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Persist reconnect-safe unresolved-objection state as objection_ledger plus feedback_pacing_state, and stop relying on replaying the last action-card payload after reconnect.
  - Use one shared objection-ledger helper for both StepFun and classic capability-composition paths so topic-drift pressure, closure heuristics, and arbiter overrides stay on one contract.
duration: ""
verification_result: passed
completed_at: 2026-03-25T04:06:02.560Z
blocker_discovered: false
---

# T02: Carried unresolved objection pressure through classic and StepFun runtime turns with reconnect-safe snapshot recovery.

**Carried unresolved objection pressure through classic and StepFun runtime turns with reconnect-safe snapshot recovery.**

## What Happened

I followed a test-first pass around the two live coaching paths. On the StepFun path, I added a shared unresolved-objection ledger helper that normalizes one active objection family, recognizes explicit gap acknowledgment versus proof delivery, and synthesizes arbiter-only stage/score context so later turns keep pressing the same business gap even when the raw score payload drifts to another weak dimension. `StepFunRealtimeHandler._run_realtime_feedback(...)` now resolves and persists that ledger on each turn, feeds the override into the existing `RealtimeFeedbackArbiter`, and logs ledger transitions for later debugging. I also tightened StepFun reconnect recovery so `_create_state_snapshot()` persists the normalized objection ledger plus `feedback_pacing_state`, but no longer relies on replaying `_latest_action_card`; `_restore_session_state()` rehydrates ledger+pacing while clearing transient card state, which keeps same-turn reconnects from bursting stale coaching cards back into the UI.

On the classic/enhanced path, I wired the same helper into `CapabilityProcessor.run_and_send_feedback(...)` so the capability-composed runtime uses the identical ledger and arbiter override logic instead of drifting onto a separate implementation. I added focused regression coverage for classic topic drift plus new StepFun tests covering: open-ledger follow-up pressure during topic drift, ledger closure when the seller explicitly acknowledges the missing proof, snapshot exclusion of transient action-card state, and reconnect suppression of same-turn stale pressure. I recorded the reconnect-state decision in `.gsd/DECISIONS.md` because downstream work on T03 and later slices now depends on the rule that objection ledger + pacing signature are the durable runtime facts, not the last action-card payload.

## Verification

Ran the task-plan backend verification command with timing evidence: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`, which passed all 68 tests covering StepFun runtime feedback, objection-ledger carry-forward, reconnect snapshot recovery, and persistence behavior. Because this task also changed the classic capability-composition path, I ran an extra focused regression: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_capability_processor.py`, which passed all 7 tests, including the new classic-path topic-drift objection-ledger case.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py` | 0 | ✅ pass | 7890ms |
| 2 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_capability_processor.py` | 0 | ✅ pass | 7350ms |


## Deviations

Added `backend/src/sales_bot/websocket/components/objection_ledger_helpers.py` plus `backend/tests/unit/test_capability_processor.py` coverage beyond the four-file planner snapshot so both runtime paths could share one ledger/update heuristic instead of duplicating logic in the handler and capability processor.

## Known Issues

None.

## Files Created/Modified

- `backend/src/sales_bot/websocket/components/objection_ledger_helpers.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`
- `backend/tests/unit/test_capability_processor.py`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
