---
id: T01
parent: S03
milestone: M020
key_files:
  - backend/src/common/websocket/session_manager.py
  - backend/src/common/websocket/session_state_service.py
  - backend/tests/unit/test_session_runtime_authority.py
  - backend/tests/integration/test_sales_realtime_reconnect_flow.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - Runtime connection visibility remains process-local authority in `SessionManager`, while reconnect-safe snapshots remain Redis authority in `SessionStateService`.
  - Sales reconnect snapshots preserve `current_request_id` continuity but intentionally exclude `latest_action_card` to avoid replaying stale coaching UI after reconnect.
duration: 
verification_result: passed
completed_at: 2026-04-13T15:55:31.550Z
blocker_discovered: false
---

# T01: Documented websocket runtime authority boundaries and added reconnect-focused proofs for process-local connections versus Redis snapshots.

**Documented websocket runtime authority boundaries and added reconnect-focused proofs for process-local connections versus Redis snapshots.**

## What Happened

I audited the current websocket runtime ownership split across `SessionManager`, `SessionStateService`, and the sales/presentation reconnect handlers, then wrote the missing authority baseline into both code and architecture docs. `SessionManager.get_stats()` now exposes that live connection visibility is a process-local in-memory registry, while `SessionStateService.get_stats()` now exposes Redis snapshot authority, save/get/delete/healthcheck metrics, and the latest snapshot error surface for downstream support/runtime consumers. I added a focused unit test file to lock those inspection surfaces and updated the sales reconnect integration proof to assert the real reconnect contract: `current_request_id` survives reconnect as the current request epoch, but `latest_action_card` is intentionally not persisted so stale coaching UI is not replayed after reconnect. I also appended the non-obvious reconnect rule to `.gsd/KNOWLEDGE.md` and recorded the authority-boundary decision in `.gsd/DECISIONS.md`.

## Verification

Verified the new authority surfaces and reconnect contract with focused pytest coverage and the task-plan grep inventory. The authority tests proved `SessionManager` reports process-local connection ownership and `SessionStateService` reports Redis snapshot ownership plus operation metrics/last-error state. The reconnect integration test proved persisted/restored runtime state keeps `current_request_id` continuity while omitting `latest_action_card`. The task-plan `rg` command also confirmed the relevant authority/snapshot/reconnect symbols are now visible across the intended websocket modules.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_runtime_authority.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -q` | 0 | ✅ pass | 47000ms |
| 2 | `rg -n "SessionManager|SessionStateService|snapshot|reconnect|active_connections|runtime_state" backend/src/common/websocket backend/src/sales_bot/websocket backend/src/presentation_coach/websocket` | 0 | ✅ pass | 54300ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_persistence.py backend/tests/unit/test_presentation_handler_persistence.py backend/tests/unit/test_session_runtime_authority.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -q` | 0 | ✅ pass | 29200ms |

## Deviations

Adjusted the sales reconnect integration proof to stop expecting `latest_action_card` inside persisted `runtime_state`. The existing handler code already intentionally suppressed stale action-card replay; the test contract was older than the shipped reconnect-safe behavior.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/websocket/session_manager.py`
- `backend/src/common/websocket/session_state_service.py`
- `backend/tests/unit/test_session_runtime_authority.py`
- `backend/tests/integration/test_sales_realtime_reconnect_flow.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
