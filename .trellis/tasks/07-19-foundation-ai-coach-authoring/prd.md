# Foundation 结构化 AI 教练配置中心

## Goal

把当前只能由 Seed 建立的 `CoachProfileRevision` 变成受治理、可预览、可发布的管理对象，让训练管理员能够配置三个结构化检查点、训练卡、知识来源、评价 Rubric、补练和人工转接策略，而不把 AI 教练退化为自由聊天或普通 Prompt 编辑器。

## Dependencies

- `07-19-foundation-authoring-contract-inventory`。
- 多媒体内容资产任务提供 SourceRevision/Anchor 的可选知识范围。

## Page Contract

当训练管理员准备 AI 补练时，帮助其定义教练要训练的能力、使用哪些已发布资料、给学员哪些结构化卡片、如何判断掌握和何时转人工，并通过受控预览验证后形成可被路径绑定的 Profile 修订。

页面采用 List–Detail + Editor–Preview：左侧 Profile/版本，中间按检查点编辑，右侧显示学员卡片预览、规则校验和依赖状态；不以聊天窗口作为配置主界面。

## Requirements

### R1. Profile 生命周期

补齐 CoachProfile 逻辑资源的 list/search、create、get、save working revision、validate、compare、archive 和 ReleasePlan dependency。已发布修订不可变，正在运行的 Session 始终冻结启动时 Profile/Prompt/模型/来源。

### R2. 三个默认检查点

默认模板保留并允许组织复制调整：

- 商务表达与分寸改写；
- 产品功能转客户价值；
- 首访提问、顾虑承接和下一步推进。

每个检查点结构化配置：目标能力、进入说明、3～5 张卡片上限、允许卡片类型、来源范围、Rubric、掌握阈值、不确定性阈值、最大尝试/补练轮次和人工帮助条件。

检查点顺序可以调整，但首发 Profile 不支持任意图工作流或自定义可执行 Handler。

### R3. 训练卡配置

允许的卡片保持封闭联合：场景判断、表达改写、角色回应、提问设计，以及当前合同已有的确定性选择/排序卡。每种卡片配置输入说明、预期证据、评分方式和反馈边界；未知类型、任意 HTML/脚本和外部指令拒绝。

可从模板创建卡片规则，但真实 Session 卡仍由受治理 AI/确定性规则结合冻结上下文生成，不能把编辑器示例当正式成绩。

### R4. 来源与 AI 合同

- 选择 exact published Source/Unit/Anchor 或受治理知识范围，不允许任意全库检索。
- 分别绑定卡片生成、回答评估和受限解释的 PromptRevision/ModelRoutingRevision/Schema。
- 普通界面展示用途、版本、健康状态、预算/超时的用户语言摘要；Prompt 正文和 Provider payload 进入授权高级 Inspector。
- 缺来源、合同、Schema 或 Provider 时 fail closed，显示修复入口；不得回退到未版本化本地 Prompt 或固定分数。

### R5. 补练与人工接管

- 学员答案先持久化再调用 AI；重复 client token 不产生重复 Turn。
- 最多补练轮次、每轮卡片数、掌握计算和升级人工由 Profile + 领域规则冻结。
- 高不确定性、来源不足、连续失败或达到上限进入 `needs_human_help`，不伪造通过。
- 正式总结持久化到 Session/Outcome，管理员可查看证据但不能改写历史 Turn。

### R6. 预览

- 使用受控 preview context 和已发布来源展示卡片、评分说明、失败/人工帮助状态。
- Preview 不创建正式 Session、Attempt、Evidence 或预算账单，除非明确使用受治理的 preview invocation 并标记成本/审计。
- 校验结果定位到检查点/卡片/来源/合同字段。

## Required States

覆盖首次无 Profile、复制模板、来源为空/过期、AI contract 不健康、生成中、非法输出、部分预览成功、无权限、并发冲突、dirty、发布阻塞、归档只读和回滚。失败必须保留 Profile 草稿。

## Acceptance Criteria

- [ ] 管理员无需修改 Seed 或数据库即可创建和维护 Coach Profile working revision。
- [ ] 三检查点、卡片白名单、来源、Rubric、掌握/补练/人工转接策略均可结构化配置。
- [ ] 普通 UI 不暴露 raw Prompt/JSON/Provider；授权高级区仍可追踪 exact AI contract。
- [ ] Preview 不污染正式 Session/Evidence，并能展示无来源、模型失败和人工帮助路径。
- [ ] 非法卡片、未知字段、跨组织来源、未发布合同和越界策略被后端拒绝。
- [ ] 发布后新 Session 使用新 Profile，既有 Session 继续使用冻结旧修订。
- [ ] AI 不能直接授予 `foundation_ready`，失败不生成固定通过/分数。

## Minimal Verification

- 后端：Profile Schema、状态/版本、来源范围、AI contract、权限、幂等和冻结 Session 测试。
- 前端：编辑器、卡片预览、普通/高级权限、错误/冲突/dirty 状态组件测试。
- 集成：发布两个 Profile 修订，证明旧 Session 不漂移、新 Session 使用新修订。
- 浏览器：复制默认模板、调整一个检查点、校验和预览；不运行无关 Provider 全量评测。

## Out of Scope

- 不实现自由聊天、通用 Agent Builder 或任意工具调用。
- 不改变 AI 平台 Provider 选择逻辑或引入新模型。
- 不实现实时客户角色扮演。
- 不迁移 Legacy AI Coach 会话。

## Risk And Rollback

- 风险等级：P1（AI 训练合同与学员结果）。
- Authoring capability 可关闭，已发布 Seed Profile 和现有 Session 继续可用。
- 错误发布通过 ReleasePlan 回滚；历史 Session/Turn/Outcome 不删除或重写。

## Likely Areas

- `backend/src/ai_coach/`、`foundation_admin_api.py`、ReleasePlan composition；
- `web/src/components/admin/newcomer-training/` 新增 Coach Profile 工作区；
- 现有 `coach-runner.tsx` 只做契约兼容和预览复用，不改成通用聊天。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，发现 AI 平台无关问题只记录。

