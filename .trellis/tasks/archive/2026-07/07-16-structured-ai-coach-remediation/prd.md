# 切片 4：结构化 AI 教练与补练闭环

## Goal

把现有 AI Coach 从宽泛聊天界面收口为围绕新人薄弱能力的结构化训练工作台：系统基于已发布内容、题目结果和录音证据生成有限训练卡，学员提交答案后获得可解释反馈，并通过最多两轮补练形成可靠 ActivityOutcome。

AI Coach 的任务是促进掌握，不是陪聊，也不直接授予正式 `foundation_ready`。

## Dependencies

- 切片 0：AI 治理、Activity、Evidence 和权限契约。
- 切片 1：AIInvocationPort、Prompt 修订、持久化任务、预算和 Provider Fake。
- 切片 2：学习内容、题目、能力映射、Journey 和 Activity Runtime。
- 可选消费切片 3 的录音薄弱点，但不得阻塞本切片基于 Quiz/Lesson 证据上线。

## Product Decisions

- 三个训练检查点。
- 每个检查点生成 3–5 张结构化训练卡。
- 掌握标准默认 80%，从后端配置快照读取。
- 每个检查点最多两轮自动补练。
- 超过自动补练上限或证据不足时转人工/其他训练，不无限聊天。

## Requirements

### R1. Coach Profile Revision

- `CoachProfileRevision` 冻结：
  - 训练目标；
  - 适用能力；
  - 允许知识范围；
  - 语气与反馈原则；
  - 三个 checkpoint 定义；
  - card type 白名单；
  - mastery rule；
  - remediation policy；
  - Prompt revision；
  - model policy；
  - safety policy。
- 发布后不可原地修改。
- PathRevision 只引用已发布 ProfileRevision。

### R2. Structured Session

- Session 保存 enrollment、activity revision、profile revision、checkpoint、cycle、source context snapshot、weakness inputs 和状态。
- 状态至少覆盖：
  - `created`；
  - `preparing`；
  - `awaiting_answer`；
  - `evaluating`；
  - `feedback_ready`；
  - `checkpoint_mastered`；
  - `remediation_required`；
  - `completed`；
  - `needs_human_help`；
  - `failed_recoverable`；
  - `cancelled`。
- 会话由命令驱动，不以任意消息文本隐式改变正式状态。

### R3. Context Scope

- Context Builder 只读取有权且已发布的内容、题目结果、录音 Outcome 和能力证据摘要。
- 每次运行保存 context references 和 revision，不把整个数据库或无关个人数据发给模型。
- UI 显示“本轮基于哪些学习内容/薄弱点”，但不泄露内部 Prompt。
- 缺少必要来源时明确降级，不编造知识。

### R4. Training Card Contract

- 训练卡使用有类型联合和白名单，首发可包含：
  - 单选/多选辨析；
  - 排序/结构化步骤；
  - 短答改写；
  - 场景选择；
  - 要点补全；
  - 示例对比；
  - 总结卡。
- 每种卡定义输入 schema、回答 schema、评估方式、可访问性和渲染组件。
- 模型不能生成任意 HTML、组件名或脚本。
- 未知 card type 或非法 payload fail closed。

### R5. Three Checkpoints

- Checkpoint 1：识别与理解。
- Checkpoint 2：组织与表达。
- Checkpoint 3：迁移到销售场景。
- 具体名称和内容可由 Profile 配置，但首发标准包必须覆盖这三层能力递进。
- 每个 checkpoint 生成 3–5 张卡，数量由策略配置约束。
- 只有当前 checkpoint 达标后才能进入下一个；人工策略可明确跳过或终止。

### R6. Save Before AI

- 学员提交答案时，先在本地/服务端持久化原始回答和 client token，再创建 AI 评估任务。
- 网络断开、Provider 失败或页面刷新后，已提交答案不得丢失。
- 重复提交相同 token 不产生重复 Turn、预算或评分。
- 学员可离开页面，任务完成后从 Session 恢复。

### R7. Evaluation

- 可确定性评分的卡优先使用规则。
- 语言理解卡通过 AIInvocationPort 评估，输出结构化：
  - score/mastered；
  - evidence from answer；
  - missing points；
  - misconception；
  - feedback；
  - next card/remediation suggestion；
  - uncertainty。
- 最终掌握投影由应用服务按 Profile 快照计算。
- UI 不展示裸内部 `100/100`；使用答对/掌握度/是否达到标准等用户语义。

### R8. Remediation Loop

- Checkpoint 未达标时根据缺失点创建新一轮 3–5 张针对性卡。
- 自动补练最多两轮。
- 每轮保存原因、输入证据、生成策略和结果。
- 达标后进入下一 checkpoint。
- 两轮后仍未达标、模型不确定性过高或内容证据不足时进入 `needs_human_help`，给出明确下一步。
- 不允许无限自动生成或无限消耗预算。

### R9. Feedback And Explanation

- 每张卡反馈包含：
  - 结果；
  - 做得好的具体点；
  - 缺失/错误点；
  - 来自学习内容的依据；
  - 可执行改进；
  - 下一步。
- 区分系统事实、规则计算、AI 推断和建议。
- 学员可对答案或反馈提出“解释一下/给一个例子”等受限动作；这些动作不绕过卡片状态机。
- 重要反馈持久化到 Session，不只存在 SSE 消息。

### R10. Human Review And Takeover

- 培训负责人可查看需要帮助的 Session、证据、失败原因和已尝试轮次。
- 人工可添加指导、指派补学/录音/重新 Coach，或标记无需继续。
- 人工不能静默改写学员原回答或 AI 历史。
- 高风险覆盖需原因、capability 和审计。

### R11. Outcome And Evidence

- 三个 checkpoint 完成后生成 ActivityOutcome。
- Outcome 包含 ProfileRevision、Session、checkpoint 结果、cycle 历史、mastery projection 和 evidence refs。
- 写入 Competency Evidence，但不直接授予正式 readiness。
- `needs_human_help` 产生可见阻塞和复核队列，不视为失败完成。

### R12. Prompt And Model Governance

- 生成卡片、评估答案、生成解释分别使用明确 Prompt Type 和输出 schema。
- Prompt 预览与正式运行同编译器。
- 模型路由、temperature、token、timeout、retry、预算和 fallback 配置化。
- Prompt 或模型升级不得改变历史 Session；新 Session 使用新修订。
- 提供 gold set 覆盖正常、边界、幻觉、错误答案、空答案和 prompt injection。

### R13. Learner Workspace

- 工作区以“当前训练任务”为中心，不以空白聊天框为中心。
- 稳定显示 checkpoint、进度、当前卡、反馈和下一动作。
- 消息历史若保留，仅作为解释辅助，不成为正式状态真源。
- 覆盖 preparing、waiting、evaluating、partial、error、offline、cancelled、needs help、completed。
- 只允许一个主操作；输入、提交和下一卡状态清晰。
- 视口内布局稳定，长内容在工作区内部滚动，底部操作可达。

### R14. Clean Cut

- 删除或封存首发路径中自由聊天式 Coach 入口。
- 删除直接 Provider 调用、隐式 message-command 状态变更和只存在流内的正式结果。
- 新结构化 Session/Turn/Card 是唯一正式 Coach 权威。
- 如保留旧对话记录，仅提供只读历史，不参与新达标判断。

## Acceptance Criteria

- [x] 每个 Session 明确绑定 ProfileRevision、ActivityRevision 和 Context Revisions。
- [x] 三个 checkpoint 顺序和状态机由后端控制。
- [x] 每个 checkpoint 只生成白名单内 3–5 张有效训练卡。
- [x] 学员回答先保存再发起 AI；刷新或 Provider 失败后可恢复。
- [x] 可确定性卡不调用模型。
- [x] AI 结构化输出非法时不完成评分，并提供重试/人工路径。
- [x] 掌握标准来自配置快照，前端不写死 80。
- [x] 自动补练最多两轮，不出现无限会话和无限预算消耗。
- [x] 两轮未达标进入明确人工帮助队列。
- [x] 正式反馈和 Outcome 持久化，不只存在 SSE。
- [x] Coach Evidence 可追溯到回答、卡片、内容来源、Prompt 和模型策略。
- [x] 旧自由聊天式正式链路和直接 Provider 调用已移除。

## Verification

- 状态机测试：三个 checkpoint、两轮 remediation、取消、恢复、人工接管。
- Card schema contract：每种 card 的后端、API 类型和 React 渲染一致。
- AI fake：正常、schema invalid、空输出、超时、重复响应、不确定性过高。
- 前端 E2E：提交前断网、提交后刷新、处理完成恢复、两轮未达标。
- Prompt gold set：知识边界、prompt injection、依据缺失、错误反馈。
- 权限：本人、培训负责人、跨组织和无 capability。

## Definition Of Done

- AI Coach 成为可测量的训练活动，而非通用聊天。
- 所有正式状态和结果都有持久化对象与审计。
- 学员输入在可恢复失败中不丢失。
- 人工可理解为什么未达标并采取下一步。
- Provider 不可用时可降级，不破坏整个训练路径。

## Out Of Scope

- 不实现实时客户角色扮演。
- 不实现开放式 Agent 工具市场。
- 不允许模型自行创建任意 UI 或执行任意命令。
- 不用 Coach 结果单独决定 `foundation_ready`。

## Risk And Rollback

- 风险等级：P1。
- 主要风险是模型输出不稳定、状态隐藏在会话文本和预算失控。
- 通过 structured schema、checkpoint 状态机、两轮上限和 feature flag 控制。
- 回滚时保留 Session/Answer 历史，停止创建新 AI 任务，并将未完成活动投影为可恢复或人工处理。
