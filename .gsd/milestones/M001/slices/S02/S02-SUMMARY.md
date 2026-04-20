---
id: S02
parent: M001
milestone: M001
provides:
  - Unified persisted/session-projected evidence for report, replay, history, and trends, with explicit evaluability semantics and stable web consumers
requires:
  - slice: S01
    provides: Stable sales session lifecycle, reconnect recovery boundary, and server-authoritative terminal state needed before evidence persistence/projection could be trusted
affects:
  - S03
  - S05
  - S06
  - S07
key_files:
  - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/api/practice.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/analytics/history_service.py
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
key_decisions:
  - D013: StepFun sales evidence writes canonicalize `score_snapshot.overall_score` and persist thin-evidence endings as explicit `evaluable=false` facts
  - D014: Report/replay consume one `SessionEvidenceService` projection with shared overall/evaluability/completeness semantics and legacy score-key normalization
  - D015: History/statistics/trends aggregate from the same projection and only roll up evaluable completed sessions for averages/trends
  - D016: Web report/replay/history pages trust only the unified evidence contract for baseline facts; comprehensive report/highlights remain optional enhancements
patterns_established:
  - Persist turn/session evidence once, project it once, and make every consumer read that same projection instead of recomputing overall/evaluable semantics locally
  - Treat insufficient evidence as an explicit terminal fact (`evaluable=false`, `not_evaluable_reason`) rather than a disguised summary failure
  - Keep enhanced report/highlight layers optional so their absence degrades UI copy, not factual score/evidence consistency
observability_surfaces:
  - `practice_session_evidence_persisted`
  - `practice_session_evidence_not_evaluable`
  - `practice_session_evidence_projection_built`
  - `practice_history_projection_query`
  - report / replay / history responses exposing `evaluable`, `not_evaluable_reason`, `stage_summary`, `evidence_completeness`
  - `[Report] Loaded unified evidence contract`
  - `[Replay] Loaded unified evidence contract`
  - `[History] Loaded unified evidence list`
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md
duration: 2h35m
verification_result: passed
completed_at: 2026-03-23T09:45:31+08:00
---

# S02: 训练证据落库与报告事实源统一

**Stabilized sales-session evidence from write path to web consumer so report, replay, history, and trends now read one consistent fact baseline with explicit evaluability semantics.**

## What Happened

S02 按“写入层 → 共享读模型 → 聚合面 → Web 消费面”的顺序把训练事实源收口成一条线，而不是继续在多个接口和页面里各算各的。

1. **T01 收稳写入面**
   - StepFun 销售逐轮 evidence 写入统一规范到 `score_snapshot.overall_score`，同时继续兼容历史 `overall` 输入。
   - 终态收口不再把零轮/薄证据会话伪装成 `[SUMMARY_GENERATION_FAILED]`；改为显式落 `evaluable=false`、`not_evaluable_reason=INSUFFICIENT_TURN_DATA`。
   - runtime snapshot、message analysis patch、session-level score flush 现在共享同一规范化逻辑，并补齐 `practice_session_evidence_persisted` / `practice_session_evidence_not_evaluable` 诊断。

2. **T02 建立共享 `SessionEvidenceService`**
   - 新增统一 projection，从 `PracticeSession` + ordered `ConversationMessage` 生成 canonical overall、stage summary、turn evidence、main issue / next goal、evaluability、completeness。
   - quick report 与 replay 改读同一 projection，不再一个偏 session 顶层、一个偏 messages 细节各自补分。
   - 读模型对 legacy `score_snapshot.overall` 做兼容，并把 `legacy_score_key_used` / `evidence_completeness` 暴露出来，方便定位是旧数据还是 consumer 绕过 projection。

3. **T03 让 history / statistics / trends 改读同一基线**
   - `HistoryService` 批量加载 completed session 的 messages，再统一投影成 history summary。
   - history list、`/users/me/history`、analytics history、statistics、trends 全部改读 projection-backed summary，不再依赖 `ComprehensiveReport` 或旧 0.4/0.3/0.3 公式。
   - trends/statistics 只聚合 `evaluable=true` 的 completed sessions，history list 则保留 non-completed 行并显式暴露 not-evaluable 语义。

4. **T04 收口前端事实消费面**
   - report / replay / history 页面共享统一 evidence contract 类型，top-line score、stage summary、evaluability、completeness 直接来自后端统一 contract。
   - `ComprehensiveReport`、highlights、statistics/trends 仅作为增强层；缺失时显示清晰降级提示，不再反向覆盖基线事实。
   - 页面 focused tests 锁住“不再本地重算 overall / 不再拼接冲突消息来源 / 不再把 not-evaluable 塌成模糊状态”。

整体结果是：**同一 completed session 在 report、replay、history、trends 上的 overall / evaluable / stage / main issue / next goal 终于共享同一事实基线**，而零轮或薄证据会话也能以显式不可评估事实存在，不再把 summary 失败误当业务语义。

## Verification

本 slice 的全部计划内验证在 T04 完成前已真实跑通，并在本次 crash recovery 中按记录核对为最终证明面：

- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py`
- `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'`

额外 observability / diagnostics 证明：
- focused browser 验证在本地 app 上确认 `/history` 页面能显式区分“统一证据 contract 拉取失败”与空白/泛化失败态；页面正确显示 `统一训练证据加载失败` 与 `重试`
- `browser_get_network_logs` / `browser_get_console_logs` 证明降级来源是本地开发库缺少 `conversation_messages.transcript_metadata` 列，而不是页面重新拼装事实失败
- backend / frontend focused tests 锁住四类诊断面：写入规范化、projection completeness、history aggregation baseline、web optional-enhancement degradation

## Requirements Advanced

- R005 — 证明了单次报告、回放、历史、趋势背后的事实基线已经统一，S03 可以在可信 evidence 之上做“可读、可执行”的报告翻译，而不是先解决漂分/漂事实问题。
- R011 — 逐轮内容、阶段、分数、不可评估原因、main issue / next goal 现在可稳定沉淀并跨 report/replay/history/trends 复用，为后续更强的回放/高光/证据链式复盘建立统一资产底座。

## Requirements Validated

- none — S02 证明的是“事实不再漂”，还没有单独证明学员/主管已拿到最终可读、可执行的报告，也还没有完成 M004 级别的高光/逐轮点评增强。

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- 浏览器 happy-path 数据一致性验证被本地开发数据库 schema 漂移打断：`conversation_messages.transcript_metadata` 列缺失导致 history analytics 请求 500。该偏差没有改变 slice 的目标或 contract，只让实时浏览器验证退化为 failure-state / diagnostics 验证；happy-path 一致性继续由 fresh pytest + vitest 证明。

## Known Limitations

- S02 只统一了事实源，没有把这些事实翻译成学员/主管更可读、更可执行的单次报告；这仍由 S03 负责。
- 本地开发数据库缺少 `conversation_messages.transcript_metadata` 列；若后续要继续依赖浏览器做 report/replay/history happy-path 验证，必须先补 migration。
- richer replay/highlight/逐轮点评能力仍未完成；R011 仍需后续 slice 深化，而不是在 S02 宣称全部闭环完成。

## Follow-ups

- 重新评估路线并选择下一 slice；S03（单次报告可读化）已被 S02 直接解锁，S04 也仍可并行考虑。
- 若下一轮需要浏览器 happy-path 复验 report/replay/history，先修复本地 dev DB schema 漂移，再做页面级真实数据检查。
- 继续监控是否还有 consumer 绕过 `SessionEvidenceService` 或前端重新本地补分的回归点。

## Files Created/Modified

- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — 统一逐轮 analysis payload 规范化、canonical `overall_score` 写入和 persistence logging。
- `backend/src/sales_bot/websocket/components/message_persistence.py` — 让旧 message analysis 更新入口也遵守同一 evidence 写入合同。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 统一 runtime score snapshot 规范化、session-level score flush 与薄证据终态语义。
- `backend/src/common/api/practice.py` — terminal evidence sync 与 quick report 改接共享 projection/explicit not-evaluable semantics。
- `backend/src/common/conversation/session_evidence.py` — 新增共享 session evidence projection 与 completeness / legacy fallback diagnostics。
- `backend/src/common/conversation/replay.py` — replay 改读统一 projection，而不是自己拼 stage / score / metadata。
- `backend/src/common/analytics/history_service.py` — history/statistics/trends 批量投影 completed sessions 并统一 evaluability aggregation。
- `backend/src/common/api/users.py` — `/users/me/history` 接入 projection-backed history summary。
- `backend/src/common/api/analytics.py` — analytics history / statistics / trends 改读统一 evidence 基线。
- `web/src/lib/api/types.ts` — 统一 report/replay/history evidence contract 类型。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 只信 unified report evidence，增强内容降为可缺失层。
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — 只信 unified replay payload，不再回退 `/messages` 拼接冲突事实。
- `web/src/app/(dashboard)/history/page.tsx` — 以 `/users/me/history` 列表事实为基线，stats/trends 仅作增强看板。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 锁住 report 的 unified-evidence / degraded-enhancement contract。
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — 锁住 replay 不再拼接 `/messages` 的 contract。
- `web/src/app/(dashboard)/history/page.test.tsx` — 锁住 history 页面渲染 projection-backed score 与 not-evaluable 状态。

## Forward Intelligence

### What the next slice should know
- S02 已经把“哪一套事实才算真相”收口好了；S03/S06/S07 不应再回头发明自己的 overall/evaluable/stage 计算逻辑，而应直接消费 unified evidence contract。
- thin-evidence completed sessions 现在是合法业务态，不是异常态；后续页面和文案必须显式解释 `evaluable=false`，不要再把它们当“评分中”或“失败重试”。

### What's fragile
- 本地浏览器 happy-path 验证环境对数据库 schema 很敏感 — 缺少 `conversation_messages.transcript_metadata` 会直接让 history analytics 500，从而掩盖真实页面 contract 状态。
- 任何重新引入 `ComprehensiveReport` 顶分覆盖、`/messages` 额外拼接、或 client-side overall 重算的改动都会让 S02 事实统一成果失效。

### Authoritative diagnostics
- `backend/src/common/conversation/session_evidence.py` — 这是 report/replay/history/trends 共享事实投影的第一检查点。
- `practice_session_evidence_projection_built` / `practice_history_projection_query` — 这两个结构化日志最能快速判断漂移发生在 projection 层还是 consumer 层。
- report / replay / history page tests — 它们能最快暴露“前端又开始拼多套事实”的回归。

### What assumptions changed
- “summary 失败大多意味着异常” — 实际上零轮/薄证据 completed session 是一个正常但不可评估的业务终态，必须显式落成事实。
- “统一后端事实源就足够了” — 实际上前端如果继续把 comprehensive/highlights/messages/stats 当 baseline，也会制造新的假一致，因此 web consumer 边界同样必须收口。
