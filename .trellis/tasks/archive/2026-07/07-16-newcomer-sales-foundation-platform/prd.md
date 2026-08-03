# 新人销售基础训练平台重构与首发闭环

> **实施状态（2026-07-18）：** 九个切片已按顺序完成；权威入口见 [`../../../../../docs/newcomer-foundation-contract-index.md`](../../../../../docs/newcomer-foundation-contract-index.md)，逐项证据见 [`acceptance-matrix.md`](acceptance-matrix.md)。本 PRD 的旧现状描述只作为实施前基线。

## Goal

把当前分散在新人训练、学习内容、题库、录音评分、AI Coach、训练记录和管理后台中的能力，重构为一套以“新人销售基础能力达标”为中心的企业级训练产品。

首发版本帮助新人依次完成学习、测验、录音讲解、结构化 AI 补练、异步客户场景回答和人工复核，最终形成可追溯的 `foundation_ready`（基础训练达标）结论。实时客户语音对练暂不纳入本任务，后续通过新的训练路径修订和更高等级 `customer_roleplay_ready` 单独建设。

本任务的成功不是“现有页面还能打开”，而是完成业务主线、模块边界、数据契约、AI 治理、持久化任务、证据档案、管理运营、性能和验证门禁的系统性收口。

## Product Promise

> 新人按一条清晰路径完成训练，系统把每次学习与练习转化为可信证据；培训负责人无需翻日志或拼 Excel，即可判断新人基础能力是否达标、卡在哪里、为什么、下一步练什么。

## Target Users

### 新人销售

当新人进入已分配的训练路径时，帮助其基于当前任务、材料、评分重点和反馈完成训练，并得到清晰、可恢复、可继续的下一步。

### 培训负责人 / 训练经理

当培训负责人处理新人训练结果时，帮助其基于证据、能力状态、AI 初评和历史趋势完成复核、要求重练或例外处理，并得到可审计的正式结论。

### 内容编辑

当内容编辑维护训练材料和题库时，帮助其在同一工作流内完成资料导入、精编、AI 草稿生成、人工审核和版本发布准备，并确保未经审核的 AI 内容不会进入正式训练。

### 训练管理员

当训练管理员配置路径、活动、评分规则和发布版本时，帮助其完成依赖检查、预览、影响分析和原子发布，并确保学员冻结在正确的路径修订。

### 系统管理员 / 运维

当系统管理员处理模型、Provider、任务、失败和配置健康时，帮助其定位问题、降级或恢复服务，但不让技术配置泄露到普通用户界面。

## Confirmed Decisions

本任务已经完成产品与架构讨论，以下不是待选项：

- 核心产品是新人销售训练，不是通用 Agent 平台或实时对练产品。
- AI 是一等训练与反馈引擎，但路径、权限、状态、发布、审计和最终达标由确定性控制面负责。
- 首发结论为 `foundation_ready`，不宣称新人已经具备真实客户实战能力。
- 实时客户对练、Realtime Runtime 和实时语音表现教练不在本任务中实现。
- 当前处于开发阶段，允许干净切换、清理旧链路和重建开发数据库基线。
- 不做抛弃式 UI 原型选择；直接复用当前项目视觉基础并按任务优先原则收口。
- 训练路径采用稳定主干加有限补练分支，不发展为任意拖拽工作流平台。
- 人工复核是最终基础达标权威；AI 只产生初评、证据、建议和不确定性。
- 所有正式训练依据冻结资料、题目、能力点、Prompt、模型配置和评分规则修订。
- 旧记录不可覆盖；技术重试、学习重试、转写校正和历史重评使用不同语义。

完整决策记录见 [`decision-log.md`](decision-log.md)。

## Current-State Findings

仓库已经有大量可复用能力，但现状不能直接作为目标架构：

- 新人训练路径、课程学习、自由训练存在重叠入口和重复业务权威。
- 后端存在跨包强连通依赖，部分共享 Facade 和 Adapter 过深过宽。
- AI 调用仍存在直接调用、硬编码 Prompt、固定降级分数和不一致 Provider 路由。
- 长耗时任务仍有进程内 BackgroundTask 或同步请求执行，缺少统一持久化任务运行时。
- 当前 AI 出题没有独立候选题和生成批次，生成确认会直接创建正式题目草稿。
- 当前新人录音提交会在请求内完成转写和评分，且统一 Attempt 无可靠异步回流。
- 当前前端存在多个新人训练入口、大型 Client Component、弱缓存和重复请求。
- 当前活动层级、Enrollment 发布迁移行为和 Realtime 首发范围与本任务决策冲突。

详细证据见 [`research/current-state.md`](research/current-state.md)。

## Scope

### In Scope

- 新人销售训练单一主入口与单一业务主线。
- 新的模块边界、API 契约、数据库表权威和依赖方向。
- `PathRevision -> Stage -> ActivityDefinition` 路径模型。
- Learning、题库、AI 出题候选、试卷和标准训练包。
- 录音直传、音频校验、ASR、评分、证据和重评闭环。
- 结构化 AI Coach、训练卡、补练、失败恢复和人工转接。
- 能力证据、达标档案、人工复核、重练和例外。
- 统一管理工作台、资源快速创建、发布计划和影响分析。
- 学员、内容编辑、训练管理员、训练负责人和系统管理员权限。
- 持久化任务运行时、Outbox、幂等、租约、重试、死信和通知。
- 性能、可观测性、审计、安全、隐私、测试和受控发布。
- 旧入口、旧 Facade、重复业务权威和直接 AI 调用的清理。

### Out of Scope

- 实时 WebSocket 客户角色对练。
- StepAudio Realtime、Realtime Session Engine 和实时语音中断策略重构。
- 自动预测真实销售业绩或宣称训练与业绩存在因果关系。
- 自动替代培训负责人作出最终达标决定。
- 通用低代码训练流程编排器。
- 多服务拆分、微服务化或为未来规模提前引入消息中间件。
- 公共排行榜、强制摄像头监考、AI 作弊检测或侵入式监控。
- CRM 深度集成；只保留后续 Adapter 边界。
- 新视觉系统、新品牌色、新图标库或脱离现有 UI 基础的全面改版。
- 生产历史数据迁移；本任务以新的首发基线和开发环境干净切换为前提。

## Domain Language

| 中文业务词 | 推荐技术名 | 说明 |
|---|---|---|
| 训练路径修订 | `PathRevision` | 已发布后不可变 |
| 训练阶段 | `Stage` | 业务顺序与阶段结果 |
| 训练活动定义 | `ActivityDefinition` | 封闭类型联合 |
| 学员路径 | `Enrollment` | 冻结一个 PathRevision |
| 训练尝试 | `ActivityAttempt` | 通用生命周期信封 |
| 活动结果 | `ActivityOutcome` | 标准化结果与证据引用 |
| 能力证据 | `CompetencyEvidence` | 不可变事实 |
| 达标档案 | `ReadinessDossier` | 证据和决策汇总 |
| 人工复核 | `ReadinessReview` | 最终结论与原因 |
| 重练任务 | `RetrainingAssignment` | 面向薄弱能力的行动 |
| 生成批次 | `QuestionGenerationBatch` | AI 批量出题任务 |
| 候选题 | `QuestionCandidate` | 未审核 AI / 导入产物 |
| 评分方案 | `ScoringSchemeRevision` | 学员 Rubric + 机器合同 |
| 转写修订 | `TranscriptRevision` | 追加式 ASR / 人工校正结果 |
| 评分结果版本 | `ScoreOutcomeVersion` | 不覆盖历史评分 |

## Functional Requirements

### R1. 单一新人训练主线

- 学员主导航只保留“当前训练、训练历史、个人资料、通知”。
- `/newcomer-training` 是新人训练唯一主入口。
- 管理入口统一到 `/admin/newcomer-training`。
- 普通学员不得再同时面对 `/training`、`/learning-path`、自由练习和新人路径等竞争入口。
- 路径首页首屏展示当前任务、后台处理中任务、整体进度、最近反馈和明确下一步。
- 每个页面三秒内能看出当前任务、主操作和下一步。

### R2. 标准训练流程

首发默认流程：

1. 低风险基线：8 道诊断题 + 2～3 分钟录音，不计入达标。
2. 产品与客户背景学习。
3. 商务礼仪核心训练。
4. 综合知识测验。
5. 3～5 分钟公司与方案讲解。
6. 三个结构化 AI Coach 检查点。
7. 三段异步客户情景录音。
8. 达标档案汇总与人工复核。
9. 未达标时定向补练、重试和重新复核。

默认有效训练时间控制在 4～6 小时，分布在 5 个工作日内。

### R3. 路径与 Enrollment

- 路径层级收敛为 `PathRevision -> Stage -> ActivityDefinition`。
- 工作修订可编辑，使用 `expected_revision` 乐观并发控制。
- 已发布路径修订不可变。
- Enrollment 冻结指定 PathRevision，不因新版本发布自动迁移。
- 迁移必须显式执行 `MigrateEnrollmentRevision`，展示影响并留审计。
- 同一逻辑路径不允许同一学员存在多个活动 Enrollment。
- Cohort 绑定一个 PathRevision，支持计划开始、截止、负责人和学员名单。

### R4. Activity 深模块

首发活动类型为封闭联合：

- `lesson`
- `quiz`
- `audio_assessment`
- `ai_coach`
- `assignment`

每种活动实现稳定接口：

- `project(context)`
- `execute(command, context)`
- `reconcile(attempt, evidence)`
- `validate_definition(definition)`
- `preview_definition(definition)`
- `compile_definition(definition)`

Journey 只管理路径、Attempt、Gate 和通用结果，不承载活动内部实现。

### R5. Attempt 与结果状态

Attempt 生命周期：

- `created`
- `in_progress`
- `submitted`
- `processing`
- `completed`
- `processing_failed`
- `cancelled`
- `expired`

评估结果：

- `not_assessed`
- `passed`
- `not_passed`
- `needs_review`
- `waived`
- `degraded`

技术重试复用同一 Attempt；学习重试创建新 Attempt；重新评分创建新 Outcome Version。

### R6. Learning 与内容资产

- 原始资料、精编学习单元和来源锚点分层。
- 原始资料不可被 AI 直接修改。
- 学员只阅读适合训练的精编内容，可展开查看原文。
- 商务礼仪保留 7 个小单元：
  - 默认必修：职业信任、初次见面、商务沟通、接待拜访、综合补救。
  - 岗位可配置：会议洽谈、餐饮应酬。
- 当前仓库公司产品资料和制造业 CIO 首访材料只作为示例包，不成为系统硬编码。
- 标准模板定义结构和规则；组织内容包提供真实资料和题目。

### R7. 题库与 AI 出题治理

- AI 出题和文件导入先进入 `QuestionCandidate`，不得直接进入正式题库。
- 每次生成保存 Generation Batch、资料修订、来源片段、Prompt、模型、合同哈希和参数。
- 正式题型集合：单选、多选、判断、排序、匹配、简答。
- AI Coach 的表达改写、提问设计、角色回应不混入普通小测题型。
- AI 默认只能使用指定资料，资料不足时返回“无法可靠生成”。
- 候选题经过确定性质量门禁、重复检测和人工审核。
- 普通题由内容编辑审核；红线题和 AI 评分简答题由训练管理员再次确认。
- 审核通过只生成题目工作修订，正式生效由训练包 Release Plan 原子发布。
- 来源资料更新后，工作题标记 stale，新发布前必须重新验证。

### R8. 综合测验

- 示例训练包至少有 60 道已审核题，每次综合测验抽取 15 道。
- 按能力、难度、题型和红线标签平衡抽题。
- 总分达到 80，且所有关键红线题通过。
- 客观题由规则判分；简答题进入异步 AI 评分并保留人工复核入口。
- 题目、答案、评分合同、资料和能力映射在 Attempt 中冻结。

### R9. 录音评测

- 上传确认后 2 秒内返回，不在请求内等待转写和评分。
- 浏览器使用单一麦克风流、分片录制、续传和本地草稿。
- 生产使用对象存储分片直传；默认 30 分钟 / 100MB。
- 服务端校验文件魔数、解码、时长、静音、削波、有效语音和恶意文件。
- 保留原始音频，生成供 ASR 使用的标准化派生文件。
- 处理阶段拆为 Validate、Transcribe、Score、Finalize 四个持久化任务。
- 转写使用追加式 TranscriptRevision，包含分段时间和置信度。
- ASR 低置信度不得直接形成正式评分；受控回退后仍不足则进入人工复核。
- 正式考核中，学员只能标记转写错误，培训负责人确认后产生新修订和重评。
- 语义评分与音频确定性指标分开；不得把口音、性别或地区作为扣分依据。
- AI 提供维度分、证据和置信度；领域规则计算总分、关键维度和结果。
- 公司与方案讲解默认总分 75、关键信息准确性 70；异步场景默认总分 75、核心维度 70。
- 编造事实、虚假指标、越权承诺或敏感数据泄露触发红线，不受平均分保护。

### R10. AI Coach

- AI Coach 是目标明确的训练工作台，不是自由聊天入口。
- 三个默认检查点：
  - 商务表达与分寸改写；
  - 产品功能转客户价值；
  - 首访提问、顾虑承接和下一步推进。
- 每个检查点默认 3～5 张卡、5～10 分钟。
- 首次检查点必做；未达标后生成针对性补练，每轮最多 5 张，默认最多两轮。
- 白名单训练卡至少包含场景判断、表达改写、角色回应和提问设计。
- 学员答案必须先持久化，再调用模型。
- Prompt、模型、输出 Schema、超时、重试和预算由集中治理解析。
- AI Coach 掌握度默认达到 80；关键卡未达标不得被平均分掩盖。
- 达到补练上限仍不稳定时停止无限聊天并进入人工复核。
- AI 失败不丢失学员答案，不生成固定 60/70 分兜底。

### R11. 能力证据与达标

全局新人销售能力模型固定为：

1. 表达清晰度；
2. 结构化讲解；
3. 产品理解；
4. 客户视角；
5. 需求识别；
6. 异议回应；
7. 商务礼仪与职业表达。

训练包局部维度映射到上述能力，不临时扩大全局能力模型。

- CompetencyEvidence 保存不可变事实和来源。
- Readiness 负责证据完整性、趋势、风险和人工结论。
- 使用最新有效证据、完整性和趋势，不取历史最高分覆盖问题。
- 低置信度和降级结果不能单独支持正式达标。
- 每个学员都进入人工复核；清晰低风险案例支持批量确认。
- 复核动作：确认基础达标、要求重练、批准例外、退回补证。
- 培训负责人调整结论时保留 AI 原始评分，不手动覆盖历史分数。
- 学员可以对转写、评分和结论提出申诉。

### R12. 管理工作台与上下文内完成

- `/admin/newcomer-training` 是统一工作区。
- 首页是待处理工作队列，不是 KPI 卡片墙。
- 路径编辑器使用大纲、编辑区、检查器三栏模型。
- 缺少学习内容、试卷、材料、评分方案时在当前抽屉内选择或快速新建。
- 快速新建产生工作修订，自动绑定当前活动，并保留去重、权限、审计和错误恢复。
- 内容工作台覆盖资料导入、精编、AI 候选、审核、题库和小测预览。
- 学员管理覆盖 Cohort、Enrollment、进度、待处理任务和档案。
- 复核队列按风险、证据缺失和多次重练排序。

### R13. 发布治理

- 发布使用 `PathReleasePlan`。
- 状态：draft、validating、ready/blocked、publishing、published/failed/cancelled。
- 发布检查路径结构、资源版本、题目数量、评分方案、Prompt、能力映射、权限、Provider 和任务运行能力。
- 内容、题目、试卷、评分方案和路径修订原子发布。
- 发布前提供学员预览、Gate 模拟、影响分析和回滚说明。
- 已开始训练的 Enrollment 保持原修订；新版本默认仅影响新 Cohort / 新 Enrollment。
- 变更 Prompt、阈值、答案和评分权重属于高风险修订。

### R14. 持久化任务运行时

- PostgreSQL 是任务和业务结果真源，Redis 只做加速。
- API 和 Worker 是独立进程。
- 任务状态：queued、running、retry_wait、succeeded、dead_letter、cancel_requested、cancelled。
- 任务有租约、续约、重试策略、幂等键、进度、取消、超时、结果位置和审计。
- 任务阶段不得在外部 IO 期间持有长数据库事务。
- Outbox 与业务写入同事务，Worker 至少一次消费，消费者幂等。
- 长任务 UI 支持进度、离开、恢复、取消和持久化通知。

### R15. AI Platform

- 所有 LLM / ASR 调用通过一个统一 Invocation Interface。
- 业务模块拥有语义、Rubric、Prompt 变量、Schema 和失败政策。
- AI Platform 拥有 Provider、模型路由、超时、重试、限流、预算、血缘、输出校验和可观测性。
- 按任务选择模型，不使用一个全局模型覆盖所有场景。
- 正式评分不得静默切换未校准模型。
- Prompt 集中管理、发布、冻结和回滚。
- 运行记录区分事实、规则、推断、建议和人工结论。
- 高风险建议不会自动执行。

### R16. 前端体验

- 复用当前项目 Token、组件和 Modern Soft UI 基础，不引入新视觉系统。
- 降低玻璃卡片墙，优先使用列表、表格、分栏、时间线和稳定层级。
- 建立统一 Activity Shell，但不同活动只复用壳和状态，不被迫使用相同交互。
- 学习页聚焦正文；测验页自动保存；录音页覆盖准备、录制、试听、上传、后台处理和结果。
- AI Coach 使用训练卡工作台，不以聊天消息流作为唯一信息结构。
- 结果页先展示结论和下一步，再展示证据、维度和历史。
- 能力使用列表和时间线，不默认使用雷达图。
- 学员端完整支持移动端；复杂管理编辑器面向桌面和平板。
- 所有核心流程支持键盘、可见焦点、200% 缩放、长文本和窄屏。
- 用户输入在可恢复失败后保留；重要结果不只用 Toast 表达。

### R17. 权限、安全与隐私

- 所有表和事件携带 `organization_id`，首发使用逻辑多租户和单 PostgreSQL。
- 后端执行 capability + 对象级权限。
- 角色至少包括内容编辑、训练管理员、训练负责人、系统管理员和学员。
- 文件访问使用短时签名 URL，普通 API 不暴露存储 Key。
- 音频、转写和评分属于敏感训练数据，访问、下载、导出和重评留审计。
- Provider 使用组织数据允许清单，发送最小必要上下文。
- 密钥不进入数据库明文、日志或前端。
- 删除与匿名化保持证据关系可解释，不伪造“从未发生”。

### R18. 性能与运行目标

首发 SLO：

- 学员路径首屏 p75 不超过 2 秒。
- 普通 API p95 不超过 500ms。
- AI Coach 1.5 秒内出现可见运行反馈，完整响应目标不超过 8 秒。
- 录音上传确认不超过 2 秒。
- 录音评测 p95 不超过 90 秒。
- 达标档案基础数据不超过 2 秒。

首发容量基线：

- 每组织 1,000 名学员；
- 100 名同时在线；
- 20 个并发上传；
- 20 个并发 AI 任务；
- 每条路径 100 个活动；
- 管理列表可处理 10,000 个 Attempt。

### R19. 可观测性

- 所有请求和任务传播 trace_id、correlation_id、causation_id。
- 记录任务排队、执行、重试、Provider、耗时、成本、错误和降级。
- 日志不记录音频内容、完整转写、密钥和敏感个人数据。
- 健康检查区分 liveness、readiness 和 capability health。
- 关键指标包括路径加载、提交成功率、任务积压、ASR 低置信度、AI 输出非法率、重练率和复核积压。

### R20. 开发体验与架构守卫

- 后端按模块组织 contracts、domain、application、adapters、delivery，避免空目录仪式。
- 前端按领域组织 DTO、Model、Presenter、Client、Queries、Commands 和 Components。
- OpenAPI 传输 DTO 可生成，但必须由领域模型和 Presenter 包装。
- 禁止跨模块 ORM 查询和直接表访问。
- 禁止字符串动态导入活动 Handler。
- Architecture Guard 阻止新增循环依赖和过期临时边。
- 本地使用确定性 Fake LLM、Fake ASR 和场景化失败。
- 提供稳定命令：reset、seed、verify、test-affected、e2e-core、provider-test。

## Page Contract Summary

| 页面 | 用户任务 | 主操作 | 关键状态 |
|---|---|---|---|
| 学员当前训练 | 完成当前活动 | 开始/继续当前任务 | loading、locked、processing、failed、completed |
| 学习活动 | 阅读并确认掌握 | 完成本单元 | progress、offline draft、stale content |
| 测验活动 | 完成并提交题目 | 提交测验 | autosaving、submitting、async scoring、retry |
| 录音活动 | 完成录制并后台评测 | 提交录音 | permission、recording、uploading、processing、needs_review |
| AI Coach | 完成当前训练卡目标 | 提交回答/继续训练 | waiting、streaming、scoring、retry、manual review |
| 学员结果 | 理解结果和下一步 | 开始补练/继续路径 | partial、degraded、appeal、regrade |
| 内容工作台 | 产出可发布内容和题目 | 审核候选题 | generating、partial、duplicate、stale source |
| 路径编辑器 | 编排并发布路径 | 验证并发布 | dirty、conflict、blocked、publishing、failed |
| 复核工作台 | 处理待复核学员 | 确认达标/要求重练 | loading、insufficient evidence、conflict |
| 学员档案 | 核验证据和趋势 | 作出复核结论 | stale projection、regrade pending、appeal |

## Acceptance Criteria

完整矩阵见 [`acceptance-matrix.md`](acceptance-matrix.md)。本任务级门禁：

- [x] 学员只有一个新人训练主入口，能够完成首发全流程。
- [x] 默认训练包可以从后台复制、编辑、验证、发布和分配给 Cohort。
- [x] Enrollment 冻结路径修订，新发布不会静默迁移在学人员。
- [x] 所有活动通过统一 Attempt 和 ActivityOutcome 契约回流。
- [x] 录音、简答题、AI Coach 和报告使用持久化任务，不阻塞请求。
- [x] AI 出题只产生候选题，未经人工审核不得进入正式训练。
- [x] 录音上传可续传、转写有置信度、评分有时间证据和红线判断。
- [x] AI Coach 不丢输入、不使用固定兜底分数、达到上限后转人工。
- [x] 达标档案区分 AI 初评、证据完整性和人工最终结论。
- [x] 培训负责人可以在档案内直接要求重练并自动关联薄弱能力。
- [x] 管理员可以在路径编辑器内快速创建并绑定缺失资源。
- [x] 发布计划原子发布依赖，失败不会产生部分生效。
- [x] 普通用户界面不暴露 Prompt、Provider、traceId、原始枚举、数据库 ID 和 Raw JSON。
- [x] Realtime 代码不挂载到首发路径和学员 UI。
- [x] 重复入口、重复业务权威、直接 AI 调用和废弃 Facade 被移除。
- [x] 核心单元、集成、契约、E2E、权限、性能和 Provider 校准门禁通过。

## Definition of Done

- 用户主路径、主操作和下一步清晰。
- loading、empty、no-result、error、permission、partial、stale、conflict、submitting、retrying、cancelled 状态完整。
- API 契约稳定，OpenAPI 与运行时一致。
- 后端权限和对象范围为唯一授权权威。
- 状态流转集中，业务阈值和规则来自已发布配置修订。
- 关键写入具备事务、幂等、并发和审计。
- AI 输出有依据、置信度、失败兜底和人工复核。
- 历史证据和版本不可覆盖。
- Architecture Guard 无新增循环或未登记边。
- Ruff、Mypy、Pytest、Alembic、TypeScript、ESLint、Vitest、Playwright 和生产构建通过。
- 实际渲染界面经过桌面、移动、200% 缩放、长文本和慢网验证。
- 受控首发、回滚、Feature Flag 清理和运行手册完成。

## Technical Approach

采用“干净模块边界 + 垂直切片 + 每片即时删除旧权威”的方式实施。

不进行一次性大爆炸，也不长期保留双写和双读。每个切片必须交付一个可以验证的端到端业务增量，建立新权威后立即删除该切片范围内的旧入口、旧 Facade、直接 ORM 访问和直接 AI 调用。

目标架构、接口和数据流见 [`architecture.md`](architecture.md)。

阶段依赖、子任务和小 PR 计划见 [`execution-plan.md`](execution-plan.md)。

## Decision (ADR-lite)

### Context

当前项目已经拥有大量新人训练能力，但其产品入口、模块边界、长任务、AI 调用、题库生产、录音回流和达标结论仍存在重复权威和技术泄漏。继续在现有边界上叠加功能会扩大循环依赖和运营成本。

### Decision

- 以新人销售基础训练为产品中心。
- 以 `foundation_ready` 作为首发终点。
- 采用模块化单体和 PostgreSQL 单一业务真源。
- 新路径、新 Attempt、新 Task Runtime、新证据与复核模型成为唯一新权威。
- Realtime 客户对练延后。
- 允许开发期干净数据库和代码切换，不维护无用户价值的旧兼容。
- 复用当前 UI 基础，不做原型竞选和视觉系统替换。

### Consequences

- 本任务是跨模块 P1 / 局部 P0 风险重构，需要阶段化执行和严格质量门禁。
- 短期会删除部分现有入口和兼容代码。
- 数据模型、API、测试和文档必须同步重写。
- 通过清晰模块和契约，后续新增行业内容、产品课程和实时对练时不需要再次改写主路径。

## Dependencies

- 依赖新的首发 Alembic 基线和安全 reset 能力；复用现有任务 `.trellis/tasks/07-15-reset-database-launch-baseline` 的结果，不在本任务重复实现 destructive reset。
- 依赖当前 Team 作为组织范围与对象级权限权威。
- 依赖根目录 `DESING.md` 和当前设计系统作为 UI 规范。
- 实施前必须更新与本任务冲突的 Trellis Spec 和 ADR。

## Risks

| 风险 | 等级 | 控制方式 |
|---|---|---|
| 跨模块重构扩大现有 SCC | P1 | Slice 0 先冻结依赖政策；每片运行 Architecture Guard |
| 数据模型切换造成双重权威 | P1 | 不长期双写；建立新权威后删除旧写入 |
| 长任务丢失或重复执行 | P1 | PostgreSQL Task + Outbox + 租约 + 幂等 |
| AI 评分不稳定或不公平 | P1 | 金标集、置信度门禁、人工复核、禁止静默换模 |
| 录音上传丢失 | P1 | 本地草稿、分片续传、确认后清理 |
| 发布部分成功 | P1 | Release Plan 原子提交和失败补偿 |
| 管理页面复杂度失控 | P2 | 任务型页面模型、一个主操作、URL 状态 |
| 当前脏工作区互相覆盖 | P1 | 逐文件检查、禁止 reset/checkout、子任务独立范围 |

## Rollout And Rollback

- 每个切片使用独立 Feature Flag，只在新端到端链路完整时开启。
- 新切片上线前先在开发 / integration / provider-staging 验证。
- 不采用长期双写；切换窗口内允许短期只读对比。
- 回滚恢复到上一已发布路径、Prompt、评分方案或前端入口，不重写历史 Attempt。
- 删除旧链路前保留消费者清单、影响分析和恢复提交点。
- 最终切片清理所有长期 Flag、兼容路由和双权威代码。

## Research References

- [`research/current-state.md`](research/current-state.md) — 当前仓库事实、可复用能力、结构缺口和任务冲突。
- [`decision-log.md`](decision-log.md) — 已确认产品与架构决策。
- [`architecture.md`](architecture.md) — 目标模块、接口、数据、事件和事务边界。
- [`acceptance-matrix.md`](acceptance-matrix.md) — 业务、状态、权限、AI、性能与测试验收矩阵。

## Open Questions

无阻塞产品问题。实施过程中如发现与仓库真实约束冲突，必须记录到 `implementation-notes.md`，采用保守方案继续；只有会改变产品范围、数据权威或安全边界的冲突才重新请求用户决策。
