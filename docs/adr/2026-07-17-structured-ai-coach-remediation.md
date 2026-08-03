# ADR：结构化 AI Coach、保存优先与有界补练

- 状态：Accepted / implemented in Slice 4
- 日期：2026-07-17
- 决策范围：新人销售基础训练的 `ai_coach` 活动

## 背景

旧 Coach 以自由消息驱动状态，在请求事务中直接调用模型，并在模型返回后才保存回答。它无法可靠证明输入恢复、卡片合法性、Prompt/模型血缘、掌握规则、预算上限或正式 Outcome，且容易把“聊天继续”误当成训练进展。

新人首发需要在学习、测验和录音之后提供可测量的能力补练，但 AI 不能成为 Journey、Competency Evidence 或 `foundation_ready` 的第二写权威。

## 决策

1. Coach 使用发布后不可变的 `CoachProfileRevision`，一次 Session 冻结 Profile、三个 checkpoint、Context references、卡片白名单、掌握/不确定性规则、两轮补练上限、Prompt/模型/Schema/重试/预算合同。
2. 一个 cycle 生成 3～5 张有类型训练卡；未知类型、额外字段、任意 HTML/脚本/外部指令、越界来源或非法结构化输出 fail closed。
3. 学员回答与 client token 先写数据库，再执行规则评分或排入 `ai_coach.answer.evaluate`。选择/排序用确定性规则；语言理解只经 `AIInvocationPort`。
4. 卡片生成、语言评估和受限讲解使用三个独立持久任务，执行方式为短 prepare 事务 → 外部 AI → fenced apply 事务。任务结果位置统一指向 Activity Workspace。
5. 模型只能返回初评分、回答证据、缺失点、反馈、建议和不确定性。应用按 Profile 快照计算 `mastered`；高不确定性、证据不足或两轮补练后未达标进入 `needs_human_help`。
6. 讲解/示例是持久化辅助动作，不推进正式状态。人工介入只追加指导、指派与审计，不改写学员回答或 AI 历史。
7. 三个 checkpoint 完成后才写 `CoachOutcome` 和 normalized `ActivityOutcome`。正式 CompetencyEvidence 由后续单写模块消费，Coach 永不授予 `foundation_ready`。
8. 删除新人首发旧自由聊天 Session/Turn/SSE writer 和直接 Provider 调用，不保留双写或回退到旧权威。

## 结果与权衡

- 优点：回答可恢复、状态可测试、模型输出可约束、历史可追溯、预算有上限、人工可接管。
- 代价：需要 Profile/Session/Cycle/Card/Response/Assistance/Outcome 等持久对象和三个 Worker handler；自由对话表达能力被主动限制。
- 接受的延后：统一管理员工作台与 Team scope 在后续切片完成；本切片平台管理员按 organization + capability 复核。正式 CompetencyEvidence writer 在 Slice 5 建立。
- 不接受：进程内任务、事务跨 Provider IO、模型直接决定 mastered/readiness、任意生成 UI、无限补练、把失败当零分。

## 发布、降级与回滚

发布顺序：migration → API/Worker/Prompt/model readiness → 新 PathRevision 标准包 → ReleasePlan/Cohort 分范围启用。开发期 `NEWCOMER_AI_COACH_ENABLED` 环境开关已在 Slice 8 Clean Cut 退役；组织范围 rollout、暂停和回滚分别由 ReleasePlan、Cohort 与受审计 TaskTypeControl 承担。既有 Enrollment 继续冻结旧 PathRevision。

降级时关闭 feature flag 与新任务入队，保留 Session/Response/Invocation/Outcome/审计；在途任务完成、重试或协作取消。回滚不恢复旧聊天 writer，也不通过破坏性 downgrade 删除学员回答。

## 验证

- 契约：八类白名单卡、未知类型/额外字段/HTML/越界来源/空输出拒绝。
- Runtime：保存优先、幂等恢复、规则无 AI、Provider/Schema 失败恢复、取消/恢复、受限讲解。
- 状态：三个 checkpoint、两轮补练、高不确定性和人工帮助队列。
- 血缘：Outcome 回溯回答、卡片、内容来源、Prompt 和模型路由修订。
- 权限：capability、组织范围、跨组织隐藏与 denied audit。
