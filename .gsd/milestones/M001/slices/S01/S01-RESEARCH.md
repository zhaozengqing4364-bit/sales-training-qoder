# M001/S01: 多轮会话稳定化与运行时状态收口 — Research

**Date:** 2026-03-23

## Summary

S01 直接承接 **R001（桌面端客户演练主链路稳定可连续多轮运行）** 和 **R002（异常可恢复或可降级）**。代码库里其实已经存在一套可复用的“正确方向”：`PracticeSession` + `SessionLifecycleService` 提供了明确生命周期状态机，`SessionStateService` + `BaseWebSocketHandler` 提供了 Redis 快照恢复与 `reconnected` 协议，`runtime-lock.ts` + `sales_bot/websocket/router.py` 又提供了“以后端持久化运行时为准”的收口机制。问题不在于能力缺失，而在于**销售训练主链路没有完全走这套收口路径**。

当前最危险的碎裂点有三处。第一，生命周期写入口重复：REST `POST /practice/sessions/{id}/lifecycle`、销售 WebSocket handler 内部 `control` 消息、以及仍保留的 `DELETE /practice/sessions/{id}` 结束逻辑并存，而且三者副作用并不等价。第二，重连能力不对齐：展示教练走了 `SessionStateService` + `reconnected`，销售 handler 则自己接管连接循环，只做 DB 状态同步，未恢复 Redis 快照，也未向前端发 `reconnected`。第三，前端结束流会掩盖失败：`handleEndSession()` 即使结束失败也会在 `finally` 跳转报告页，容易把运行时分歧伪装成“报告页问题”。

S01 不该继续增加新的运行时抽象，而应做**状态面收口**：把 DB 生命周期当成唯一真相，把销售训练重连接入现有恢复协议，把结束流程统一到一个后端实现，再补上覆盖“开始→多轮→暂停/恢复→断开→重连→结束”的集成验证。否则第二轮异常、结束流程混乱、状态丢失会继续以不同症状重复出现。

## Recommendation

**推荐路径：以 `SessionLifecycleService` + 持久化会话运行时为唯一真相，围绕它收口销售训练的连接、重连、结束三个高风险阶段。**

具体建议：

1. **生命周期单写入口化**
   - 以 `backend/src/common/db/session_lifecycle.py` 为唯一状态机。
   - 前端用户路径继续走 REST 生命周期控制，不再让销售主路径依赖 WebSocket `control` 写状态。
   - 后端应统一 `POST /practice/sessions/{id}/lifecycle { action: "end" }` 与 `DELETE /practice/sessions/{id}` 的副作用，避免“结束成功但清理/总结/报告逻辑不一致”。

2. **销售侧重连接入已有恢复协议，而不是再造一套**
   - 复用 `SessionStateService`、`SessionStateSnapshot`、`BaseWebSocketHandler._send_reconnection_success()` 的既有协议面。
   - 销售 handler 至少恢复：`session_status`、`ai_state`、`turn_count`、最近活动/可继续交互状态；不要试图把整个 StepFun 上游连接对象序列化。
   - 前端已经支持 `reconnected` 事件；销售侧缺的是发出该事件，而不是再改一套前端恢复 UI。

3. **结束流程先统一，再谈报告可信**
   - 当前前端用的是 `api.practice.endSession(sessionId)`，实际只是 REST lifecycle `end` 的别名；但旧 `DELETE` 路由仍承载销售 summary/cleanup/report 兼容逻辑。
   - S01 应先明确“谁负责结束后的 summary / runtime cleanup / report trigger”，否则 S02 的事实落库和 S03 的报告可信都立不住。

4. **前端不要吞掉结束失败**
   - `use-practice-session-lifecycle.ts` 现在无论结束成功与否都 `router.push(report)`；这会掩盖 R001/R002 的真实失败面。
   - S01 至少需要把失败显式暴露为可诊断状态，或只在服务端确认进入终态后再跳转。

5. **验证重点放在集成链路，不是只补单元测试**
   - 现有测试已经覆盖生命周期状态机和消息 envelope，但没有证明销售训练的“重连恢复 + 多轮继续 + 结束一致性”。
   - S01 验证要围绕真实销售链路：创建会话、连接、开始、至少两轮输入、断开/重连、结束、读取终态与诊断信号。

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| 生命周期状态迁移 | `backend/src/common/db/session_lifecycle.py` + `POST /practice/sessions/{id}/lifecycle` | 已定义 `start/pause/resume/end`、终态差异（sales=`scoring`，presentation=`completed`）、时长计算和报告触发边界，不该再在 handler 内写第二套语义。 |
| 会话重连协议 | `backend/src/common/websocket/base_handler.py` + `backend/src/common/websocket/session_state_service.py` + `reconnected` 消息 | 展示教练已经在用；前端 reducer 也已支持。销售侧应复用该合约，而不是自创新的恢复事件或纯本地猜状态。 |
| 运行时参数收口 | `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts` + `backend/src/sales_bot/websocket/router.py` | 前后端都已经以持久化 session runtime 为准，忽略 query 覆盖。S01 应延续这个方向，而不是让 URL/query 再次成为真相源。 |
| 心跳/超时/活动追踪 | `backend/src/common/websocket/session_manager.py` | 已有统一 heartbeat、timeout、activity tracking。S01 应让销售链路贴合它，而不是再做独立超时判断。 |

## Existing Code and Patterns

- `backend/src/common/db/session_lifecycle.py` — 规范化生命周期状态机。`start/pause/resume/end`、终态、`ai_state` 推导、时长计算都在这里，S01 应把它当成唯一业务真相。
- `backend/src/common/api/practice.py` — 当前前端实际命中的生命周期入口。`control_session_lifecycle()` 已具备“DB 写入 → report trigger → live handler sync → broadcast → terminal close”的完整收口链路。
- `backend/src/common/api/practice.py` — 同文件仍保留 `DELETE /practice/sessions/{id}` 旧结束逻辑，带额外 sales summary / runtime cleanup / report 兼容副作用；这是 S01 必须收敛的历史分叉。
- `backend/src/common/websocket/base_handler.py` — 通用 WS 基类已支持 `_save_session_state()` / `_restore_session_state()` / `_send_reconnection_success()`；销售侧目前没有完整复用。
- `backend/src/common/websocket/session_state_service.py` — Redis 会话快照服务已支持 `turn_count`、`session_status`、`ai_state`、最近消息读取，具备重连恢复基础。
- `backend/src/common/websocket/session_manager.py` — 统一的会话注册、活动更新时间、heartbeat、timeout 清理与 REST→live handler 同步机制。S01 应围绕它收口，而不是旁路它。
- `backend/src/sales_bot/websocket/router.py` — 销售 WS 接入点会从 DB 解析 `scenario_type`、`voice_mode`、`agent_id`、`persona_id`，并忽略 query 覆盖，说明“持久化 runtime 优先级”已经成立。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 销售 Realtime handler 自己持有浏览器 WS、上游 StepFun WS、局部生命周期状态与能力运行时，是当前状态碎片最多的对象。
- `backend/src/presentation_coach/websocket/presentation_handler.py` — 展示教练已接通快照恢复、`reconnected`、断线保存与页面上下文恢复，是销售侧最直接的对照样板。
- `web/src/hooks/use-practice-websocket.ts` — 前端 WS hook 同时持有本地 `PracticeState`、音频缓存、重连次数、`sendControl()`；其中 `sendControl()` 仍会乐观改本地状态，容易与 REST 生命周期写入产生双写语义。
- `web/src/hooks/websocket/message-handlers.ts` — 前端 reducer 已支持 `reconnected`、`session_timeout`、`heartbeat`、`status` 等恢复/诊断消息；销售侧目前没有把这些能力完整喂回来。
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` — 前端当前已把开始/暂停/恢复/结束收口到 REST，但结束失败仍被 `finally` 跳转报告页掩盖。
- `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts` — 页面首次加载后会拉取 session 元信息并重写 query，使前端逐步向 DB runtime 收敛；这是好方向，但也说明首连前存在短暂“query 与 DB 不一致”窗口。

## Constraints

- **Sales 与 presentation 的终态不同。** `SessionLifecycleService` 对 sales 使用 `scoring`，对 presentation 使用 `completed`；S01 的统一不能把两种场景抹平。
- **后端持久化 runtime 已是权威。** 销售 WS 路由会忽略不匹配的 `voice_mode` / `agent_id` / `persona_id` query 覆盖，说明不能把 URL 参数当成主真相。
- **销售 handler 当前绕开了基类恢复路径。** `BaseWebSocketHandler` 有重连保存/恢复，但销售 realtime handler 自己实现 `handle_connection()`，只做 `_sync_session_state()` 的 DB 同步，不做快照恢复。
- **StepFun runtime 状态面本身就比 presentation 复杂。** 它同时管理浏览器 WebSocket、上游 StepFun WebSocket、音频流、评分/阶段能力和 runtime policy，恢复策略必须克制，先恢复“可继续会话”的最小状态。
- **SessionManager 已承担 heartbeat / timeout / activity tracking。** 若销售链路不及时 `update_activity()` 或未对 heartbeat 语义保持一致，会出现假超时或断线后幽灵连接。
- **现有测试覆盖偏契约、偏局部。** `test_session_lifecycle_service.py` 证明状态机规则，`test_websocket_status_contract.py` 证明 envelope 一致性；但尚未证明 sales 多轮 + 重连 + 结束链路整体稳定。

## Common Pitfalls

- **同时保留 REST 生命周期写入和 WebSocket `control` 写入作为主路径** — 这会制造重复状态迁移、时序竞争和“谁是最终状态”的争议。S01 应明确一条主写路径。
- **把销售重连做成“仅重新连上 socket”** — 前端 reducer 已期待 `reconnected` 和恢复后的状态；若只重开连接不恢复会话态，用户会在第二轮或恢复后看到错乱 UI。
- **沿用当前 `finally` 跳报告页行为** — 这会把结束失败伪装成报告问题，既损害 R001，也损害 R002 的可诊断性。
- **试图完整恢复 StepFun 上游连接内部状态** — 风险高且收益低。S01 应优先恢复 `session_status`、`ai_state`、turn 连续性与用户可继续训练能力，而不是序列化整个上游对象图。
- **误以为已有 `SessionStateService` 就代表销售链路已支持恢复** — 当前只是基础设施已存在，销售主链路没有真正接上。

## Open Risks

- `turn_count` 现在主要是 handler 本地态；若要保证重连后的多轮连续性，可能需要从 `ConversationMessage` 或快照中补齐恢复依据。
- `DELETE /practice/sessions/{id}` 上承载的 sales summary / cleanup 兼容副作用一旦被合并，可能暴露出报告生成或 runtime cleanup 的遗漏，需要连带梳理。
- `runtime-lock.ts` 采取“先按入口参数尝试连接，再异步拉 DB runtime 收口”的模式，首连窗口内仍可能出现一次无效连接或错误提示，需要验证用户体验是否可接受。
- 真正的多轮稳定性仍受 ASR / TTS / LLM / StepFun 上游行为影响；S01 可以先把状态面收口，但最终仍需真实链路验证，而不是只靠 mock 测试。

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Next.js / React | `vercel-react-best-practices` | installed |
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| WebSocket / realtime | `jeffallan/claude-skills@websocket-engineer` | available — `npx skills add jeffallan/claude-skills@websocket-engineer` |
| Redis state / recovery | `redis/agent-skills@redis-development` | available — `npx skills add redis/agent-skills@redis-development` |
| PostgreSQL | `wshobson/agents@postgresql-table-design` | available — `npx skills add wshobson/agents@postgresql-table-design` |

## Sources

- Canonical lifecycle transitions, terminal state rules, and report-trigger boundary (source: `backend/src/common/db/session_lifecycle.py`)
- Frontend-used lifecycle endpoint and legacy end-session divergence (source: `backend/src/common/api/practice.py`)
- Redis-backed reconnection snapshot model and saved fields (`turn_count`, `session_status`, `ai_state`) (source: `backend/src/common/websocket/session_state_service.py`)
- Generic websocket save/restore/reconnected contract (source: `backend/src/common/websocket/base_handler.py`)
- Session registration, activity tracking, heartbeat, timeout, and live handler sync (source: `backend/src/common/websocket/session_manager.py`)
- Sales websocket runtime lock enforcement and query override rejection (source: `backend/src/sales_bot/websocket/router.py`)
- Sales realtime handler self-managed browser/upstream websocket lifecycle and local session state sync (source: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`)
- Presentation handler reconnection restore path and `reconnected` emission (source: `backend/src/presentation_coach/websocket/presentation_handler.py`)
- Frontend websocket hook reconnect logic and lingering `sendControl()` local optimistic updates (source: `web/src/hooks/use-practice-websocket.ts`)
- Frontend reducer support for `reconnected` / `session_timeout` (source: `web/src/hooks/websocket/message-handlers.ts`)
- Frontend lifecycle orchestration and unconditional report redirect on end (source: `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`)
- Frontend runtime lock rewrite toward persisted session runtime (source: `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts`)
- Existing automated coverage proves lifecycle rules and message envelope consistency but not full sales reconnect/multi-turn stability (source: `backend/tests/unit/test_session_lifecycle_service.py`, `backend/tests/integration/test_websocket_status_contract.py`, `web/src/hooks/websocket/message-handlers.test.ts`, `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`)
