---
id: T02
parent: S01
milestone: M001
provides:
  - Sales StepFun reconnect-safe snapshot recovery with terminal/timeout cleanup
key_files:
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - backend/tests/integration/test_sales_realtime_reconnect_flow.py
  - backend/tests/integration/test_websocket_status_contract.py
key_decisions:
  - D010: Sales StepFun snapshots persist only minimal recoverable runtime and explicitly clear unrecoverable upstream state on reconnect
patterns_established:
  - Handler-owned save-or-delete snapshot boundary in `finally`, with `reconnected` emitted from `BaseWebSocketHandler` and unsafe StepFun stream state reset before reuse
observability_surfaces:
  - `reconnected` events carrying restored snapshot payloads
  - `session_timeout` events enriched with `session_status` `ai_state` `turn_count` and `disconnect_reason`
  - StepFun snapshot logs: `Restored StepFun reconnect snapshot`, `Saved StepFun session snapshot`, `Deleted StepFun session snapshot`, plus existing upstream-close diagnostics
  - targeted pytest coverage for save/restore/cleanup and reconnect continuity
duration: 55m
verification_result: passed
completed_at: 2026-03-23T02:10:18+08:00
blocker_discovered: false
---

# T02: 让 Sales StepFun runtime 接通快照恢复协议

**Hooked the sales StepFun runtime back into the shared snapshot/reconnect contract so reconnect restores minimal training state, timeout/end clears dirty snapshots, and backend tests now prove turn continuity across disconnects.**

## What Happened

这次重试没有再补测试表面，而是把 `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 真正接回 `SessionStateService` / `BaseWebSocketHandler` 合约。

核心实现有四块：

1. 新增 StepFun 专属 `_create_state_snapshot()` / `_restore_session_state()` / `_save_session_state()`。
   - 只持久化 `session_status`、`ai_state`、`turn_count`，以及继续训练需要的最小 runtime 字段：`current_request_id`、最近 stage、最新评分快照、最新 action card。
   - 不再尝试序列化 StepFun 上游 websocket、active response、tool call 流、grounding 缓冲等不可安全恢复的内部状态。
   - 重连时会显式清空 `_active_response`、function call state、pending grounding / blocked response、未提交音频与 transcription 等脏中间态。

2. `handle_connection()` 现在按基类恢复协议工作。
   - 连接前先读取已有快照并判断是否为重连。
   - 连接建立后，如果命中快照则调用基类 `reconnected` 发送逻辑，把恢复快照回给前端。
   - 读取 `websocket.disconnect` 帧后会正常退出连接循环，不再靠测试超时取消任务才能落到清理逻辑。
   - `finally` 里统一执行 `_save_session_state()`，保证普通断线保存、终态/超时删除都发生在同一个出口。

3. 把活动时间和 timeout 诊断接回 `SessionManager`。
   - 收到 text / binary 帧时调用 `get_session_manager().update_activity()`，不再让 StepFun runtime 游离于 session timeout 跟踪之外。
   - 覆盖 `send_message()`，当 `SessionManager` 下发 `session_timeout` 时自动补齐 `session_status`、`ai_state`、`turn_count`、`disconnect_reason=session_timeout`，并标记当前断线需要删除快照。

4. 让终态快照清理和重连连续性变成可证事实。
   - `scoring` / `completed` / timeout 断开都会删除旧快照，避免终态后残留可误恢复状态。
   - 断线前后 `turn_count`、`session_status`、`ai_state` 和最新 scoring/action card 会连续恢复，第三轮可以在重连后继续。

## Verification

Passed:
- `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
  - 13 tests passed
  - 覆盖最小快照 save/restore、`reconnected`、timeout 诊断、terminal cleanup、两轮后断开重连继续第三轮、结束后 `scoring` + 快照删除
- `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`
  - 18 selected tests passed
  - 证明 T02 没把 T01 的统一终态写入口回归打坏
- `cd web && npx vitest --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - 3 files / 27 tests passed

Slice-plan exact web command status:
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - still fails before running tests because the package script already injects `--run`, so the exact command becomes duplicated `--run --run ...`
  - this is the same command-shape issue already observed in T01, not a T02 regression

## Diagnostics

- Reconnect path:
  - inspect `reconnected` payloads from the sales websocket; `data.restored_state` now includes `session_status` / `ai_state` / `turn_count` / minimal `runtime_state`
- Timeout path:
  - inspect `session_timeout` payloads; `data.disconnect_reason` should be `session_timeout` and include `session_status` / `ai_state` / `turn_count`
- Snapshot lifecycle logs in `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`:
  - `Restored StepFun reconnect snapshot`
  - `Saved StepFun session snapshot`
  - `Deleted StepFun session snapshot`
- Upstream close diagnostics still land in:
  - `upstream_disconnect_diagnostics`
  - `StepFun upstream closed`
- Fast regression tests:
  - `backend/tests/unit/test_stepfun_realtime_persistence.py`
  - `backend/tests/integration/test_sales_realtime_reconnect_flow.py::test_sales_stepfun_reconnect_restores_turn_continuity_and_cleans_terminal_snapshot`
  - `backend/tests/integration/test_websocket_status_contract.py::test_stepfun_handler_session_timeout_event_includes_restore_context`

## Deviations

- None.

## Known Issues

- The slice-plan web verification command is still malformed when routed through `npm test -- --run ...`; use the direct `npx vitest --run ...` form until T03 or a follow-up normalizes the package-script entrypoint.

## Files Created/Modified

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — added minimal reconnect snapshot save/restore/delete behavior, SessionManager activity updates, timeout diagnostics enrichment, disconnect-frame handling, and final cleanup persistence.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — verifies StepFun minimal snapshot contents, reconnect restore/reset behavior, terminal cleanup, and timeout event diagnostics.
- `backend/tests/integration/test_sales_realtime_reconnect_flow.py` — proves start → two turns → disconnect → reconnect → continue → end keeps turn continuity and clears terminal snapshot.
- `backend/tests/integration/test_websocket_status_contract.py` — locks the timeout/status/error websocket contract for the StepFun handler.
- `.gsd/DECISIONS.md` — recorded D010 for the minimal-recoverable StepFun snapshot boundary.
