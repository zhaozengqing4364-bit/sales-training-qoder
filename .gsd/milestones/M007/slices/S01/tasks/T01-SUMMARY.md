---
id: T01
parent: S01
milestone: M007
provides: []
requires: []
affects: []
key_files: ["backend/src/sales_bot/websocket/stepfun_realtime_handler.py", "backend/src/sales_bot/websocket/enhanced_handler.py", "backend/tests/unit/test_stepfun_realtime_persistence.py", "backend/tests/unit/test_enhanced_handler_coach_health.py", "web/src/hooks/websocket/message-handlers.test.ts", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Emit `reconnected.restored_state` from a freshly rebuilt handler snapshot instead of echoing the raw persisted snapshot.", "Rehydrate `session_id` and `user_id` onto the live handler before rebuilding reconnect snapshots so emitted restore payloads stay aligned with runtime truth."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the focused reconnect and diagnostics suite from repo root. `backend/tests/unit/test_enhanced_handler_coach_health.py` passed with classic reconnect parity and malformed-payload coverage. `backend/tests/unit/test_stepfun_realtime_persistence.py -k "restore_session_state"` passed with normalized reconnect emission, omission-after-recovery, and stale-action-card suppression coverage. `backend/tests/integration/test_voice_runtime_session_snapshot.py -k "live_coach_health"` passed, confirming `/api/v1/practice/sessions/{id}/knowledge-check` still surfaces the expected live degraded coach-health diagnostics. The reducer suite passed with the corrected repo-root filter path `src/hooks/websocket/message-handlers.test.ts`, including malformed reconnect normalization and omitted-after-recovery behavior."
completed_at: 2026-03-28T03:18:34.336Z
blocker_discovered: false
---

# T01: Reconnect now emits normalized coach-health state from the live handler instead of replaying stale raw snapshots.

> Reconnect now emits normalized coach-health state from the live handler instead of replaying stale raw snapshots.

## What Happened
---
id: T01
parent: S01
milestone: M007
key_files:
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/sales_bot/websocket/enhanced_handler.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - backend/tests/unit/test_enhanced_handler_coach_health.py
  - web/src/hooks/websocket/message-handlers.test.ts
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Emit `reconnected.restored_state` from a freshly rebuilt handler snapshot instead of echoing the raw persisted snapshot.
  - Rehydrate `session_id` and `user_id` onto the live handler before rebuilding reconnect snapshots so emitted restore payloads stay aligned with runtime truth.
duration: ""
verification_result: passed
completed_at: 2026-03-28T03:18:34.337Z
blocker_discovered: false
---

# T01: Reconnect now emits normalized coach-health state from the live handler instead of replaying stale raw snapshots.

**Reconnect now emits normalized coach-health state from the live handler instead of replaying stale raw snapshots.**

## What Happened

I verified the interrupted reconnect implementation against the current contract and found the remaining mismatch in the emission path: both StepFun and classic handlers restored coach-health internally, but the `reconnected` payload still echoed the raw persisted snapshot back to the frontend. I added failing restore tests that proved stale `latest_action_card` / legacy score snapshot data and malformed `coach_health` values could survive in the emitted payload even after the live handler had normalized them. I then updated both handlers to rehydrate identifiers during restore and emit `_send_reconnection_success(...)` with a freshly rebuilt `_create_state_snapshot()` from the live handler state. After that, I extended focused backend and reducer tests to cover malformed restore payloads, omission-after-recovery, and classic/StepFun parity, and reran the focused reconnect plus diagnostics suite successfully.

## Verification

Ran the focused reconnect and diagnostics suite from repo root. `backend/tests/unit/test_enhanced_handler_coach_health.py` passed with classic reconnect parity and malformed-payload coverage. `backend/tests/unit/test_stepfun_realtime_persistence.py -k "restore_session_state"` passed with normalized reconnect emission, omission-after-recovery, and stale-action-card suppression coverage. `backend/tests/integration/test_voice_runtime_session_snapshot.py -k "live_coach_health"` passed, confirming `/api/v1/practice/sessions/{id}/knowledge-check` still surfaces the expected live degraded coach-health diagnostics. The reducer suite passed with the corrected repo-root filter path `src/hooks/websocket/message-handlers.test.ts`, including malformed reconnect normalization and omitted-after-recovery behavior.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py` | 0 | ✅ pass | 4000ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_persistence.py -k "restore_session_state"` | 0 | ✅ pass | 11100ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py -k "live_coach_health"` | 0 | ✅ pass | 7300ms |
| 4 | `npm test -- --run 'src/hooks/websocket/message-handlers.test.ts'` | 0 | ✅ pass | 4500ms |


## Deviations

Planned repo-root web verification used `web/src/...`, but the repository root `npm test` shim already runs inside `web/`; I ran the equivalent working command with `src/hooks/websocket/message-handlers.test.ts` so the focused reducer suite actually executed.

## Known Issues

None.

## Files Created/Modified

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/enhanced_handler.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`
- `backend/tests/unit/test_enhanced_handler_coach_health.py`
- `web/src/hooks/websocket/message-handlers.test.ts`
- `.gsd/KNOWLEDGE.md`


## Deviations
Planned repo-root web verification used `web/src/...`, but the repository root `npm test` shim already runs inside `web/`; I ran the equivalent working command with `src/hooks/websocket/message-handlers.test.ts` so the focused reducer suite actually executed.

## Known Issues
None.
