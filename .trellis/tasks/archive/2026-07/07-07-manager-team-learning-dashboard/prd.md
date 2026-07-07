# 管理者团队学习看板与权限收窄

## Goal

销售组长/培训经理（training_manager）当前被迫钻进 `/admin/*` 的系统治理页面（题库、评分规则、AI prompt、知识库检索策略等 20+ 配置页）才能了解下属学习情况，角色严重错配。本任务为该角色打造专属「团队学习看板」+ 收窄其 admin 权限，让管理者只关注带教（谁学到哪、谁卡关、谁需辅导），不碰与带教无关的系统配置。

## What I already know

### 角色与权限现状
- 系统有 14 种角色（roles.py），training_manager 是其中之一，定位为「销售组长/培训经理」。
- admin API 权限校验是**散落式**：20+ 个 `backend/src/admin/api/*.py` 各自调 `require_role([...])`（service.py:601）。`require_role` 是集中函数，改它可全局影响，但每个 router 自己声明 allowed_roles。
- training_manager 现在能进 `/admin/*` 全部页面（含 test-bank、prompts、rag-profiles、scoring-rulesets、business-rules、governance、retrieval-strategies 等与带教无关的配置）。
- 现有 `/dashboard` 主页**无角色分流**，training_manager 登录后看到和学员一样的「自己的学习」视图。

### 数据基础
- `team_department` 过滤能力**后端已具备**：audio_regrade_service、material_service、training_record_service 都支持按 `team_department: str | None` 过滤。
- `User` 表有 `department` 字段，但**无 `reports_to` 上下级关系字段**——"我的下属"目前只能靠部门归属推断。
- journey 数据（training_journey_service.py）含 modules/overall_progress/module status/stage/next_action，是看板聚合的核心数据源。
- `/admin/analytics` 已有部门维度统计（department_issue_buckets、active_departments），但是治理视角，非带教视角。

### 约束（来自项目规则）
- AGENTS.md：禁止只靠前端隐藏按钮做权限，权限以后端校验为准；普通用户界面不得展示工程字段/内部术语（E2E/test/mock/traceId/workflow/raw JSON/数据库主键等）。
- 上下文内完成原则：管理者在看板里看到某个下属需辅导时，应能就地查看详情/发起点评，不跳转到另一个模块。
- 前端按任务组织，不按数据库对象组织；页面契约必须含目标用户/使用场景/主操作/核心信息/状态规范。

## Assumptions（待 brainstorm 验证）

- 「我的下属」= 与 training_manager 同 department 的 learner/user 角色用户（部门即团队）。若实际需跨部门带教或显式上下级，需加 reports_to 字段 + migration。
- MVP 看板放 `/dashboard/team` 新路由，training_manager 登录后默认进此看板（学员仍进 `/dashboard`）。
- 权限收窄用「白名单」：training_manager 默认看不到任何 admin 配置页，只显式开放 records（学员记录）、analytics（团队分析）、sales-trainer 子页的查看权限。
- 看板 MVP 含：团队学员列表 + 每人当前关卡/进度 + 成绩概览 + 待辅导标记；暂不做趋势/对比/历史快照。

## Open Questions

1. ~~【Blocking】「我的下属」如何定义~~ → **已定：方案 A 部门即团队**（同 department 的 learner/user，不加 reports_to 字段）
2. ~~【Preference】看板放哪~~ → **已定：方案 A `/dashboard/team` 新路由 + 登录后按角色分流**
3. ~~【Preference】权限收窄范围~~ → **已定：training_manager 当前已被收窄**（前端 sidebar 只对 admin 显示入口，后端 403），无需新增收窄工作
4. ~~【Preference】看板 MVP 维度~~ → **已定：套餐 C**（核心维度 + 团队汇总 + 待辅导标记 + 下钻跳转）

## Requirements（已收敛）

- R1 新增 `/team` 团队学习看板页面，training_manager 登录后默认跳转此页（learner 仍进 `/`）。注：采用 `/team` 而非 PRD 早期字面 `/dashboard/team`，因现有主页 URL 是 `/`（route group `(dashboard)` 不进 URL），无 `/dashboard` 前缀；详见 implementation-notes.md「URL 决定」
- R2 看板展示本部门（同 department）所有 learner/user 的学习情况：学员列表 + 每人当前关卡（module/stage）+ 整体进度 + 成绩概览（通过/未通过/待判分）
- R3 看板顶部团队汇总卡片：总人数 / 进行中 / 已完成 / 待辅导数
- R4 看板「待辅导标记」：自动标出卡在某关、未通过、长时间无进展的学员，规则硬编码合理默认值（非可配置）
- R5 看板支持下钻：点学员名跳转到 `/team/[learnerId]` 只读详情页，展示该学员完整 journey（所有 module 进度/成绩/反馈），复用后端 `GET /admin/journeys/{learner_id}` 接口
- R6 sidebar 为 training_manager 增加「我的团队」入口（现有 sidebar 只对 admin 显示管理后台，training_manager 无任何管理入口）
- R7 后端权限复用现有 `can_view_sales_trainer_records`（含 training_manager）+ team_department 过滤，training_manager 只能看本部门，不能传任意 department 绕过
- R8 看板与详情页覆盖 loading / empty（无部门/无学员）/ error / 无权限 状态，不泄露工程字段/内部术语

## Acceptance Criteria

- [ ] AC1 training_manager 登录后自动跳转 `/team`，看到本部门学员列表及各自进度
- [ ] AC2 看板顶部显示团队汇总（总人数/进行中/已完成/待辅导）
- [ ] AC3 待辅导标记正确标出卡关/未通过/停滞学员
- [ ] AC4 点学员名跳到 `/team/[learnerId]` 只读详情页，展示完整 journey
- [ ] AC5 training_manager 只能看本部门学员（传其他 department 被后端拒）
- [ ] AC6 看板与详情页覆盖 loading/empty/error/无权限 状态
- [ ] AC7 页面不泄露工程字段/内部术语（无 traceId/workflow/raw JSON/数据库主键）
- [ ] AC8 training_manager 自己无 department 时显示友好 empty 提示
- [ ] AC9 权限回归测试：training_manager 可调 `/admin/journeys`，普通 learner 不可调

## Definition of Done

- 前端看板 + 详情页单测覆盖各状态 + 下钻
- 后端权限测试覆盖 training_manager 只看本部门（team_department 过滤不被绕过）
- 集成测试覆盖看板聚合（按部门过滤 journey）
- lint/typecheck/CI 绿
- 无吞异常/伪造成功
- 交付说明含影响、兼容性、回滚路径

## Out of Scope（explicit）

- training_lead / content_admin 等其他角色的看板（本次只做 training_manager，但过滤逻辑预留扩展）
- 趋势/对比/历史快照（需新增数据模型，后续迭代）
- regrade/补训/发消息等写操作从看板触发（MVP 只看不做）
- 待辅导规则可配置（MVP 硬编码默认值，预留规则集中点）
- 全量 admin 页面重构（training_manager 权限已收窄，无需新增工作）

## Technical Approach

### 分层实现（按 PR 切分）

**PR1（后端权限确认 + 看板 API 透传，低风险）**
- 确认 `GET /admin/journeys` 已支持 training_manager + team_department 过滤（已具备，仅补测试）
- 新增 `GET /admin/journeys/summary`（团队汇总卡片数据：总人数/进行中/已完成/待辅导）——或复用 `get_admin_analytics` 看是否够用
- 后端权限测试：training_manager 只看本部门、learner 被拒

**PR2（前端看板页面 + sidebar 入口 + 登录分流）**
- 新建 `web/src/app/(dashboard)/team/page.tsx` 看板页
- sidebar 增加「我的团队」入口（仅 training_manager 可见）
- 登录后角色分流：training_manager → `/team`，learner → `/`
- 看板覆盖 loading/empty/error/无权限

**PR3（下钻详情页 + 待辅导标记，中风险）**
- 新建 `web/src/app/(dashboard)/team/[learnerId]/page.tsx` 只读详情页
- 复用 `GET /admin/journeys/{learner_id}` 渲染完整 journey
- 待辅导标记逻辑（硬编码默认规则）+ 单测

### 关键约束
- 后端复用现有 `list_admin_journeys` + `get_admin_journey`，零新增业务逻辑
- training_manager 权限走现有 `can_view_sales_trainer_records`，不改权限模型
- 前端不引入新依赖，复用现有 UI 组件库
- 看板数据量分页（现有 limit/offset，默认 50）

## Decision (ADR-lite)

**Context**：training_manager 被迫钻 admin 配置页了解下属学习，角色错配。需判断是"权限没收窄"还是"缺看板入口"。

**Decision**：
1. 「我的下属」用部门归属（方案 A），不加 reports_to 字段——MVP 快速闭环，组织结构复杂时再升级。
2. 看板独立路由 `/dashboard/team` + 登录分流，不改造现有 `/dashboard`——职责清晰，符合"按任务组织"。
3. MVP 套餐 C（核心 + 汇总 + 待辅导 + 下钻）——直击"知道谁要管"的痛点，下钻让带教闭环成立。
4. 权限不新增收窄——核实发现 training_manager 前后端均已无 admin 权限，真正缺失的是看板入口本身。
5. 下钻新建只读详情页，复用现有 journey 接口——不依赖 admin 页面。

**Consequences**：
- 部门即团队不支持跨部门带教，若未来需要升级到 reports_to（加字段 + migration）。
- 待辅导规则硬编码，未来要可配置需提取规则集中点。
- 看板模式可扩展给 training_lead（改过滤逻辑看全量）。

## Technical Notes

### 关键文件
- 角色：`backend/src/common/auth/roles.py`、`backend/src/common/auth/service.py:565 get_current_admin_user`（校验 is_platform_admin_role）
- journey 聚合：`backend/src/sales_trainer/services/training_journey_service.py`（list_admin_journeys:213 / get_admin_journey:182）
- journey API：`backend/src/sales_trainer/api.py:1547`（GET /admin/journeys）、`:1611`（GET /admin/journeys/{learner_id}）
- 权限：`backend/src/sales_trainer/permissions.py:108 can_view_sales_trainer_records`（含 is_sales_trainer_manager）
- 前端 sidebar：`web/src/components/layout/sidebar.tsx:133`（isAdmin/isSupport 判断，需加 training_manager 分支）
- 前端 dashboard：`web/src/app/(dashboard)/page.tsx`（登录落点，需角色分流）

### 数据可行性确认（brainstorm 探索）
- **后端 API 已具备**：`GET /api/v1/admin/journeys` 已暴露 `list_admin_journeys`，支持 `team_department` 过滤 + 分页。
- **权限已具备**：`can_view_sales_trainer_records` 含 `is_sales_trainer_manager`，training_manager 可调用。
- **journey 数据字段齐全**：module 含 stage/status/passed/failed/score/next_action/latest_outcome，overall_progress 含总数/完成数/通过数/待补救数。
- **单学员接口已具备**：`GET /admin/journeys/{learner_id}` 返回完整 journey。
- **结论**：后端零新增业务逻辑，核心工作在前端新建看板 + 详情页 + sidebar 入口 + 登录分流。

### 待辅导判定规则（MVP 硬编码默认值）
- 卡关：module stage="in_progress" 且 `next_action` 字段含需关注提示（journey 已有 next_action，MVP 不算精确天数）
- 未通过：latest_outcome.passed === false
- 停滞：overall_progress.completed_modules === 0 且创建时间超 7 天（用 journey.created_at/generation_time）
- 精确"卡关 N 天"判定留后续迭代（需新增停滞时间计算 + 可配置阈值）
- 前端 dashboard：`web/src/app/(dashboard)/page.tsx`（无角色分流）
- 前端 admin 页面：`web/src/app/admin/*`（20+ 子页）

### 数据可行性确认（brainstorm 探索）
- **后端 API 已具备**：`GET /api/v1/admin/journeys`（api.py:1547）已暴露 `list_admin_journeys`，支持 `team_department` 过滤 + 分页。
- **权限已具备**：`can_view_sales_trainer_records`（permissions.py:108）含 `is_sales_trainer_manager`，training_manager 可调用该接口。
- **journey 数据字段齐全**：module 含 stage/status(not_started/in_progress/completed)/passed/failed/score/next_action/latest_outcome，overall_progress 含总数/完成数/通过数/待补救数。
- **结论**：看板后端零新增（复用现有 API），核心工作在前端新建 `/dashboard/team` 页面 + sidebar 入口 + 登录后角色分流。

### 待确认约束
- ~~是否需要给 User 加 reports_to 字段~~ → 不需要（方案 A）
- ~~training_manager 当前依赖哪些 admin 页面~~ → 已确认 training_manager 无 admin 权限（前后端均已收窄），无需收窄工作
