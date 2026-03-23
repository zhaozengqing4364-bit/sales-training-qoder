---
estimated_steps: 4
estimated_files: 6
---

# T03: 让历史与趋势改读同一证据基线

**Slice:** S02 — 训练证据落库与报告事实源统一
**Milestone:** M001

## Description

T02 只把 report / replay 收口了一半；主管真正会频繁看的还有 history list、statistics、trends。这个任务把这些聚合面也切到同一 evidence projection，去掉 `ComprehensiveReport.overall_score` 与 0.4/0.3/0.3 独立加权公式。完成后，history/trends 看到的 overall score 必须与单次 report/replay 同源。

## Steps

1. 让 `HistoryService` 基于共享 session evidence projection 组装 history summary、statistics 与 trends 数据，不再直接 join `ComprehensiveReport` 或自行重算另一套 overall。
2. 保持 `users/me/history`、`/practice/history/statistics`、`/practice/history/trends` 的分页、过滤、scenario alias 归一与 completed-session 约束，但返回统一 overall/evaluable 语义。
3. 新增/扩展 service 与 integration tests，覆盖 report cache 缺失、legacy score key、无证据 session、scenario 过滤与趋势聚合对齐。
4. 运行 focused pytest，确保 history/trends 的数据面与 report/replay 不再漂移。

## Must-Haves

- [ ] history list、statistics、trends 使用与 report/replay 相同的 overall/evaluable 基线，不再依赖 `ComprehensiveReport` 是否存在或另一套公式。
- [ ] 现有分页、过滤、时间窗、scenario alias 归一化行为继续成立，避免因为事实源收口而退化接口可用性。

## Verification

- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py`
- 额外断言：同一批 sessions 在 history / trends 里显示的 overall score 与共享 evidence projection 完全一致。

## Observability Impact

- Signals added/changed: history/trends service 日志要能标出 session 数量、过滤条件、使用的 evidence source，而不是只记最终聚合结果。
- How a future agent inspects this: 看 `HistoryService` 与新的 history evidence tests，就能分辨问题是 projection 本身、history 聚合逻辑，还是 API 适配层。
- Failure state exposed: 当某条 session 缺 evidence 或被过滤掉时，要能看见是 completed gating、projection 不完整，还是 query 条件导致。

## Inputs

- `backend/src/common/analytics/history_service.py` — 当前同时承担 history summary、statistics、trends，且仍在使用 split-brain score 来源。
- `backend/src/common/api/users.py` / `backend/src/common/api/analytics.py` — 对外暴露用户历史与趋势接口，必须继续保持路由与分页契约。
- T02 提供的共享 session evidence projection — 本任务只允许在这一基线上聚合，不再引入新的平行 score 公式。

## Expected Output

- `backend/src/common/analytics/history_service.py` — history/statistics/trends 统一改读 session evidence projection。
- `backend/src/common/api/users.py` / `backend/src/common/api/analytics.py` — 对外接口继续稳定，但其事实源已经收口。
- `backend/tests/unit/test_history_service_evidence_projection.py` / `backend/tests/integration/test_history_evidence_flow.py` — 回归覆盖 history/trends 与 report/replay 的事实对齐。
