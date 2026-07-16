# 销售组长 `/team` 工作台性能修复

## Goal

降低销售组长工作台 `/team` 在打开、切换团队/时间范围、搜索成员时的等待感，并让后端耗时随学员数增长时保持可解释、可测量。

本任务只针对 `/team`。平台管理员维护团队关系的 `/admin/teams` 是另一条链路，当前实测没有证据表明它被 `listJourneys` 或 Supervisor Workbench 拖慢，因此不在本任务中顺带修改。

## User and Page Contract

当销售组长在查看其被授权团队的训练进展时，帮助其基于新人训练路径、额外任务和确定性风险快速筛选成员、比较本期与上一同期，并得到可下钻的成员列表。

- **目标用户**：销售组长；平台管理员按既有权限也可只读查看。
- **页面模型**：Dashboard → 成员下钻；不是团队关系维护页。
- **核心对象**：显式 Team 范围内的学员、训练 Journey、当前/上一同期 Workbench。
- **主要任务**：在保留筛选上下文的前提下识别进度与需关注成员。
- **数据权威**：后端 TeamScopePolicy、Journey 投影、Supervisor Workbench；前端过滤不是权限边界。
- **状态要求**：首次加载、刷新、无团队、空团队、筛选无结果、部分请求失败、无权限、重试均有独立表达。

## Verified Current State

- `/team` 首屏并行请求 `scope`、`listJourneys(limit=100)`、本期 Workbench、上一期 Workbench，共四个请求；两次 Workbench 是并行而非串行。
- `listJourneys` 当前按已存在的 enrollment 查询学员，随后逐学员执行 `get_or_create_for_learner()` 和完整 `_project()`，并在 GET 末尾无条件 `commit()`。
- 完整 Journey 投影不仅逐学员查询最新 attempts；每个 lesson 还会读取学习内容、章节与学习进度。列表消费者只需要进度、当前阶段、下一步和最多两条风险标题。
- Workbench 当前复用完整 `get_team_insights()`：sessions/tasks 先全量查询再用 Python 日期过滤；`_learner_summaries()` 串行逐人构建，并可能逐人读取/刷新分数。
- Workbench 路径会构造最终响应未返回的 readiness、retraining candidate 数据；没有证据表明它计算 calibration 或 ranking。风险 fallback 仍可能依赖 retraining 数据，优化时不得误删语义。
- 搜索框每输入一个字符就更新 URL，继而重打服务端请求；`只看需关注` 仅做本地过滤，不会重新请求。
- 每次筛选/搜索把已有页面替换成整页 Skeleton；四个请求中任一失败会让整页失败。
- 当前相关文件已经包含尚未提交的 Team/Scope 功能改动。本任务必须在其上增量实施，禁止 reset、覆盖或回退这些改动。

## Decisions (ADR-lite)

1. **路由边界**：只优化 `/team`；`/admin/teams`、管理后台导航预取、后台页面服务端化不在范围内。
2. **风险等级**：P2。未取得 50/100/500 学员基准前，不使用“P0”或“数量级提升”等结论。
3. **对比 UX**：继续并行请求本期与上一同期两个 Workbench；不合并接口、不删除“较上一同期”。
4. **Journey 列表**：同一列表接口改为显式摘要 DTO；详情 `/journeys/{learner_id}` 继续返回完整 Journey，并保留首次读取创建 enrollment / 单对象自愈语义。
5. **列表 enrollment 语义**：列表只返回已有 enrollment，不能为了“模型完整”给所有 Team 成员批量创建 enrollment。若页面内 enrollment revision 过期，允许一次批量自愈；只有确实写入时才提交。
6. **Workbench 语义**：新增/使用专门的轻量 Workbench 投影，不再先构造完整 Insights 再丢字段；权限、search/team/date、风险 fallback、常见问题和响应形状保持兼容。
7. **前端状态**：URL 仍是已应用筛选的权威；搜索草稿本地即时响应，≥300ms 后才写 URL。刷新保留已有内容，并显式显示局部更新/局部失败。
8. **500 人口径**：500 是底层 Team 数据规模的性能基准。当前 Journey API 单页上限 100，本任务不扩展分页；500 场景必须记录 `total=500 / returned=100`，不得把单页结果宣称为完整 500 人视图。

## Requirements

### R1. 可复现基准先行

- 在修改性能路径前建立同一套 50/100/500 学员 fixture，覆盖：已发布路径、lesson 进度、attempt 型活动、训练任务、完成 session、报告/评审数据。
- 分别记录 Journey 列表、单次 Workbench、两期并行 Workbench 与 `/team` 内容稳定时间。
- 每组至少预热 1 次、采样 10 次，记录 median、p95、SQL 数量与响应字节数；前后必须使用同一环境、同一数据和同一命令。
- CI 以“SQL 数量不随 N 线性增长”和功能断言为稳定门禁；本机毫秒值作为证据，不在普通集成测试里保留易抖动的 `elapsed < 0.5` 断言。

### R2. Journey 列表批量摘要

- 路由保持薄层；把批量读取、摘要投影和条件提交放入明确的 service/read repository。
- 一次读取分页 enrollment + learner，批量读取 Team、当前 revision、最新 attempts 与 lesson 章节/学习进度；禁止逐学员调用 `get_or_create_for_learner()` 或完整 `_project()`。
- 摘要 DTO 至少包含：学员、Team、path revision/title、当前阶段、总体进度、primary next action、最多两条风险标题。
- 摘要与完整 Journey 对相同 fixture 的进度、当前阶段、下一步、风险结果一致。
- 正常只读列表不得 `commit()`；仅批量自愈确实过期的 enrollment revision 时一次提交。详情 API 行为不变。
- 同步迁移两个已知消费者：`/team` 与 `/admin/newcomer-training/learners`；更新 TypeScript DTO、ViewModel、API 契约文档和测试。

### R3. Workbench SQL 下推与轻量投影

- `_filtered_training_tasks` 的 `created_at` 与 `_filtered_sessions` 的 `start_time` 使用 SQL `>= date_from` / `<= date_to`（同等语义亦可），不再全量取回后 Python 过滤。
- 无日期边界时保留现有 null/全量语义；naive/aware datetime 行为需有边界测试。
- `/supervisor/team/workbench` 不再调用完整 `get_team_insights()` 后丢弃字段；只读取当前响应所需数据。
- 成员摘要先按 learner 分组，再同步投影；禁止逐成员 `_session_overall_score()` / `refresh()` 查询。
- 不构造未返回的 readiness、retraining candidate、snapshot/config metadata、latest score；但需保留现有 common issues 与“无报告弱项时 retraining fallback”语义，可按需懒加载 fallback 数据。
- Workbench JSON 形状、本期/上一期比较、TeamScopePolicy、team/search/date 权限范围保持兼容。

### R4. `/team` 搜索与刷新体验

- 输入值立即更新本地草稿；停止输入至少 300ms 后才更新 URL 和触发新请求。连续输入多个字符只产生一次已应用搜索。
- 外部 URL 变化（返回/前进/分享链接）能同步回输入框；`只看需关注` 继续本地过滤且不发请求。
- scope 首次加载后不因 q/range/team 每次重复获取；手动刷新可显式刷新 scope。
- 区分 `initialLoading` 与 `isRefreshing`：只有首次无可展示数据时使用页面 Skeleton；刷新时保留现有内容，并以可访问的局部状态提示更新中。
- 处理竞态：旧请求晚返回不得覆盖新筛选结果；可用 AbortSignal 或 request generation guard。
- 部分失败不得伪装成全部成功：scope 失败可阻断；Journey、本期 Workbench、上一期 Workbench 分别保留已有数据、显示对应错误与重试路径。

## Acceptance Criteria

- [ ] 基准产物包含 50/100/500 学员前后数据、命令、环境、median、p95、SQL 数和响应大小；结论不超出数据。
- [ ] Journey 列表路径不再出现 N 次 `get_or_create_for_learner()`、完整 `_project()` 或 lesson 逐人读取。
- [ ] Journey SQL 数量在 1/50/100 返回行下保持常数级；500 数据集按 `limit=100` 明确记录返回口径。
- [ ] 无过期 enrollment 的列表 GET 不提交；存在过期 revision 时批量自愈且只提交一次。
- [ ] session/task 日期条件可从捕获的 SQL 中证明已下推，边界包含且行为与旧逻辑一致。
- [ ] Workbench SQL 数量不随 50/100/500 学员线性增长；不再逐人查分或刷新 session。
- [ ] Workbench 响应、风险 fallback、常见问题、权限、空团队和搜索行为回归通过。
- [ ] 搜索不会每键更新 URL/触发请求；防抖测试使用 fake timers 验证 ≥300ms。
- [ ] 非首次筛选/搜索不全页 Skeleton；旧数据保留，更新/失败/重试状态可见且可访问。
- [ ] 本期与上一同期仍并行请求并正确展示比较；上一期失败时不把当前期伪装成完整比较结果。
- [ ] `/admin/teams` 代码没有因本任务被修改。

## Definition of Done

- 功能、契约、权限、空/无结果/错误/部分失败和竞态测试齐全。
- 后端 focused unit/integration/performance tests、Ruff、Mypy 通过；前端 focused Vitest、TypeScript、ESLint 通过。
- 使用 CodeGraph `impact/affected` 复核共享函数影响，并按 deterministic quality selector 扩大必要回归。
- 实际渲染 `/team`，验证慢网、窄屏、200% zoom、键盘焦点、长姓名与刷新状态。
- 基准前后证据写入任务目录；没有基准支撑时不宣称数量级收益。
- 无新依赖、无 migration、无无关重构；保留工作树中既有 Team/Scope 修改。

## Out of Scope

- `/admin/teams` 专属性能、后台侧栏 prefetch、后台 Server Component 化。
- 合并本期/上一期 Workbench、删除对比文案、全站 React Query 迁移。
- Glass/blur 或视觉重做、Insights 产品功能重做。
- Journey 超过 100 行的分页/虚拟化产品设计；只记录其在 500 数据规模下的口径和残余风险。
- 新索引或 migration；只有 EXPLAIN/基准证明现有索引不足时另提 P1 数据库任务。

## Execution Slices

1. **Slice 0 — 基准与结构性回归测试**：先固定 fixture、SQL 捕获和 baseline。
2. **Slice 1 — Journey 批量摘要**：后端 read service/DTO/契约 + 两个前端消费者适配。
3. **Slice 2 — Workbench 轻量投影**：日期 SQL 下推、去逐人分数查询、保留响应语义。
4. **Slice 3 — `/team` 交互硬化**：搜索防抖、scope/data 分载、刷新/部分失败/竞态状态。
5. **Slice 4 — 50/100/500 复测与完整门禁**：产出 before/after 报告，按证据收口。

## Open Questions

无阻塞问题。若执行中发现 500 人必须在同一页面完整浏览，应停止扩展本任务，单独提出分页/聚合设计，而不是静默把性能修复变成列表重构。
