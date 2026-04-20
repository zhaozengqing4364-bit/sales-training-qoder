---
estimated_steps: 5
estimated_files: 4
skills_used:
  - safe-grow
  - test-driven-development
  - systematic-debugging
  - code-refactoring
  - verification-before-completion
---

# T01: 把主管连续变化聚合收口到 HistoryService 并对齐 admin stats/progress

**Slice:** S06 — 连续变化视图（主管判断是否进步）
**Milestone:** M001

## Description

这个任务先把 S06 的 backend 事实线收口。当前 `backend/src/admin/api/users.py` 的 `/progress` 和 score-bearing `/stats` 仍然直接按 `PracticeSession.logic_score/accuracy_score/completeness_score` 做 legacy 0.4/0.3/0.3 加权和 SQL date average，这会让主管趋势图、顶部分数卡和 S03 已经 projection-backed 的 completed-session preview 在同一页上继续说不同的话。这里要做的是把“最近几次训练有没有进步 / 重复卡在哪 / 要不要换重点”建成 `HistoryService` 上的 supervisor snapshot，而不是在 route 里直接做新一套聚合。

## Steps

1. 先在 `backend/tests/unit/test_history_service_evidence_projection.py` 和 `backend/tests/integration/test_admin_users_api.py` 写 failing tests，锁住 supervisor snapshot 的关键合同：projection-backed trend points、truthful `day/week` granularity、repeated `main_issue.issue_type` / `next_goal.goal_type` buckets、`not_evaluable_session_count`、`should_switch_focus` / recommendation，以及 `/stats` score fields 与 `/sessions` preview 不再漂移。
2. 在 `backend/src/common/analytics/history_service.py` 新增 supervisor progress snapshot / grouping helper，复用 `build_history_entries(...)` / `build_trend_points(...)` 的 completed-session projection，而不是重新按 raw session score 列做 SQL 平均；聚合逻辑必须显式区分 completed+evaluable、completed+not-evaluable、以及 non-completed session。
3. 在同一个 helper 里实现 truthful granularity：`day` 返回日粒度趋势点，`week` 返回按周分组的趋势点；如果 route 继续暴露 `granularity` 参数，就必须真的兑现，而不是继续忽略它。
4. 把 `backend/src/admin/api/users.py` 的 `/progress` 改成调用新的 HistoryService helper；同时把 `/stats` 中 `average_score` / `best_score` / `worst_score` 对齐到同一 projection-backed summaries，raw `total_sessions` / `completed_sessions` / `agent_usage` / `persona_usage` 可以继续用现有查询，只要不再引入第二套 score 真相。
5. 跑 backend focused suites，检查 route payload 是否沿用 S03 vocabulary（`overall_result` / `evaluable` / `main_issue` / `next_goal`）并且显式暴露 repeated blocker/goal 与 not-evaluable semantics，必要时补 projection query 日志字段帮助后续排障。

## Must-Haves

- [ ] `backend/src/common/analytics/history_service.py` 必须成为 S06 连续变化聚合的唯一实现位置；`backend/src/admin/api/users.py` 不能继续在 route 内直接做 legacy weighted SQL trend math。
- [ ] `/progress` payload 必须区分 evaluable 与 not-evaluable completed sessions，并输出 repeated issue/goal buckets 与保守 `should_switch_focus` 建议；不能把“证据不足”误当成“没有进步”。
- [ ] `/stats` 中 `average_score` / `best_score` / `worst_score` 必须和 projection-backed completed-session summaries 对齐，避免 admin user detail 页面同时出现两套分数口径。

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py -k 'progress or stats'`

## Observability Impact

- Signals added/changed: `practice_history_projection_query` 中与 supervisor snapshot 相关的 evaluable/not-evaluable counts、projection coverage，以及新 `/progress` payload 的 repeated issue/goal bucket 与 recommendation reason。
- How a future agent inspects this: 调用 `GET /api/v1/admin/users/{id}/progress` / `GET /api/v1/admin/users/{id}/stats`，再对照 `backend/tests/unit/test_history_service_evidence_projection.py` 与 `backend/tests/integration/test_admin_users_api.py`。
- Failure state exposed: `not_evaluable_session_count`、重复 `issue_type` / `goal_type` 的计数、以及 granularity 不生效时的 focused test failure。

## Inputs

- `backend/src/common/analytics/history_service.py` — 已经持有 completed-session projection、statistics payload 和 trend points，是 S06 唯一该扩展的聚合层。
- `backend/src/common/conversation/session_evidence.py` — 单次会话 projection contract 的权威来源，S06 只能消费它，不能复制逻辑。
- `backend/src/common/effectiveness/evaluator.py` — `main_issue.issue_type` / `next_goal.goal_type` 的稳定 vocabulary 来源。
- `backend/src/admin/api/users.py` — 当前 `/stats` 和 `/progress` 仍使用 legacy weighted SQL。
- `backend/tests/unit/test_history_service_evidence_projection.py` — 已覆盖 projection-backed history/stats/trends 的单测基线。
- `backend/tests/integration/test_admin_users_api.py` — 已覆盖 completed-session preview contract 的 admin integration 基线。

## Expected Output

- `backend/src/common/analytics/history_service.py` — 新的 supervisor progress snapshot / grouping helper，复用 projection-backed summaries 提供 trend、repeated blockers/goals、not-evaluable counts 和 recommendation。
- `backend/src/admin/api/users.py` — `/progress` 与 `/stats` 改读同一 projection-backed score semantics，而不是 legacy weighted SQL。
- `backend/tests/unit/test_history_service_evidence_projection.py` — 锁住 supervisor snapshot 的 granularity、repeated issue/goal、not-evaluable 与 recommendation 合同。
- `backend/tests/integration/test_admin_users_api.py` — 锁住 admin `/progress` 和 `/stats` 对齐同一 evidence line 的 API 证明。
