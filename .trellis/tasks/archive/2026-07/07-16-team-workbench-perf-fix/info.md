# 实施设计与任务拆解

## 0. 执行前护栏

1. 当前工作树有大量未提交改动，且以下目标文件已被其他任务修改：
   - `backend/src/sales_trainer/orchestration/admin_api.py`
   - `backend/src/supervisor/api.py`
   - `backend/src/supervisor/service.py`
   - `web/src/app/(dashboard)/team/page.tsx`
   - `web/src/lib/team-journey/view-models.ts`
2. 先对目标文件保存 `git diff -- <paths>` 证据；只做增量编辑。禁止 reset、checkout、覆盖整文件或顺手整理无关 diff。
3. `/admin/teams` 与 `/team` 是不同产品链路。本任务不得触碰 `web/src/app/admin/teams/**` 或 `backend/src/admin/api/teams.py`。
4. 先创建 `implementation-notes.md`，发现偏离本计划时记录原因、保守选择和后续影响。

## Slice 0 — 基准与红灯测试

### 目标

在改变实现前固定“慢在哪里”和“什么算不回归”，避免用单次本机耗时替代结构证据。

### 工作项

1. 新增 `backend/tests/performance/test_team_workbench_performance.py`（名称可按现有规范微调）：
   - 复用 `sqlalchemy.event.before_cursor_execute` 捕获 SQL；忽略 PRAGMA/SAVEPOINT。
   - fixture 同时创建 Team/leader/membership、发布路径、enrollment、lesson progress、attempt、TrainingTask、PracticeSession、ComprehensiveReport、SupervisorReview。
   - 数据规模参数化为 50/100/500。
   - Journey 在 500 数据规模下请求 `limit=100`，断言 `total=500`、返回 100，并单独记录口径。
   - 记录 endpoint elapsed、query count、serialized response bytes；预热 1 次、采样 10 次。
2. 把 `backend/tests/integration/test_team_lead_insights_scope.py` 中环境敏感的 `elapsed < 0.5` 移入性能证据，不让权限测试承担墙钟门禁。
3. 先写失败测试：
   - Journey 1→50→100 返回行时 SQL 数不应线性增长；当前实现应失败。
   - 捕获 SQL 必须包含 task/session 日期谓词；当前实现应失败。
   - Workbench 50→100 学员 SQL 数不应逐人增长；当前实现应失败。
4. 前端 `page.test.tsx` 先补失败用例：连续输入、刷新不卸载旧内容、上一期失败的局部状态、旧请求晚返回。

### 交付物

- `research/benchmark-before.md`：环境、提交/dirty 状态、命令、数据生成方式、每组原始样本、median/p95、SQL、响应大小。
- 红灯测试证据。不得为了让 baseline 绿而放宽断言。

## Slice 1 — Journey 批量摘要

### 目标

把“分页列表读取”与“单学员完整 Journey”拆开，列表不再执行 N 次业务全树。

### 建议结构

- 在 `sales_trainer/orchestration` 下建立小型 `JourneySummaryReadService`（或同职责命名）与明确 DTO；不要继续把 SQL 堆入 `admin_api.py`。
- 可扩展现有 repository 以提供：
  - page enrollments + learners；
  - 当前 Team 映射；
  - 多 enrollment 的 latest attempts；
  - 所有 lesson content 的 chapter count 与 `(learner, content)` completed count。
- 批量依赖预载后，使用现有 completion 聚合规则生成 phase/path summary。不要复制另一套阈值或状态词。

### DTO 契约

同一 `GET /admin/newcomer-training/journeys` 返回列表摘要，而详情接口不变。建议显式字段：

```text
item
├── learner_id / learner_name / team
└── summary
    ├── path_revision_id / path_title
    ├── current_phase { phase_id, title, status } | null
    ├── progress { completed, completed_count, total_required, percent }
    ├── primary_next_action | null
    └── risk_labels[0..2]
```

不要用缺字段的“伪 JourneyResponse”冒充完整 Journey。

### 事务规则

- 列表查询只包含已有 enrollment；不创建缺失 enrollment。
- 先解析 active revision 一次。若本页 enrollment revision 已过期，一次批量 update/flush，成功响应前一次 commit；否则不 commit。
- 详情读取仍保留首次创建和单对象自愈，并继续显式提交。

### 测试

- 摘要与完整 Journey 在 lesson、quiz/audio 失败、全部完成、锁定阶段、无 attempt 下等价。
- SQL 数对 1/50/100 行保持常数级。
- 无 stale row 时无 commit；有 stale row 时一次批量更新/一次 commit。
- Team/search/offset/limit/total/越权/空范围保持原行为。
- 同步更新：后端集成测试、`docs/api-contract/sales-trainer.md`、前端 DTO/API 测试、admin learners 页面测试、`toTeamJourneyRow` 测试。

## Slice 2 — Workbench 轻量读模型

### 目标

保持 `/supervisor/team/insights` 完整能力，同时让 `/supervisor/team/workbench` 不再为未返回字段付费。

### 工作项

1. `_filtered_training_tasks` / `_filtered_sessions` 在 statement 上追加日期条件，再执行 SQL；删除对应 Python 列表过滤。
2. 在 `SupervisorReviewService` 增加专用 `get_team_workbench()`（或等价小型 read service），API 不再调用 `get_team_insights()`。
3. 只加载 Workbench 响应需要的 tasks/sessions/reports/reviews/users：
   - completion；
   - report-based weaknesses；
   - common issues（包括现有 review comment 语义）；
   - 每 learner 的 task completion 与 weaknesses。
4. 先计算 report weaknesses；只有为空且现有语义需要 fallback 时再批量读取 retraining tasks。
5. 不读取 snapshots，不构造 readiness/retraining_candidates/latest_score/config metadata，不逐 learner 调 `_session_overall_score()` 或 `refresh()`。
6. 先将 tasks/sessions/reviews/reports 按 learner/session 建索引，再同步 map；避免循环内反复全表过滤造成 O(N²) CPU。

### 测试

- 捕获 SQL 文本，断言 `training_tasks.created_at`、`practice_sessions.start_time` 边界已下推。
- `date_from == value`、`date_to == value` 均包含；越界和 null 与旧逻辑一致；覆盖 naive/aware 输入。
- 新 Workbench 与旧响应 fixture 深比较：completion、risk_groups、common_issues、learners。
- 无 report weakness 时 retraining fallback 仍返回；有 report weakness 时可证明不读取 fallback 表。
- 50/100/500 学员 query count 近似常量；权限、team/search、空团队、撤销 membership 回归通过。

## Slice 3 — `/team` 防抖、刷新与部分失败

### 状态拆分

建议至少拆成：

```text
scope:       data | initialLoading | error
journeys:    data | refreshing | error
current:     data | refreshing | error
previous:    data | refreshing | error
searchDraft: string
appliedQuery: URL q
```

### 工作项

1. 输入框绑定 `searchDraft`；300ms timer 后才 `router.replace`。URL q 变化时同步草稿，避免 back/forward 失真。
2. scope 初次单独加载；team/range/q 只刷新 Journey + 两期 Workbench。手动“刷新”再显式刷新 scope。
3. 首次无任何数据才显示 Skeleton。刷新时保留页面，列表工具栏附近使用 `role=status`/`aria-live=polite` 显示“正在更新团队数据”。
4. 使用 AbortSignal（若 facade 已支持）或 monotonically increasing request id；旧请求的 success/error/finally 均不得覆盖新请求状态。
5. `Promise.allSettled` 或独立请求状态保留部分结果：
   - scope 失败：阻断并提供重试；
   - Journey 失败：概览仍可显示，列表区域报错；
   - current 失败：路径列表仍可显示，额外任务概览报错；
   - previous 失败：当前值可显示，但比较文案明确“上一同期暂不可用”。
6. `riskOnly` 仍只改 URL/本地过滤，不触发后端请求。

### 测试

- fake timers：299ms 不更新 URL，300ms 后一次更新；快速输入 3 个字符只应用一次。
- applied q 改变才调用三个数据接口；scope 不重复调用。
- 刷新期间旧行仍存在且不出现整页 Skeleton。
- 后发请求先完成时，先发请求晚到不会覆盖。
- 三类部分失败均有区域级错误和重试；上一期失败不显示虚假的百分点。
- 本期/上一期仍在同一轮并行启动。
- 输入 label、刷新状态 live region、键盘 focus、长姓名与窄屏渲染检查。

## Slice 4 — 复测与收口

1. 用 Slice 0 完全相同的 fixture/命令采集 `research/benchmark-after.md`。
2. 生成 before/after 表：50/100/500 × Journey/Workbench/双期/页面稳定时间，包含 query count 和 payload bytes。
3. 性能结论只描述实际数据；若提升不足，保留结构修复事实并记录剩余瓶颈，不夸大。
4. 运行 CodeGraph `impact` 与 `affected`；图谱结果过宽或过旧时，以 deterministic selector 和直接调用者测试为下界。
5. 最终验证命令（按实际脚本/环境调整，但需记录自然退出结果）：

```bash
cd backend
pytest tests/unit/test_newcomer_orchestration_journey_service.py
pytest tests/integration/test_newcomer_orchestration_admin_api.py
pytest tests/integration/test_supervisor_retraining_api.py
pytest tests/integration/test_team_lead_insights_scope.py
pytest tests/performance/test_team_workbench_performance.py -m performance
ruff check src/ tests/
mypy src/

cd ../web
npx vitest run 'src/app/(dashboard)/team/page.test.tsx' \
  'src/app/admin/newcomer-training/learners/page.test.tsx' \
  'src/lib/team-journey/view-models.test.ts'
npx tsc --noEmit
npm run lint
```

6. 浏览器检查 `/team`：冷启动、慢网、连续输入、切换时间、上一期失败、返回/前进、窄屏、200% zoom、键盘焦点。

## 残余风险（不在本任务静默解决）

- Journey 单页仍为 100；500 人同队时不等于完整浏览能力。
- 两期 Workbench 仍传输两份 learner rows；本任务保留比较契约，不做合并接口。
- 若 PostgreSQL EXPLAIN 证明复合索引不足，另开 migration/P1 任务；不要在本任务凭感觉加索引。
- 当前工作树改动巨大，完整门禁失败时必须区分本任务回归与既有失败，不得吞掉或伪造成功。
