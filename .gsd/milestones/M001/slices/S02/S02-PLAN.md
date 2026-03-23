# S02: 训练证据落库与报告事实源统一

**Goal:** 把销售训练会话的逐轮证据与会话级 evaluable/result 语义稳定写入同一事实基线，并让报告、回放、历史、趋势都从同一个标准化读模型取数。
**Demo:** 对同一条已结束训练会话，`/practice/sessions/{id}/report`、`/sessions/{id}/replay`、`/users/me/history`、`/practice/history/trends` 返回的 overall score、阶段/逐轮证据、main issue / next goal、是否可评估语义彼此一致；零轮或薄证据会话返回显式 `evaluable=false` / `not_evaluable_reason`，不再因为 summary 生成失败而把事实面打断。
**Requirements:** Supports `R005`, `R011`.

## Must-Haves

- StepFun 销售写入面把逐轮证据落到稳定字段基线：逐轮 transcript / sales stage / fuzzy words / score snapshot / AI feedback 保持同一 payload 语义，`score_snapshot` 读写统一到 `overall_score`，但对历史 `overall` 仍兼容。
- 会话结束时必须持久化明确的 evaluability / result metadata；零轮或薄证据会话要落成“不可评估”的事实，而不是继续把 `[SUMMARY_GENERATION_FAILED]` 当成完成态语义。
- 后端提供一个共享 session evidence projection，由 `PracticeSession` + `ConversationMessage` 生成统一读模型，并被 report / replay / history / trends 共用。
- Web 报告页、回放页、历史页停止拼接互相冲突的分数来源；综合报告可以继续作为增强视图存在，但不再是“事实存在”的前提。

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py`
- `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py`
- `cd web && npm test -- --run src/app/(user)/practice/[sessionId]/report/page.test.tsx src/app/(user)/practice/[sessionId]/replay/page.test.tsx src/app/(dashboard)/history/page.test.tsx`

## Observability / Diagnostics

- Runtime signals: `practice_session_evidence_persisted` / `practice_session_evidence_not_evaluable` / `practice_session_evidence_projection_built` 一类结构化日志，以及 report / replay / history 响应中的 `evaluable`、`not_evaluable_reason`、`evidence_completeness` 字段。
- Inspection surfaces: `backend/src/common/conversation/session_evidence.py` 统一投影实现、相关 API JSON 响应、focused pytest / vitest 结果。
- Failure visibility: 具体缺失的是消息证据、会话级 score、effectiveness snapshot，还是 consumer 自己又在重算分数；零轮会话要能暴露不可评估原因，而不是只剩 500。
- Redaction constraints: 仅记录 session_id、turn_number、stage、score/evaluable 等非敏感诊断；不得输出音频原始内容、token 或任何密钥。

## Integration Closure

- Upstream surfaces consumed: `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/api/practice.py`, `backend/src/common/conversation/replay.py`, `backend/src/common/analytics/history_service.py`, `backend/src/common/api/users.py`, `backend/src/common/api/analytics.py`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/app/(dashboard)/history/page.tsx`.
- New wiring introduced in this slice: 新增共享 `SessionEvidenceService`（或同等职责服务）作为后端统一读模型；report / replay / history / trends 全部改经这层投影；前端页面改为信任统一 evidence contract。
- What remains before the milestone is truly usable end-to-end: S03 仍需把统一事实翻译成学员/主管真正可读、可执行的单次报告；S02 只证明“事实不再漂”。

## Tasks

- [x] **T01: 稳定逐轮证据写入与无证据终态语义** `est:2h`
  - Why: 如果写入层还在混用 `overall` / `overall_score`、并在零轮结束时继续依赖 summary 生成成功，后面的共享读模型只是在翻译不稳定事实。
  - Files: `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/api/practice.py`, `backend/tests/unit/test_stepfun_message_helpers.py`, `backend/tests/unit/test_stepfun_realtime_persistence.py`, `backend/tests/unit/test_sales_message_persistence.py`
  - Do: 规范 StepFun message/session persistence payload，让逐轮分析与会话级 score snapshot 一律写出稳定键形；终态收口在证据不足时写入显式 `evaluable=false` / reason 与 result metadata，不再把薄证据会话等同于 summary 失败。
  - Verify: `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py`
  - Done when: 销售训练的逐轮与会话级证据都有稳定落库契约，零轮/薄证据结束能落成可读的不可评估事实，而不是 500。
- [x] **T02: 建立共享会话证据读模型并收口报告/回放** `est:3h`
  - Why: 当前 report 主要读 `PracticeSession`，replay 主要读 `ConversationMessage`，两边甚至对 overall key 的理解都不一致；必须先让这两个直接复盘入口共用一条投影边界。
  - Files: `backend/src/common/conversation/session_evidence.py`, `backend/src/common/conversation/replay.py`, `backend/src/common/api/practice.py`, `backend/tests/unit/test_session_evidence_service.py`, `backend/tests/unit/test_replay_service.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_practice_evidence_flow.py`
  - Do: 新增共享 session evidence service，从 `PracticeSession` + ordered `ConversationMessage` 生成标准化 projection（overall score、阶段汇总、逐轮证据、evaluable/result metadata、completeness）；让 quick report 与 replay 都改读这层，同时保留 completed-session gating 与 legacy score key 兼容。
  - Verify: `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
  - Done when: 对同一 completed session，report 与 replay 的 top-line score、阶段汇总、逐轮 evidence 与 evaluability 语义来自同一 projection，并有 contract/integration 测试锁定。
- [x] **T03: 让历史与趋势改读同一证据基线** `est:2h`
  - Why: 即使 report / replay 对齐，history summary 继续 join `ComprehensiveReport`、trends/statistics 继续用 0.4/0.3/0.3 重算，也会让主管看到另一套事实。
  - Files: `backend/src/common/analytics/history_service.py`, `backend/src/common/api/users.py`, `backend/src/common/api/analytics.py`, `backend/tests/unit/test_history_service_evidence_projection.py`, `backend/tests/unit/common/test_analytics_api_normalization.py`, `backend/tests/integration/test_history_evidence_flow.py`
  - Do: 把 history list、statistics、trends 统一改成消费 session evidence projection，去掉对 `ComprehensiveReport.overall_score` 和独立加权公式的依赖；保留现有分页、过滤、别名归一化与 completed-session 约束，但返回一致的 overall / evaluable 基线。
  - Verify: `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py`
  - Done when: history / stats / trends 与 report / replay 读取同一 overall/evaluable 基线，不再因为 report cache 缺失或不同公式而漂移。
- [x] **T04: 收口报告/回放/历史页面的统一消费面** `est:2h`
  - Why: 后端即使已经统一，如果页面还继续并行拉 quick report、comprehensive report、messages、highlights 后再本地补分，用户看到的仍可能是拼出来的假一致。
  - Files: `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/app/(dashboard)/history/page.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`, `web/src/app/(dashboard)/history/page.test.tsx`
  - Do: 调整类型与页面取数逻辑，让 report / replay / history 直接消费统一 evidence contract；综合报告仅作为增强内容存在，页面不再本地重算 overall，也不再靠多接口回退拼接事实一致性。
  - Verify: `cd web && npm test -- --run src/app/(user)/practice/[sessionId]/report/page.test.tsx src/app/(user)/practice/[sessionId]/replay/page.test.tsx src/app/(dashboard)/history/page.test.tsx`
  - Done when: 三个页面对同一会话展示的 top-line score、不可评估提示与逐轮/趋势事实一致，前端测试能断言它们不再自行拼接冲突来源。

## Files Likely Touched

- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/common/api/users.py`
- `backend/src/common/api/analytics.py`
- `backend/tests/unit/test_stepfun_message_helpers.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`
- `backend/tests/unit/test_sales_message_persistence.py`
- `backend/tests/unit/test_session_evidence_service.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/unit/test_history_service_evidence_projection.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `backend/tests/integration/test_history_evidence_flow.py`
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`
