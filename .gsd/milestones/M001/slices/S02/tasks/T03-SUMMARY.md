---
id: T03
parent: S02
milestone: M001
provides:
  - History/statistics/trends now read the shared session evidence projection, expose aligned evaluability metadata, and stop depending on `ComprehensiveReport` or the old weighted overall formula
key_files:
  - backend/src/common/analytics/history_service.py
  - backend/src/common/api/users.py
  - backend/src/common/api/analytics.py
  - backend/tests/unit/test_history_service_evidence_projection.py
  - backend/tests/integration/test_history_evidence_flow.py
key_decisions:
  - D015: History/statistics/trends aggregate from one projection-backed summary surface, and statistics/trends only roll up evaluable completed sessions while history list preserves non-completed rows without inventing scores
patterns_established:
  - History consumers batch-load completed-session messages, project them through `SessionEvidenceService`, then serialize one `HistorySessionSummary` shape for list/stats/trends APIs
  - History API responses now surface `evaluable`, `not_evaluable_reason`, `evidence_completeness`, `main_issue`, and `next_goal` from the same baseline used by report/replay
observability_surfaces:
  - `practice_history_projection_query`
  - `/api/v1/users/me/history`
  - `/api/v1/analytics/practice/history`
  - `/api/v1/practice/history/statistics`
  - `/api/v1/practice/history/trends`
  - `backend/tests/unit/test_history_service_evidence_projection.py`
duration: 45m
verification_result: passed
completed_at: 2026-03-23T08:25:48+08:00
blocker_discovered: false
---

# T03: 让历史与趋势改读同一证据基线

**Reworked `HistoryService` to batch-project completed sessions through the shared evidence reader, then switched history/statistics/trends APIs to that same baseline with explicit evaluability semantics.**

## What Happened

`backend/src/common/analytics/history_service.py` 不再 join `ComprehensiveReport` 或用 0.4/0.3/0.3 公式重算 overall。新的实现先按用户 / 过滤条件查 `PracticeSession`，再批量拉取 completed session 的 `ConversationMessage`，通过 `SessionEvidenceService.build_projection()` 生成统一 `HistorySessionSummary`，供 history list、statistics、trends 复用。

history list 继续保留分页与非 completed 行，但只有 completed 行才带 projection-based `overall_score` / `evaluable` / `not_evaluable_reason` / `evidence_completeness` / `main_issue` / `next_goal` / `stage_summary`。statistics 与 trends 则只聚合 `evaluable=true` 的 completed sessions，避免无证据终态把平均分和趋势线拉成另一套伪事实；同时保留 `total_sessions`、`not_evaluable_sessions` 与总时长，显式说明哪些完成态没有可评估证据。

`backend/src/common/api/users.py` 和 `backend/src/common/api/analytics.py` 已接到这层 summary contract，并补上 `sales_bot -> sales` 的 scenario alias 归一。`/users/me/history` 与 `/analytics/practice/history` 现在都能在 report cache 缺失时直接返回 projection overall，不再因为 `ComprehensiveReport` 缺席而给空分或漂分。

测试面新增了 service-level unit tests 和 integration flow，锁住四个关键点：
- report cache 缺失时 history/trends 仍和 shared projection 对齐
- legacy `score_snapshot.overall` 仍能通过 projection 落到 canonical overall
- 无证据 completed session 在 history 里显式 `evaluable=false`
- history/trends/report/replay 对同一 session 的 overall 不再漂移

## Verification

Task-focused verification passed:
- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py`

Slice-level verification run during this task:
- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py` ✅
- `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` ✅
- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py` ✅
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'` ❌ `No test files found`（T04 owning frontend page tests still not created）

Additional behavior explicitly asserted:
- 同一批 sessions 在 `/users/me/history`、`/analytics/practice/history`、`/practice/history/trends` 和 shared evidence projection 上的 overall score 完全一致
- `/practice/sessions/{id}/report`、`/sessions/{id}/replay` 与 history list 对同一 session 的 overall score 对齐
- `practice_history_projection_query` 日志带出 `query_name`、`filters`、`evidence_source`、session 数量与 not-evaluable 计数

## Diagnostics

后续排查先看：
- `backend/src/common/analytics/history_service.py`
- `backend/src/common/api/users.py`
- `backend/src/common/api/analytics.py`
- `backend/tests/unit/test_history_service_evidence_projection.py`
- `backend/tests/integration/test_history_evidence_flow.py`

关键诊断面：
- 结构化日志 `practice_history_projection_query`：`query_name`、`filters`、`evidence_source`、`session_count`、`completed_session_count`、`projected_session_count`、`evaluable_session_count`、`not_evaluable_session_count`
- history / analytics history 响应里的 `overall_score`、`evaluable`、`not_evaluable_reason`、`evidence_completeness`
- trends/statistics 响应里的 `evaluable_sessions`、`not_evaluable_sessions` 与 per-point `overall_score`

如果后续历史页还漂，先确认调用方是不是走了这几个接口；若接口已走统一 reader，再看 `practice_history_projection_query` 里是 alias 过滤错了、completed gating 生效、还是 projection incomplete / not-evaluable 导致聚合排除。

## Deviations

- Statistics/trends 在同一 projection 基线上进一步固定为“只聚合 evaluable completed sessions”，而不是把无证据 completed session 的 0 分混进平均值和趋势线。这是同一 contract 内的语义收口，不是引入新公式。

## Known Issues

- S02 的前端 page tests 仍未创建；因此 slice-level web verification 命令继续以 `No test files found` 失败，留待 T04 完成。
- `backend/src/common/api/practice.py` 里的 `/practice/history` 仍是旧消费面，不在本任务 contract 内；当前 dashboard history 主页面已走 `/users/me/history` + `/practice/history/statistics` + `/practice/history/trends`，但如果后续要把 `/practice/history` 也彻底收口，应在后续任务统一处理。

## Files Created/Modified

- `backend/src/common/analytics/history_service.py` — 用 batch session/message loading + shared projection 重写 history/statistics/trends 聚合逻辑，并补 `practice_history_projection_query` 日志
- `backend/src/common/api/users.py` — `/users/me/history` 接入 normalized scenario filter 与新的 evidence/evaluability fields
- `backend/src/common/api/analytics.py` — `/analytics/practice/history` 改读 projection-backed history summaries，移除旧 weighted overall 公式
- `backend/tests/unit/test_history_service_evidence_projection.py` — 新增 history summary/statistics/trends baseline 和 observability log 的 unit coverage
- `backend/tests/unit/common/test_analytics_api_normalization.py` — 扩展 history alias normalization coverage
- `backend/tests/integration/test_history_evidence_flow.py` — 新增 history/trends/report/replay/shared projection 的对齐回归
- `.gsd/DECISIONS.md` — 追加 D015，记录 history/stats/trends 的 evaluable aggregation contract
- `.gsd/milestones/M001/slices/S02/S02-PLAN.md` — 标记 T03 完成
