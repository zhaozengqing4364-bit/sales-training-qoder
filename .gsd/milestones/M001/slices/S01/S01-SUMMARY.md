---
id: S01
parent: M001
milestone: M001
provides:
  - Unified server-authoritative sales session lifecycle, reconnect recovery, and on-page terminal failure handling for desktop practice
requires: []
affects:
  - S02
  - S04
key_files:
  - backend/src/common/api/practice.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/websocket/message-handlers.ts
  - backend/tests/integration/test_session_lifecycle_api.py
  - backend/tests/integration/test_sales_realtime_reconnect_flow.py
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
key_decisions:
  - D009
  - D010
  - D011
patterns_established:
  - REST lifecycle end and legacy DELETE both delegate to one terminal executor, while each route keeps its own response shape
  - Sales StepFun reconnect restores only the minimal safe runtime snapshot and explicitly clears unrecoverable upstream stream state before reuse
  - Practice-page lifecycle UI trusts only server status/reconnected/session_ended events; local code only clears transient audio state and exposes retryable end failures
observability_surfaces:
  - practice_session_lifecycle_transition_applied / practice_session_terminal_connection_close structured logs
  - sales websocket status / reconnected / session_timeout / session_ended payloads plus browser-side [PracticeWS] reconnect logs
  - training-page error banner with trace-bearing lifecycle failure text and 重试结束 action
  - slice verification commands and targeted backend/frontend regression suites
  - backend highlights showing Reconnection detected for session and Restored StepFun reconnect snapshot
  - backend server error logs with error_code and trace_id on failed lifecycle end
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
duration: 3h50m
verification_result: passed
completed_at: 2026-03-23T02:46:24+08:00
---

# S01: 多轮会话稳定化与运行时状态收口

**Unified the sales practice lifecycle around one backend terminal path, reattached StepFun sessions to reconnect-safe runtime snapshots, and made the training page trust only server lifecycle signals with visible retryable failures instead of optimistic report jumps.**

## What Happened

S01 first removed backend lifecycle split-brain. `POST /practice/sessions/{id}/lifecycle` end and the legacy `DELETE /practice/sessions/{id}` path now share one terminal executor in `backend/src/common/api/practice.py`, so sales/presentation terminal writes, report trigger, live handler sync, and terminal close all run through the same authority path. That gave the slice one place to reason about terminal state and one log surface to inspect when end behavior drifts.

With terminal writes unified, the sales StepFun websocket path was pulled back into the shared `SessionStateService` contract. `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` now saves only a minimal recoverable snapshot (`session_status`, `ai_state`, `turn_count`, plus the latest safe runtime crumbs), restores that snapshot on reconnect, emits the base `reconnected` flow, and deletes dirty snapshots on timeout or terminal cleanup. The handler now updates `SessionManager` activity and enriches timeout diagnostics with restore context instead of silently dropping the runtime state.

On the frontend, the practice page stopped pretending lifecycle transitions had already happened. `use-practice-session-lifecycle.ts`, `use-practice-websocket.ts`, and `message-handlers.ts` were tightened so pause/resume/end UI follows server `status` / `reconnected` / `session_ended` events, not local guesses. End requests now keep the user on `/practice/{sessionId}` when the server rejects termination, surface a retryable error with trace context, and only navigate to `/report` after the session is confirmed terminal by server state.

Fresh slice-close runtime verification also exercised the observability surfaces directly. In a local realtime sales session, stopping the backend produced the expected reconnect UI (`连接中断，正在重连...`, `网络波动，正在自动重连...`). Restarting the backend brought the page back to `已连接 • 进行中`, and backend logs showed `Reconnection detected for session` plus `Restored StepFun reconnect snapshot` with the recovered `session_status` / `ai_state`. Triggering `结束练习` on a zero-turn realtime session produced a backend 500 with `[SUMMARY_GENERATION_FAILED]`; the frontend stayed on the training page, showed `总结生成失败 (...)` with `重试结束`, and did not redirect to the report page.

## Verification

Passed fresh slice-plan verification commands:

- `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`
  - 18 selected tests passed
  - proved unified lifecycle end/DELETE behavior, idempotent terminal writes, report trigger, and live handler sync/close
- `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
  - 13 tests passed
  - proved minimal snapshot save/restore/delete, reconnect continuity, timeout/status diagnostics, and terminal cleanup
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - 3 files / 30 tests passed
  - proved server-only lifecycle state, paused audio gating, reconnect restoration, and end-failure-on-page behavior

Passed live runtime / observability checks against the local app:

- Dev login into the real web app and created a realtime sales session on a published agent with personas
- Confirmed steady-state runtime UI: `已连接 • 进行中 • Realtime 模式` and the connected prompt surfaced on `/practice/{sessionId}`
- Killed the backend and confirmed the page stayed on the practice view while exposing reconnect copy: `连接中断，正在重连...` and `网络波动，正在自动重连...`
- Restarted the backend and confirmed the same session recovered to connected state; backend highlights showed `Reconnection detected for session` and `Restored StepFun reconnect snapshot`
- Triggered an end failure and confirmed the page remained on `/practice/{sessionId}` with `总结生成失败` + `重试结束`; backend logged the corresponding server error response with `error_code` and `trace_id`

## Requirements Advanced

- none

## Requirements Validated

- R001 — backend lifecycle/reconnect suites plus live browser reconnect verification now prove the desktop sales session can survive disconnect/reconnect without dropping the authoritative runtime state surface.
- R002 — disconnects and end failures now stay visible and recoverable: websocket reconnect copy, timeout/reconnect diagnostics, trace-bearing lifecycle errors, and on-page retry behavior are all exercised by fresh tests and live runtime checks.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

Live realtime browser verification required starting the local backend with proxy variables cleared. Without that host-level runtime environment, websocket startup produced misleading 1006 loops unrelated to the slice code. No repository code change was needed for that workaround.

## Known Limitations

- Browser automation in this slice-close pass did not produce two spoken turns; the exact “two rounds then continue” proof still relies on the targeted backend reconnect integration test rather than a mic-driven browser loop.
- Ending a zero-turn realtime session can still raise `[SUMMARY_GENERATION_FAILED]`. S01 now exposes that failure cleanly and keeps the user on the training page, but it does not yet define the downstream report/data behavior for empty-evidence sessions.

## Follow-ups

- S02 should define how zero-turn or partially recovered sessions are persisted and reported so terminal lifecycle success does not depend on summary generation being able to infer enough evidence.
- Future live-runtime slices that require proof of spoken multi-turn continuity should use a repeatable audio-input harness; browser-only click automation is enough for lifecycle/failure proof but not for conversation-depth proof.

## Files Created/Modified

- `backend/src/common/api/practice.py` — unified lifecycle terminal writes, report trigger behavior, live handler sync/close, and structured lifecycle logging.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — added minimal snapshot save/restore/delete behavior, reconnect recovery, timeout diagnostics enrichment, and final cleanup persistence.
- `backend/tests/integration/test_session_lifecycle_api.py` — locked shared end-path behavior, idempotency, and terminal logging context.
- `backend/tests/contract/test_sessions.py` — locked lifecycle/delete contract semantics for sales/presentation terminal states.
- `backend/tests/integration/test_session_flow.py` — covered end/delete flow sequencing and idempotent terminal re-entry.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — covered minimal StepFun snapshot contents, restore behavior, timeout enrichment, and cleanup deletion.
- `backend/tests/integration/test_sales_realtime_reconnect_flow.py` — proved two-turn disconnect/reconnect continuity and terminal snapshot cleanup.
- `backend/tests/integration/test_websocket_status_contract.py` — locked websocket status/error/timeout payload shape, including restore context.
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` — removed unconditional report navigation and added explicit end-failure state.
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — surfaced lifecycle errors in the practice-page banner with retry-end affordance.
- `web/src/hooks/use-practice-websocket.ts` — removed optimistic lifecycle mutations from control sends and kept only client-owned audio cleanup.
- `web/src/hooks/websocket/message-handlers.ts` — reconciled transient runtime flags from server status/reconnected/session_ended events.
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts` — covered terminal-only redirect timing and failed-end staying on-page.
- `web/src/hooks/use-practice-websocket.test.ts` — covered pause gating and reconnect recovery semantics.
- `web/src/hooks/websocket/message-handlers.test.ts` — covered paused cleanup and reconnected runtime restoration.
- `web/package.json` — normalized the Vitest script so the slice-plan verification command runs as written.
- `.gsd/REQUIREMENTS.md` — moved R001 and R002 from active to validated.
- `.gsd/milestones/M001/M001-ROADMAP.md` — marked S01 complete.
- `.gsd/PROJECT.md` — refreshed current-state notes after S01 runtime stabilization.
- `.gsd/STATE.md` — advanced the active slice/state snapshot to post-S01 handoff.

## Forward Intelligence

### What the next slice should know
- The trustworthy lifecycle chain is now: REST terminal write → shared backend logs → websocket status/reconnected/session_ended → practice-page lifecycle UI. If S02 sees drift, debug in that order instead of starting from the report page.
- Local realtime browser verification is sensitive to host runtime environment. If StepFun starts looping with 1006 before session state moves, inspect the backend process environment before assuming a reconnect regression.

### What's fragile
- Zero-turn terminal sessions — they now fail visibly instead of silently redirecting, but the data/report side still treats “no usable evidence” as a hard failure.
- Agent catalog quality on local data — at least one published sales agent had no usable personas, so runtime UAT should start from an agent/persona pair already known to be trainable.

### Authoritative diagnostics
- Browser console `[PracticeWS]` logs plus the practice-page banner — quickest view of whether the page is following server lifecycle or inventing local state.
- Backend highlights `practice_session_lifecycle_transition_applied`, `Reconnection detected for session`, `Restored StepFun reconnect snapshot`, and `Server error response generated` — the most reliable backend signals for lifecycle, reconnect, and terminal failure correlation.

### What assumptions changed
- “Repeated 1006 closes mean the slice reconnect code is still broken” — in local runtime this turned out to be false; once the backend ran without the interfering proxy environment, the same session recovered and the reconnect snapshot path behaved as designed.
