# S01: 多轮会话稳定化与运行时状态收口

**Goal:** 把销售训练多轮会话的生命周期、重连恢复和结束阶段收口到同一权威状态面，让桌面端可以稳定完成开始→多轮→断开/重连→结束。
**Demo:** 在真实销售训练页上，会话开始后至少完成两轮来回；断线后前端收到 `reconnected` 并继续训练；结束仅在服务端确认进入终态后跳转报告页，失败时留在训练页并显示可重试错误。
**Requirements:** Owns `R001`, `R002`.

## Must-Haves

- 销售训练生命周期以 `SessionLifecycleService` + `POST /practice/sessions/{id}/lifecycle` 为唯一权威写入口；保留旧 `DELETE /practice/sessions/{id}` 时也必须委托同一结束实现，不再分叉副作用。
- Sales StepFun WebSocket 复用 `SessionStateService` + `reconnected` 协议，至少恢复 `session_status`、`ai_state`、`turn_count` 与可继续训练所需的最小运行时状态。
- 训练页不再靠本地乐观状态伪造暂停 / 恢复 / 结束结果；结束失败必须留在当前页并暴露可诊断错误，而不是无条件跳报告页。
- 自动化验证覆盖开始→至少两轮→暂停/恢复→断开→重连→结束，以及关键失败信号（超时 / 结束失败 / 终态清理）。

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`
- `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
- `cd web && npm test -- --run src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`

## Observability / Diagnostics

- Runtime signals: 统一 lifecycle transition 日志、sales websocket `status` / `reconnected` / `session_timeout` / `session_ended` 事件、前端结束失败错误态。
- Inspection surfaces: `/api/v1/practice/sessions/{id}/lifecycle` 响应、WebSocket 事件负载、训练页错误提示与重连入口、针对性 pytest / vitest。
- Failure visibility: `session_status` / `ai_state` / `turn_count`、重连恢复结果、上游关闭 / 超时原因、结束失败后留在训练页的错误消息。
- Redaction constraints: 仅暴露 trace_id、session_id 和非敏感运行时状态；不得记录 token、音频原始 payload 或密钥。

## Integration Closure

- Upstream surfaces consumed: `backend/src/common/db/session_lifecycle.py`, `backend/src/common/api/practice.py`, `backend/src/common/websocket/base_handler.py`, `backend/src/common/websocket/session_state_service.py`, `backend/src/common/websocket/session_manager.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/websocket/message-handlers.ts`, `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`.
- New wiring introduced in this slice: 后端统一结束 helper、sales StepFun 快照恢复 + `reconnected` 发射、前端报告跳转门禁改为服务端终态确认。
- What remains before the milestone is truly usable end-to-end: S02 仍需把训练事实稳定落库并统一报告事实源；S01 只负责把运行时状态面和失败面收口。

## Tasks

- [x] **T01: 收口会话结束与生命周期单写入口** `est:2h`
  - Why: 结束逻辑当前同时存在于 lifecycle POST、旧 DELETE 兼容路由和 sales runtime 清理里；不先把终态副作用收成一条线，第二轮异常和报告跳转问题会继续换症状出现。
  - Files: `backend/src/common/api/practice.py`, `backend/src/common/db/session_lifecycle.py`, `backend/tests/integration/test_session_lifecycle_api.py`, `backend/tests/contract/test_sessions.py`, `backend/tests/integration/test_session_flow.py`
  - Do: 抽出 practice API 内共享的终态收口 helper，让 `POST /practice/sessions/{id}/lifecycle` 的 `end` 与旧 `DELETE /practice/sessions/{id}` 委托同一实现；保留 sales=`scoring` / presentation=`completed` 差异，同时统一 summary / cleanup / report trigger / live handler sync / terminal close 的副作用与响应语义。
  - Verify: `cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"`
  - Done when: 生命周期终态只由一套后端实现驱动，sales / presentation 的终态与收尾副作用在两条入口下都一致可测。
- [x] **T02: 让 Sales StepFun runtime 接通快照恢复协议** `est:3h`
  - Why: 销售 handler 现在绕开了 `BaseWebSocketHandler` 的保存 / 恢复路径，断线后只能重新连 socket，不能恢复最小会话状态，也没有 `reconnected` 合约。
  - Files: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/websocket/base_handler.py`, `backend/src/common/websocket/session_manager.py`, `backend/tests/unit/test_stepfun_realtime_persistence.py`, `backend/tests/integration/test_sales_realtime_reconnect_flow.py`, `backend/tests/integration/test_websocket_status_contract.py`
  - Do: 为 StepFun handler 实现最小快照的创建 / 保存 / 恢复与终态删除，复用基类 `reconnected` 消息；把活动时间、超时、上游断开诊断接回 `SessionManager`，并新增开始→两轮→断开→重连→继续→结束的 backend unit / integration 覆盖。
  - Verify: `cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
  - Done when: sales websocket 可在重连后恢复 `session_status` / `ai_state` / `turn_count` 并继续训练，终态后不会残留脏快照，关键恢复 / 失败信号可被测试断言。
- [x] **T03: 让训练页只信服务端生命周期并显式暴露结束失败** `est:2h`
  - Why: 前端仍会在 `sendControl()` 中乐观改本地状态，`handleEndSession()` 也会在失败后照样跳报告页，这会把运行时分歧伪装成报告问题。
  - Files: `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`, `web/src/app/(user)/practice/[sessionId]/page.tsx`, `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/websocket/message-handlers.ts`, `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/hooks/websocket/message-handlers.test.ts`
  - Do: 去掉或收窄 lifecycle 的本地乐观状态写入，让暂停 / 恢复 / 结束 UI 以 `status` / `reconnected` / `session_ended` 为准；把结束失败保留在训练页现有错误提示面上，只有服务端确认终态后才跳转报告页，并补齐失败重试与重连恢复测试。
  - Verify: `cd web && npm test -- --run src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts`
  - Done when: 训练页不会在结束失败后跳转报告页，UI 生命周期状态与音频门禁跟随后端事件而不是本地猜测，重连恢复路径有前端回归测试保护。

## Files Likely Touched

- `backend/src/common/api/practice.py`
- `backend/src/common/db/session_lifecycle.py`
- `backend/src/common/websocket/base_handler.py`
- `backend/src/common/websocket/session_manager.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/integration/test_session_lifecycle_api.py`
- `backend/tests/integration/test_sales_realtime_reconnect_flow.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/websocket/message-handlers.ts`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/websocket/message-handlers.test.ts`
