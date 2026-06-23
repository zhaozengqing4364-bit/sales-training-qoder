# 15 分钟信息化负责人实时客户对练 v1

## Goal

构建并验证一个高质量实时客户对练样板：销售新人和国企、央企、政教医的信息化负责人进行 12-15 分钟首次拜访语音对练，训练重点是石犀数据流动治理平台的方案可信度和需求澄清。v1 的目标不是做完整平台，而是证明一个场景可以稳定扮演、知识可控、结束后可解释评分。

## What I already know

- 主线产品是实时客户对练平台，角色、人设、知识库、实时语音、评分为核心。
- v1 客户画像固定为国企、央企、政教医的信息化负责人 / 信息中心主任 / 数字化建设负责人。
- v1 场景固定为首次拜访，产品固定为石犀数据流动治理平台。
- 用户明确要求方案符合当前技术可实现，效果不好不如不做。
- 用户指出当前问题包括记忆漂移、长流程角色扮演弱、没有搭载公司或客户知识库、无法长时间保存上下文。
- StepFun Realtime 可支撑实时语音会话，但 15 分钟准确扮演不能只靠模型长 prompt，需要后端角色合同、状态卡、知识预取和离线评分。
- 当前系统已有实时语音、Persona、知识库、评分、训练路径、快照等基础概念，v1 应优先收敛和复用。

## Requirements

- 本 PRD 及对应设计文档现在作为后续 v1 implementation scope 的实现依据，不再保留“当前不进入实现阶段，因此不修改代码”的约束；后续实现应按本 PRD/设计拆分最小任务推进。
- 提供一个固定 v1 训练模板：信息化负责人 / 首次拜访 / 石犀平台 / 12-15 分钟。
- v1 入口轨道选择平台直练 `/practice/[sessionId]`，通过 `VoiceRuntimePolicyService` / `voice_policy_snapshot` / StepFun realtime 路径开练；不要接入 `sales_trainer` 新人训练路径中的 realtime 占位，也不要通过 `PracticeTemplate` 课程闭环开练。
- 开练时冻结 `roleplay_contract`，包含客户身份、场景、训练目标、可见知识、隐藏知识、行为规则和禁止行为。
- `roleplay_contract` 必须记录 hash 和 revision refs，runtime 只消费本次冻结快照；禁止 runtime fallback 到 latest assets。发布或回滚只影响未来会话，v1 入口必须能通过配置或 feature flag 关闭。
- 使用轻量 `session_state_card` 管理阶段、客户态度、已确认事实、学员完成动作、缺失动作、已提出异议和下一轮压力。
- 训练分四阶段：开场与来意、现状澄清、方案可信度、下一步推进。四阶段是 roleplay phase/view，不是新的 `SalesStageCapability` stage 枚举，不新增第三套销售 stage。
- 异步状态卡更新必须带 version 或 sequence，乱序更新丢弃；更新失败时保留上一版。重连时从 persisted snapshot / runtime_state 恢复当前合同、阶段、状态卡和必要事实。
- 阶段推进采用半自动策略：默认按时间推进，但可根据学员关键动作完成情况延迟或加压。
- 知识库分为客户背景 KB、产品事实 KB、评分教练 KB，严格区分 AI 客户可见与不可见内容。
- 产品事实缺失或检索超时时，AI 客户应自然追问或表达“需要你们给出可验证材料/PoC 指标”，不得臆测产品能力；同时记录 quality flag。
- 实时语音热路径只放短角色锚点、当前状态卡、最近几轮对话和必要事实。
- 状态卡更新、知识预取、角色漂移检查走旁路异步，不阻塞实时语音。
- 评分采用离线大模型评分 + 规则校验 + 原话证据。v1 使用 6 项 100 分 business rubric 作为版本化 scoring ruleset / report projection；不得破坏现有架构文档里的 5 个教练维度，必要时保留映射说明：6 项用于本样板报告，5 维若存在则作为现有 evaluation 兼容层。
- 提供学员反馈视图和管理员质检视图。
- 管理员视图必须能区分学员能力问题和 AI 角色质量问题。
- 权限默认 fail-closed：learner 只能看总分、分项、建议、学员原话证据；admin/supervisor 可看完整转写、评分 JSON、状态卡、角色合同 hash、AI 质量检查；ops 只能看脱敏日志和指标。
- 观测字段至少记录 `roleplay_contract_hash`、`state_card_version`、`violation_count`、`blocking_violation_count`、`knowledge_timeout_count`、`scoring_confidence`、`quality_flags`。
- 至少设计 9 段评分回归样本结构，用于后续验证 prompt、模型和知识库调整后的评分稳定性。样本按优秀、普通、较差各 3 段组织，覆盖开场、现状澄清、风险识别、价值说明、可信度回应、下一步推进、隐藏信息防泄漏、知识缺失降级、评分证据绑定；本 PRD 只定义结构，不写完整 transcript。

## Acceptance Criteria

- [ ] 设计文档明确 v1 目标、用户画像、训练流程、技术架构、评分体系和暂不做范围。
- [ ] 角色合同样板明确可见知识、隐藏知识、行为规则和禁止行为。
- [ ] 状态卡样板覆盖阶段、态度、事实、动作、异议和下一轮压力。
- [ ] 知识库接入方案明确哪些知识可以给 AI 客户看，哪些只能给评分器或管理员看。
- [ ] 评分方案明确谁评分、怎么评分、如何绑定原话证据、如何规则校验、何时人工复核。
- [ ] 报告方案区分学员反馈视图和管理员质检视图。
- [ ] v1 明确不做多行业自由配置、长期客户记忆、实时教练打断、模型微调和复杂后台配置中心。
- [ ] 后续实现前能基于本 PRD 拆分出最小实现任务。

## Definition of Done

- 方案文档写入 `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md`。
- Trellis 任务 PRD 写入 `.trellis/tasks/06-23-15-v1/prd.md`。
- 方案保持 v1 收敛，没有把长期客户关系、多角色组织博弈、复杂后台配置中心提前纳入 MVP。
- 后续实现基于本 PRD/设计推进，并在实现任务中补充代码级影响面、测试计划、发布与回滚策略。

## Technical Approach

v1 采用热路径、旁路和离线三层架构：

- 热路径：StepFun Realtime 负责语音输入输出、自然接话和短期上下文。
- 旁路：后端保存转写、更新状态卡、预取知识、检测角色漂移。
- 离线：评分模型读取完整转写、状态卡和评分规则，生成带原话证据的报告。

核心原则：

- Realtime = 说话。
- Roleplay Contract = 角色边界。
- State Card = 长流程记忆。
- Knowledge Prefetch = 必要事实。
- Offline Scorer = 训练效果。
- Regression Set = 效果不退化。

## Decision (ADR-lite)

**Context**: 用户需要 15 分钟左右流畅、准确的实时客户对练，但当前问题包括记忆漂移、模型长流程角色扮演弱、知识库接入不足和评分可信度不足。

**Decision**: v1 选择验证型单场景方案，只做“国企/央企/政教医信息化负责人首次拜访”样板。实时模型只负责语音互动，长流程记忆、角色边界、知识可见范围和评分分别由角色合同、状态卡、知识预取和离线评分承担。

**Consequences**: 该方案牺牲短期的多场景灵活性，换取可验证的训练效果和更低实现风险。若 v1 稳定，再扩展复访、方案评审、多角色和长期关系史。

## Out of Scope

- 多行业、多客户角色自由配置。
- 长期客户关系记忆。
- 多轮拜访连续剧情。
- 实时教练提示或实时打断评分。
- 模型微调。
- 复杂后台配置中心。
- 每轮强制知识库检索。
- 大范围 UI 重做。

## Technical Notes

- 官方 StepFun Realtime 文档显示实时会话可支撑 15 分钟级体验，但角色稳定性需要后端状态管理和 prompt 边界控制。
- 仓库领域语言已有 Persona、RoleProfile、CaseItem、Roleplay Contract、Visible/Hidden Information Scope、KnowledgeConfigVersion、RagProfile 等概念，应优先复用。
- 本 PRD/设计现在作为后续实现依据；本次文档补丁不创建 migration、不修改 API、不调整前后端代码。
- 正式设计文档：`docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md`。
