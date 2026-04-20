# S01: 多轮会话稳定化与运行时状态收口 — UAT

**Milestone:** M001
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S01 is a runtime slice. The core proof comes from the three slice verification suites plus a live browser check of reconnect and end-failure visibility on the real practice page.

## Preconditions

- Backend running locally on `:3444` in development mode
  - for local StepFun realtime verification on this machine, start with proxy vars cleared:
    - `cd backend && ENVIRONMENT=development ALL_PROXY= all_proxy= HTTP_PROXY= http_proxy= HTTPS_PROXY= https_proxy= NO_PROXY=localhost,127.0.0.1 /opt/homebrew/bin/uvicorn src.main:app --reload --port 3444`
- Frontend running locally on `:3445`
  - `cd web && npm run dev`
- Use a valid login session (dev-login is sufficient in local development)
- Use a published sales agent that actually has personas; during slice-close verification, `语言的魅力` was usable while another published agent had none

## Smoke Test

Open a realtime sales practice session and confirm the practice page reaches `已连接 • 进行中 • Realtime 模式` without redirecting away from `/practice/{sessionId}`.

## Test Cases

### 1. Realtime reconnect restores the active session

1. Log into the local app and open a sales agent with personas.
2. Start a realtime practice session and wait until the practice page shows `已连接 • 进行中 • Realtime 模式`.
3. Stop the backend server.
4. Confirm the page stays on the current practice URL and shows reconnect copy such as `连接中断，正在重连...` and `网络波动，正在自动重连...`.
5. Restart the backend server with the same no-proxy local command.
6. **Expected:** the page returns to connected/in-progress state on the same session, and backend logs include `Reconnection detected for session` plus `Restored StepFun reconnect snapshot`.

### 2. End failure remains on the practice page with retryable diagnostics

1. With an active sales practice session open, click `结束练习`.
2. If the backend rejects the end request, inspect the page instead of navigating manually.
3. **Expected:** the browser remains on `/practice/{sessionId}`, the error banner shows the lifecycle failure message with trace context, and `重试结束` is visible.

### 3. Slice regression suites stay green

1. Run `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`.
2. Run `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`.
3. Run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`.
4. **Expected:** all three commands pass with no failing tests.

## Edge Cases

### Backend restart during an active realtime session

1. Let a realtime session reach `进行中`.
2. Restart the backend while the browser stays on the practice page.
3. **Expected:** the client shows reconnect state instead of jumping to report or freezing in a fake terminal state, then recovers to connected state once the backend is back.

### Zero-turn end request

1. Open a session and end it before meaningful conversation evidence exists.
2. **Expected:** if summary/report generation cannot complete, the user still stays on the practice page and gets a trace-bearing retryable failure instead of an unconditional redirect.

## Failure Signals

- Clicking `结束练习` redirects to `/report` even though the lifecycle request failed
- Practice page shows `已暂停` / `已完成` / `评分中` without matching server events
- Backend restart leaves the page stuck with no reconnect copy and no restored connected state
- Backend logs do not show `Restored StepFun reconnect snapshot` on a real reconnect cycle
- The three slice verification commands report any failed tests

## Requirements Proved By This UAT

- R001 — proves the desktop sales practice lifecycle can hold an active session through disconnect/reconnect and keep the practice page tied to authoritative runtime state
- R002 — proves runtime failures surface as reconnectable or retryable states instead of silently dumping the user out of flow

## Not Proven By This UAT

- A fully mic-driven, browser-automated two-spoken-turn session; that proof still relies on the targeted backend reconnect integration suite in this slice
- Report factual quality, shared evidence persistence, and supervisor readability; those belong to S02/S03

## Notes for Tester

Use the browser console and backend logs together. On the frontend, `[PracticeWS]` logs tell you whether reconnect is happening or the page is inventing local state. On the backend, start with `practice_session_lifecycle_transition_applied`, `Reconnection detected for session`, `Restored StepFun reconnect snapshot`, and `Server error response generated`.
