# Research: current-admin-ia-audit

- Query: 审查当前仓库新人训练后台 `/admin/sales-trainer` 信息架构与语义，重点看路由、导航、页面标题、模块命名、英文/内部术语泄漏，以及管理员是否知道“什么是什么、能做什么”。
- Scope: internal
- Date: 2026-07-08

## Findings

### CodeGraph First

- `.codegraph/` exists. 已先使用 `codegraph explore "admin sales trainer routes navigation page titles module names /admin/sales-trainer"` 了解功能链路、路由源和模块导航。
- 已使用 `codegraph node web/src/lib/sales-trainer/routes.ts` 查看新人训练后台路由表与模块内导航。
- 已使用 `codegraph explore "AdminSidebar AdminShell admin sidebar navigation sales trainer"` 和 `codegraph node web/src/components/layout/admin-sidebar.tsx` 查看全局后台导航、角色入口和侧边栏展开逻辑。

### Files Found

- `web/src/lib/sales-trainer/routes.ts` - `/admin/sales-trainer` 导航、能力过滤、模块内导航、工作台入口列表的源头。
- `web/src/components/layout/admin-sidebar.tsx` - 后台全局侧边栏、非平台管理员可见区块、侧边栏默认展开逻辑。
- `web/src/app/admin/sales-trainer/page.tsx` - 新人训练路径工作台、指标卡、风险学员和入口卡片。
- `web/src/app/admin/sales-trainer/paths/page.tsx` - 新人训练路径配置中心入口页。
- `web/src/components/admin/sales-trainer/path-config-center.tsx` - 配置中心主体，含发布治理、四关卡卡片、诊断、学员端预览。
- `web/src/components/admin/sales-trainer/material-setup-guide.tsx` - 从材料库引导回路径配置中心发布绑定的 in-flow 引导。
- `web/src/app/admin/sales-trainer/materials/page.tsx` 与 `web/src/components/admin/sales-trainer/material-*` - PPT/逐字稿/附件材料库。
- `web/src/app/admin/sales-trainer/score-standards/*` 与 `web/src/components/admin/sales-trainer/score-prompt-form.tsx` - 录音评分标准列表、新建、编辑和评分 Prompt 表单。
- `web/src/app/admin/sales-trainer/questions/*` 与 `web/src/components/admin/sales-trainer/question-form.tsx` - 题库、AI 出题草稿、分类、小测预览、题目表单。
- `web/src/app/admin/sales-trainer/articles/*` - 学习文章、商务礼仪专题、资料导入和能力点管理。
- `web/src/app/admin/sales-trainer/training-records/*` - 学员训练记录列表与详情。
- `web/src/app/admin/sales-trainer/audio-submissions/*` - 学员录音列表与详情。
- `web/src/app/admin/sales-trainer/score-results/page.tsx` - 做题结果与录音评分结果列表。
- `web/src/app/admin/sales-trainer/analytics/page.tsx` - Journey Analytics 页面。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx` - 商务技巧 AI 教练配置页。
- `web/src/app/admin/sales-trainer/settings/page.tsx` 与 `settings/operational-diagnostics-panel.tsx` - 配置健康与路径诊断。

### Main IA / Semantics Issues

1. **侧边栏当前新人训练区块默认不展开，尤其会影响只拥有新人训练权限的管理员。**

   - 证据：新人训练区块 label 是“新人训练路径”，items 来自 `SALES_TRAINER_ADMIN_NAV_ITEMS`：`web/src/components/layout/admin-sidebar.tsx:111`、`web/src/components/layout/admin-sidebar.tsx:129`。
   - 证据：非平台管理员只返回一个新人训练区块：`visibleAdminNavSections` 在有 sales trainer capability 时返回 `[salesTrainerSection(salesTrainerItems)]`：`web/src/components/layout/admin-sidebar.tsx:236`。
   - 证据：默认展开条件排除了 `sales-trainer`：`isOpen={openSectionKeys[section.key] ?? (section.key !== "sales-trainer" && section.key === activeSectionKey)}`，因此当前位于 `/admin/sales-trainer/*` 时也不会自动展开：`web/src/components/layout/admin-sidebar.tsx:339`。
   - 影响：管理员进入后台后只能看到一个“新人训练路径”折叠区块，不展开就不知道有哪些管理入口；这直接削弱“什么是什么、能做什么”的可发现性。
   - 优化方向：当前 active section 默认展开；如果可见区块只有新人训练，应直接展开；长列表可按“配置与发布 / 学员复核 / 诊断审计”分组显示。

2. **新人训练顶层导航是 16 个平铺名词，且记录类入口语义重叠。**

   - 证据：路由表平铺包括“模块单元、路径配置、AI 教练配置、题库管理、录音评分标准、学习文章、考卷管理、材料库、训练记录、达标验收、学员录音、评分结果、Journey 分析、配置、操作记录”：`web/src/lib/sales-trainer/routes.ts:46`。
   - 证据：内容类和记录类只是数组拆分，实际侧边栏仍平铺为同一 section 的 items：`web/src/lib/sales-trainer/routes.ts:145`、`web/src/lib/sales-trainer/routes.ts:157`、`web/src/lib/sales-trainer/routes.ts:165`。
   - 证据：训练记录页说明“替代单独追录音与评分结果”，但“学员录音”和“评分结果”仍是并列顶层入口：`web/src/app/admin/sales-trainer/training-records/page.tsx:573`、`web/src/lib/sales-trainer/routes.ts:113`、`web/src/lib/sales-trainer/routes.ts:119`。
   - 证据：工作台入口卡片只展示 icon + label，没有一句话说明或主动作解释：`web/src/app/admin/sales-trainer/page.tsx:267`。
   - 影响：管理员难以判断“训练记录 / 学员录音 / 评分结果 / 达标验收”之间的边界，也难以判断配置入口的先后关系。
   - 优化方向：把顶层改成任务分组。建议：
     - 配置与发布：路径配置、PPT 讲解配置、商务礼仪学习专题、题库与考卷、评分标准、材料库。
     - 学员复核：达标验收、训练记录。
     - 诊断审计：训练分析、配置健康、操作日志。
     - “学员录音”和“评分结果”降级为训练记录里的筛选/快捷入口，除非有明确独立主任务。

3. **Analytics 页面有明显英文与内部投影术语泄漏。**

   - 证据：导航 label 是“Journey 分析”：`web/src/lib/sales-trainer/routes.ts:127`、模块内导航也是“Journey 分析”：`web/src/lib/sales-trainer/routes.ts:424`。
   - 证据：页面标题是 `Journey Analytics`，描述使用“Journey”和“后端投影”：`web/src/app/admin/sales-trainer/analytics/page.tsx:897`。
   - 证据：空态文案出现 `fail-closed`、`Journey 投影`：`web/src/app/admin/sales-trainer/analytics/page.tsx:1092`。
   - 证据：页面正文显示 `training_stage`、`module_summaries`、`learner level`、`role level`、`fallback`、`source` 等实现/投影词：`web/src/app/admin/sales-trainer/analytics/page.tsx:1143`、`web/src/app/admin/sales-trainer/analytics/page.tsx:1181`、`web/src/app/admin/sales-trainer/analytics/page.tsx:1202`。
   - 影响：这些词更像研发/数据投影语言，不是运营管理员的任务语言。
   - 优化方向：改成“训练路径分析”或“新人训练分析”；把 `training_stage` 表达成“训练阶段”，把 `module_summaries` 表达成“模块统计”；`fallback/source` 放到管理员调试或审计详情，不在默认卡片文案中展示。

4. **训练记录详情和角色一致性观察页泄漏 endpoint、fallback、Trace ID、Prompt Contract、raw payload 等内部诊断。**

   - 证据：训练记录详情描述直接出现 `observation endpoint / legacy compliance fallback`：`web/src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx:469`。
   - 证据：历史回放快照展示 `Path Revision`、`Prompt Version`、`Trace ID`、`Prompt Contract`、`Coach State`：`web/src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx:161`、`web/src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx:249`。
   - 证据：默认展示“原始记录”并直接 `JSON.stringify` raw payload：`web/src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx:97`、`web/src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx:658`。
   - 证据：观察组件错误说明出现 `admin observation endpoint`，指标出现 `LLM Timeout`、`Turn`、`Trace`、`visible keys`：`web/src/app/admin/sales-trainer/training-records/roleplay-observation-panel.tsx:138`、`web/src/app/admin/sales-trainer/training-records/roleplay-observation-panel.tsx:216`、`web/src/app/admin/sales-trainer/training-records/roleplay-observation-panel.tsx:319`。
   - 影响：普通后台用户会看到工程术语和内部对象，和仓库规则“普通用户界面不得默认展示 traceId、workflow、raw JSON、数据库主键、原始枚举、内部错误码”的方向不一致。即使这是 admin，也应区分“运营管理员默认视图”和“技术诊断/审计详情”。
   - 优化方向：默认展示业务复盘：学员、任务、材料版本、当前有效分、评分证据、需要复核/重练动作。把 raw payload、trace、contract hash、revision id 放入可折叠“技术诊断”或“审计详情”，并用权限控制。

5. **AI 教练配置页大量使用配置键和权限码，管理员需要理解代码字段才能操作。**

   - 证据：页面描述使用 `prompt`：`web/src/app/admin/sales-trainer/ai-coach/page.tsx:812`。
   - 证据：表单 fieldset 直接显示 `allowed_ui_event_types`、`session_start_behavior`、`entry_resume_policy`、`remediation_strategy`、`generation_timeout_seconds`、`max_auto_steps_per_session` 等字段名：`web/src/app/admin/sales-trainer/ai-coach/page.tsx:1017`、`web/src/app/admin/sales-trainer/ai-coach/page.tsx:1084`、`web/src/app/admin/sales-trainer/ai-coach/page.tsx:1137`。
   - 证据：恢复文案字段显示 `empty_response_recovery_message`、`empty_response_recovery_prompts`、`generation_failure_recovery_message`：`web/src/app/admin/sales-trainer/ai-coach/page.tsx:1190`。
   - 证据：Prompt 绑定区直接显示 `sales_trainer.manage_prompts`、`prompt_template_id`、`prompt_revision_id`、`prompt_contract_hash`、`output_schema_version`、`scoring_prompt_template_id`：`web/src/app/admin/sales-trainer/ai-coach/page.tsx:1306`。
   - 影响：这更像后端配置编辑器，不像“商务技巧 AI 教练”运营面板；管理员难以知道哪个字段影响学员体验。
   - 优化方向：字段改为业务标签和选择器，例如“开场方式”“继续上次训练”“答错几次后补救”“生成超时时间”“教练提示词版本”。权限提示改为“需要提示词管理权限”，不要露出权限码。Prompt ID 改为选择已发布 Prompt/版本，contract hash 仅在审计详情展示。

6. **评分标准和题目表单暴露 JSON / schema / prompt 细节。**

   - 证据：评分标准表单默认要求编辑“学员可见评分标准（JSON）”：`web/src/components/admin/sales-trainer/score-prompt-form.tsx:264`。
   - 证据：高级模式仍直接显示 `system_prompt`、`output_schema（JSON）`：`web/src/components/admin/sales-trainer/score-prompt-form.tsx:280`、`web/src/components/admin/sales-trainer/score-prompt-form.tsx:293`。
   - 证据：新建题目页描述出现 `scoring_criteria` 和 JSON：`web/src/app/admin/sales-trainer/questions/new/page.tsx:99`。
   - 证据：题目表单显示“LLM 模型配置”“最大输出 tokens”“系统提示词”“评分提示词模板”，并提示模板变量：`web/src/components/admin/sales-trainer/question-form.tsx:513`、`web/src/components/admin/sales-trainer/question-form.tsx:546`、`web/src/components/admin/sales-trainer/question-form.tsx:552`。
   - 影响：题库管理员可能需要管理评分规则，但不应默认手写 JSON/schema 或理解 prompt/template 变量；这增加误配置风险。
   - 优化方向：用结构化评分维度编辑器替代 JSON；Prompt/schema 放到“高级配置/技术配置”中并标注高风险；使用中文业务标签和示例，保存前展示变更影响与审计结果。

7. **PPT 讲解治理入口已经有底层能力，但缺少一个明确的一站式入口。**

   - 证据：配置定义里有 `ppt_explanation`，标题是“PPT 讲解录音”，说明需要绑定 PPT 材料和录音评分标准：`web/src/lib/sales-trainer/config-center-definitions.ts:5`。
   - 证据：路径配置中心标题明确说管理员不需要再到模块单元编辑页理解抽象路径字段：`web/src/app/admin/sales-trainer/paths/page.tsx:81`。
   - 证据：材料库诊断引导能从 `module=ppt_explanation` 回到路径配置中心完成发布绑定：`web/src/components/admin/sales-trainer/material-setup-guide.tsx:14`、`web/src/components/admin/sales-trainer/material-setup-guide.tsx:35`。
   - 证据：但全局/模块导航没有“PPT 讲解配置”或“第一关：PPT 讲解”入口，只有“路径配置 / 材料库 / 录音评分标准”三个分散入口：`web/src/lib/sales-trainer/routes.ts:59`、`web/src/lib/sales-trainer/routes.ts:77`、`web/src/lib/sales-trainer/routes.ts:95`。
   - 影响：要完成“更新 PPT 讲解训练”这类任务，管理员仍需知道要跨材料库、评分标准、路径配置中心三处协作；这和上下文内完成原则存在张力。
   - 优化方向：在工作台和路径配置中心增加“PPT 讲解配置”任务入口，展示材料版本、评分标准、发布状态、学员端预览和缺口补齐动作；底层仍复用材料库/评分标准/路径配置，不复制数据模型。

8. **学习文章 / 商务礼仪专题语义在“文章、专题、训练包、active path、business_skills”之间摇摆。**

   - 证据：导航是“学习文章”，页面标题也是“学习文章”，但页面正文按“学习专题”管理：`web/src/lib/sales-trainer/routes.ts:83`、`web/src/app/admin/sales-trainer/articles/page.tsx:149`。
   - 证据：专题详情标题是“商务礼仪规范”，但引导说从 active path 的 `business_skills` 模块生成草稿：`web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:226`、`web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:257`。
   - 证据：导入页表单暴露“训练包 key”，结果文案显示 `working revision v...`：`web/src/app/admin/sales-trainer/articles/import/page.tsx:277`、`web/src/app/admin/sales-trainer/articles/import/page.tsx:596`。
   - 影响：管理员看到的是“文章”，实际管理对象是“非阻塞学习专题 + 章节小单元 + 题目规则 + 发布修订”；训练包 key / working revision 又把内部模型暴露出来。
   - 优化方向：统一命名为“商务礼仪学习专题”或“非阻塞学习专题”；导入字段改为“专题标识”；`working revision` 改为“待发布草稿版本”；把 `business_skills` 和 active path 语义隐藏在说明或审计详情里。

9. **操作记录/操作日志、配置/配置健康等标签不完全一致。**

   - 证据：顶层路由 label 是“操作记录”，context nav label 是“操作日志”，页面标题是“新人训练路径操作日志”：`web/src/lib/sales-trainer/routes.ts:137`、`web/src/lib/sales-trainer/routes.ts:439`、`web/src/app/admin/sales-trainer/operation-logs/page.tsx:174`。
   - 证据：顶层路由 label 是“配置”，context nav 子项是“配置健康”，页面标题是“新人训练路径配置”：`web/src/lib/sales-trainer/routes.ts:131`、`web/src/lib/sales-trainer/routes.ts:429`、`web/src/app/admin/sales-trainer/settings/page.tsx:94`。
   - 影响：小词不一致会让管理员误以为是不同对象或不同权限域。
   - 优化方向：统一为“配置健康”和“操作日志”，或统一为“系统配置 / 操作记录”，并在工作台卡片说明用途。

### Code Patterns

- 导航源集中在 `web/src/lib/sales-trainer/routes.ts:46`，`SALES_TRAINER_ADMIN_NAV_ITEMS` 由内容类、记录类、配置、日志拼接：`web/src/lib/sales-trainer/routes.ts:145`。
- 模块内导航依赖 `SALES_TRAINER_ADMIN_CONTEXT_NAV_GROUPS`，工作台入口取每个 group 的第一项：`web/src/lib/sales-trainer/routes.ts:298`、`web/src/lib/sales-trainer/routes.ts:450`。
- 权限过滤按 capability 把可见路由拼出来：`web/src/lib/sales-trainer/routes.ts:172`。
- 全局侧边栏非平台管理员只显示新人训练 section：`web/src/components/layout/admin-sidebar.tsx:236`。
- 侧边栏默认展开逻辑排除了新人训练 section：`web/src/components/layout/admin-sidebar.tsx:339`。
- 工作台复用 `SALES_TRAINER_ADMIN_WORKBENCH_LINKS`，但卡片没有描述字段：`web/src/app/admin/sales-trainer/page.tsx:83`、`web/src/app/admin/sales-trainer/page.tsx:267`。
- 路径配置中心是当前最接近“一站式配置”的模式：`web/src/app/admin/sales-trainer/paths/page.tsx:81`、`web/src/components/admin/sales-trainer/path-config-center.tsx:61`。
- 材料库已有上下文内补齐引导：`web/src/components/admin/sales-trainer/material-setup-guide.tsx:35`。

### External References

- 未使用外部网页。此轮为代码与本仓库规范静态审查。
- 版本背景来自仓库文档：`docs/architecture.md` 说明前端为 Next.js 16.2.3、React 19.2.3。

### Related Specs

- `.trellis/spec/frontend/admin-console-patterns.md` - 后台页面按用户意图组织、List/Import/Detail/Edit 分离、页面三层结构。
- `.trellis/spec/frontend/index.md` - 前端硬规则：后台体验不中断、配置/状态从 API 读取、可观测性。
- `.trellis/spec/guides/design-artifact-audit-guide.md` - 审计“上游假设是否追到下游验证”的方法。
- `web/AGENTS.md` - 前端 hard rules，强调 `/admin/sales-trainer/*` 是新人训练路径独立产品。
- `web/src/app/AGENTS.md` - App Router/admin map 与 Admin Console Patterns 摘要。
- `web/src/app/admin/sales-trainer/AGENTS.md` - 新人训练后台本地约定：`module-nav.tsx` 作为导航源，显示文案应反映业务策略，缺失配置要给 admin remediation。
- `.trellis/spec/backend/sales-trainer-learning-topic-governance.md` - 商务礼仪学习专题应独立于必修路径，`required` 和 `blocks_next` 必须保持 false。

## Caveats / Not Found

- `python3 ./.trellis/scripts/task.py current --source` 返回 `Current task: (none)`；本文件写入用户明确给出的任务目录。
- 只做静态代码审查，未启动前端、未截图、未做浏览器可用性验证。
- 未修改产品代码、未运行测试、未执行 git 操作。
- 未发现更深层 `web/src/app/admin/sales-trainer/*/AGENTS.md`，只读到了 `web/src/app/admin/sales-trainer/AGENTS.md`。
