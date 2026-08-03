# 切片 5：能力证据、达标档案与人工复核

## Goal

建立跨 Lesson、Quiz、录音和 AI Coach 的统一能力证据体系，把分散的活动结果投影成可追溯的新人基础训练档案，并通过培训负责人复核形成正式 `foundation_ready` 结论、补练计划、申诉和再评闭环。

本切片是首发训练主线的最后业务环节；AI 只提供摘要和建议，正式结论由受权人员作出。

## Dependencies

- 切片 0：能力、证据、Readiness、权限和事件契约。
- 切片 1：Outbox、任务和 AI 摘要治理。
- 切片 2：Lesson/Quiz Outcome 和路径门禁。
- 切片 3：Audio Outcome、重评与质量标记。
- 切片 4：Coach Outcome 和补练历史。

## Product Scope

- 七类标准能力。
- 不可变证据记录。
- Readiness Dossier 和 Snapshot。
- 风险/待办复核队列。
- 培训负责人正式决策。
- 补练分配、申诉、重评重开和校准。

## Requirements

### R1. Canonical Competency Model

- 建立稳定 Competency 身份和修订。
- 首发标准能力：
  - 产品知识；
  - 客户理解；
  - 需求发现；
  - 价值表达；
  - 异议处理；
  - 流程与合规；
  - 沟通结构。
- 每项能力定义用户语言描述、可观察行为、证据类型、最低要求和适用范围。
- 能力定义更新产生新修订，不改写历史证据。
- 支持组织在受控范围内扩展映射，但不得破坏标准能力统计。

### R2. Competency Mapping

- Lesson、QuestionRevision、QuizRevision、ScorecardDimension、CoachCheckpoint 和 ActivityDefinition 可映射一个或多个 Competency。
- Mapping 包含权重、证据角色（知识/应用/表达等）和适用修订。
- 发布检查确保所有首发 Activity 都有有效 Mapping。
- 前端不自行维护能力枚举或权重。

### R3. Immutable Evidence

- 每个 ActivityOutcome 产生一个或多个 `CompetencyEvidenceRecord`。
- Evidence 保存：
  - learner/enrollment；
  - competency revision；
  - source activity/attempt/outcome version；
  - evidence type；
  - observed score/result；
  - confidence/quality；
  - source refs；
  - validity；
  - created by/system；
  - timestamp。
- Evidence 不原地覆盖；重评、人工失效或纠正产生新记录/状态变更和审计。
- 相同 OutcomeVersion 重放不会重复创建 Evidence。

### R4. Evidence Validity

- 区分 valid、superseded、invalidated、pending_review、insufficient_quality。
- 音频无法评分、AI schema 失败、未完成活动不能作为有效未通过证据。
- Regrade 新版本 supersede 旧版本，但历史可查看。
- 证据过期规则如启用必须配置化、可解释且不改写原记录。

### R5. Competency Projection

- 生成每个能力的当前投影：
  - 最新有效结果；
  - 多来源覆盖；
  - 趋势；
  - 证据数量与质量；
  - 缺口；
  - 最近活动；
  - 是否满足复核前置条件。
- 不用简单平均掩盖明显短板。
- 规则区分门槛型要求和趋势/参考信息。
- 投影算法修订化；Readiness Snapshot 保存使用的 policy revision。

### R6. Readiness Dossier

- 每个 Enrollment 有一个 Readiness Dossier。
- Dossier 聚合：
  - 路径修订与完成度；
  - 七项能力投影；
  - 关键 Activity Outcome；
  - 无效/待处理证据；
  - 补练历史；
  - AI 摘要草稿；
  - 人工决策历史。
- Dossier 是正式业务对象，不是临时报表或聊天消息。
- 支持从事件增量更新，并提供全量 rebuild/reconcile 命令。

### R7. Readiness Snapshot

- 发起复核时冻结 Snapshot：
  - 所有使用的 evidence ids/version；
  - competency policy revision；
  - path revision；
  - 生成时间；
  - 缺口与风险；
  - AI summary revision（若有）。
- 复核期间新证据到达时标记 Snapshot stale，不静默改变审查材料。
- Reviewer 可选择刷新 Snapshot，旧 Snapshot 与决策仍保留。

### R8. Review Eligibility

- 达到以下前置条件后可申请/自动进入复核队列：
  - 必需活动完成；
  - 必需能力有足够有效证据；
  - 无阻塞处理中的任务；
  - 无未解决质量/权限/数据冲突；
  - 路径定义的门禁满足。
- 不满足时给出明确缺口和下一步。
- AI 只能建议“可能已准备好”，不能绕过 eligibility。

### R9. Review Queue

- 培训负责人看到按风险和等待时间排序的队列，而非原始记录列表。
- 队列聚合重复待办，解释排序原因。
- 筛选支持 Cohort、组织、状态、能力缺口、等待时长和 Reviewer。
- 显示数据新鲜度、部分失败和 stale Snapshot。
- 支持就地指派 Reviewer、快速查看证据和发起补练。

### R10. Human Review Decision

- 正式命令至少包括：
  - `approve_foundation_ready`；
  - `request_retraining`；
  - `request_more_evidence`；
  - `reject_due_to_integrity_issue`；
  - `close_without_decision`（受策略限制）。
- 决策必须保存 Reviewer、capability、Snapshot、理由、备注、时间和审计。
- `foundation_ready` 只能由有权限 Reviewer 在有效 Snapshot 上授予。
- AI 摘要和建议必须明确标注为辅助。

### R11. Retraining Plan

- Reviewer 可基于能力缺口分配具体 Activity/Stage 补练。
- 优先复用现有已发布 ActivityDefinition；缺少对象时在当前 Dossier 内就地选择或快速创建最小草稿并交由管理员完善。
- Retraining Assignment 保存原因、目标能力、截止时间、关联证据和完成规则。
- 完成补练后自动更新 Evidence、Dossier 和复核状态。
- 不要求 Reviewer 离开当前流程到其他模块补数据。

### R12. Appeal And Correction

- 学员可针对录音质量、转写、评分或复核事实错误发起申诉。
- 申诉不直接删除原结论；创建 Case 并关联证据与决策。
- Reviewer/管理员可触发重转写、重评、证据失效或重新复核。
- 新有效 Evidence 到达后，相关 Dossier 标记 stale/reopened。
- 每一步保留时限、责任人、状态和审计。

### R13. Calibration

- 提供 Reviewer 校准视图：同类能力、相似证据、决策分布和分歧。
- 不用模型自动统一人工结论。
- 规则或 Rubric 变更可评估影响并触发抽样复核。
- 保存 calibration session 和行动项，避免只做一次性报表。

### R14. AI Summary

- AI 可基于 Snapshot 生成结构化摘要草稿：
  - 已有证据事实；
  - 计算结果；
  - 风险与缺口；
  - 建议复核点。
- 摘要必须引用 evidence ids/refs，区分事实与推断。
- Reviewer 可编辑、拒绝或重新生成。
- AI 失败不阻塞人工复核；系统提供确定性档案视图。

### R15. Learner View

- 学员看到：
  - 当前训练完成情况；
  - 各能力的用户语言反馈；
  - 待完成/待处理/待复核；
  - 正式决定与理由；
  - 补练和申诉入口。
- 不展示内部风险分、Reviewer 私密备注、模型原始输出或其他学员数据。
- “未达标”必须带下一步，不形成无出口状态。

### R16. Audit And Security

- 所有正式决策、覆盖、证据失效、重开、指派和申诉动作审计。
- 后端执行组织与对象级权限。
- 导出受权限、脱敏、水印/审计和数据保留策略控制。
- 重要结论不只通过 Toast 通知，必须持久化并可再次访问。

## Acceptance Criteria

- [x] 七项标准能力有稳定身份、修订和用户语言说明。
- [x] 所有首发 Activity 的 Outcome 都能幂等地产生 Evidence。
- [x] 无法评分、处理中或非法 Evidence 不进入正式达标计算。
- [x] Regrade 新结果 supersede 旧结果但历史可追溯。
- [x] Dossier 可从事件增量更新，也可全量 rebuild 得到一致结果。
- [x] Review Snapshot 冻结证据；新证据到达时显式 stale。
- [x] 只有有权限人工 Reviewer 能授予 `foundation_ready`。
- [x] AI Summary 失败不阻塞复核，且事实均有证据引用。
- [x] Reviewer 可在当前档案中分配补练，无需跳出流程补数据。
- [x] 补练完成后档案更新并自动重入复核条件判断。
- [x] 学员可发起申诉，重评后相关复核可重开。
- [x] 跨组织访问、越权导出和越权决策被拒绝并审计。

## Verification

- Evidence 幂等、supersede、invalidate 和 rebuild 集成测试。
- Readiness policy 单元测试：门槛、趋势、证据不足、质量不足。
- 并发测试：复核中证据到达、重复决策、两个 Reviewer 同时提交。
- 权限矩阵测试：学员、负责人、编辑、训练管理员、系统管理员。
- E2E：
  - 正常完成 -> 复核 -> foundation_ready；
  - 未达标 -> 补练 -> 重试 -> 再复核；
  - 申诉 -> 重评 -> Snapshot stale -> 重开。
- AI fake：摘要正常、无引用、schema invalid、超时。

## Definition Of Done

- 首发业务从训练活动完整闭环到人工正式结论。
- 每个结论可追溯到不可变证据、规则修订和 Reviewer。
- 任何失败、申诉、重评和补练都有明确状态与下一步。
- 管理队列可实际运营，不依赖手工拼 Excel 或查日志。
- 文档、指标、审计、导出和回滚策略完整。

## Out Of Scope

- 不评估真实成交业绩或 CRM 工作表现。
- 不允许 AI 自动审批正式达标。
- 不实现 Realtime 角色扮演等级。
- 不建设通用 HR 绩效系统。

## Risk And Rollback

- 风险等级：P1。
- 主要风险是错误 Evidence 或规则变更影响正式结论。
- Readiness 规则、Snapshot 和 Decision 全部修订/版本化；新规则不改写历史。
- 必要时暂停新复核、重建 Projection、标记受影响 Snapshot stale，而不是直接删除结论。
