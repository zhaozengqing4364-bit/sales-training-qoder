# S06: 连续变化视图（主管判断是否进步）

**Goal:** 让主管在 `/admin/users/[id]` 上基于统一 evidence projection 直接判断某个学员最近几次训练有没有进步、反复卡在哪类问题、以及是否该切换训练重点，而不是再看一张与单次报告脱节的 generic 分数曲线。
**Demo:** 对同一学员，`GET /api/v1/admin/users/{id}/progress` 返回 projection-backed 的趋势点、重复 `main_issue` / `next_goal` 桶、`not_evaluable_session_count` 与 `should_switch_focus` 建议；`GET /api/v1/admin/users/{id}/stats` 的平均/最好/最差分与该事实线一致；`web/src/app/admin/users/[id]/page.tsx` 把这些结果渲染成主管可读的连续变化摘要，并在 progress 读取失败或无可评估数据时展示本地 inline 状态。
**Requirements:** Owns active `R007`; advances `R011`; reinforces validated `R005` by keeping supervisor trends on the same S02/S03 evidence baseline as report and session previews.

## Must-Haves

- `backend/src/admin/api/users.py` 的 `/progress` 不能再直接按 `PracticeSession.logic_score/accuracy_score/completeness_score` 做 0.4/0.3/0.3 SQL 平均；它必须改读 `backend/src/common/analytics/history_service.py` 的 projection-backed completed-session summaries，并显式区分 evaluable 与 not-evaluable completed sessions。
- `/progress` 必须给出主管真正能用的连续变化合同：truthful `day/week` granularity、recent trend points、重复 `main_issue.issue_type` / `next_goal.goal_type` 聚合、`not_evaluable_session_count`、以及保守可解释的 `should_switch_focus` / recommendation 结论，而不是只返回一条 improvement 百分比。
- 同一页面上的 score-bearing stats 不能继续漂：`/stats` 中的 `average_score` / `best_score` / `worst_score` 必须对齐同一 projection-backed summaries；raw session totals、completion rate、agent/persona usage 可以保留现有查询，只要不重新引入另一套分数真相。
- `web/src/app/admin/users/[id]/page.tsx` 必须继续保留当前页面壳和 completed-session report drill-in，但把“进步率 + generic 折线图”改成主管可读的连续变化摘要，并在 progress 区域提供本地 empty/error state，而不是把失败只留在 `console.error`。

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py -k 'progress or stats'` — 锁住 `/progress` repeated issue/goal、`not_evaluable_session_count`、`should_switch_focus` 与 `/stats` 对齐，并让 failure-path/empty-state 语义在 focused API 断言里可检查。
- `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'`
- Manual/runtime review — 先执行 `cd backend && venv/bin/alembic upgrade head`，再打开 `/admin/users/{id}`：页面必须能直接回答“有没有进步 / 总卡在哪 / 下一轮继续补同一问题还是切换重点”；如果 progress 读取失败或没有可评估数据，页面必须显示本地 inline 状态；如果本地环境因缺少 `conversation_messages.transcript_metadata` 报错，必须把它识别为 migration/blocker 而不是前端 regressions。

## Observability / Diagnostics

- Runtime signals: `practice_history_projection_query` 及其 evaluable/not-evaluable projection 摘要、admin `/progress` 返回的 repeated issue/goal buckets、`should_switch_focus` 与 recommendation reason、page-level progress empty/error state。
- Inspection surfaces: `backend/src/common/analytics/history_service.py`, `GET /api/v1/admin/users/{id}/progress`, `GET /api/v1/admin/users/{id}/stats`, `GET /api/v1/admin/users/{id}/sessions`, `web/src/app/admin/users/[id]/page.tsx`, focused backend/web tests.
- Failure visibility: 显式 `not_evaluable_session_count`、重复问题/目标 bucket、inline progress error/empty copy、以及测试里锁住的 `/stats` / `/progress` 对齐断言。
- Redaction constraints: 只暴露 projection 已有的 `issue_type` / `goal_type` / summary 文本与计数；不新增 transcript 原文、知识库全文或其他敏感材料到趋势视图。

## Integration Closure

- Upstream surfaces consumed: `backend/src/common/analytics/history_service.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/effectiveness/evaluator.py`, `backend/src/admin/api/users.py`, `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/lib/session-evidence.ts`, `web/src/app/admin/users/[id]/page.tsx`.
- New wiring introduced in this slice: HistoryService supervisor snapshot -> admin `/progress` + aligned `/stats` -> typed web contract -> `/admin/users/[id]` progress summary / local failure state.
- What remains before the milestone is truly usable end-to-end: S07 和 S08 仍需完成 milestone 级整合验收；但 S06 自身不应再依赖新的 scorer、第二条事实线或额外 supervisor-only 报告页。

## Tasks

- [x] **T01: 把主管连续变化聚合收口到 HistoryService 并对齐 admin stats/progress** `est:4h`
  - Why: 先把 backend 收成一条 projection-backed 事实线，否则 `/progress`、`/stats` 和已完成 session 预览会继续在同一页面上讲三套不同真相。
  - Files: `backend/src/common/analytics/history_service.py`, `backend/src/admin/api/users.py`, `backend/tests/unit/test_history_service_evidence_projection.py`, `backend/tests/integration/test_admin_users_api.py`
  - Do: 先写 failing unit/integration tests，再在 `HistoryService` 新增 supervisor progress snapshot / grouping helper，基于 completed-session projection 计算 truthful `day/week` trend、evaluable/not-evaluable counts、重复 `main_issue.issue_type` / `next_goal.goal_type`、保守 `should_switch_focus` 与 recommendation；随后把 `/progress` 改读它，并把 `/stats` 的平均/最好/最差分对齐到同一 summaries，同时保留 raw completion/usage 统计。
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py`
  - Done when: `/progress` 与 `/stats` 的 score-bearing fields 都来自同一 projection-backed summaries，integration tests 证明 repeated blocker / next goal / not-evaluable semantics 与 `/sessions` preview vocabulary 对齐。
- [x] **T02: 把 `/admin/users/[id]` 改成主管可读的连续变化视图** `est:3h`
  - Why: backend 即使已经聚合出正确 snapshot，如果页面仍只显示 improvement 百分比和 generic 曲线，主管仍然无法据此判断是否进步或是否该换训练重点。
  - Files: `web/src/lib/api/types.ts`, `web/src/lib/session-evidence.ts`, `web/src/app/admin/users/[id]/page.tsx`, `web/src/app/admin/users/[id]/page.test.tsx`
  - Do: 扩展 `UserProgressResponse` 到 richer supervisor contract，必要时在 `web/src/lib/session-evidence.ts` 增加 issue/goal label helpers；把 page 的 progress 区域改成“趋势 + 重复卡点 + 重复下一步 + not-evaluable 说明 + switch-focus 建议”的摘要面，并加本地 inline empty/error state；保留现有 session table 与 canonical `查看报告` drill-in。
  - Verify: `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'`
  - Done when: 页面 test 证明 progress 区域能直接回答“有没有进步 / 卡在哪 / 要不要换重点”，并且 progress 加载失败或无可评估数据时不会把整页塌成 console-only failure。

## Files Likely Touched

- `backend/src/common/analytics/history_service.py`
- `backend/src/admin/api/users.py`
- `backend/tests/unit/test_history_service_evidence_projection.py`
- `backend/tests/integration/test_admin_users_api.py`
- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
