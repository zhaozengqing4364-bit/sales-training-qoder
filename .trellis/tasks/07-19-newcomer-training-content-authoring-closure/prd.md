# 新人训练内容配置与旧数据迁移闭环

## Goal

把现有新人训练从“只有统一工作台入口、部分资源只能绑定预置数据、旧配置与新学员路径断开”的状态，收口为一套可由培训团队独立完成配置、预览、发布和追溯的内容生产闭环。首批迁移现有的 `石犀ppt讲解`、`demo讲解` 与关联 PPT 材料，使管理员能够围绕学习内容、题库测验、录音讲解与评分、结构化 AI 教练、异步客户场景和训练路径完成端到端配置，并确保新学员端只读取统一 Foundation 权威数据。

## Confirmed Context

- 用户的核心目标是新人销售训练：录音/PPT/Demo 讲解、内容学习、题库做题、AI 教练与后续训练形成一条连续路径。
- 实时客户语音对练继续延期；本任务只保留异步客户场景配置，不建设实时 Runtime。
- 管理端应保留一个新人训练产品入口，但不能把内容配置能力压缩成一个难以发现的工作台页面。
- 旧数据未丢失：旧发布路径中仍有 `石犀ppt讲解` 和 `demo讲解`，旧素材库仍有对应 PPT 材料。
- 新学员端 `/newcomer-training` 读取 Foundation 路径与资源修订；旧销售训练页面写入另一套数据，当前没有迁移或兼容桥。
- 新路径编辑器可绑定学习单元、测验、录音材料、评分方案、教练配置和客户场景，但当前快速新建只完整支持学习单元与测验。
- 新内容工作区不支持 PPT/PPTX、视频和音频资产的完整创建、预览、版本与发布流程。
- 题库工作区偏向 AI 候选题审核，尚未形成手工建题、批量导入、分类治理、组卷预览的完整闭环。
- 当前处于开发阶段，用户明确允许按“干净、方便、全面”的方式收口，不要求维持两套管理入口并行。

## Confirmed Decisions

- 新 Foundation 数据模型继续作为唯一目标权威，不恢复旧销售训练模块为长期写入口。
- 旧数据采用一次性、可预览、可重复执行的迁移，而不是长期双写。
- 现有项目 UI、组件、Token 和导航基础保持不变，不另做原型选择或视觉系统重构。
- `石犀ppt讲解` 与 `demo讲解` 迁移后仍保持两个独立训练活动，可分别绑定材料与评分方案。
- “统一入口”表示一个产品入口下有清晰的任务型子工作区，不表示只保留一个模糊页面。
- 路径只编排并冻结精确资源修订；材料、题目、评分、教练和场景分别由领域模块维护。
- 实时客户语音对练继续排除；异步客户场景仍属于新人基础训练闭环。

## Open Questions

- 无阻塞问题；此前批量讨论中的建议已全部接受，本任务按既定边界拆解。

## Requirements

- 建立唯一内容资产与版本权威，覆盖 PPT/PPTX、PDF/文档、Demo 视频或链接、讲解稿、示范音频和附件。
- 在新人训练管理端提供清晰的训练方案、内容中心、题库与测验、讲解与评分、AI 教练、客户场景、学员评测、发布治理入口。
- 所有路径活动绑定精确的已批准资源修订；缺失资源可在当前路径编辑上下文内选择或快速新建并自动绑定。
- 迁移旧发布路径和旧 PPT 材料到 Foundation，并验证新学员端可见、可学习、可提交、可评分。
- 补齐手工建题、批量导入、AI 出题候选审核、分类标签、组卷和测验预览。
- 补齐录音材料、评分方案、教练配置和异步客户场景的创建、编辑、校验、版本、发布与审计。
- 发布前提供依赖校验、学员视角预览、影响预览和失败恢复；已发布修订不可变。
- 旧管理写入口在迁移验收后只读或移除，禁止形成双权威和静默双写。

## Acceptance Criteria

- [ ] 管理员从 `/admin/newcomer-training` 能明确进入所有配置模块，不依赖记忆隐藏 URL。
- [ ] 内容编辑可以创建并发布 PPT、Demo、文档、讲解稿、示范音频等训练资产及其修订。
- [ ] 内容编辑可以从材料形成学习单元、题目与测验，并查看来源与版本关系。
- [ ] 题库支持手工建题、批量导入、AI 候选审核、分类治理、组卷与学员视角预览。
- [ ] 路径编辑器能在当前抽屉内为五类活动选择或快速新建所需资源并自动绑定精确修订。
- [ ] 录音讲解可配置材料、录音约束、评分维度、权重、红线、示例答案与人工复核策略。
- [ ] AI 教练可配置目标、知识范围、卡片类型、介入与补练策略、模型策略和失败降级。
- [ ] 异步客户场景可配置背景、客户角色、分段任务、评分方案和证据要求，但不包含实时对练。
- [ ] 旧 `石犀ppt讲解`、`demo讲解` 和 PPT 材料经预览后迁移，迁移可重复执行且不会产生重复资源。
- [ ] 迁移后新学员端能够按发布路径完成材料学习、做题、录音讲解和后续活动。
- [ ] 旧入口不再产生新权威数据；回滚时能够恢复迁移前读取行为或清晰撤销目标发布。
- [ ] 权限、组织隔离、审计、并发、幂等、错误恢复和长任务状态具备针对性验证证据。

## Definition of Done

- 每个子任务只实现自身明确范围，满足验收后立即停止。
- 修改文件通过静态检查，相关模块单元/集成测试与最小关键路径验证通过。
- 只有公共基础设施、核心跨模块契约或局部测试不足以证明安全时，才运行全量测试。
- UI 覆盖相关 loading、empty、no-result、error、permission、stale/conflict、submitting、partial success 和 recovery 状态。
- 实际渲染页面完成桌面与窄屏关键路径检查，核心操作支持键盘与可见焦点。
- API、版本、权限、状态、审计、迁移、发布与回滚契约有测试或可重复验证脚本。
- 与当前任务无关的问题只记录，不顺带修复或重构。

详细执行边界以 [`execution-policy.md`](execution-policy.md) 为准；每个子任务还必须给出自己的最小测试矩阵。

## Technical Approach

### 1. 唯一权威与分域写入

- `learning` 继续拥有来源材料、精编学习单元、题目与测验。
- 文档/PPT/Demo 链接等来源进入受治理 `SourceDocumentRevision`；学员呈现由 `LearningUnitRevision` 的封闭内容块引用精确来源修订，不把任意 HTML/脚本直接交给浏览器执行。
- `audio_assessment` 继续拥有录音讲解材料、评分方案和异步客户场景资源修订。
- `ai_coach` 继续拥有结构化教练 Profile 修订。
- `newcomer_training` 只拥有路径、阶段、活动、Enrollment 和 Attempt 信封，绑定其他领域的精确修订 ID。
- `ReleasePlan` 保持唯一正式发布协调者，不恢复资源直发或浏览器双写。

### 2. 管理端页面模型

- 保留 `/admin/newcomer-training` 单一产品入口。
- 使用稳定的本地一级导航表达：训练方案、内容中心、题库与测验、讲解与评分、AI 教练、客户场景、学员与评测、发布与治理。
- 列表使用 List–Detail；复杂资源使用 Editor–Preview；路径使用现有三栏 Editor–Preview；发布使用 Process–Approval。
- 路径缺资源时使用 Drawer 完成搜索、预览、快速新建、自动绑定和失败恢复；复杂完整编辑进入对应对象页。

### 3. 迁移与切换

- 先建立目标资源合同和写入口，再执行只读 inventory、dry-run、apply、verify。
- 迁移使用稳定 legacy key + source revision/hash 作为幂等身份，重复运行不得创建重复逻辑资源或修订。
- 迁移发布前显示对象映射、缺失依赖、冲突和将激活的 ReleasePlan；不自动迁移活跃 Enrollment。
- 验收后旧新人训练写入口只读或删除；不建立长期兼容 Facade、双写或静默回退。

### 4. 安全、AI 与长任务

- 上传校验扩展名、MIME、文件签名、大小、组织范围和恶意内容；访问通过受权短时 URL。
- PPT 解析、预览生成、批量导入、AI 出题和必要媒体处理使用持久任务，保留输入、进度、取消/重试和结果位置。
- 数据库事务只记录业务意图、状态、幂等结果与 Outbox；对象存储、文件转换、媒体解码和 Provider 调用不得占用长事务，完成后以短事务回写版本与任务结果。
- Prompt、模型、超时、重试、预算和 Schema 继续走受治理修订；普通内容编辑界面不暴露 Prompt 正文、Provider payload 或 raw JSON。
- AI 产物先进入候选/草稿，人工审核后才能进入正式发布闭包。

## Decision (ADR-lite)

**Context**：原 Foundation 首发把“统一管理入口”和运行时闭环实现了，但把内容生产能力误判为已经完整交付。旧素材与路径仍在 Legacy 表，新管理端对录音材料、评分方案、教练和场景主要只能选择 Seed 资源，导致管理员无法完成实际配置。

**Decision**：保留 Foundation 单一权威和 ReleasePlan，不恢复旧后台作为第二写入口；分十个可验收子任务补齐资源合同、内容资产、题库、录音评分、AI 教练、异步场景、管理导航、路径内绑定、旧数据迁移与端到端门禁。

**Consequences**：这是 P1 跨模块收口，需要 additive schema/API、受治理迁移和实际 UI 验证；收益是培训团队可以独立配置真实训练，不再依赖 Seed 或隐藏旧页面。切换前旧读取保持可回退，切换后禁止双权威。

## Subtasks And Dependencies

| 顺序 | Trellis 子任务 | 交付结果 | 依赖 |
|---|---|---|---|
| 0 | `07-19-foundation-authoring-contract-inventory` | 修正权威合同、资源联合、迁移映射和当前缺口基线 | 无 |
| 1A | `07-19-foundation-multimedia-content-assets` | PPT/PPTX、文档、Demo、讲解稿、示范音频等内容资产与学员呈现 | 0 |
| 1B | `07-19-foundation-question-bank-quiz-authoring` | 手工建题、导入、AI 候选审核、题库治理、组卷与预览 | 0 |
| 1C | `07-19-foundation-audio-scoring-authoring` | 录音讲解材料和评分方案完整配置 | 0、1A 的资产引用合同 |
| 1D | `07-19-foundation-ai-coach-authoring` | 教练 Profile 的创建、编辑、预览、版本和发布 | 0、1A 的来源范围合同 |
| 1E | `07-19-foundation-async-scenario-authoring` | 三段异步客户场景、任务材料、评分与人工复核策略 | 0、1C |
| 2A | `07-19-foundation-admin-ia-capabilities` | 可发现的管理信息架构、真实 capability 与权限状态 | 1A～1E 的路由/对象稳定 |
| 2B | `07-19-foundation-path-inflow-binding-preview` | 五类活动全部支持选择/快建/自动绑定、预览和发布校验 | 1A～1E |
| 3 | `07-19-foundation-legacy-migration-cutover` | 迁移 `石犀ppt讲解`、`demo讲解` 和 PPT，切断旧写权威 | 2A、2B |
| 4 | `07-19-foundation-authoring-e2e-closure` | 管理配置到学员执行的最终验收矩阵与发布/回滚演练 | 0～3 |

合同冻结后，1A 与 1B 可独立推进；1C/1D 只等待 1A 的引用接口冻结即可推进，1E 等待 1C 的评分接口冻结。2A/2B 不得用未完成占位页伪造闭环；迁移和最终验收必须串行。

## Failure And Edge Cases

- 同名或同 hash 旧材料映射到多个目标对象时必须列为冲突，不自动猜测。
- 文件解析部分成功时保留原文件和已生成成果，明确缺失页/片段并允许重试。
- 外部 Demo 链接失效或不允许嵌入时，展示来源与替代打开方式，不把空白播放器当成功。
- 题目导入逐行报告成功、重复、格式错误和权限失败；不得整批假成功。
- 评分权重、阈值、红线或能力映射不合法时阻止发布，但允许保存草稿。
- AI 教练/场景缺 Prompt、模型或来源合同必须 fail closed，并给出管理员修复位置。
- 快速新建失败保留表单、当前 Activity 和已选资源；重试不重复创建。
- 新发布只影响未来 Enrollment；活跃 Enrollment 迁移必须另行 preview/confirm。
- 回滚重新激活已知稳定 ReleasePlan，不删除已产生的 Attempt、Evidence、评分或人工决定。

## Out of Scope

- 实时 WebSocket/Realtime 客户语音对练及低延迟打断能力。
- 新视觉系统、新品牌色、新图标库或全面 UI 重设计。
- 通用低代码工作流编排器。
- CRM 深度集成和真实业绩预测。
- 自动替代培训负责人作出最终达标决定。
- 与本闭环无关的旧模块清理、性能优化和架构重构。

## Technical Notes

- 上游平台 PRD：`.trellis/tasks/archive/2026-07/07-16-newcomer-sales-foundation-platform/prd.md`。
- 管理端单入口：`web/src/components/layout/admin-sidebar.tsx`。
- 新人训练工作区导航：`web/src/components/admin/newcomer-training/workspace-nav.tsx`。
- 路径编辑与资源绑定：`web/src/components/admin/newcomer-training/v2-path-editor.tsx`、`activity-resource-drawer.tsx`。
- 内容与题库工作区：`content-workspace.tsx`、`question-review-workspace.tsx`。
- Foundation 管理 API 与权限：`backend/src/foundation_admin_api.py`、`foundation_admin_permissions.py`、`foundation_admin_workspace.py`。
- 标准包中的预置资源：`backend/src/foundation_standard_pack.py`。
- 旧销售训练素材与路径仅作为迁移来源，不作为目标写权威。
- 现有 planning 任务 `.trellis/tasks/07-16-material-upload-bind-ux` 与本任务 1A/2B 重叠；执行 Wave 0 时必须决定将其并入/标记 superseded，禁止两个任务并行实现相同上传绑定链路。
- 当前缺口证据与对象映射见 [`research/current-state-gap.md`](research/current-state-gap.md)。
- 执行顺序、合并门和停止条件见 [`execution-sequence.md`](execution-sequence.md)。
