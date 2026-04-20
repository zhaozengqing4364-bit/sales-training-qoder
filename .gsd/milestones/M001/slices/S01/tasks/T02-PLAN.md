---
estimated_steps: 4
estimated_files: 6
---

# T02: 让 Sales StepFun runtime 接通快照恢复协议

**Slice:** S01 — 多轮会话稳定化与运行时状态收口
**Milestone:** M001

## Description

把 sales StepFun handler 接回现有 `SessionStateService` + `BaseWebSocketHandler` 恢复协议，只恢复最小可继续会话状态，而不是重建整个上游连接对象。这个任务的目标是证明 sales 主链路在断开 / 重连后不会丢 `session_status`、`ai_state`、`turn_count`，并且终态后能清干净脏快照，让“第二轮就坏”和“重连后 UI 乱掉”有明确的后端修复边界。

## Steps

1. 在 `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 为 sales runtime 实现最小快照创建 / 保存 / 恢复边界，覆盖 `session_status`、`ai_state`、`turn_count` 与继续训练所需的最小运行时字段，但不要序列化 StepFun 上游连接内部状态。
2. 复用 `BaseWebSocketHandler` 的 `reconnected` 发送逻辑，并把活动时间、断线保存、终态删除、超时 / 上游关闭诊断与 `SessionManager` 对齐。
3. 新增 `backend/tests/unit/test_stepfun_realtime_persistence.py`，参考 presentation persistence 测试补齐 save / restore / terminal cleanup / `reconnected` 事件断言；再新增 `backend/tests/integration/test_sales_realtime_reconnect_flow.py` 覆盖开始→两轮→断开→重连→继续→结束的集成链路。
4. 运行针对性 pytest，修正 turn continuity、terminal cleanup、timeout / reconnect 诊断字段，直到 sales runtime 恢复合约稳定。

## Must-Haves

- [ ] sales StepFun 重连后会发出 `reconnected`，并恢复 `session_status`、`ai_state`、`turn_count` 与用户可继续训练的最小状态。
- [ ] 终态或超时后不会残留可误恢复的脏快照，且上游关闭 / 超时原因能通过事件或日志定位，而不是静默丢失。

## Verification

- `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
- 检查集成测试明确断言断线前后的 `turn_count` 连续、`reconnected` 恢复字段完整、结束后 `session_status == "scoring"` 且快照被清理。

## Observability Impact

- Signals added/changed: `reconnected` 恢复事件、timeout / upstream close 诊断字段、terminal snapshot cleanup 日志。
- How a future agent inspects this: 通过新增 unit / integration tests、`status` / `reconnected` / `session_timeout` 事件，以及 StepFun handler 日志判断恢复在哪一步失效。
- Failure state exposed: 恢复失败时能够看到是快照缺字段、turn 连续性断裂、终态未清理，还是上游关闭导致的不可恢复中断。

## Inputs

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 当前 sales runtime 自己管理连接循环，但没有接入基类快照恢复。
- `backend/src/common/websocket/base_handler.py` — 现有 `_save_session_state()`、`_restore_session_state()`、`_send_reconnection_success()` 合约。
- `backend/src/common/websocket/session_manager.py` — 统一 activity / heartbeat / timeout 管理。
- `backend/tests/unit/test_presentation_handler_persistence.py` — presentation 已验证的恢复测试形状，可作为 sales 对照样板。
- `T01` 产出 — 统一终态收口后，sales runtime 的 terminal cleanup 才有稳定后端基线。

## Expected Output

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 接通快照恢复与终态清理的 sales runtime。
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — save / restore / `reconnected` / terminal cleanup 单元覆盖。
- `backend/tests/integration/test_sales_realtime_reconnect_flow.py` — 多轮 + 断线重连 + 结束的后端集成证明。
