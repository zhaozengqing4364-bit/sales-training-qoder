# Foundation 录音讲解材料与评分方案配置

## Goal

把当前主要由 `foundation_standard_pack.py` 预置的 `audio_material` 和 `scoring_scheme` 变成培训管理员可完整维护的领域资源，使 PPT 讲解、公司产品 Demo 讲解等录音任务能够配置材料、任务说明、参考结构、录音约束、评分维度、红线和人工复核策略，并通过 ReleasePlan 发布到新路径。

## Dependencies

- `07-19-foundation-authoring-contract-inventory`。
- `07-19-foundation-multimedia-content-assets` 冻结 SourceRevision/内容块引用合同。

## Page Contract

当训练管理员准备一项录音讲解任务时，帮助其选择真实材料，编写学员任务说明和参考结构，配置可解释的评分方案并预览学员/审核员视角，最终得到可被 `audio_assessment` Activity 精确绑定的已验证修订。

主要页面：

- 讲解与评分总览：PPT 讲解、Demo 讲解等任务及缺失配置；
- 讲解材料 List–Detail/Editor–Preview；
- 评分方案结构化编辑器、版本比较与发布影响；
- 高级 AI 合同 Inspector，仅授权人员可见。

## Domain Contract

继续由 `audio_assessment.AudioActivityResourceRevision` 承载封闭 `resource_type`，但所有写入必须经过领域应用服务、Schema、权限、乐观并发、幂等和审计，禁止管理 API 直接拼装 ORM/JSON。

### R1. 录音讲解材料

`audio_material` working revision 至少结构化表达：

- 业务场景：PPT 讲解、公司产品 Demo、其他批准的异步讲解；
- 标题、目标、为什么重要、学员说明和准备步骤；
- exact SourceDocumentRevision/Anchor 引用；
- 必讲要点、允许知识范围、参考结构、禁用/高风险陈述；
- 示例讲解稿和可选示范音频 exact revision；
- 适用语言、预计准备/录音时长和可访问替代内容；
- 来源、版本、创建/审核/发布审计。

材料只引用已存在的受治理内容，不复制 PPT 原文到多个 JSON 快照；发布时冻结安全的学员投影和 exact refs。

### R2. 评分方案

`scoring_scheme` working revision 使用结构化字段，至少包括：

- 维度 key、用户语言名称、说明、权重和满分；
- 每维达标线、总达标线和关键维度 Gate；
- 红线事实、越权承诺、敏感数据和禁止表达；
- 可验证证据要求、引用来源和低置信度处理；
- AI 评分允许范围、不确定性阈值和人工复核触发条件；
- 参考答案/优秀表现特征，不作为唯一模板答案；
- governed PromptRevision、ModelRoutingRevision、input/output Schema exact refs；
- 重评、失效和历史版本语义。

权重、分数、维度集合、红线和模型合同由后端确定性校验。普通编辑界面不默认显示 system prompt、output schema 或 raw JSON。

### R3. Authoring API

补齐 list/search、create、get、save working revision、validate、compare、archive、reference impact 和 ReleasePlan dependency。快速创建返回最小 working revision；复杂字段可稍后补齐，但未通过校验不得发布。

所有写命令要求 capability、organization/object scope、`If-Match`、`Idempotency-Key` 和审计；跨组织返回隐藏 404 或项目统一安全语义。

### R4. 任务模板与复用

- PPT 讲解和 Demo 讲解使用同一录音评测能力，不新增两套提交/转写/评分 Runtime。
- 差异由材料和评分方案表达，不在深层代码增加 `if ppt` / `if demo` 特判。
- 新建任务时可从受治理模板复制为独立 working revision；后续模板更新不得静默改写已发布任务。
- 录音方式、最大时长/大小、语言和 baseline 仍由 ActivityDefinition 配置，避免与材料/评分方案双重权威。

### R5. 预览与发布

- 学员预览显示材料、任务要求、评分重点、录音限制和示例，不显示机器合同。
- 审核预览显示评分维度、证据要求、红线和人工复核条件。
- 校验精确来源、能力映射、Prompt/Model/Schema、Provider capability、权重与阈值。
- ReleasePlan 原子冻结材料、评分方案及依赖；失败时旧发布保持有效。

## Required States

覆盖首次无资源、缺材料、缺评分、草稿不完整、重复 stable key、并发冲突、来源 stale、Prompt/Provider 不可用、无权限、归档、发布阻塞、发布成功和回滚。表单失败保留所有结构化字段。

## Acceptance Criteria

- [ ] 管理员可在 Foundation 管理端创建、编辑、校验、比较和归档录音材料及评分方案。
- [ ] PPT 讲解与 Demo 讲解均可绑定真实内容资产、参考结构和独立评分方案。
- [ ] 评分 UI 使用用户语言字段；Prompt/Schema/Provider 只在授权高级区出现且不泄露密钥。
- [ ] 后端拒绝权重不闭合、阈值越界、未知维度、无来源、跨组织、未发布 AI 合同和非法红线配置。
- [ ] 发布后新 Submission 冻结 exact 材料/评分修订；旧 Submission、Transcript 和 ScoreOutcome 不漂移。
- [ ] 录音流水线、重评和人工复核继续使用现有单一 Runtime，不出现 PPT/Demo 分叉实现。
- [ ] 快速新建失败可恢复且相同幂等键不会创建重复资源。

## Minimal Verification

- 后端：两个 Snapshot Schema、确定性校验、应用服务、权限、并发、幂等、审计、ReleasePlan 依赖测试。
- 集成：用 PPT/Demo 各发布一个任务并冻结 Submission config snapshot；旧评分版本不变。
- 前端：结构化表单、普通/高级权限、错误映射、dirty/conflict、预览组件测试。
- 浏览器：从内容资产选择材料、创建评分方案、学员预览；不跑无关音频压力测试。

## Out of Scope

- 不重写 ASR、评分 Provider、DurableTask pipeline 或音频上传协议。
- 不实现实时语音反馈或实时客户对练。
- 不迁移旧材料/Prompt；后续迁移任务负责。
- 不允许普通管理员编辑任意 Prompt/JSON。

## Risk And Rollback

- 风险等级：P1（正式评分合同）。
- 新 Authoring API/UI 可关闭；既有 Seed published revisions 和在途 Submission 继续可用。
- 发布失败不移动 active ReleasePlan；回滚重新激活稳定计划，不覆盖评分历史。

## Likely Areas

- `backend/src/audio_assessment/contracts.py`、`models.py`、新增 authoring application/ports；
- `backend/src/foundation_admin_api.py`、`foundation_release_composition.py`；
- `web/src/components/admin/newcomer-training/` 下讲解材料/评分编辑器；
- 现有 audio runtime/pipeline 只做必要合同接入，不顺带重构。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，当前任务不处理旧数据迁移。

