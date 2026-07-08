# Research: current crud governance audit

- Query: 审查当前新人训练后台 materials、units、paths、score-standards、articles、questions、papers、ai-coach、records/readiness 等页面的页面耦合与 CRUD 治理问题，并给出可落地拆分顺序。
- Scope: internal
- Date: 2026-07-08

## Findings

### 结论摘要

当前后台并非所有资源都混在一个页面：`units`、`score-standards`、`questions` 主列表、`papers`、`training-records`、`audio-submissions`、`readiness` 的列表/详情/新建/编辑路由整体比较清晰。但与 PPT 讲解训练治理直接相关的入口仍然分散：`paths` 负责配置、发布和诊断，缺材料时跳到 `materials`，缺评分标准时跳到 `score-standards`；`materials` 又把新建材料、上传版本、发布版本、列表、详情塞在同一页。最严重的高耦合页面是 `ai-coach/page.tsx`、`articles/capabilities/page.tsx`、`questions/drafts/page.tsx`、`articles/business-etiquette/page.tsx`、`paths/page.tsx` 与 `materials/page.tsx`。

对当前任务“PPT 讲解训练后台治理入口”而言，优先不是继续扩大 `paths` 或 `materials`，而是新增一个面向任务的治理入口，聚合当前 PPT 讲解所需的路径、材料、版本、评分标准、发布状态、诊断和审计，并在当前页提供最小必要的选择、快速创建、上传、绑定、发布预览和审计跳转能力。

### Files Found

- `web/src/lib/sales-trainer/routes.ts`：新人训练后台导航定义；当前有材料库、路径配置、AI Coach、题库、评分标准、文章、试卷、记录、准备度等入口，但没有专门的 PPT 讲解训练治理入口。
- `web/src/app/admin/sales-trainer/materials/page.tsx`：材料库列表页，同时承载新建材料、上传版本、发布版本、列表和详情。
- `web/src/components/admin/sales-trainer/material-create-card.tsx`：内嵌在材料列表页的完整新建材料表单。
- `web/src/components/admin/sales-trainer/material-detail-panel.tsx`：内嵌在材料页右侧的详情、版本上传、版本发布面板。
- `web/src/components/admin/sales-trainer/material-setup-guide.tsx`：材料绑定引导，明确要求用户从路径配置跳转到材料库再回到路径配置。
- `web/src/app/admin/sales-trainer/paths/page.tsx`：路径配置中心入口，承载模块配置、保存、发布、回滚、诊断、预览。
- `web/src/components/admin/sales-trainer/path-config-center.tsx`：路径配置中心主体，把模块编辑、发布预览、诊断、学员预览、历史记录组合在同一页面。
- `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx`：材料与评分提示词绑定编辑器；缺资源时只给跨页链接。
- `web/src/components/admin/sales-trainer/path-config-business-binding-editor.tsx`：业务礼仪学习/考试绑定与单元配置编辑器。
- `web/src/app/admin/sales-trainer/units/page.tsx`、`units/new/page.tsx`、`units/[unitId]/edit/page.tsx`：训练单元列表、新建、编辑路由，整体拆分清晰。
- `web/src/app/admin/sales-trainer/score-standards/page.tsx`、`score-standards/new/page.tsx`、`score-standards/[id]/edit/page.tsx`：评分标准列表、新建、编辑路由，整体拆分清晰。
- `web/src/app/admin/sales-trainer/questions/page.tsx`、`questions/new/page.tsx`、`questions/[questionId]/edit/page.tsx`：题库列表、新建、编辑路由，整体拆分清晰。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx`：AI 生成草稿、筛选、审阅、编辑、转正式题、拒绝、Prompt 合约提示集中在一页。
- `web/src/app/admin/sales-trainer/questions/categories/page.tsx`：题目分类小型 CRUD 页面；低风险。
- `web/src/app/admin/sales-trainer/papers/page.tsx`、`papers/new/page.tsx`、`papers/[paperId]/edit/page.tsx`：试卷列表、新建、编辑路由，整体拆分清晰，但历史/回滚仍在列表页内联。
- `web/src/app/admin/sales-trainer/articles/page.tsx`：文章/业务礼仪专题入口页，提供生成专题草稿和发布专题配置能力。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx`：业务礼仪详情页，同时承载新建文章跳转、内容绑定、草稿生成、预览发布、发布、回滚、历史、内容列表。
- `web/src/app/admin/sales-trainer/articles/import/page.tsx`：文章导入独立页，上传、预览影响、发布导入版本在同一导入流程中。
- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx`：能力配置页，同时承载能力新增、JSON 规则编辑、章节绑定、保存、发布、归档。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx`：AI Coach 全局策略页，约 1500 行，把模型/提示词/阈值/治理规则/发布都集中在一个页面。
- `web/src/app/admin/sales-trainer/training-records/page.tsx`、`training-records/[recordType]/[recordId]/page.tsx`：训练记录列表/详情拆分清晰，详情含重评分、补救建议、快照、原始记录、操作日志。
- `web/src/app/admin/sales-trainer/audio-submissions/page.tsx`、`audio-submissions/[submissionId]/page.tsx`：音频提交列表/详情拆分清晰，重试类运维操作位于详情页。
- `web/src/app/admin/sales-trainer/readiness/page.tsx`、`readiness/[learnerId]/page.tsx`：准备度工作台/学员档案拆分清晰，档案页内联人工复核动作符合上下文内完成原则。
- `web/src/app/admin/sales-trainer/operation-logs/page.tsx`：集中审计日志页，已有可复用审计入口。

### Code Patterns

#### 1. 当前导航缺“PPT 讲解训练治理”任务入口

- `web/src/lib/sales-trainer/routes.ts:46` 定义新人训练后台分组导航。
- `web/src/lib/sales-trainer/routes.ts:72` 有 `aiCoach`。
- `web/src/lib/sales-trainer/routes.ts:88` 有 `questions`。
- `web/src/lib/sales-trainer/routes.ts:104` 有 `scoreStandards`。
- `web/src/lib/sales-trainer/routes.ts:119` 有 `materials`。
- `web/src/lib/sales-trainer/routes.ts:127` 有 `trainingRecords`。
- `web/src/lib/sales-trainer/routes.ts:131` 有 `readiness`。

风险：导航按资源/能力分散，管理员要完成 PPT 讲解训练发布，必须理解路径配置、材料库、评分标准之间的隐含关系。缺少按业务任务组织的“治理入口”。

建议目标形态：新增类似 `/admin/sales-trainer/tasks/ppt-explanation` 或 `/admin/sales-trainer/paths/ppt-explanation` 的专门入口。该页不重复完整 CRUD，而是聚合 PPT 讲解训练的当前有效路径、材料绑定、发布版本、评分标准、发布诊断、历史和审计链接。

#### 2. Materials 是典型“列表 + 新建 + 详情 + 上传 + 发布”混合页

- `web/src/app/admin/sales-trainer/materials/page.tsx:28` 到 `:44` 在单页维护列表、选中文件、材料草稿、版本草稿等多组状态。
- `web/src/app/admin/sales-trainer/materials/page.tsx:105` 到 `:129` 在列表页直接创建材料。
- `web/src/app/admin/sales-trainer/materials/page.tsx:131` 到 `:162` 在同页上传材料版本。
- `web/src/app/admin/sales-trainer/materials/page.tsx:164` 到 `:175` 在同页发布版本。
- `web/src/app/admin/sales-trainer/materials/page.tsx:177` 到 `:236` 同时渲染引导、新建卡片、列表卡片、详情面板。
- `web/src/components/admin/sales-trainer/material-create-card.tsx:28` 到 `:101` 是完整新建材料表单。
- `web/src/components/admin/sales-trainer/material-detail-panel.tsx:46` 到 `:63` 在详情面板里同时放概览、上传表单、版本列表。
- `web/src/components/admin/sales-trainer/material-detail-panel.tsx:123` 到 `:147` 在版本列表里直接发布版本。

风险：材料是多个训练任务共享资产。把创建、上传、发布和详情都放在列表页，会让“资产治理”与“任务绑定”混在一起，审计、失败反馈、发布预览和权限边界难以单独收紧。

建议拆分：

- `/materials`：只做材料列表、筛选、状态、轻量行操作。
- `/materials/new`：新建材料元数据。
- `/materials/[materialId]`：材料详情、当前发布版本、使用关系、审计链接。
- `/materials/[materialId]/versions/new` 或 `/materials/[materialId]/upload`：上传版本。
- `/materials/[materialId]/versions/[versionId]/publish-preview`：发布预览、影响范围、确认发布。
- 在 PPT 讲解治理入口中只提供“选择已有材料 / 快速创建最小材料 / 上传新版本并自动绑定”的轻量 in-flow surface。

#### 3. Materials 与 Paths 之间已经形成跨页补资料流程

- `web/src/components/admin/sales-trainer/material-setup-guide.tsx:12` 到 `:21` 定义从材料库回到 `/admin/sales-trainer/paths?module=...` 的链接。
- `web/src/components/admin/sales-trainer/material-setup-guide.tsx:34` 到 `:36` 明确要求“先在材料库创建/发布版本，再回到路径配置中心完成绑定发布”。
- `web/src/components/admin/sales-trainer/material-setup-guide.tsx:40` 到 `:50` 把流程拆为创建材料、上传版本、返回配置中心。
- `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:40` 到 `:60` 缺资源时仅提供跳转到评分标准或材料库的链接。
- `web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:62` 到 `:107` 只提供已发布材料和评分提示词下拉选择，没有快速创建、上传或绑定后的自动回填。

风险：这违反上下文内完成原则。管理员在路径发布前发现缺 PPT 材料或评分标准，会被要求离开当前任务流，去另一个资源页面补资料，再返回继续绑定。

建议：PPT 讲解治理入口中应内联提供最小必要处理能力：

- 从已有已发布材料版本选择。
- 快速新建材料壳并上传版本。
- 快速选择或创建评分标准草稿。
- 自动关联到当前路径模块工作版本。
- 保存/发布时给出影响预览、失败原因和审计记录。

#### 4. Paths 是配置中心而不是单一任务页，发布/诊断/历史都在一屏

- `web/src/app/admin/sales-trainer/paths/page.tsx:22` 到 `:42` 通过 query 参数 `module` 聚焦模块。
- `web/src/app/admin/sales-trainer/paths/page.tsx:44` 到 `:75` 同一页根据模块渲染业务礼仪或音频/PPT 绑定编辑器。
- `web/src/app/admin/sales-trainer/paths/page.tsx:121` 到 `:134` 将保存、发布、回滚等操作全部交给 `PathConfigCenter`。
- `web/src/components/admin/sales-trainer/path-config-center.tsx:79` 到 `:175` 同时渲染变更说明、保存、发布、日志、刷新诊断。
- `web/src/components/admin/sales-trainer/path-config-center.tsx:99` 到 `:121` 将发布预览内联在配置页。
- `web/src/components/admin/sales-trainer/path-config-center.tsx:177` 到 `:185` 在同页渲染所有模块卡片和当前模块编辑器。
- `web/src/components/admin/sales-trainer/path-config-center.tsx:188` 到 `:197` 同页还放运营检查、学员预览、历史记录。

风险：作为全局配置中心可以接受较多信息，但不适合作为 PPT 讲解训练的主入口。继续往此页叠加 PPT 讲解治理会进一步放大“配置、诊断、发布、历史、业务资产绑定”耦合。

建议：保留 `/paths` 作为全局配置中心，另建 PPT 讲解任务页。PPT 页可复用 path config 的 domain/API，但 UI 只展示 PPT 讲解相关模块，并将发布预览、诊断、审计作为清晰的独立区块或子路由。

#### 5. Units 路由较清晰，但历史/回滚仍内联在列表

- `web/src/app/admin/sales-trainer/units/page.tsx:185` 到 `:201` 页面文案明确列表只做浏览与流程引导，新建/编辑独立路由。
- `web/src/app/admin/sales-trainer/units/page.tsx:286` 到 `:297` 行操作进入编辑、发布、历史。
- `web/src/app/admin/sales-trainer/units/page.tsx:312` 到 `:370` 历史和回滚以内联卡片存在列表页。
- `web/src/app/admin/sales-trainer/units/new/page.tsx:115` 到 `:155` 是独立新建页。
- `web/src/app/admin/sales-trainer/units/[unitId]/edit/page.tsx:129` 到 `:165` 是独立编辑页。

风险：核心 CRUD 拆分已合理。残余风险是历史/回滚属于审计/发布治理，后续复杂化后会拖重列表页。

建议：短期可保留；中期拆 `/units/[unitId]/history` 或统一接入 `operation-logs` 和发布预览页。

#### 6. Score Standards 路由较清晰，但列表暴露系统提示词片段

- `web/src/app/admin/sales-trainer/score-standards/page.tsx:105` 到 `:121` 列表页主操作进入新建页。
- `web/src/app/admin/sales-trainer/score-standards/page.tsx:180` 在列表展示 `system_prompt` 片段。
- `web/src/app/admin/sales-trainer/score-standards/page.tsx:190` 到 `:195` 行操作为编辑和发布。
- `web/src/app/admin/sales-trainer/score-standards/new/page.tsx:63` 到 `:86` 是独立新建页。
- `web/src/app/admin/sales-trainer/score-standards/[id]/edit/page.tsx:102` 到 `:135` 是独立编辑页。

风险：CRUD 结构基本合格；但系统提示词属于治理敏感内容，列表页展示片段容易泄露内部 prompt 细节。对普通管理员应展示“评分维度/适用模块/版本/状态”，prompt 明文放详情或开发/审计权限下。

建议：列表页移除 prompt 片段或改为“已配置/未配置 + 版本摘要”；PPT 治理入口只展示评分标准名称、适用模块、发布状态和规则摘要。

#### 7. Questions 主流程拆得较好，AI Drafts 是高耦合工作台

- `web/src/app/admin/sales-trainer/questions/page.tsx:184` 到 `:211` 主列表把 AI 草稿、组卷预览、新建题目拆到独立路由。
- `web/src/app/admin/sales-trainer/questions/new/page.tsx:96` 到 `:130` 是独立新建题目页。
- `web/src/app/admin/sales-trainer/questions/[questionId]/edit/page.tsx:106` 到 `:140` 是独立编辑题目页。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:78` 到 `:102` 页面目标涵盖生成、审阅、转正式题、发布、组卷。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:105` 到 `:143` 单页状态同时包含草稿、分类、能力、选择、筛选、生成配置、编辑字段等。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:255` 到 `:285` 同页生成 AI 草稿。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:291` 到 `:322` 同页保存草稿。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:324` 到 `:346` 同页批准并转正式题。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:348` 到 `:370` 同页拒绝草稿。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:763` 到 `:787` 同一审阅表单提供保存、转正式题、拒绝。
- `web/src/app/admin/sales-trainer/questions/drafts/page.tsx:788` 到 `:800` 页面直接展示 Prompt contract 相关说明与正式题编辑跳转。

风险：AI 生成、人工审阅、编辑、转正式题、拒绝都在一页，责任边界不清晰；Prompt/AI 规则也被页面承载，后续治理、审计和失败兜底难以单独演进。

建议拆分：

- `/questions/drafts`：草稿队列。
- `/questions/drafts/generate`：生成任务配置和结果预览。
- `/questions/drafts/[draftId]`：审阅详情。
- `/questions/drafts/[draftId]/promote-preview`：转正式题预览、去重、能力绑定、审计。
- Prompt 契约移到配置/审计视图或只显示版本摘要。

#### 8. Papers 路由较清晰，但历史/回滚内联在列表

- `web/src/app/admin/sales-trainer/papers/page.tsx:173` 到 `:189` 列表页主操作进入新建页。
- `web/src/app/admin/sales-trainer/papers/page.tsx:267` 到 `:289` 行操作提供编辑、发布、历史、归档。
- `web/src/app/admin/sales-trainer/papers/page.tsx:298` 到 `:357` 历史/回滚内联在列表页。
- `web/src/app/admin/sales-trainer/papers/new/page.tsx:137` 到 `:191` 是独立新建试卷页。
- `web/src/app/admin/sales-trainer/papers/[paperId]/edit/page.tsx:158` 到 `:226` 是独立编辑试卷页。
- `web/src/app/admin/sales-trainer/papers/[paperId]/edit/page.tsx:191` 到 `:195` 对归档试卷做只读提示。

风险：主体结构合理。后续若发布影响、题目快照、考试绑定变复杂，列表页内联历史会变重。

建议：中期拆 `/papers/[paperId]/history` 和 `/papers/[paperId]/publish-preview`。

#### 9. Articles 入口与业务礼仪详情承载过多治理动作

- `web/src/app/admin/sales-trainer/articles/page.tsx:114` 到 `:128` 入口页可生成专题草稿。
- `web/src/app/admin/sales-trainer/articles/page.tsx:130` 到 `:143` 入口页可发布学习专题配置。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:52` 到 `:63` 单页状态包含内容、配置、预览、历史、错误。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:75` 到 `:95` 直接加载内容、专题配置、历史；该页未见与其他页面一致的 route access/capabilities 导航模式。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:101` 到 `:112` 可创建文章并跳到学习内容后台。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:114` 到 `:142` 同页绑定内容到专题配置。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:144` 到 `:159` 同页生成草稿。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:161` 到 `:178` 同页预览发布并发布。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:180` 到 `:220` 同页做预览和回滚。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:343` 到 `:381` 历史和回滚内联。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx:385` 到 `:435` 同页展示可绑定内容列表、编辑章节、保存专题草稿。

风险：业务礼仪专题页承担文章选择、专题编排、生成草稿、发布、回滚、历史，已经接近 God page。权限投影模式与其他 sales-trainer 页面不一致，存在直接路由访问治理动作的风险。

建议拆分：

- `/articles/business-etiquette`：专题当前状态和内容结构只读概览。
- `/articles/business-etiquette/edit`：专题内容绑定/排序/章节编辑。
- `/articles/business-etiquette/generate`：从路径配置生成草稿。
- `/articles/business-etiquette/publish-preview`：发布预览、影响、确认发布。
- `/articles/business-etiquette/history`：历史与回滚。
- 同步补齐 route access/capabilities 校验。

#### 10. Articles Import 是独立路由，结构比主详情页清晰

- `web/src/app/admin/sales-trainer/articles/import/page.tsx:54` 到 `:81` 状态集中在导入任务上下文。
- `web/src/app/admin/sales-trainer/articles/import/page.tsx:132` 到 `:157` 提交导入。
- `web/src/app/admin/sales-trainer/articles/import/page.tsx:172` 到 `:198` 发布导入版本。
- `web/src/app/admin/sales-trainer/articles/import/page.tsx:244` 到 `:365` 形成独立导入流程。
- `web/src/app/admin/sales-trainer/articles/import/page.tsx:370` 到 `:580` 发布影响面板。

风险：作为 `/import` 专用流程，上传、预览、发布在同一导入工作流中可以接受。若后续导入为异步批量任务，应拆出导入任务详情和历史。

建议：保留独立导入页；补充导入任务历史、失败行下载、审计链接，而不是并回文章列表。

#### 11. Articles Capabilities 是能力规则 God Page，且暴露 JSON 编辑

- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx:82` 到 `:98` 状态包含快照、能力、章节绑定、选中项、JSON 字段、归档项、权限。
- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx:199` 到 `:207` 新增能力。
- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx:232` 到 `:251` 保存快照。
- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx:253` 到 `:273` 发布能力。
- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx:275` 到 `:296` 归档能力。
- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx:381` 到 `:462` 同页编辑能力、JSON 掌握规则、JSON 证据规则、章节绑定和保存原因。
- `web/src/app/admin/sales-trainer/articles/capabilities/page.tsx:522` 到 `:579` 行内编辑并发布/归档能力。

风险：能力定义、规则 JSON、章节绑定、发布归档都在一页，且直接操作 JSON。对业务管理员不友好，也容易绕过表单校验和规则解释。

建议拆分：

- `/articles/capabilities`：能力列表和状态。
- `/articles/capabilities/new`、`/[capabilityId]/edit`：结构化表单。
- `/articles/capabilities/[capabilityId]/bindings`：章节绑定。
- `/articles/capabilities/[capabilityId]/rules`：规则编辑，使用结构化字段，JSON 仅放开发/高级模式。
- `/articles/capabilities/publish-preview`：快照发布影响。

#### 12. AI Coach 是最严重的单页策略配置耦合

- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:36` 到 `:88` 页面内硬编码模式、卡片类型、事件类型、补救方式、下一步动作。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:122` 到 `:160` 定义大体量配置接口。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:168` 到 `:229` 页面内定义大体量默认配置。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:216` 到 `:229` 页面内定义校验阈值常量。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:236` 到 `:405` 页面内实现复杂校验逻辑。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:560` 到 `:576` 页面状态同时覆盖配置、能力、模型配置、权限等。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:760` 到 `:782` 保存配置。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:784` 到 `:807` 发布配置。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:809` 到 `:850` 自行渲染权限失败和页面头，未采用其他后台页常见的 `AdminIndexShell` 结构。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:1288` 到 `:1360` 同页编辑 prompt template/revision/hash、评分 prompt 绑定等高风险配置。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx:1458` 到 `:1504` 页面内直接封装 request/save/publish config API。

风险：AI 功能治理要求 prompt、模型、temperature、timeout、retry、工具调用、发布和审计可控可追踪。当前页面把全局策略、默认值、校验、prompt 绑定、保存发布都塞在一个客户端页面，长期会导致发布风险、审计困难、误操作成本高。

建议拆分：

- `/ai-coach`：只读概览、当前发布版本、风险状态、最近审计。
- `/ai-coach/model`：模型、超时、重试、降级。
- `/ai-coach/prompts`：prompt 模板/修订绑定，只显示版本摘要和 hash；详情受权限控制。
- `/ai-coach/policies`：提醒、补救、卡片、下一步规则。
- `/ai-coach/validation`：诊断和校验失败项。
- `/ai-coach/publish-preview`：发布影响、diff、确认、回滚。
- 将默认配置和校验规则迁出页面，至少集中到 shared config/schema，并由 API 返回治理状态。

#### 13. Records、Audio Submissions、Readiness 路由整体健康

- `web/src/app/admin/sales-trainer/training-records/page.tsx:266` 到 `:287` 列表 API 与过滤器在列表页。
- `web/src/app/admin/sales-trainer/training-records/page.tsx:396` 到 `:567` 表格行操作进入详情。
- `web/src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.tsx:501` 到 `:683` 详情页集中展示摘要、重评分、补救、能力、快照、原始记录、日志。
- `web/src/app/admin/sales-trainer/audio-submissions/page.tsx:58` 到 `:134` 音频提交列表进入详情。
- `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx:121` 到 `:140` 详情页提供重试转写/评分。
- `web/src/app/admin/sales-trainer/readiness/page.tsx:210` 到 `:307` 准备度工作台展示分组与指标。
- `web/src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx:525` 到 `:635` 学员档案读证据和复核记录。
- `web/src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx:637` 到 `:793` 档案页内联人工复核动作。

风险：列表/详情拆分清晰，运维动作放详情页是合理的。细节风险在于训练记录筛选仍使用学员编号、训练任务编号、材料版本编号等偏工程字段，详情页展示原始记录/JSON 应明确限定管理员调试或审计上下文。

建议：暂不作为优先拆分对象。后续将 raw record 折叠到“调试/审计详情”，列表过滤逐步改成业务语义优先。

### Route Clarity Matrix

| 区域 | 当前治理形态 | 问题等级 | 建议目标 |
| --- | --- | --- | --- |
| PPT 讲解治理入口 | 分散在 `paths`、`materials`、`score-standards` | P1 | 新增任务型治理入口，聚合绑定、发布、诊断、审计 |
| `materials` | 列表 + 新建 + 详情 + 上传 + 发布同页 | P1 | 拆列表、新建、详情、上传、发布预览 |
| `paths` | 全局配置 + 发布 + 诊断 + 历史同页 | P1 | 保留配置中心；PPT 场景另建聚焦入口 |
| `ai-coach` | 全局 AI 策略 God page | P1 | 拆概览、模型、prompts、策略、诊断、发布预览 |
| `articles/capabilities` | 能力规则、JSON、绑定、发布归档同页 | P1 | 拆列表、编辑、绑定、规则、发布预览 |
| `questions/drafts` | AI 生成、审阅、编辑、转正式题、拒绝同页 | P1 | 拆生成、队列、审阅详情、转正式预览 |
| `articles/business-etiquette` | 专题详情、绑定、生成、发布、历史、回滚同页 | P1 | 拆概览、编辑、生成、发布预览、历史 |
| `units` | 列表/新建/编辑清晰，历史内联 | P2 | 后续拆历史/发布预览 |
| `score-standards` | 列表/新建/编辑清晰，列表露 prompt 片段 | P2 | prompt 明文收敛到详情/授权视图 |
| `questions` 主列表 | 列表/新建/编辑清晰 | P2 | 保持；重心在 drafts |
| `papers` | 列表/新建/编辑清晰，历史内联 | P2 | 后续拆历史/发布预览 |
| `records/readiness/audio` | 列表/详情清晰，详情承载运维动作 | P3 | 保持；收敛 raw/debug 展示 |

### 可落地优化顺序

1. **先做 PPT 讲解训练治理入口，不先重构全站 CRUD。** 新增专门页面，围绕“能否发布 PPT 讲解训练”组织信息：当前训练单元/路径模块、材料、材料版本、评分标准、发布诊断、最近变更、审计记录。缺数据时在当前页提供选择已有、快速新建最小对象、上传版本、自动绑定、稍后补充的轻量入口。
2. **把 `materials` 拆出最小关键路由。** 至少先拆 `/materials/new`、`/materials/[id]`、`/materials/[id]/upload` 或上传抽屉，避免继续把新建、上传、发布叠在列表页。PPT 治理入口复用这些能力的轻量版本。
3. **给 PPT 发布建立明确 publish preview。** 不要只在 `paths` 内联预览；需要可分享/可审计的发布预览 surface，展示发布后影响的路径模块、材料版本、评分标准、学员可见状态、失败 gate。
4. **收紧 `score-standards` 列表暴露。** 列表不展示系统提示词明文片段；PPT 治理入口展示评分标准摘要与版本状态即可。
5. **拆 `ai-coach` 高风险策略页。** AI 治理风险最高，建议在 PPT 入口稳定后拆概览、prompt、模型、策略、诊断、发布预览。
6. **拆 `questions/drafts` 的 AI 生成/审阅/转正式题链路。** 这是第二类 AI 治理耦合，高风险动作应有独立预览与审计。
7. **拆 `articles/business-etiquette` 与 `articles/capabilities`。** 它们与本次 PPT 入口不是同一主线，但已违反 admin console route pattern，应纳入后续治理。
8. **最后处理低风险内联历史。** `units`、`papers` 的历史/回滚可以中期拆，不阻塞本次 PPT 入口。

### Related Specs

- `.trellis/spec/frontend/admin-console-patterns.md:9` 到 `:22` 要求后台按 intent-based surfaces 组织，把 browse/view/create/edit/import/diagnostics/global config 拆成独立页面或 surface。
- `.trellis/spec/frontend/admin-console-patterns.md:26` 到 `:34` 明确五条硬规则：列表页不放完整新建/编辑表单；导入独立；详情/编辑分离；子资源走子路由；策略与资产分离。
- `.trellis/spec/frontend/admin-console-patterns.md:68` 到 `:79` 给出标准路由树：`/admin/{resource}`、`/new`、`/import`、`/[id]`、`/[id]/edit`、`/[id]/{sub-resource}`。
- `.trellis/spec/frontend/admin-console-patterns.md:85` 到 `:92` 要求 publish gate/error list 使用 dedicated page/shareable URL，async/bulk import 使用 dedicated page。
- `.trellis/spec/frontend/admin-console-patterns.md:96` 到 `:117` 要求每页一个主要 surface task，行操作不做核心字段编辑。
- `.trellis/spec/frontend/admin-console-patterns.md:178` 到 `:189` 将 God page、List+form same page、Inline import、Editable global policy on asset detail、Row inline core edit 列为反模式。
- `.trellis/spec/frontend/admin-console-patterns.md:237` 到 `:247` 要求治理诊断来自 API payload，不使用页面本地常量伪造。
- `docs/api-contract/sales-trainer.md:13` 到 `:17` 定义新人训练路径覆盖 PPT/material learning、audio、scoring、topics、papers、AI Coach、records、audit，并要求实时门禁 fail-closed。
- `docs/api-contract/sales-trainer.md:21` 到 `:31` 明确材料是独立域，PPT 话术门禁必须使用已发布材料并冻结快照。
- `docs/api-contract/sales-trainer.md:33` 到 `:70` 要求后台能力投影统一来自 `/capabilities`，导航、按钮、直达页面都使用同一投影并 fail-closed。
- `docs/api-contract/sales-trainer.md:84` 到 `:88` 要求模块配置以服务端为 source of truth，前端不得把标签、顺序、绑定当成源头硬编码。
- `.trellis/spec/backend/sales-trainer-learning-topic-governance.md`：业务礼仪专题治理相关规则，支持对 `articles/business-etiquette` 与 `articles/capabilities` 的拆分建议。

### External References

- 未使用外部网络资料；本次为内部代码审查。
- 本地依赖版本参考 `web/package.json`：Next.js `16.2.7`、React `19.2.3`、Radix dialog/tooltip、Vitest。当前建议不需要新增依赖。

## Caveats / Not Found

- `.trellis/scripts/task.py current --source` 返回当前任务为空；本次按用户明确给出的任务目录写入研究文件，没有猜测其他目录。
- 已遵守 CodeGraph first：存在 `.codegraph/` 时先使用 `codegraph explore` 与 `codegraph node` 理解 sales-trainer 后台链路，再用 `find`、`rg`、`nl` 补充未索引文件和精确行号。
- `web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx` 未被 CodeGraph 索引命中，已用只读方式直接查看文件行号。
- 本次只读前端页面与相关规范/API 文档，未深入审查后端服务实现、数据库 schema、权限策略实现细节。
- 未运行测试或构建，因为本任务是研究审查，不修改产品代码。
- 未修改产品代码、规范文件、脚本或其他任务目录；仅写入本 research 文件。
