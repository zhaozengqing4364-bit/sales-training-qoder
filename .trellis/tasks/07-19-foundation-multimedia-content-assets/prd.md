# Foundation 多媒体内容资产与学习呈现

## Goal

把当前偏文字的 Source/学习单元扩展为真实新人销售训练可用的内容资产闭环，使内容编辑能创建、上传、解析、预览、精编、版本化并发布 PPT/PPTX、PDF/办公文档、Demo 视频或受控链接、讲解稿、示范音频和附件；新人能在学习活动中安全、连续地查看这些内容。

## Dependencies

- `07-19-foundation-authoring-contract-inventory` 已冻结资源与发布合同。

## Page Contract

当内容编辑准备一项新人训练材料时，帮助其从文件、链接或手工内容建立受治理来源，查看解析/预览结果，编排成学员可读的学习单元并提交发布，最终得到可被路径精确绑定的资源修订。

主要页面：

- 内容中心列表：搜索、类型、状态、解析状态、引用与负责人；
- 内容详情：来源/版本、预览、精编内容、引用影响、历史；
- Editor–Preview：左侧结构化内容块，右侧学员视角预览；
- 上传/处理结果页：持久任务进度、部分成功、重试和结果位置。

## Data And Domain Contract

### R1. 来源资产

在 `learning` 权威内扩展 `SourceDocumentRevision` 的受控元数据，至少表达：

- `source_type`: file / url / manual；
- `content_kind`: document / slide_deck / demo_video / external_demo / script / example_audio / attachment；
- 原始文件名、可信 MIME、大小、hash、语言、页数/时长（可得时）；
- artifact ref、解析器版本、预览版本、处理状态和失败原因；
- working/published revision、组织范围、创建者和审计。

不得把公开 URL、任意 iframe、原始 HTML/JavaScript 当成可直接执行的学员内容。

### R2. 支持范围

首批文件至少覆盖：

- PPT/PPTX；
- PDF、DOCX、TXT、MD、XLS/XLSX；
- MP4/WebM 或项目现有播放器可安全解码的视频格式；
- MP3/WAV/M4A 或项目现有音频链路可安全解码的示范音频；
- 普通附件下载。

文件大小、时长和格式采用配置化 allowlist/限制；验证真实签名与解码结果，不只信扩展名和 MIME。新依赖必须先证明现有 PPT/媒体能力无法复用，并记录部署、License、包体积与移除路径。

### R3. 解析与预览

- PPT/PPTX 产生可分页预览（缩略图或受控渲染）与可用文本提取；保留原文件下载权限。
- 文档产生来源锚点和结构化文本；表格材料明确可解析范围。
- 视频/音频提取安全元数据和可播放派生，不在请求内做长处理。
- 处理使用 DurableTask；状态至少有 pending/processing/partial/ready/failed/cancelled。
- 上传请求只完成校验、受控 artifact 落地/登记和任务入队；文件转换、媒体解码、外链探测等慢 IO 不得放在长数据库事务内，最终状态以独立短事务和 Outbox 回写。
- 部分页失败保留成功页和原文件，明确缺失范围并支持从失败阶段重试。

### R4. 学习单元内容块

`LearningUnitRevision` 使用封闭联合内容块引用 exact source revision/anchor，例如：rich_text、source_excerpt、slide_deck、video、audio_example、attachment、checkpoint。每块有稳定 ID、标题、说明、顺序和可访问替代文本；未知类型 fail closed。

原始资料不可被 AI 改写。AI 只能生成精编工作草稿，必须展示来源锚点、差异和人工确认后才进入 ReleasePlan。

### R5. 学员呈现

- Lesson Runner 按内容块呈现 PPT、Demo、正文、示范音频和附件，不退化为文件名列表。
- 每个关键材料显示训练目标、当前页/段、完成条件和下一步。
- 外链不可嵌入、网络失败、媒体不支持时提供明确替代动作，不能伪装成功。
- 学员端不得暴露 artifact storage key、数据库 ID、解析器、内部状态码或原始 AI 数据。
- 完成规则由领域合同决定；仅打开链接不自动等同完成全部学习。

### R6. 版本、引用与归档

- 同一逻辑内容可新增 working revision、比较差异、验证并纳入 ReleasePlan。
- working 内容可在同一 ReleasePlan 中被其他 working 资源引用；只有完整依赖闭包通过审核与校验后才移动 published pointers。
- 已发布修订不可原地修改；活跃 Attempt 继续使用冻结修订。
- 被 Path/Attempt 引用的修订不能硬删；归档前展示引用影响。
- 内容详情可追到引用它的 LearningUnit、Question、AudioMaterial 和 Path。

## Required States

覆盖首次上传、处理中、部分成功、解析失败、预览失败、外链失效、无权限、重复 hash、并发冲突、超限、取消、重试、发布成功和已归档只读。失败必须保留标题、类型、说明和未提交精编内容。

## Acceptance Criteria

- [ ] 内容编辑可在新管理端创建上述七类内容资产，不使用 Legacy 页面。
- [ ] 上传校验、组织隔离、幂等、持久处理、进度和失败恢复均有后端证据。
- [ ] PPT/PPTX 可查看分页预览和提取结果；失败时仍能受权访问原文件并重试。
- [ ] Demo 视频/链接、讲解稿与示范音频可进入结构化学习单元并显示学员预览。
- [ ] LearningUnit 只引用 exact revision/anchor，发布后不可变且来源可追溯。
- [ ] 新学员 Lesson Runner 能连续使用真实内容，桌面、360px、200% zoom、键盘和长文件名可用。
- [ ] 普通 UI 不执行任意 HTML/脚本，不泄露内部 artifact/Prompt/Provider 字段。
- [ ] 当前文字学习单元向后兼容，无内容块的已发布修订仍可读取。

## Minimal Verification

- 后端：内容块 Schema、文件验证、幂等、组织隔离、解析状态、版本/归档保护单元与针对性集成测试。
- 前端：内容列表/编辑器/Lesson Runner 的组件测试和 API DTO→ViewModel 测试。
- 浏览器：上传一个 PPT、创建一个含 Demo 与讲解稿的学习单元、学员预览和失败恢复关键路径。
- 只对相关 Python/TS/TSX 做 Ruff、类型、ESLint；仅当引入公共上传/存储接口时运行其跨模块契约测试。

## Out of Scope

- 不建设在线 PPT 编辑器或视频剪辑器。
- 不做实时直播、视频会议或实时客户对练。
- 不自动生成未经人工审核的正式课程。
- 不迁移 Legacy PPT；迁移由后续切换任务完成。

## Risk And Rollback

- 风险等级：P1（文件安全、存储、内容合同和学员呈现）。
- 新字段/API additive；功能可由 capability/feature flag 隐藏，既有文字 Lesson 继续工作。
- 处理失败不改变 published pointer；回滚恢复旧页面读取，保留新 artifact 供清理任务审计处理。

## Likely Areas

- `backend/src/learning/`、受控文档存储与 DurableTask；
- `backend/src/foundation_admin_api.py`、ReleasePlan 依赖校验；
- `web/src/components/admin/newcomer-training/content-workspace.tsx`；
- `web/src/components/newcomer-training/activity-runners/lesson-runner.tsx`；
- 现有 `common/ppt`、presentation preview 与媒体组件仅在确认契约适配后复用。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，不顺带重构通用上传体系。
