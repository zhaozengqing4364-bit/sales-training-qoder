# S03: Multi-instance session state 与 reconnect authority 收口 — UAT

**Milestone:** M020
**Written:** 2026-04-13T23:53:38.121Z

# S03 UAT — multi-instance runtime authority / reconnect / restart semantics

## Preconditions
- Backend is running against a reachable Redis instance.
- A support/admin operator can inspect `/api/v1/support/runtime/*` and can run a Python shell or admin debug command against the backend process to call `get_session_manager().get_stats()` and `get_session_state_service().get_stats()`.
- A sales practice session can connect through the StepFun websocket flow.

## Test Case 1 — Live connection visibility stays instance-local
1. Start a fresh sales practice session and keep the websocket connected on one backend instance.
   - **Expected:** the learner session becomes active normally.
2. On that same backend instance, inspect `get_session_manager().get_stats()`.
   - **Expected:** `connection_visibility.scope` is `process_local`; `tracked_sessions` includes the active session; `runtime_diagnostics` includes `session_status`, `ai_state`, `current_request_id`, and `reconnect_state` fields.
3. Check `/api/v1/support/runtime/overview` and `/api/v1/support/runtime/faults?severity=high`.
   - **Expected:** the route returns release-health/fault summary data only; it does not claim to be a cluster-wide websocket state API or expose cluster-wide active-connection truth.

## Test Case 2 — Reconnect restores request/pacing authority but not stale UI residue
1. With the active sales session running, capture the current `current_request_id` and any visible realtime coaching state.
   - **Expected:** a non-zero request epoch is visible once the session is actively exchanging realtime events.
2. Force a transient disconnect (for example by dropping the websocket/tab/network briefly) and reconnect within the Redis TTL window.
   - **Expected:** the session reconnects rather than starting from a blank runtime.
3. Inspect `get_session_state_service().get_stats()` after reconnect.
   - **Expected:** `last_loaded_snapshot` / `last_saved_snapshot` show the reconnect-safe fields, including request epoch / connection epoch and no fatal `last_error`.
4. Verify the restored StepFun runtime state.
   - **Expected:** `current_request_id` continuity is preserved; pacing/dedupe context (`feedback_pacing_state`) is still available; `latest_action_card` is not replayed from Redis snapshot state.

## Test Case 3 — Restart semantics remain truthful
1. While a reconnectable sales session exists, record both `get_session_manager().get_stats()` and `get_session_state_service().get_stats()`.
   - **Expected:** the first shows instance-local live tracking; the second shows shared reconnect snapshot metadata.
2. Restart the backend instance without clearing Redis.
   - **Expected:** the process restarts successfully.
3. Inspect both surfaces again before the learner reconnects.
   - **Expected:** `SessionManager` live registry is empty on the new process; `SessionStateService` still explains the reconnect-safe snapshot state until TTL expiry or cleanup.
4. Let the learner reconnect.
   - **Expected:** reconnect uses the shared snapshot authority rather than any preserved live socket state from the old process.

## Test Case 4 — Drain guidance does not overclaim cluster support
1. Read the runtime authority sections in `docs/api-contract/support-runtime.md` and `docs/backup-recovery-runbook.md`.
   - **Expected:** both documents explicitly distinguish instance-local live connections from shared Redis snapshots.
2. Confirm the documented multi-instance caveat.
   - **Expected:** the docs state that the repo does **not** ship a cluster-wide live-connection authority or repo-native drain endpoint, and that real rolling drain still depends on external ingress/LB/systemd orchestration.

## Edge Cases
- If Redis is unavailable during reconnect, `SessionStateService.get_stats()` should expose a meaningful `last_error`; operators must treat reconnect authority as degraded instead of inferring truth from an empty `SessionManager` registry.
- If one instance reports `total_sessions=0`, do **not** treat that as proof the whole cluster drained; the UAT only passes if operators preserve the instance-local/shared-snapshot distinction.
- If a focused reconnect check sees `latest_action_card` replayed after reconnect, fail the UAT: that indicates stale UI residue leaked into persisted snapshot state.
