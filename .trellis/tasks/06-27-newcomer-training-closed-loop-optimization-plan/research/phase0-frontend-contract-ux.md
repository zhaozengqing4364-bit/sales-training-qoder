# Phase 0 子代理 C 审计报告

> 主题：前端契约、fail-closed 与 UI/UX
>
> 时间：2026-06-27
>
> 方法：只读分析；优先使用 CodeGraph CLI；未启动 dev server；未改业务代码

## 结论摘要

- 当前 learner 首页、商务技巧工作台、AI Coach、admin workbench、config center 已经形成可用骨架，但“路径单一真源”“capability 五层一致 fail-closed”“typed dashboard DTO”“移动端分析面板”四件事没有收口。
- 最大风险不在视觉，而在前端仍然保留 legacy/catalog fallback、admin 混用 learner 端点推状态、工作台卡片与 module nav 未受 capability 投影约束、部分成功路径 loading 状态不会复位。
- AI Coach learner 直链页已有相对明确的不可用态与重试态；但 admin AI Coach 配置页仍把一部分契约缺口吞进本地默认值，属于 fail-open 倾向。

## 1. 当前前端入口 / DTO / API client 事实与路径

### 1.1 API facade 现状

- `web/src/lib/api/client.ts:2038-2058, 2851-2854` 同时装配了四个域：
  - `api.salesTrainer`
  - `api.newcomerTraining`
  - `api.admin.salesTrainer`
  - `api.admin.newcomerTraining`
- `web/src/lib/api/domains/sales-trainer.ts:248-403` 的 `createAdminSalesTrainerDomain()` 不只是 `/admin/sales-trainer/*`，还把大量 `/admin/newcomer-training/*` 能力通过 `createAdminNewcomerTrainingDomain()` 重新挂进了 `api.admin.salesTrainer.*`。
- 结果是页面层已经出现“双 admin API surface”：
  - 页面 URL 主要是 `/admin/sales-trainer/*`
  - API 真实调用仍大量落在 `/admin/newcomer-training/*`

### 1.2 主要 learner 入口链路

| 入口 | 页面/Hook | API | 关键 DTO | 当前行为 |
|---|---|---|---|---|
| `/sales-trainer` | `web/src/app/(dashboard)/sales-trainer/page.tsx` | `api.salesTrainer.listUnits()` + `api.salesTrainer.listPaths()` | `SalesTrainerPath`, `SalesTrainerPathLevel` | 先尝试路径视图；无路径时退回 catalog fallback |
| 首页模块卡 | `web/src/components/sales-trainer/sales-trainer-module-grid.tsx` + `web/src/lib/sales-trainer/module-path.ts` | 依赖首页已有 `path`/`units` | `SalesTrainerModuleView` | business skills/coach 入口由 path level 决定；实时对练固定 disabled |
| `/sales-trainer/business-skills` | `useBusinessSkillsWorkbench()` | `api.salesTrainer.listUnits()`、`api.newcomerTraining.getModuleArticle()`、`api.newcomerTraining.getBusinessEtiquetteLearningUnits()`、`api.salesTrainer.listPaths()` | `NewcomerArticle`, `BusinessEtiquetteLearningUnit` | 工作台把文章、小单元、小测、coachHref 拼在前端 |
| `/sales-trainer/business-skills/coach` | `web/src/app/(dashboard)/sales-trainer/business-skills/coach/page.tsx` | `api.newcomerTraining.startAiCoachChatSessionStream()`、`getBusinessEtiquetteLearningUnits()`、`getBusinessEtiquetteAiCoachProgress()` | `AiCoachChatSessionPublicV1`, `BusinessEtiquetteAiCoachProgress` | 直链页存在不可用态、恢复态、流式错误态 |
| `/sales-trainer/audio/result/[submissionId]` | `web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx` | `useSalesTrainerSubmissionPoll()` + `api.salesTrainer.getUnit()` | `SalesTrainerAudioSubmission` | 轮询录音结果；unit 拉取失败时把通过线硬兜底成 70 |

### 1.3 主要 admin 入口链路

| 入口 | 页面/Hook | API | 关键 DTO | 当前行为 |
|---|---|---|---|---|
| `/admin/sales-trainer` | `web/src/app/admin/sales-trainer/page.tsx` | `api.admin.salesTrainer.getManagerDashboard()` | `SalesTrainerManagerDashboard` | 工作台只消费 summary/risk/weak/intervention，未消费 `module_summaries` |
| `/admin/sales-trainer/paths` | `page.tsx` + `use-path-config-center-workflow.ts` + `page-data.ts` | `api.admin.newcomerTraining.getPathConfig()`、`listPathConfigRevisions()`、`save/publish/rollback`，并混入 `api.newcomerTraining.getModuleArticle()` | `NewcomerPathConfigResponse` | config center 是 admin 页面，但“已绑定文章”仍走 learner 读接口 |
| `/admin/sales-trainer/articles` | `web/src/app/admin/sales-trainer/articles/page.tsx` | `api.learningContents.list()` + `api.newcomerTraining.getModuleArticle()` + `api.admin.newcomerTraining.bindModuleArticle()` | `LearningContent`, `NewcomerArticleBinding` | 绑定写走 admin，绑定读走 learner |
| `/admin/sales-trainer/questions/quiz-preview` | `web/src/app/admin/sales-trainer/questions/quiz-preview/page.tsx` | `api.newcomerTraining.getBusinessEtiquetteLearningUnits()` + `api.admin.salesTrainer.getBusinessEtiquetteUnitQuizPreview()` | `BusinessEtiquetteLearningUnit`, `BusinessEtiquetteUnitQuiz` | 小单元列表读 learner，题目预览读 admin |
| `/admin/sales-trainer/ai-coach` | `web/src/app/admin/sales-trainer/ai-coach/page.tsx` | `api.admin.newcomerTraining.getAiCoachConfig()`、`saveAiCoachConfig()`、`publishAiCoachConfig()` | `AiCoachAdminConfigLike` | 页面本地 `DEFAULT_CONFIG` 与契约默认值存在漂移 |

### 1.4 capability / nav / 直链的当前分层

- `web/src/app/admin/layout.tsx:9-24` 只做“角色级”进入 admin shell 的门槛，允许 `support/content_admin/newcomer_content_admin/training_lead/training_manager/ops/...` 全部进入 `/admin/*`。
- `web/src/components/layout/admin-shell.tsx:58-63` 只把销售训练管理角色约束在 `/admin/sales-trainer` 前缀内，不判断更细 capability。
- `web/src/components/layout/admin-sidebar.tsx:236-248, 282-305` 会读取 `api.admin.salesTrainer.getCapabilities()` 并仅在 sidebar 里调用 `salesTrainerAdminItemsForCapabilities()`。
- `web/src/components/admin/sales-trainer/module-nav.tsx:14-54` 只根据当前 pathname 展示固定分组，不接受 capability。
- `web/src/app/admin/sales-trainer/page.tsx:196-209` 直接渲染 `SALES_TRAINER_ADMIN_WORKBENCH_LINKS`，未经过 capability 过滤。

结论：

- capability 现在只真正约束了 sidebar。
- workbench card、module nav、页面直链、刷新后的直接 URL 访问没有形成同一套 fail-closed。

### 1.5 关键 DTO 现状

- `SalesTrainerPath` / `SalesTrainerPathLevel` 已经有较强结构化字段：
  - `goal_context`
  - `locked/lock_reason/status`
  - `primary_action_label/retry_action_label/review_action_label`
  - `ai_coach_availability`
- `SalesTrainerAudioSubmission` 仍然把以下关键快照定义为 `Record<string, unknown> | null`：
  - `material_snapshot`
  - `score_scheme_snapshot`
  - `task_brief_snapshot`
- `SalesTrainerManagerDashboard` 仍把以下聚合结果定义为宽松结构：
  - `summary: Record<string, unknown>`
  - `module_summaries: Array<Record<string, unknown>>`
  - `weak_dimensions: Array<Record<string, unknown>>`
  - `risk_learners: Array<Record<string, unknown>>`
  - `intervention_suggestions: Array<Record<string, unknown>>`
- `NewcomerPathConfigResponse.source` 只声明 `"active_revision" | "unit_backfill"`，但 `web/src/lib/sales-trainer/config-center-types.ts:49-58` 的治理模型已经额外接受 `"legacy_units"`。

## 2. 前后端契约漂移清单

### 2.1 P0 / P1 漂移

1. learner 首页仍保留 catalog / legacy fallback，不符合“active path revision 唯一真源”。
   - 证据：
   - `web/src/app/(dashboard)/sales-trainer/page.tsx:112-145, 242-244` 无路径时直接渲染 `CatalogSection`。
   - `web/src/lib/sales-trainer/module-path.ts:16-30, 260-277` 仍保留 `new_seller_modules_v1`、`LEGACY_GOAL_PATH_KEY`、`buildLegacyModuleViews()`。
   - 风险：
   - 前端会继续把“路径缺失/发布缺失”伪装成“还有可练单元”，与 audit-synthesis 的产品决策冲突。

2. capability projection 没有覆盖 sidebar 之外的四层入口。
   - 证据：
   - sidebar 过滤：`admin-sidebar.tsx:236-248`
   - module nav 静态：`module-nav.tsx:14-54`
   - workbench links 静态：`routes.ts:366-392` + `admin/sales-trainer/page.tsx:196-209`
   - admin layout 仅做角色级 gate：`admin/layout.tsx:9-24`
   - 风险：
   - 用户可以从工作台卡片、module nav、手输 URL 打开不该看到的页面，最终只在接口层吃 403，或者先看到页面骨架再报错。

3. admin 页面仍用 learner 端点侧推绑定态/可用态，且部分错误被吞成“缺绑定”。
   - 证据：
   - `admin/sales-trainer/articles/page.tsx:108-121` 读取当前绑定文章时调用 `api.newcomerTraining.getModuleArticle()`。
   - `admin/sales-trainer/paths/page-data.ts:80-90` 的 `loadBoundArticle()` 对任意 `Error` 都返回 `null`。
   - `web/src/lib/sales-trainer/config-center.ts:178-186, 222-226` 把 `boundArticle === null` 解释为 `article_missing`。
   - `admin/sales-trainer/questions/quiz-preview/page.tsx:40-47` 用 learner 的 `getBusinessEtiquetteLearningUnits()` 决定 admin 可预览单元。
   - 风险：
   - 403/500/网络错误可能被误渲染成“未绑定”“暂无小单元”“路径配置缺失”，把权限/传输故障伪装成业务状态。

4. admin workbench 与 manager dashboard 契约宽松，前端只消费少数字段。
   - 证据：
   - DTO 宽类型：`types.ts:6213-6220`
   - 页面只取 `risk_learners/weak_dimensions/intervention_suggestions`：`admin/sales-trainer/page.tsx:47-51`
   - `module_summaries` 完全未渲染。
   - 风险：
   - 后端即使已经输出模块维度、漏斗维度，前端也没有承接；字段漂移时只会显示 `--`，不容易被测试抓住。

5. `passed` 三态没有在所有页面保持一致。
   - 正例：
   - learner 商务技巧页：`business-skills/page.tsx:174-186, 291-305` 把 `passed === null` 视为“待评分”。
   - regrade panel：`quiz-attempt-regrade-panel.tsx:28-37` 把 `null` 渲染为“待判定”。
   - 反例：
   - admin 录音详情：`admin/sales-trainer/audio-submissions/[submissionId]/page.tsx:187-190` 使用 `submission.score_result.passed ? "是" : "否"`，`null` 会显示为“否”。

6. learner 录音结果页仍保留 `70` 硬兜底。
   - 证据：
   - `audio/result/[submissionId]/page.tsx:253-262`
   - 风险：
   - 一旦 `api.salesTrainer.getUnit()` 因配置/权限/网络失败，页面把真实的配置故障伪装成“通过线 70”。

7. admin AI Coach 默认值与销售训练契约文档存在漂移，`normalize()` 仍会对残缺 payload 做 fail-open。
   - 证据：
   - 契约要求的安全默认值来自 `docs/api-contract/sales-trainer.md`：
     - `generation_timeout_seconds=120`
     - `allowed_interaction_types=["single_choice","multiple_choice"]`
     - `allowed_training_card_types=["scenario_judgment"]`
     - `session_start_behavior="welcome_only"`
     - `auto_advance_enabled=false`
   - 页面本地 `DEFAULT_CONFIG`：
     - `generation_timeout_seconds=30`
     - 默认直接放开 `short_answer`
     - 默认直接放开三类 training card
     - `session_start_behavior="plan_then_wait"`
     - `auto_advance_enabled=true`
   - `normalize()`：`admin/sales-trainer/ai-coach/page.tsx:391-535` 缺字段时直接回落到本地默认值。
   - 风险：
   - 配置损坏或后端返回部分字段缺失时，前端会把“坏配置”渲染成“有默认值的好配置”，不满足 fail-closed。

8. `NewcomerPathConfigResponse.source` 与 config center 内部治理类型不一致。
   - 证据：
   - API type：`types.ts:5323-5330` 只有 `active_revision | unit_backfill`
   - 内部治理模型：`config-center-types.ts:49-58` 额外支持 `legacy_units`
   - 风险：
   - 前端已经隐含接受第三种来源，但公开 DTO 没表达；调用方无法稳定判断“兼容聚合”是否是合法状态。

### 2.2 UX / 运行态问题

9. 至少两处成功路径存在 loading/按钮卡死风险。
   - `admin/sales-trainer/audio-submissions/[submissionId]/page.tsx:65-80`
     - `retry()` 成功后没有 `setIsOperating(false)`，只在 catch 里复位。
   - `admin/sales-trainer/units/page.tsx:68-87`
     - `handleConfirm()` 成功后同样没有 `setIsOperating(false)`，只在 catch 里复位。

10. `useBusinessSkillsWorkbench()` 会把 coach 跳转能力缺失/路径读失败吞成 `coachHref = null`。
   - 证据：
   - `use-business-skills-workbench.ts:40-49`
   - 风险：
   - `listPaths()` 的网络/权限/后端错误和“AI Coach 本就不可用”被混成同一种无按钮状态。

11. admin / learner 的移动端信息密度没有收口。
   - 证据：
   - `units/page.tsx`, `papers/page.tsx`, `score-standards/page.tsx`, `operation-logs/page.tsx`, `audio-submissions/page.tsx`, `training-records/page.tsx`, `score-results/page.tsx`, `questions/categories/page.tsx` 都是裸 `<table className="w-full text-sm">`，没有同层 `overflow-x-auto` 或移动端卡片回退。
   - 风险：
   - 在手机断点会直接出现截断、横向溢出、操作按钮不可达。

## 3. 训练看板与 admin analytics 阶段任务拆解

### 阶段 A：先收口契约，再碰页面

- 目标：
  - 冻结 learner dashboard / admin analytics 的 typed DTO。
- 必要交付：
  - `TrainingJourneyCardDTO`
  - `TrainingJourneyModuleDTO`
  - `TrainingJourneyActionDTO`
  - `SalesTrainerManagerDashboardSummaryDTO`
  - `SalesTrainerManagerDashboardModuleSummaryDTO`
  - `SalesTrainerRiskLearnerDTO`
  - `SalesTrainerWeakDimensionDTO`
- 关键要求：
  - `status`
  - `blocked_reason`
  - `next_action`
  - `learner_level`
  - `training_stage_level`
  - `fallback_applied`
  - `trace_id`
- 验收：
  - 首页和 workbench 不再从 `Record<string, unknown>` 猜字段。

### 阶段 B：learner 首页改成真正的“训练看板”

- 目标：
  - `/sales-trainer` 只消费 active projection，不再降级到 catalog fallback。
- 必要交付：
  - 模块卡显示三类状态：
    - 可进入
    - 已完成
    - 不可进入/不可用
  - 每张卡必须显示：
    - 当前阶段
    - 未开放原因
    - 下一步动作
    - 证据数量 / 最近结果
  - `PPT / 商务技巧 / 电梯演讲 / 实时对练占位` 用统一卡片模型。
- 验收：
  - 缺 active revision 时显示诊断空态，不显示 quiz/audio catalog fallback。

### 阶段 C：capability 五层一致 fail-closed

- 目标：
  - sidebar、workbench card、module nav、页面、直链页 五层统一。
- 必要交付：
  - `AdminCapabilityGuard` 或 route-level wrapper
  - `SalesTrainerAdminModuleNav` 改为 capability-aware
  - `SALES_TRAINER_ADMIN_WORKBENCH_LINKS` 改为 capability-aware
  - 受限页面的直链态必须显示：
    - 无权限说明
    - remediation 文案
    - trace_id
- 验收：
  - `support/content_admin/ops` 在直输 URL 时看不到不属于自己的页面内容，不依赖“先隐藏侧边栏”。

### 阶段 D：admin newcomer analytics 独立化

- 目标：
  - 把 `/admin/sales-trainer` 从“摘要工作台”升级为“可分析、可筛选、可下钻”的新人训练分析面。
- 必要交付：
  - 先消费现有 `module_summaries`
  - 增加 filter：
    - 部门
    - 角色等级
    - 学员等级
    - 训练阶段等级
    - 模块
    - passed / failed / pending
  - 增加 drill-down：
    - 总览
    - 模块
    - 学员
    - 训练记录
    - 证据
    - 补救动作
- 验收：
  - 不再只展示 `risk_learners/weak_dimensions/intervention_suggestions` 的 top5 切片。

### 阶段 E：移动端 / 小屏分析态

- 目标：
  - workbench、列表、分析页都能在移动端可靠使用。
- 必要交付：
  - table 页增加：
    - `overflow-x-auto`
    - 或小屏 card list fallback
  - 训练看板卡片纵向堆叠
  - analytics 图表提供移动端简化态
- 验收：
  - 手机断点下：
    - 主要 CTA 可点击
    - 关键信息不被裁剪
    - 不需要横向拖拽才能完成核心操作

## 4. 前端测试 / E2E 建议

### 4.1 建议补强的 Vitest 证明点

1. learner 首页：
   - `listPaths()` 为空时，不再退回 `CatalogSection`，而是显示 typed 空态/诊断态。
   - `newcomer_training_path_v1` 缺模块配置时，不应泄露 legacy 单元入口。

2. module card / workbench card：
   - business skills coach 按 capability/path availability 显示或隐藏。
   - realtime placeholder 永远 disabled，且原因来自后端字段，不来自常量。

3. 录音结果：
   - `getUnit()` 失败时，页面不能显示“70 分通过线”。
   - `passed === null` 必须显示“待评分/待判定”，不能显示“否”。

4. admin capability fail-closed：
   - `salesTrainerAdminItemsForCapabilities()` 的结果必须同时驱动：
     - sidebar
     - workbench cards
     - module nav
   - 受限用户进入 `/admin/sales-trainer/settings` / `/operation-logs` 直链时显示 fail-closed 页面。

5. admin 绑定页 / config center：
   - `/articles`、`/paths` 的当前绑定读取如果遇到 403/500/network，必须显示错误态，不得等同于“未绑定”。

6. loading 复位：
   - `units/page.tsx` 发布/归档成功后按钮恢复可点击。
   - `audio-submissions/[submissionId]/page.tsx` 重试成功后按钮恢复可点击。

### 4.2 建议补强的 Playwright 证明点

1. 新人训练 fail-closed：
   - active revision 缺失
   - 模块 disabled
   - AI Coach 不可用
   - 录音评分 pending / failed / missing threshold

2. admin capability：
   - `content_admin` 只能看到内容治理入口
   - `support/training_manager` 只能看到 records/dashboard
   - `ops` 只能看到 settings/logs/retry
   - 直链受限页返回可解释的 fail-closed 状态

3. admin analytics：
   - workbench 能渲染 `module_summaries`
   - mobile viewport 下 training-records / score-results / audio-submissions 可操作

### 4.3 建议命令

已有仓库脚本：

```bash
cd web
npx tsc --noEmit
npm run lint
npm run test
npm run test:coverage
npm run e2e
```

建议的聚焦 Vitest 命令：

```bash
cd web
npx vitest run \
  src/lib/sales-trainer/routes.test.ts \
  src/components/sales-trainer/sales-trainer-module-grid.test.tsx \
  src/app/(dashboard)/sales-trainer/page.test.tsx \
  src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx \
  src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx \
  src/app/(dashboard)/sales-trainer/business-skills/coach/page.test.tsx \
  src/app/admin/sales-trainer/page.test.tsx \
  src/app/admin/sales-trainer/articles/page.test.tsx \
  src/app/admin/sales-trainer/paths/page.test.tsx \
  src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx
```

建议的 Playwright 方向：

```bash
cd web
npm run e2e -- tests/e2e/smoke.spec.ts
npm run e2e -- tests/e2e/sales-phase4.spec.ts
```

新增 newcomer training 专项 spec 后建议运行：

```bash
cd web
npm run e2e -- tests/e2e/newcomer-training-fail-closed.spec.ts
npm run e2e -- tests/e2e/newcomer-training-admin-analytics.spec.ts
```

## 5. 禁止硬编码与配置化建议

### 必须移除或收口的硬编码

1. `audio/result/[submissionId]/page.tsx` 的 `70` 通过线兜底。
   - 结论：
   - 这不是稳定规则，必须移除。
   - 应改为：
     - 优先读取 `score_scheme_snapshot`
     - 其次读取后端显式返回的 threshold 字段
     - 失败时显示配置错误态

2. `admin/sales-trainer/ai-coach/page.tsx` 的 `DEFAULT_CONFIG`。
   - 结论：
   - 页面级默认值不能继续充当业务默认值权威。
   - 应改为：
     - 后端返回完整默认配置
     - 前端只做 shape 校验
     - 缺必填字段直接 fail-closed

3. `coach-workbench-config.ts` 的 `BUSINESS_SKILLS_COACH_WORKBENCH_COPY` / `BUSINESS_SKILLS_COACH_WORKBENCH_RULES`。
   - 结论：
   - 文案和交互开关已经影响业务策略，不应长期留在前端常量。
   - 建议：
     - 文案迁入 `modules[].ai_coach.workbench_copy`
     - `showFreeFollowup` / `allowSkipActiveCard` 迁入 contract-backed config

4. `routes.ts` 的静态 workbench link / context nav。
   - 结论：
   - 导航定义可以保留，但“是否可见”不能由静态常量决定。
   - 建议：
     - 每个 route item 显式声明 required capability
     - 所有入口统一走同一个 capability filter

### 应配置化 / 类型化的内容

1. `SalesTrainerManagerDashboard` 的 `summary/module_summaries/risk_learners/weak_dimensions/intervention_suggestions`
   - 建议：
   - 从 `Record<string, unknown>` 升级为专门 DTO。

2. `SalesTrainerAudioSubmission.material_snapshot/score_scheme_snapshot/task_brief_snapshot`
   - 建议：
   - 为 learner 页面真正消费到的字段抽出 typed snapshot。

3. config center 的 `source`
   - 建议：
   - 统一成一份公开契约：
     - `active_revision`
     - `unit_backfill`
     - `legacy_units`
   - 或前端不再声明 `legacy_units`。

## 建议优先级

### 先做

- 去掉 learner catalog fallback
- capability 五层一致 fail-closed
- 修复 admin 录音详情 `passed=null`
- 修复 `70` 兜底
- 修复 `isOperating` 成功路径不复位

### 紧接着做

- admin 页面停止用 learner 端点推绑定态
- workbench / analytics 消费 typed dashboard DTO
- AI Coach admin 默认值与契约对齐

### 再做

- 移动端表格/card 化
- 新人训练专属 analytics 深化与下钻

## 本次未执行

- 未启动 dev server
- 未跑 Vitest / Playwright
- 未改业务代码

