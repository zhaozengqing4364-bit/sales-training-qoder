# brainstorm: 项目后续发展路线

## Goal

和用户一起分析当前销售训练项目的后续发展方向，明确项目应该往哪里发展、优先发展什么、如何分阶段推进，并形成可继续拆解为任务或路线图的决策记录。

## What I already know

* 用户希望进行协作式分析，而不是立即实现某个单点功能。
* 用户明确触发 `trellis-brainstorm`，需要先沉淀任务与 PRD，再逐步收敛。
* 当前仓库名称与已有任务显示，项目核心方向是“销售训练 / AI 教练 / 商务礼仪 / 售前场景闭环”。
* 用户补充：项目最初愿景是实时语音对练，AI 扮演客户、厂商等角色，与用户进行实时对话练习。
* 用户补充：实时对练在推进中暴露了知识获取、角色扮演一致性、知识库/角色定义连接、长时间对话稳定性等问题，因此阶段性退到更可控的训练闭环。
* 用户补充：当前简化版本初步分三阶段，第一阶段是上传视频或语音，转文字后由 AI 对文字评分并给出反馈，对应第一关 PPT 训练。
* 用户补充：第二阶段是阅读商务、销售、技术相关文章后考试；考试方式包含传统题库（单选、多选、判断、简答）以及 AI 教练形式。
* `CLAUDE.md` 将项目定义为企业级 AI 智能演练系统，强调实时性、模块隔离、成本控制、隐私合规和可观测性。
* `CONTEXT.md` 明确“新人训练路径”不是实时 WebSocket 对练，而是异步学习、录音提交、文章、考卷、后台配置和审计闭环。
* `docs/plans/2026-05-29-sales-training-roadmap-report.md` 已形成路线共识：先做离线训练闭环，再沉淀内容和标准，再扩行业场景，最后接实时语音对练。
* `docs/design/sales-trainer-system.md` 显示销售训练 MVP 的基础闭环已基本成型：题库、录音上传、ASR、Deucate 评分、后台记录、配置健康和操作日志。
* `docs/api-contract/sales-trainer.md` 已把新人训练路径、模块配置、AI Coach、权限、审计、提示词治理和实时边界写成契约。
* 前端已有学员端 `/sales-trainer`、录音、测验、商务技巧、AI Coach，以及后台训练单元、材料、题库、考卷、评分、记录、日志、配置等大量入口。
* 近期任务表明当前重心集中在商务礼仪训练包、AI Coach 主动训练闭环、提示词治理和架构优化修复。
* 2026-06 架构审计显示工程底座存在治理债：CI、可观测性、前端设计系统、WebSocket 鉴权、死指标、降级链声明与生产引用不一致等。

## Assumptions (temporary)

* 本次讨论的目标是产品与工程路线规划，不是本轮直接写代码。
* 需要先基于仓库现状判断已有能力、技术债、可扩展方向，再向用户询问关键偏好。
* 后续路线应兼顾可商业化、可治理、可迭代，而不是只堆功能。
* “往哪里发展”的关键不是新增更多入口，而是选择一个能形成商业证据的主轴。
* 实时语音对练应保留为最终方向，但当前路线要先解决它依赖的三类前置资产：可靠知识、稳定角色、可追踪评分/训练证据。

## Open Questions

* 训练任务模板最小验收应先覆盖哪几个现有训练任务：PPT 讲解、电梯演讲、产品讲解，还是先只覆盖 PPT？

## Requirements (evolving)

* 输出项目现状判断。
* 提出 2-3 个可选发展方向，并说明取舍。
* 收敛出一个推荐方向与近期推进方式。
* 路线必须尊重新人训练路径与实时对练的边界。
* 路线必须兼顾产品价值、运营后台、内容资产、AI 治理、权限审计和工程治理。
* 路线必须解释“为什么先不做实时对练”，并把离线训练、文章考试、AI 教练与最终实时对练之间的关系串起来。
* 第二阶段 AI 教练长期同时支持两类形态：
  * AI 教练陪练辅导：用户可自由问、自由练，AI 适时插入训练卡、反馈和补救建议，目标是补弱和迁移应用。
  * AI 教练出题考试：AI 像考官一样发题、追问、评分，目标是达标或认证。
* 近期推荐先做陪练辅导，把 AI 考官作为受控考试模式预留；如果从考官模式开始，必须先明确边界条件、题源、评分、提示、重试、审计和成绩有效性。
* 根据用户纠正和代码盘点，以上能力大量已经实现；后续路线不得停留在“是否要做 AI Coach / 训练卡 / 能力点 / 草稿箱 / 重练”层面。
* 下一步分析必须基于现状：项目已经具备训练资产与训练证据层，关键问题是如何向最终实时语音对练演进。
* 实时语音对练仍是未来方向，但当前阶段先不推进实时对练。
* 当前阶段优先把“上传录音 → 转写 → 评分 → 反馈 → 记录/复盘”路径闭环做完整。
* 当前路径里的能力必须拆分出来，不写死在场景规则或页面里；能力应可自由组合、可配置、可复用，并符合项目配置化、权限、审计、测试规范。

## Acceptance Criteria (evolving)

* [ ] 已基于仓库代码和文档形成现状判断。
* [ ] 已识别项目的核心资产、短板与增长机会。
* [ ] 已提出可比较的发展路线选项。
* [ ] 已和用户确认优先方向。
* [ ] 已形成可继续拆解执行的路线图草案。

## Definition of Done (team quality bar)

* 关键判断已写入 PRD。
* 如涉及后续实现，已明确 MVP 范围、非目标、风险与验证方式。
* 不修改业务代码。
* 不把重要设计依据只保存在聊天记录中。

## Out of Scope (explicit)

* 本轮不直接实现新功能。
* 本轮不提交代码。
* 本轮不修改现有业务逻辑。

## Technical Notes

* 任务目录：`.trellis/tasks/06-16-project-development-roadmap/`
* 已读：`CLAUDE.md`
* 已读：`CONTEXT.md`
* 已读：`docs/architecture.md`
* 已读：`docs/plans/2026-05-29-sales-training-roadmap-report.md`
* 已读：`docs/plans/2026-05-29-sales-trainer-three-modules.md`
* 已读：`docs/design/sales-trainer-system.md`
* 已读：`docs/api-contract/sales-trainer.md`
* 已读：`docs/agents/audit-2026-06/00-executive-summary.md`
* 已读：`.trellis/tasks/05-28-sales-trainer-mvp/prd.md`
* 已读：`.trellis/tasks/06-12-ai-coach-proactive-loop/prd.md`
* 已读：`.trellis/tasks/06-14-business-etiquette-training-pack-v1/prd.md`
* 已读：`.trellis/tasks/06-14-architecture-optimization-repair-plan/prd.md`
* 已读：`backend/src/sales_trainer/services/audio_submission_service.py`
* 已读：`backend/src/sales_trainer/services/transcription_service.py`
* 已读：`backend/src/sales_trainer/services/deucate_scoring_service.py`
* 已读：`backend/src/sales_trainer/services/audio_regrade_service.py`
* 已读：`backend/src/sales_trainer/services/path_config_audio_refs.py`
* 已读：`web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.tsx`
* 已读：`web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx`

## Research References

* [`research/ai-sales-training-market-patterns.md`](research/ai-sales-training-market-patterns.md) — 同类 AI 销售训练平台普遍走“内容/场景 → 练习 → 评分认证 → 管理者复盘 → 真实业务数据回流”的闭环。
* [`research/current-state-code-inventory.md`](research/current-state-code-inventory.md) — 当前代码已经具备训练包、能力点、AI 出题草稿、传统考试、AI Coach 工作台、进度/阻断/重练等大量能力，下一步应分析更高层的实时对练就绪问题。

## Current Diagnosis

### Core Assets

* 项目已经有新人训练路径的产品边界、API 契约、后台配置、学员端路径、录音评分、题库/考卷、AI Coach、提示词治理和操作日志。
* 商务礼仪训练包 v1 是目前最像“可交付产品包”的方向：它把内容、能力点、题目、AI Coach、版本快照、管理端卡点视图串起来。
* 代码和文档都强调配置化、权限、审计、发布/回滚，这对企业级训练产品是差异化资产。
* 进一步代码盘点后修正：训练包引擎不是“未来要做”，而是已经形成了大量实现。它更准确地说是当前系统的资产层和证据层。
* 当前系统已经能沉淀对实时对练有价值的资产：内容章节、知识点、能力点、题库、AI 草稿审核、训练卡、评分 rubrics、prompt contract、弱项、重练、人工复盘状态和操作日志。

### Main Gaps

* 当前能力多，但需要一个更高阶的产品主线，否则容易变成“训练后台很完整，但和最终实时对练目标之间缺少明确桥梁”。
* AI Coach、题库、能力点和管理者视图已具备基础形态；问题不再是有没有这些模块，而是它们输出的证据如何转化为下一次训练、复训和实时对练的输入。
* 实时语音对练有市场吸引力，但当前 `sales_trainer` 契约明确把它放在后续，贸然推进会放大实时链路、权限、可观测性和评估标准风险。
* 2026-06 审计显示工程治理债需要并行修，不适合在基础门禁薄弱时继续扩大高风险实时链路。

## Feasible Directions

### Direction A: 训练包引擎深化

继续把项目发展成“企业新人/销售训练包平台”：内容导入、能力点建模、AI 出题草稿审核、文章/测验/录音/AI Coach 训练、版本发布、经理卡点复盘。

优点：
* 最贴合当前代码与活跃任务。
* 能最快形成可演示、可运营、可收费的完整闭环。
* 后续行业包和实时对练都能复用能力点、题目、prompt、评分和训练记录。

风险：
* 如果只继续补训练包功能，可能离最初“实时语音对练”愿景越来越远。
* 容易把项目做成训练内容管理系统，而不是对练系统。

### Direction B: AI 教练工作台深化

继续把 `/sales-trainer/business-skills/coach` 做成核心体验：训练卡、自由追问、补救、总结、掌握度推进。

优点：
* 学员体验更强，能体现 AI 差异化。
* 与当前 AI Coach 主动训练闭环任务一致。

风险：
* 当前基础已存在，继续深化会遇到边界收益递减。
* prompt/schema/失败兜底和前端状态复杂度会上升。

### Direction C: 角色扮演就绪层（Later）

不直接冲进实时语音，而是新增一层“实时对练就绪层”：把现有训练包资产和训练证据编译成实时角色扮演可消费的合同，包括知识包、角色约束、情景边界、训练目标、评分 rubric、失败策略和门禁检查。

优点：
* 承接用户最初愿景，避免项目长期停留在异步训练系统。
* 复用已实现资产层，不推倒重来。
* 正面解决最初实时对练失败的根因：知识获取、角色一致性、知识库/角色定义连接、长对话稳定性。
* 可以先做“就绪合同 + 非实时文本角色扮演/回放验证”，再接语音实时链路。

风险：
* 当前阶段不进入实施；需要等上传录音闭环和能力拆分稳定后再推进。
* 需要新增跨域契约，避免 `sales_trainer` 直接引用 `sales_bot` / `training_runtime`。
* 需要定义清楚哪些资产由训练包产出，哪些由实时运行时消费。
* 需要补角色一致性、知识注入、长对话诊断和实时门禁验证。

## Initial Recommendation

修正后的推荐：不要再把下一步定义为“实时角色扮演就绪层”的立即实施。用户明确要求先把当前路径闭环掉，尤其是上传录音训练闭环，并把其中能力拆分为可组合、可配置、可审计的能力模块。

短期主线应是 **录音训练能力组件化**：

* 录音任务定义
* 材料/知识输入
* 上传与存储
* 转写
* 评分 rubric / prompt
* 反馈结构
* 达标规则
* 重试/重评
* 训练记录
* 管理端复盘

这些能力先服务于 PPT 训练、电梯演讲、产品讲解、拜访复述等异步训练任务；未来再作为实时对练的稳定输入。

未来角色扮演就绪层仍有价值，但应建立在当前能力组件化之后：

* 训练包 → 知识包 / 场景包
* 能力点 → 本轮训练目标 / 评价维度
* 题目与 AI Coach 卡片 → 常见问题、错误样本、追问策略
* prompt contract → 角色扮演指令合同
* 弱项与人工复盘 → 个性化对练任务
* 评分 rubric → 对练后评估和报告

Direction A 和 B 继续作为资产层维护，但下一阶段产品叙事应转为：**我们先把录音训练闭环能力化，让任意训练任务都能组合“材料 + 录音 + 转写 + 评分 + 反馈 + 复盘”，而不是把每一关写成固定流程。**

## Grill Decisions

### Decision 1: First realtime roleplay proof target

**Decision**: 第一版实时语音对练必须证明“训练有效”。

**Rejected alternatives**:

* 只证明实时链路可用：容易变成技术 demo。
* 只证明角色扮演可信：无法承接现有训练证据层。

**Implication**:

* 对练入口必须来自用户弱项、训练包能力点或明确训练目标。
* 对练结束必须产生可解释评分、证据、改进建议和下一步训练动作。
* 实时链路、角色一致性和知识注入都是必要支撑，但不是第一版验收主目标。

### Decision 2: Current phase priority

**Decision**: 先不推进实时对练。当前阶段先闭环上传录音训练路径，并把相关能力拆分成可配置、可组合、可审计的能力模块。

**Reason**:

* 实时对练最终会依赖这些能力：材料输入、表达采集、转写、评分、反馈、达标、记录和复盘。
* 如果当前 PPT/录音训练仍写死在单一规则里，后续新增电梯演讲、产品讲解、拜访复述或实时对练都会复制流程。
* 先把录音训练能力抽出来，才能让不同训练任务自由组合，而不是每个场景重写一套链路。

**Implication**:

* PPT 训练不应是特殊硬编码流程，而应是一个由录音训练能力组合出来的任务模板。
* 能力拆分需要优先检查当前上传录音、材料绑定、转写、评分、反馈、训练记录和后台复盘中哪些规则仍散落在服务/页面中。
* 后续实现应以配置、模板、字典、权限、审计和测试为边界，而不是把新关卡直接写入页面或业务函数。

### Decision 3: Capability composition unit

**Decision**: 当前阶段的能力组合单位选择“训练任务模板”，而不是直接暴露技术步骤能力或先按能力点建模。

**Meaning**:

* 业务侧配置的是一个训练任务模板。
* 模板组合材料要求、录音要求、转写策略、评分方案、rubric、通过线、反馈结构、重评策略、记录/复盘展示。
* 上传、存储、转写、评分、重评、反馈生成、记录写入是内部技术能力，由模板驱动，不直接暴露给业务人员自由拼底层步骤。

**Rejected alternatives**:

* 技术步骤能力：太底层，容易变成流程编排工具，业务人员难以稳定配置。
* 能力点训练能力：更接近最终训练效果，但对当前“先闭环录音训练”来说抽象过高，适合在模板稳定后作为模板标签/评价维度接入。

**Implication**:

* PPT 训练、电梯演讲、产品讲解、拜访复述都应是不同训练任务模板，不能继续靠 `purpose == "ppt_pitch"` 这样的场景分支扩展。
* 模板必须有版本和快照，历史提交不能被模板修改改写。
* 模板发布、回滚、权限、审计和配置校验是第一版必需能力。

### Decision 4: Training task template scope

**Decision**: 第一版采用“标准模板”，覆盖当前录音训练闭环的关键业务配置，但不做通用流程编排器。

**Template fields / sections**:

* Task brief: 标题、目标、场景说明、操作说明、上传引导、常见错误。
* Material requirements: 是否需要材料、材料类型、是否必须确认版本、允许/必需的材料绑定。
* Recording requirements: 录音用途、允许文件类型、大小上限、是否要求时长元数据、建议时长或时长选项。
* Transcription policy: 转写供应商/模式、超时、远程文件下载策略、失败分类和是否允许重试。
* Scoring scheme: 评分 prompt / scoring standard、rubric、维度、通过线、模型配置、输出结构。
* Feedback structure: 总结、亮点、改进点、维度分、推荐重练动作、下一步 CTA。
* Failure / regrade policy: 转写失败、评分失败、prompt 缺失、模型超时、重试/重评权限和次数。
* Snapshot policy: 提交时必须冻结模板版本、材料版本、任务简报、评分方案、rubric、路径修订和关键配置。
* Admin governance: 发布、回滚、启停、权限、操作日志、配置校验。

**Out of scope**:

* 不做管理员自由拖拽编排“上传→转写→评分→通知→证书”的流程引擎。
* 不让业务人员直接编排底层技术步骤。
* 不在第一版引入实时对练、证书、复杂审批流。

**Implication**:

* 当前 `task_brief`、`materials`、`audio`、`learner_rubric`、`scoring_prompt_id`、`pass_threshold` 等配置需要被统一解释为训练任务模板的一部分。
* `ppt_pitch` 特殊门禁应迁移为模板的 material requirement，而不是 service 中的硬编码分支。

### Decision 5: Template storage strategy

**Decision**: 第一版不新建一等 `TrainingTaskTemplate` 资产；先在 `SalesTrainerUnit.config` 中按模板结构规范化，预留未来迁移为一等模板资产的字段。

**Recommended shape**:

```text
SalesTrainerUnit.config.training_task_template
  template_schema_version
  template_key
  template_version
  task_brief
  material_requirements
  recording_requirements
  transcription_policy
  scoring_scheme
  feedback_policy
  failure_policy
  snapshot_policy
  governance
```

**Why**:

* 当前目标是闭环和去硬编码，不是立即扩展资产中心。
* 现有 `audio_scoring` 单元、路径配置、提交快照、后台页面可以平滑迁移。
* 预留 `template_key/template_version/template_schema_version` 后，未来可以把模板抽成独立资产，并通过迁移脚本从 unit config 提升出去。

**Compatibility**:

* 旧字段 `config.audio`、`config.materials`、`config.task_brief`、`audio_score_prompt.learner_rubric` 可先由读取层归一化为 `training_task_template` view。
* 写入新配置时优先保存规范化结构；必要时同步生成兼容字段，保证现有 learner/admin 页面不过早大改。
* 提交快照应冻结规范化后的模板 view，而不是只冻结散落字段。

### Current audio path code facts

* 已有 `audio_scoring` 训练单元、`purpose`、`task_brief`、`learner_rubric`、`scoring_prompt_id`、`pass_threshold`、材料绑定、提交快照、转写、Deucate 评分、重评和结果页。
* 提交记录已冻结 `material_snapshot`、`score_scheme_snapshot` 和 `task_brief_snapshot`，这符合后续能力化方向。
* 当前仍存在场景特化分支：`AudioSubmissionService._require_material_binding_for_ppt()` 通过 `purpose == "ppt_pitch"` 对 PPT 材料绑定做特殊门禁。
* 当前 `unit_type` 仍主要是 `"quiz" | "audio_scoring"`；`audio_scoring_group` 作为路径模块类型存在，但底层训练单元仍是多个 audio scoring 单元的组合。
* 下一步要重点判断：把这些配置继续放在 `unit.config.audio/task_brief/materials` 里，还是抽象成更明确的“训练任务模板 / 能力编排”结构。

结合用户补充，路线应重新表述为：

1. **先把可评分表达做稳**：PPT/视频/语音上传转写评分，解决“表达是否完整、准确、清楚”的基础评估。
2. **再把知识掌握和教练式训练做稳**：文章学习、传统考试、AI 教练训练卡，解决“是否理解业务/商务/技术知识”和“能否在引导下应用”的问题。
3. **最后回到实时对练**：把前两阶段沉淀出的知识、能力点、角色规则、评分证据、常见错误和优秀样本接入实时语音角色扮演，降低知识漂移、角色漂移和长对话不稳定风险。

## AI Coach Mode Boundary Draft

### Practice / Coaching Mode

* 目标：补弱、引导练习、帮助学员把文章知识迁移到表达和场景判断。
* 题源：可使用已审核题库、能力点、章节内容和受控 prompt 生成训练卡。
* 反馈：允许提示、解释、追问、补救、推荐回看章节。
* 成绩：可记录训练证据和能力点进度，但默认不直接替代正式考试成绩。
* 风险边界：AI 输出必须是白名单 typed UI events，不允许任意 HTML/JSX；自由追问不得绕过训练卡状态机。

### Examiner / Certification Mode

* 目标：达标、认证、阶段性验收。
* 题源：只允许来自已发布题库、已审核 AI 草稿或冻结试卷；不能在正式考试中临场生成未审核题目作为成绩依据。
* 规则：考试开始时冻结试卷、题目、能力点、评分 rubric、prompt 版本、模型配置和通过线。
* 辅助边界：考试中 AI 不得泄露答案、不得给暗示性解释、不得根据学员追问降低难度，除非明确进入“放弃考试/转辅导”流程。
* 评分：客观题确定性判分；简答/追问评分必须有 rubric、证据引用、prompt 版本、原始输出和失败兜底；高风险场景可进入人工复核。
* 重试：重试次数、间隔、是否换题、是否保留最好成绩必须配置化并写审计。
* 成绩有效性：只有完成全流程且未触发非法配置、prompt 失败、题源异常或越权访问时，成绩才可标记为有效。
* 退出与降级：AI 生成失败、评分失败、题源缺失或配置非法时 fail closed，不伪造成绩；可引导转入练习模式。
