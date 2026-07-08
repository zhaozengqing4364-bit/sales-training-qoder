# Research: international-admin-patterns

- Query: 国际成熟后台 / LMS / SaaS 管理台的信息架构与 CRUD 交互经验；重点关注资源列表页是否只做索引、创建/编辑/详情/导入/发布是否分离、何时用弹窗/抽屉、如何命名让管理员看懂、如何处理学习内容/训练任务/记录/配置边界。
- Scope: mixed
- Date: 2026-07-08

## Findings

### 结论摘要

成熟后台的共同做法不是把一个资源的所有 CRUD 塞进列表页，而是按管理员意图拆面：索引、详情、创建、编辑、导入、发布、记录、配置各自有稳定入口。列表页承担发现、筛选、批量选择和轻量行操作；复杂创建/编辑、导入和发布门禁应分离到专门页面或可深链的任务面。弹窗适合短、低风险、上下文不需要保存的动作；抽屉适合在不离开索引/详情的情况下做上下文查看或小量编辑；多步骤、文件上传、异步任务、发布风险、权限校验、影响预览，应使用独立页面。

对“PPT 讲解录音”更合理的信息架构是任务治理页，不是材料库、评分标准、路径配置、学员记录四个资源页的简单拼盘。该页应该以管理员语言组织为“当前学员任务会使用什么材料、按什么标准评分、何时对后续学员生效、已有学员记录在哪里看”，并保留资源页作为高级管理入口。

### Files Found

- `.trellis/workflow.md`: Trellis 工作流要求研究、决策和经验写入任务目录，不能只留在对话中。
- `.trellis/spec/frontend/admin-console-patterns.md`: 项目后台 IA 规则，明确 list/index、detail、create、edit、import、policy center 的边界。
- `.trellis/spec/frontend/component-guidelines.md`: 项目 UI 组件与交互约束，确认弹窗、确认、toast、inline error 的使用边界。
- `.trellis/spec/backend/sales-trainer-learning-topic-governance.md`: 学习专题与必修路径的后端边界，强调 future-only revision 和记录保留。
- `.trellis/tasks/07-08-ppt-explanation-admin-governance-entry/prd.md`: 本任务目标与验收，明确需要一个“PPT 讲解录音”后台治理入口。
- `web/src/lib/sales-trainer/routes.ts`: 新人训练后台当前导航、权限和上下文导航定义。
- `web/src/components/layout/admin-sidebar.tsx`: 总后台侧边栏分组，已有“新人训练路径 / 内容与知识 / 策略中心 / 运营分析”等分类。
- `web/src/app/admin/sales-trainer/paths/page.tsx`: 当前路径配置中心页面，PPT 讲解录音通过 `?module=ppt_explanation` 聚焦。
- `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx`: 已有材料与评分标准绑定编辑器。
- `web/src/components/admin/sales-trainer/material-setup-guide.tsx`: 当前材料库引导管理员“创建材料 -> 上传版本 -> 回到路径配置发布绑定”。
- `web/src/app/admin/sales-trainer/materials/page.tsx`: 当前材料库页面，创建材料、列表、详情、上传版本在同一页。
- `web/src/app/admin/sales-trainer/score-standards/page.tsx`: 当前评分标准列表，创建/编辑已有独立页面，发布用确认弹窗。
- `web/src/app/admin/sales-trainer/audio-submissions/page.tsx`: 当前学员录音记录列表。
- `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx`: 录音详情页，包含训练快照、转写、评分、重试/重评入口。
- `web/src/components/admin/sales-trainer/path-config-center.tsx`: 路径发布治理、模块卡片、运维诊断、学员端预览和修订历史。

### Code Patterns

- 项目规范已经给出成熟后台目标形态：按用户意图拆面，索引页只承载 search/filter/table/status overview；create、edit、import、ops、global config 分别进入专门表面 `.trellis/spec/frontend/admin-console-patterns.md:13`。
- 项目硬规则明确：列表页是 Index only，不能放完整 create/edit 表单；导入不能混在列表或详情；复杂实体至少分 overview 与 edit；子资源要走子路由；资产页只绑定/预览策略，策略编辑留在策略中心 `.trellis/spec/frontend/admin-console-patterns.md:30`。
- 项目标准路由树已经偏向国际 SaaS 常见 IA：`/resource`、`/new`、`/import`、`/[id]`、`/[id]/edit`、`/[id]/{sub}` `.trellis/spec/frontend/admin-console-patterns.md:68`。
- 项目弹窗规则与外部资料一致：小于等于 4 个字段、无资产选择器可用 modal；多资产选择、长文本、多步校验、批量导入、发布门禁应使用专门页面 `.trellis/spec/frontend/admin-console-patterns.md:85`。
- 现有 PRD 指出 PPT 讲解录音能力分散在路径绑定、训练单元、材料库、评分标准和录音提交记录里，管理员难找到完整任务链 `.trellis/tasks/07-08-ppt-explanation-admin-governance-entry/prd.md:10`。
- PRD 明确主配置路径应在当前页面完成，缺材料或缺评分标准时要提供“选择已有 / 快速新建最小对象 / 跳转高级编辑”，而不是要求管理员离开任务再回来 `.trellis/tasks/07-08-ppt-explanation-admin-governance-entry/prd.md:32`。
- 当前导航把新人训练拆为工作台、模块单元、路径配置、评分标准、学习文章、考卷、材料库、训练记录、学员录音、评分结果、设置、操作记录等资源/记录/配置入口 `web/src/lib/sales-trainer/routes.ts:46`。
- 总后台侧边栏也把“新人训练路径”“内容与知识”“智能体与角色”“策略中心”“运营分析”“组织与权限”“系统治理”分组，说明“PPT 讲解录音”若是任务治理入口，应在新人训练路径语境下命名，而不是藏在材料库或策略中心 `web/src/components/layout/admin-sidebar.tsx:129`。
- 当前路径配置页通过 `focusedModuleKey = searchParams.get("module")` 聚焦某个模块，`ppt_explanation` 只是 query state，不是可被管理员直接理解的任务页 `web/src/app/admin/sales-trainer/paths/page.tsx:25`。
- `PathConfigAudioBindingEditor` 能选择已发布材料和已发布评分标准，但提示语仍要求“再去管理页创建评分标准或上传材料新版本”，这暴露出当前任务内补齐能力不足 `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:42`。
- 绑定编辑器现在有“管理评分标准 / 管理材料库”链接，适合保留为高级管理出口，但不应成为缺配置时的唯一完成路径 `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:47`。
- `MaterialSetupGuide` 直接说明材料库发布后还要“回到新人训练路径配置中心，保存并发布新的路径绑定修订”，是跨页面流程割裂的证据 `web/src/components/admin/sales-trainer/material-setup-guide.tsx:35`。
- 当前材料库把创建主档、列表选择、详情、上传版本放在一个页内 `web/src/app/admin/sales-trainer/materials/page.tsx:207`；按项目规范，这类资源页后续应拆为索引 + create/detail/version 子面，但本任务 MVP 不应复制材料库 CRUD。
- 评分标准列表已有更接近成熟后台的形态：列表页提供“新建评分标准”入口，编辑走 `/score-standards/{id}/edit`，发布用确认流 `web/src/app/admin/sales-trainer/score-standards/page.tsx:109`。
- 学员录音列表是记录索引，详情页承载授权播放、下载、重试、训练快照、转写、评分和重评；这类记录不应混入配置页的主编辑流，只应作为“查看记录/排障”入口 `web/src/app/admin/sales-trainer/audio-submissions/page.tsx:61`、`web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx:226`。
- 路径配置中心已经具备发布治理语义：保存为新修订、发布并生效、操作日志、刷新诊断、修订历史；PPT 任务页应复用这些语义，而不是新增一套发布机制 `web/src/components/admin/sales-trainer/path-config-center.tsx:79`。
- 后端学习专题规范给了边界样板：学习专题可被独立治理，但不能进入必修路径阻塞进度；active revision 控制未来可见，历史尝试和分数保留 `.trellis/spec/backend/sales-trainer-learning-topic-governance.md:39`。

### External References

- Shopify Polaris Resource list: https://polaris-react.shopify.com/components/lists/resource-list?example=resource-list-with-filtering
  - 资源列表强调筛选、排序、批量选择和资源级操作，适合作为“索引页”的模式参考。
- Shopify app home composition / Index table: https://shopify.dev/docs/api/app-home/patterns/compositions/index-table
  - Index table 用于在首页/管理界面中列出资源与操作入口，不承担复杂资源编辑。
- Shopify Polaris Modal: https://polaris.shopify.com/components/overlays/modal
  - Modal 适合阻塞式短任务和确认，不适合长流程、文件导入、发布风险清单。
- IBM Carbon Data table: https://carbondesignsystem.com/components/data-table/usage/
  - Data table 支持筛选、批量动作、行级动作；批量动作与行级编辑需保持清晰边界。
- IBM Carbon Forms usage: https://carbondesignsystem.com/components/form/usage/
  - 表单用于收集结构化输入，复杂表单应有明确字段分组、校验和提交反馈。
- IBM Carbon Modal usage: https://carbondesignsystem.com/components/modal/usage/
  - Modal 用于需要用户停下来的短任务或确认；高影响、复杂、多步流程不应放在普通弹窗。
- IBM Carbon side panel usage: https://carbondesignsystem.com/components/side-panel/usage/
  - Side panel 适合在不丢失上下文的情况下查看补充信息或完成局部任务。
- Microsoft Fluent UI Drawer guidance: https://fluent2.microsoft.design/components/web/react/core/drawer/usage
  - Drawer 用作上下文面板；涉及未保存数据关闭、破坏性或高风险动作时需要明确保护。
- Microsoft Fluent UI Dialog guidance: https://fluent2.microsoft.design/components/web/react/core/dialog/usage
  - Dialog 适合确认、错误恢复和短表单；不能作为复杂导航结构的替代品。
- Salesforce Lightning Design System Data Table: https://www.lightningdesignsystem.com/components/data-tables/
  - Salesforce 后台表格模式强调列表发现、排序、选择和行级动作，与“列表只做索引+轻操作”一致。
- Salesforce Lightning Design System Modal: https://www.lightningdesignsystem.com/components/modals/
  - Salesforce modal 是强打断式覆盖层，适合创建/编辑少量字段或确认，不适合长时间任务流。
- Salesforce Record layout / Record home page references: https://www.lightningdesignsystem.com/components/page-headers/ 和 https://www.lightningdesignsystem.com/components/tabs/
  - 成熟 CRM 把 record overview、related lists、activity/tabs 拆成详情 hub，而不是在列表里编辑完整记录。
- Nielsen Norman Group, Modal & Nonmodal Dialogs: https://www.nngroup.com/articles/modal-nonmodal-dialog/
  - UX 权威资料强调 modal 会打断用户当前任务；只有需要立即注意或必须确认时才合理。
- Nielsen Norman Group, Application Design: https://www.nngroup.com/articles/application-design/
  - 复杂后台应保持任务流清晰、状态可理解，不能把所有功能堆到一个页面。
- GOV.UK Design System Task list: https://design-system.service.gov.uk/components/task-list/
  - Task list 用“任务名 + 状态”帮助用户理解多步骤治理流程，可参考用于发布前缺配置清单。
- GOV.UK Design System Error summary: https://design-system.service.gov.uk/components/error-summary/
  - 多字段表单和发布门禁错误应集中说明，并能定位到具体项。
- GOV.UK Design System Confirmation page: https://design-system.service.gov.uk/patterns/confirmation-pages/
  - 发布/导入/提交后的结果页或结果区需要明确状态、下一步和记录。
- Canvas LMS Modules guide: https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-add-course-content-as-module-items/ta-p/1159
  - LMS 中 module 是学习路径/任务编排面，可添加已有内容或新建内容项；这支持“任务页内选择已有/快速新建最小对象”的模式。
- Canvas LMS Course Modules overview: https://community.canvaslms.com/t5/Canvas-Basics-Guide/What-are-Modules/ta-p/6
  - Modules 组织课程结构和学习顺序，和 Pages/Assignments/Quizzes/Files 等内容资源是不同层级。
- Canvas LMS Course Analytics: https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-view-analytics-for-a-student-in-a-course/ta-p/1123
  - 记录与分析是观察/诊断面，不应混入内容配置主流程。
- Moodle Docs Activities and resources: https://docs.moodle.org/en/Activities
  - Moodle 把学习活动/资源作为课程内容单元，说明内容资源与课程编排是不同概念。
- Moodle Docs Gradebook: https://docs.moodle.org/en/Gradebook
  - Gradebook 汇总活动产生的成绩记录，是记录/报告面，不是内容配置面。
- Moodle Docs Course settings: https://docs.moodle.org/en/Course_settings
  - Course settings 是课程级配置面，与活动资源和成绩记录分离。

### Patterns To Apply

1. 资源列表页只做索引和轻动作。PPT 材料库、评分标准、录音记录都应保留索引语义：搜索、筛选、状态、行级查看/发布确认/删除确认。不要把 PPT 任务治理页变成全量材料库或评分标准 CRUD。

2. “PPT 讲解录音”应是任务 hub，而不是资源列表。推荐命名为“PPT 讲解录音”或“PPT 讲解录音治理”，副标题说明“配置第一关学员会看到的讲解材料、录音要求、评分标准和发布状态”。避免让管理员看到 `ppt_explanation`、`ppt_pitch`、path revision、prompt 等内部词作为主标签。

3. 创建/编辑/详情/导入/发布应分离：
   - 任务治理页：看当前生效配置、缺失项、保存绑定、发布预览、发布/回滚、去看记录。
   - 材料资源页：维护材料主档、版本、文件上传、发布材料版本。
   - 评分标准页：维护 rubric/prompt 修订、发布评分标准。
   - 学员录音记录页：查看历史提交、转写、评分、快照、重试/重评。
   - 导入页：如果有批量导入材料、题库、文章，应使用 `/import` 或等价独立任务流，不能塞进列表或任务 hub。

4. 缺配置时遵守 In-Flow Completion：在 PPT 任务页内优先提供“选择已有已发布材料/评分标准”；如果没有可用项，提供最小快速新建抽屉或专用轻表单，只创建主档/草稿所需字段，并自动回填当前绑定上下文；高级字段和版本管理仍链接到材料库/评分标准详情页。

5. 弹窗/抽屉选择：
   - Modal: 删除确认、发布确认、低字段快速新建、离开未保存确认。
   - Drawer/side panel: 查看候选材料/评分标准摘要、快速补少量元数据、展示缺配置解释，不打断当前任务。
   - Dedicated page: 文件上传、导入映射、评分标准长文本编辑、发布风险清单、回滚预览、需要 share URL 的任务。

6. 发布模型要保留“未来生效、历史快照不变”。PPT 任务页可以展示 active/working revision、发布预览、风险级别、历史版本、操作日志，但不要让管理员以为发布会重算历史录音。历史录音详情已经有训练快照，说明记录应解释“当时用的材料版本和评分方案”。

7. 学习内容 / 训练任务 / 记录 / 配置的边界建议：
   - 学习内容：材料、文章、题目、评分标准等可复用资产，有版本、状态、发布。
   - 训练任务：面向学员的一关/一步，如“PPT 讲解录音”，负责绑定内容资产、说明任务、定义完成/评分规则、发布给未来学员。
   - 记录：学员提交、转写、评分结果、训练快照、操作日志，以只读诊断为主，允许受控重试/重评。
   - 配置：全局策略、AI/语音/业务规则、权限和系统健康，进入策略中心或系统治理，不嵌入资产详情可编辑。

8. 管理员命名原则：
   - 用业务任务名命名入口：“PPT 讲解录音”，不要用“模块单元 / 路径字段 / ppt_pitch”。
   - 用用户将要完成的动作命名区块：“学员看到的材料”“录音要求”“评分标准”“发布给后续学员”“学员录音记录”。
   - 对技术治理词做二级说明：“当前生效版本”“待发布草稿”“历史快照保留”，而不是把 revision、prompt、traceId、raw JSON 放在主 UI。
   - 操作按钮用动词 + 对象：“选择已发布材料”“快速新建材料”“保存为待发布配置”“发布并生效”“查看学员录音”。

### Recommended IA For This Task

建议把新入口做成新人训练路径下的任务治理页，例如：

```text
/admin/sales-trainer/tasks/ppt-explanation
  Header: PPT 讲解录音
  ContextBar: 当前发布状态、缺配置项、只影响后续学员说明
  Main: 当前绑定材料 + 当前评分标准 + 录音任务说明 + 发布治理
  Secondary: 学员录音记录、评分结果、材料库高级编辑、评分标准高级编辑、操作日志
```

若团队更偏向已有路径配置中心，也可以使用 `/admin/sales-trainer/paths/ppt-explanation`，但 UI 标签仍应是“PPT 讲解录音”，而不是“路径配置 / ppt_explanation”。从国际后台 IA 角度看，独立任务页更符合管理员心智：它是治理一个学员任务，不是编辑一个路径数据结构。

## Caveats / Not Found

- `python3 ./.trellis/scripts/task.py current --source` 返回 no active task；本研究按用户明确给出的任务目录写入。
- 本次只做研究文档，未修改产品代码、未运行测试、未做 git 操作。
- 外部资料来自公开官方/权威文档，未访问付费 LMS/SaaS 管理台内部实现；对 Canvas/Moodle 的引用用于边界建模，不代表其后台 UI 是唯一最佳实践。
- 部分设计系统页面会随时间更新；本文件记录的是 2026-07-08 访问时的公开资料链接和归纳。
