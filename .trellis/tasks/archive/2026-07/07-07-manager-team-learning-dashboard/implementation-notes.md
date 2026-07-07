# 实现笔记 — 管理者团队学习看板

> Main agent 维护的跨 PR 调研结论与待确认点。Sub-agent 实现时不应编辑此文件。

## PR1 调研结论（main agent 预先验证，指导 sub-agent）

### AC5 后端权限已保证（无需新增后端逻辑）

`backend/src/sales_trainer/services/training_journey_service.py:347-348` `_list_learners_for_admin`:
```python
if team_department is not None and department and department != team_department:
    return [], 0
effective_department = team_department or department
```

- training_manager（`_team_scope` 返回本部门，非 None）传**不等于本部门**的 department → 返回空列表，无法越权看其他部门
- training_manager 传自己的 department 或不传 → `effective_department = team_department`，只看本部门
- admin/super_admin（`_team_scope` 返回 None）→ `effective_department = department`，可看任意部门（符合预期）

**结论**：AC5「training_manager 只能看本部门」由后端强制，前端无法绕过。PR1 只需补回归测试固化此行为，不需改后端逻辑。

### Summary 接口结论：复用 analytics，不新增

`GET /admin/journeys/analytics`（api.py:1580）返回 `TrainingJourneyAnalyticsResponse`，已含看板汇总所需全部字段：

| 看板需要 | analytics 字段 | 位置 |
|---------|---------------|------|
| 总人数 | `summary.learner_count` | TrainingJourneyAnalyticsSummary:3053 |
| 已完成 | `summary.passed_learner_count` | :3055 |
| 待辅导数 | `summary.risk_learner_count` | :3056 |
| 进行中 | `funnel[].learner_count`（stage=in_progress） | TrainingJourneyAnalyticsFunnelEntry:3061 |
| 通过率 | `summary.pass_rate` | :3057 |
| 待辅导学员详情 | `risk_learners[]` | TrainingJourneyAnalyticsRiskLearner:3124 |

`risk_learners` 已带 `risk_reasons`/`risk_module_count`/`risk_module_keys`/`training_stage` —— **PR3 待辅导标记可复用后端已算好的 risk，无需前端硬编码判定**（PRD R4 硬编码规则可改为"复用 analytics.risk_learners + 前端补充停滞天数"，待 PR3 确认）。

**PR1 结论**：不新增 `/admin/journeys/summary` 接口，前端直接调 `/admin/journeys/analytics`。

## PR2 落点（预先调研，sub-agent 实现时参考）

### Sidebar 入口位置
`web/src/components/layout/sidebar.tsx:133-135`:
```ts
const isAdmin = currentUser?.role === "admin";
const isSupport = currentUser?.role === "support";
const canViewRuntime = isAdmin || isSupport;
```
- 现有「系统」区（运行状态/管理后台）只对 admin+support 可见（:175 `canViewRuntime`）
- training_manager 既非 admin 也非 support → 看不到任何管理入口
- **PR2 改动**：加 `isTrainingManager = currentUser?.role === "training_manager"` 分支，新增「我的团队」入口（href 待定，见下）放在主菜单区或独立「团队」分区

### 登录后分流
`web/src/app/(auth)/login/page.tsx:160,188` 登录成功 `router.push("/")`。
- 根路由 `/` 实际渲染 `web/src/app/(dashboard)/page.tsx`（Next.js route group，`(dashboard)` 不进 URL）
- **PR2 改动**：training_manager 登录后改跳团队看板路由；learner 仍跳 `/`

### URL 决定（已定，假设，待交付说明标注）

**采用 `/team`**（don't-ask 模式下基于代码现状的合理假设）。

依据：
- 现有主页 URL 是 `/`（route group `(dashboard)` 不进 URL），全站无 `/dashboard` 前缀
- PRD 字面 `/dashboard/team` 与现有架构层级不一致，且 `/dashboard` 本身无页面会 404
- `/team` 与现有主页 `/` 同级，改动最小，无重定向风险

文件路径：
- 看板：`web/src/app/(dashboard)/team/page.tsx` → URL `/team`
- 详情：`web/src/app/(dashboard)/team/[learnerId]/page.tsx` → URL `/team/[learnerId]`
- 登录分流：training_manager → `/team`，learner → `/`

**与 PRD 的偏差**：PRD R1/AC4 写 `/dashboard/team`，实际实现用 `/team`。原因见上。交付说明需标明此偏差，若用户坚持 PRD 字面值可回退改文件路径（机械改动）。

### 前端 API client 落点
`web/src/lib/api/client.ts`（4825 行）末尾是 domains 组织（presentations/internal）。PR1 sub-agent 在此新增 `journeys` domain 或在现有结构加方法。types.ts:4823 起已有 `TrainingJourney*` 类型，需确认是否已有 `TrainingJourneyListResponse`/`TrainingJourneyAnalyticsResponse` 对应类型，缺则补。

## PR3 落点

### AC5 详情页权限（后端已保证）
`get_admin_journey`（training_journey_service.py:200-205）：team_department 非空且 `learner.department != team_department` → 404 `[TRAINING_RECORD_NOT_FOUND]`（不泄露学员是否存在）。training_manager 调跨部门学员详情会被拒。PR3 无需补后端。

### 待辅导标记（已调研，PR3 sub-agent 直接采纳）
**复用 analytics.risk_learners，不前端硬编码 PRD R4 三规则**（R4 硬编码规则改为复用后端已算结果）。

- 后端 `_analytics_risk_learners`（:1910）已算出 risk_learners，条件：module.passed===false 或 status ∈ RISK_MODULE_STATUSES
- risk_reasons 格式：`{module_key}:not_passed` 或 `{module_key}:status:{status}`（:1944-1949）
- ⚠️ **risk_reasons 是工程 key，禁止直接展示**（AGENTS.md 禁止泄露内部术语）。PR3 前端需建 risk_reason → 中文映射表，例如：
  - `business_skills_exam:not_passed` → "商务技巧考试未通过"
  - `{module_key}:status:{status}` → "{模块名}状态异常：{状态中文}"
  - module_key → 中文模块名映射需从 journey.modules[].title 取（不是工程 key）
- 停滞天数判定（PRD R4「停滞」）：journey 无停滞时间字段，analytics 也未算。MVP 选项：①放弃停滞判定，只用 risk_learners（未通过+状态异常）；②前端用 journey.generated_at 与 module 开始时间算（若 module 有 started_at）。PR3 sub-agent 评估 module 字段后决定，倾向 ①（MVP 简化，停滞判定留后续迭代，记入 Out of Scope 补充）。

### TrainingJourneyResponse 字段（PR3 详情页渲染）
完整字段（schemas.py:3021）：journey_id/learner_id/learner_name/department/path_key/path_revision_id/path_revision_no/source/legacy_snapshot_only/role_capabilities/learner_level/role_level/training_stage/modules/overall_progress/retraining_requests/diagnostics/generated_at。
- modules: TrainingJourneyModuleProgress[]（含 stage/status/passed/score/next_action 等，PR3 渲染每关进度）
- overall_progress: TrainingJourneyOverallProgress（含总数/完成数/通过数）
- PR3 详情页复用 `api.admin.salesTrainer.getAdminJourney(learnerId)`（PR1 已加）

## Deviations

暂无。PR1 sub-agent 进行中。
