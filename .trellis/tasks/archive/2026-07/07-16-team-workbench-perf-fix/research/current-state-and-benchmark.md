# 当前链路核验与基准口径

## 1. 路由边界

| 路由 | 用户任务 | 当前性能结论 |
|---|---|---|
| `/admin/teams` | 平台管理员维护 Team、组长、成员关系 | 三个接口并行；团队接口固定批次查询。现有空库浏览器样本约 17–27ms/API、196–291ms 可用时间，不支持把卡顿归因于 Journey/Workbench。 |
| `/team` | 销售组长查看训练进展、风险和同期对比 | 当前存在 Journey 全树 N 次投影、Workbench 内存日期过滤、逐 learner 汇总/分数查询和输入即请求。此任务只处理该链路。 |

禁止用 `/team` 的后端瓶颈解释 `/admin/teams` 的首次导航或客户端 JS 就绪问题。

## 2. 代码证据

| 发现 | 代码位置 | 对实施的约束 |
|---|---|---|
| 首屏四请求并行 | `web/src/app/(dashboard)/team/page.tsx` 的 `load()` | 保留两期并行；不能描述成串行。 |
| 每键更新 URL | 同页 `updateParams()` + 搜索 `onChange` | 用草稿 + ≥300ms applied query。 |
| 刷新整页 Skeleton | 同页单一 `loading` | 拆首次/刷新/分区错误状态。 |
| Journey 列表逐 learner 全投影 | `backend/src/sales_trainer/orchestration/admin_api.py::learner_journeys` | 列表改批量摘要；详情保持完整投影。 |
| Lesson 投影包含额外查询 | `journey_service._project()` → `LessonActivityHandler.project()` → `LearningProgressService.get_study_content()` | 只批量 attempts 不够，必须批量 lesson content/chapter/progress。 |
| 列表无条件 commit | `learner_journeys` 尾部 | 无真实 revision 自愈时不得提交。 |
| sessions/tasks Python 日期过滤 | `SupervisorReviewService._filtered_sessions/_filtered_training_tasks` | SQL 使用包含性边界，补 datetime 兼容测试。 |
| Workbench 复用完整 Insights | `supervisor/api.py::get_team_workbench` | 建轻量投影，响应 JSON 不变。 |
| learner summary 串行 await score | `SupervisorReviewService._learner_summaries/_learner_summary` | Workbench 不需要 latest_score，禁止逐人查询/refresh。 |
| 无用字段判断曾被夸大 | `get_team_insights()` | Workbench 最终未返回 readiness/retraining candidates；没有 calibration/ranking 证据。retraining 数据仍可能参与 weakness fallback，需保留语义。 |

## 3. 已知消费者与契约

`GET /admin/newcomer-training/journeys` 的已知前端消费者只有：

1. `/team`：总体进度、当前阶段、风险标题；详情链接使用独立 learner detail 路由。
2. `/admin/newcomer-training/learners`：总体进度、primary next action、Team；详情同样使用独立路由。

因此列表可以使用显式 summary DTO，避免返回 phases/modules/activities 全树。不能返回“字段缺失但仍声称是 JourneyResponse”的半截对象。

## 4. 工作树风险

当前分支 `codex/newcomer-path-live-preview-layout` 有大量未提交改动。目标文件中的 TeamScopePolicy、team/search 参数、scope/workbench API 和 `/team` 页面均属于已有工作，不是本性能任务可以回退的基线。

执行者必须：

- 先读目标文件的当前 diff；
- 增量修改；
- 不格式化/重写无关区域；
- 不把已有 Team/Scope 改动一起归因于性能任务；
- 不触碰 `/admin/teams`。

## 5. 统一基准协议

### 数据规模

- 50、100、500 个有效 TeamMembership + enrollment。
- 每人至少：1 个 lesson 进度、1 个 attempt 型活动、1 个 TrainingTask、1 个 completed/scoring PracticeSession、对应 report/review。
- 日期数据同时包含边界内、边界等值、边界外和 null。

### 被测对象

1. `GET /admin/newcomer-training/journeys?limit=100&offset=0`。
2. `GET /supervisor/team/workbench` 当前期。
3. 当前期 + 上一期两个 Workbench 并行。
4. 浏览器 `/team` 从点击导航到主要内容稳定，并记录是否出现 dev indicator；共享/公开环境必须使用 production build。

### 采样

- 同一数据库、同一配置、同一进程模式。
- 预热 1 次，正式 10 次。
- 记录每次 elapsed ms、SQL count、HTTP status、JSON bytes。
- 报告 median 与 p95，并保留原始样本。
- 500 Journey 请求仍受 limit=100；必须同时记录 total 与 returned，不能拿 100 行响应声称完成 500 行渲染。

### 稳定门禁

- Query count 随 N 保持常数级；比绝对毫秒更适合 CI。
- 捕获 SQL 证明日期谓词存在于 database statement。
- 普通权限/功能集成测试不使用 `<0.5s` 等环境敏感断言。
- 绝对 latency 结果用于 before/after 证据；若无受控 PostgreSQL 环境，明确标记 SQLite/本机结果，不能外推生产 SLO。

## 6. 不可宣称的结论

- 未完成 50/100/500 对照前，不称 P0、不称数量级收益。
- 空数据库下的 `/admin/teams` 样本不能证明有数据时永远没有问题，但足以否定“当前由 listJourneys 拖慢”的说法。
- Glass/blur 不是已证实主因；本任务不做视觉性能归因。
- Workbench 未计算 calibration/ranking；不要把不存在的工作写进收益说明。
