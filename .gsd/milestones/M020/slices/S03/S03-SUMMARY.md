---
id: S03
parent: M020
milestone: M020
provides:
  - A stable runtime authority split that S04 recovery drills can consume directly.
  - Explicit reconnect/restart/drain semantics for support and future multi-instance work.
  - Focused proof that request epoch continuity and pacing-state persistence survive reconnect without replaying stale action-card UI.
requires:
  []
affects:
  - S04
key_files:
  - backend/src/common/websocket/session_manager.py
  - backend/src/common/websocket/session_state_service.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_session_runtime_authority.py
  - backend/tests/integration/test_websocket_status_contract.py
  - backend/tests/integration/test_sales_realtime_reconnect_flow.py
  - docs/api-contract/support-runtime.md
  - docs/backup-recovery-runbook.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
key_decisions:
  - SessionManager remains the authority for instance-local live websocket visibility, while SessionStateService remains the authority for shared Redis reconnect snapshots.
  - Sales reconnect snapshots preserve current_request_id and feedback_pacing_state but intentionally exclude latest_action_card so stale coaching UI is not replayed after reconnect.
  - Support/runtime remains a release-health summary contract; websocket restart/drain reasoning must use SessionManager.get_stats() plus SessionStateService.get_stats() instead of inventing a second cluster-state API.
patterns_established:
  - Authority-bearing runtime state is split by survivability: live socket ownership stays process-local, while reconnect-safe runtime subset lives in Redis snapshots.
  - Reconnect persistence should save only minimal authority-bearing state (epoch, pacing, summary/error context) and exclude read-side UI residue.
  - Operator-facing docs should reuse existing authority surfaces and explicitly describe monitoring gaps instead of implying unshipped cluster controls.
observability_surfaces:
  - SessionManager.get_stats() -> connection_visibility/process-local tracked_sessions runtime_diagnostics
  - SessionStateService.get_stats() -> snapshot_visibility plus last_saved_snapshot/last_loaded_snapshot/last_error
  - /api/v1/support/runtime/overview and /faults -> release-health summary only, with docs pointing to the two websocket authority surfaces
drill_down_paths:
  - .gsd/milestones/M020/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M020/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M020/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-13T23:53:38.120Z
blocker_discovered: false
---

# S03: Multi-instance session state 与 reconnect authority 收口

**Closed the websocket runtime authority split by making SessionManager the instance-local live-connection surface, SessionStateService the shared Redis reconnect authority, and support/runbook surfaces explicit about restart and drain semantics.**

## What Happened

## What this slice delivered
- Wrote the websocket runtime authority table back into the code, tests, and durable docs instead of leaving multi-instance behavior implied by single-process happy paths.
- `SessionManager.get_stats()` now acts as the explicit **instance-local live connection** inspection surface: support can see tracked sessions plus per-handler `runtime_diagnostics`, but that registry is documented as process-local and non-authoritative for cluster-wide drain decisions.
- `SessionStateService.get_stats()` now acts as the explicit **shared Redis reconnect snapshot** inspection surface: restart-safe fields such as `last_saved_snapshot`, `last_loaded_snapshot`, `request_epoch`, `connection_epoch`, `last_disconnect_reason`, and `last_error` are exposed without requiring operators to inspect raw Redis payloads.
- Sales StepFun reconnect snapshots now preserve reconnect-safe runtime context (`current_request_id`, reconnect state, pacing context, score/session summary signals) while still intentionally excluding `latest_action_card`, so reconnect restores authority-bearing state without replaying stale coaching UI.
- `docs/api-contract/support-runtime.md`, `docs/backup-recovery-runbook.md`, and `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` now explain the shipped operator contract: `/api/v1/support/runtime` is a release-health summary surface, not a websocket cluster-state API; restart/drain reasoning must distinguish process-local live sockets from shared Redis snapshots.

## Authority split now established
| Concern | Authority | Visibility | Notes |
|---|---|---|---|
| Live websocket ownership / active connection count | `SessionManager` | Instance-local only | Useful for the process that currently owns the socket; not cluster truth. |
| Reconnect-safe runtime subset | `SessionStateService` Redis snapshot | Shared across instances until TTL/cleanup | Restart-safe authority for reconnect epoch, disconnect reason, and last error. |
| Request continuity across reconnect | StepFun `current_request_id` in reconnect snapshot | Shared via Redis snapshot | Survives reconnect and remains the request-epoch authority. |
| Coaching UI residue (`latest_action_card`) | Not persisted | N/A | Intentionally excluded to avoid replaying stale action cards after reconnect. |
| Feedback pacing dedupe context | StepFun `feedback_pacing_state` in reconnect snapshot | Shared via Redis snapshot | Persists enough runtime context to resume pacing safely after reconnect. |

## Operational readiness (Q8)
- **Health signal:** inspect `SessionManager.get_stats()` for `tracked_sessions[].runtime_diagnostics` on the current instance, and inspect `SessionStateService.get_stats()` for `last_saved_snapshot` / `last_loaded_snapshot` / `last_error` when judging reconnect health across restarts.
- **Failure signal:** `last_error`, `last_disconnect_reason`, missing/expired Redis snapshots, or a reconnectable session disappearing from shared snapshot state while the instance-local registry has already reset.
- **Recovery procedure:** before restart or manual drain, record both `SessionManager.get_stats()` and `SessionStateService.get_stats()`; after restart, treat an empty `SessionManager` registry as expected, then verify Redis snapshot authority and reconnect behavior before declaring recovery complete.
- **Monitoring gaps:** the repo still ships no cluster-wide live connection authority, no repo-native drain endpoint, and no ingress/LB orchestration for rolling drain; multi-instance drain still depends on external traffic steering.

## What downstream slices should assume
- S04 recovery drill work should consume the same two inspection surfaces instead of inventing a new runtime authority path.
- Future observability/admin-support work must not turn `/api/v1/support/runtime` into a second cluster-state payload; the slice intentionally kept the release-health summary separate from websocket authority inspection.
- Future reconnect changes should preserve the current rule: persist only reconnect-safe runtime state, keep request/pacing continuity, and do not replay stale action-card UI from Redis snapshots.

## Verification

- `rg -n "SessionManager|SessionStateService|snapshot|reconnect|active_connections|runtime_state" backend/src/common/websocket backend/src/sales_bot/websocket backend/src/presentation_coach/websocket` — passed, confirming the authority/snapshot/reconnect surfaces are present in the intended websocket modules.
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -x -q` — passed fresh with **11/11 tests green**; this covered process-local live connection diagnostics, Redis snapshot stats, reconnect request epoch continuity, reconnect pacing-state persistence, and terminal snapshot cleanup. Only the pre-existing pytest-cov no-data warning remained.
- `rg -n "reconnect|epoch|snapshot|active connection|drain|restart" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — passed, confirming the support contract, runbook, and architecture scan all encode the same restart/drain/runtime-authority language.
- Fresh LSP diagnostics on `backend/src/common/websocket/session_manager.py`, `backend/src/common/websocket/session_state_service.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/tests/integration/test_websocket_status_contract.py`, and `backend/tests/integration/test_sales_realtime_reconnect_flow.py` returned no diagnostics.

## Requirements Advanced

- R001 — hardens reconnect/runtime continuity semantics so multi-turn sessions are less vulnerable to restart/reconnect drift.
- R002 — adds explicit reconnect/restart/drain diagnostics and operator guidance instead of relying on implicit process-local state.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Presentation-specific reconnect code did not need a dedicated change in this slice even though the plan’s likely-touched list named `presentation_stepfun_realtime_handler.py`; the fresh verifier gap closed in the shared session authority surfaces plus the sales StepFun reconnect path. The slice also corrected stale support-runtime documentation so the shipped overview/fault contract matches the current backend surface instead of preserving an outdated schema.

## Known Limitations

The repository still has no repo-native cluster drain endpoint, no cross-instance live connection authority, and no built-in ingress/LB orchestration for rolling websocket drain. Restart-safe visibility exists only through Redis snapshots plus instance-local inspection surfaces.

## Follow-ups

- S04 should build recovery-drill automation and deployment guidance on top of the explicit SessionManager/SessionStateService authority split established here.
- Any future multi-instance runtime work should add orchestrator/LB-aware drain controls rather than teaching /api/v1/support/runtime to impersonate a cluster-state API.

## Files Created/Modified

- `backend/src/common/websocket/session_manager.py` — Made instance-local live connection visibility explicit and exposed per-session runtime diagnostics on the tracked live-session surface.
- `backend/src/common/websocket/session_state_service.py` — Exposed Redis reconnect snapshot authority via summarized last_saved/last_loaded snapshot fields, reconnect epoch signals, and last_error metrics.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Persisted feedback_pacing_state in reconnect snapshots while keeping latest_action_card excluded and surfacing stable runtime diagnostics.
- `backend/tests/unit/test_session_runtime_authority.py` — Added focused proof for SessionManager and SessionStateService authority/inspection surfaces.
- `backend/tests/integration/test_websocket_status_contract.py` — Locked the live runtime status contract for SessionManager, SessionStateService, and StepFun reconnect diagnostics.
- `backend/tests/integration/test_sales_realtime_reconnect_flow.py` — Locked reconnect request-epoch continuity, pacing-state persistence, and non-persistence of stale action-card UI.
- `docs/api-contract/support-runtime.md` — Rewrote the support-runtime contract so it matches the shipped overview/faults API and points websocket authority inspection to the correct companion surfaces.
- `docs/backup-recovery-runbook.md` — Added explicit restart/drain guidance documenting instance-local live state versus shared Redis reconnect authority and the lack of repo-native cluster drain controls.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Recorded the runtime authority table and downstream constraints for S04 and later multi-instance/runtime slices.
