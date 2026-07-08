# CONTEXT.md — 领域术语表

> 本文件是项目的共享领域语言源头。所有模块、ADR、spec 和代码中的术语以此为准。
> 与代码矛盾时，先更新本文件，再修代码。

---

## 场景 (Scenario)

**定义**：训练类型的高层分类，决定了 WebSocket 运行时、评估逻辑和报告模板的选型。

| 取值 | 说明 |
|------|------|
| `sales` | 销售对练场景，走 `sales_bot/` 运行时 |
| `presentation` | PPT 演练场景，走 `presentation_coach/` 运行时 |

**文件**：`PracticeSession.scenario_type` 字段。

**禁止**：
- 不得将 Practice Mode / Practice Pattern 与 Scenario 混淆。
- Scenario 只取 `sales | presentation` 两个值，不扩展。

---

## 练习模式 (Practice Mode)

**定义**：某个 Scenario 下的具体练习形态。例如在 `sales` 场景下，可以有 `customer_roleplay`（客户对练）、`product_pitch`（产品介绍）等模式。

**状态**：待定 — 当前系统尚未统一定义 Practice Mode 枚举。一旦落地，此处更新。

---

## 新人训练路径 (Newcomer Training Path)

**定义**：新人入职后的异步学习、录音上传、AI 转写、AI 评分、文章学习和考卷考试路径。它面向学员学习闭环和管理员配置治理，不是实时 WebSocket 对练，也不是“销售队列”。

**对外定位**：面向企业客户时，产品主线称为“企业新人训练路径平台”，强调新人训练的标准化、追踪、达标验收和持续改进。

**北极星结果**：每个新人都形成一份可信的训练达标档案。

**第一版主用户**：第一版优先服务培训负责人查看、复核和推进新人达标；新人端先保证能顺利完成训练任务。

**技术命名**：第一版继续复用 `sales_trainer` 后端模块、`/sales-trainer` 前端路由、learner `/api/v1/sales-trainer` 和 admin `/api/v1/admin/sales-trainer` 作为兼容技术命名。用户可见产品名必须使用“新人训练路径”。

**典型模块**：
- PPT 讲解录音：学习最新新人训练路径 PPT 内容和讲解要点，上传录音后走 ASR 和 AI 评分。
- 学习专题：阅读后台发布的学习文章，按专题下的小单元完成阅读、小测和可选 AI 补练；第一版只内置“商务礼仪规范”，后续可扩展为销售技巧、客户常见质疑等专题。
- 电梯演讲：按 10/20/30 分钟等后台配置选项完成 PPT 演讲录音和评分。
- 实时对练占位：仅展示未开放状态；本阶段不创建 realtime practice session。

**第一版任务流**：上传演讲 PPT → 学习文档 → 答题或 AI 补练教练 → 金字塔演讲训练 → 真实语音对练。真实语音对练是最终训练阶段；在前置材料、学习、考试和演讲证据不足时，不应作为首个可用闭环的主入口。

**先可用闭环**：V0.9 先交付标准材料/PPT 学习、文档学习、答题或 AI 补练教练、金字塔演讲训练、达标档案、培训负责人复核和重练；真实语音对练先作为按前置训练解锁的后续阶段，不阻塞 V0.9 可用。

**V0.9 全量闭环**：V0.9 的“全量”不是一次性做完所有高级能力，而是把配置、学习、提交、评分、补练、重练、复核、档案、准入、异常和审计这些关键业务链路闭合。只证明页面能打开、录音能评分或 AI 能回复，不足以判定 V0.9 可用。

**材料与提交边界**：标准 PPT、学习文档和评分标准由管理员上传或配置；新人提交的是答题结果、录音、演讲内容或对练结果，不应让新人把准备 PPT 文件作为第一步负担。

**配置边界**：V0.9 的训练路径顺序、PPT/录音任务、材料绑定、评分 Prompt、学习专题、学习文章、小单元、题目、AI 补练教练启停、金字塔演讲任务和真实语音对练准入条件，都必须由后台配置和发布治理驱动；前端和服务端只能内置稳定模块类型、兼容 key、默认文案和安全兜底，不能把具体训练内容、材料、评分标准或关卡绑定写死。

**学习专题**：新人训练路径旁路的非阻塞学习区，由 `newcomer_learning_topics_v1` 发布配置治理。学习专题不是必修训练任务，`required=false` 且 `blocks_next=false`，未完成不影响下一关、不影响达标验收主流程；它只能作为学习证据、薄弱能力线索和可选补练入口进入 Journey 分析。第一版的 `business_etiquette` 专题来源兼容旧 `business_skills` 模块，但发布后由独立学习专题 active revision 驱动 learner 展示。

**学习文章**：后台可管理的学习内容集合，不等同于“商务技巧文章”。“商务礼仪规范”只是学习文章/学习专题的一个具体内容方向；未来销售技巧文章、客户常见质疑文章等应复用相同的文章、章节、小单元、题库和发布治理机制。

**商务礼仪 AI 教练**：商务礼仪学习专题下的可选 Chatbot 训练入口。学员进入 `/sales-trainer/business-skills/coach` 后与 AI 教练自由对话，AI 在消息流中插入后端白名单 `ui_event` 卡片（如 `quiz_card`、`explanation_card`、`summary_card`、`followup_prompt`）；前端只渲染注册好的 React 组件，不执行 LLM 返回的 JSX/HTML/脚本。它通过学习专题 `topics[].ai_coach` 配置启停、允许题型、允许 UI 事件、每轮卡片数、欢迎语、掌握阈值和 Prompt 绑定。主动训练闭环称为“教练主导训练局”：学员提交题卡后，后端根据评分和 `coach_state` 决定 `next_coach_action`（继续练、加难、补救、换场景、总结、让学员选择或结束），每次最多自动推进一步，再等待学员下一次作答或输入。它不同于策略中心的 `growth.ai_coach.rules`：后者是增长/触达规则，不管理新人训练路径学习专题的生成式 UI 对话、评分 Prompt 或学员训练 session。

**AI 补练教练**：学习材料或小测之后的 AI 辅导与补练角色，围绕当前小单元生成训练卡、批改答案、解释薄弱点、推荐回看章节，并给出 AI 初评达标、可上场或待人工复盘的阶段判断。它不是培训负责人最终确认达标的替代者。

**AI 补练准入**：AI 补练教练默认不是新人训练路径的必经环节，而是未达标后的强推荐补弱工具；只有关键岗位或关键能力项才可配置为必做。

**与 AI 实时对练的边界**：AI 实时对练由 `sales_bot`、`practice_sessions`、`training_runtime` 和 `/practice/[sessionId]` 负责，是语音实时对话运行时。新人训练路径不得绕过该边界直接创建、复用或变更实时对练会话；未来集成必须通过独立契约和启用开关进入。

**真实语音对练准入**：真实语音对练按训练准入开放，而不是按技术连通直接开放。新人应先完成标准材料学习、关键题目、金字塔演讲训练，并形成至少一组能力项状态；系统再基于弱项生成对练目标，同时校验 realtime provider readiness。

**禁止**：
- 不得把新人训练路径命名为“销售队列”或“销售训练队列”。
- 不得把 `sales_bot` 的实时对话运行时逻辑搬进 `sales_trainer`。
- 不得在页面组件中写死模块标签、评分标准、提示词、文章正文、材料 URL、考卷组成或模块启停状态；这些属于后台可配置业务内容。

## 训练达标档案 (Training Readiness Dossier)

**定义**：围绕单个新人汇总其训练任务、提交证据、评分结果、弱项、复训动作、人工复核和达标结论的可信业务档案。

**可信性来源**：训练达标档案必须能回答：新人练过什么、提交了什么证据、AI 按什么标准评分、哪些能力达标或未达标、是否经过人工复核、未达标后是否重练。

**关系**：一个 **新人训练路径** 为每个新人生成一份 **训练达标档案**；一份 **训练达标档案** 由多个训练任务结果、AI 评分证据和人工复核记录构成。

**禁止**：
- 不得把训练达标档案简化为模块完成进度或考试分数。
- 不得把未经确认的 AI 建议直接当作达标结论。

## 训练任务模板 (Training Task Template)

**定义**：后台配置的训练关卡业务模板，声明训练顺序、任务名称、材料要求、提交物、评分标准、能力项、通过线、AI 补练策略和是否阻塞下一关。

**V0.9 任务类型**：材料学习、文章小测、录音评分、AI 补练、真实语音对练准入。管理员可以新增或调整这些类型下的任务实例，但不能自由创造系统不认识的任务类型。

**关系**：一个 **新人训练路径** 由多个 **训练任务模板** 组成；一个 **训练任务模板** 驱动学习、上传、答题、转写、评分、记录、复核或重练等内部执行步骤。

**禁止**：
- 不得让管理员直接编排上传、转写、评分、写记录等底层技术步骤。
- 不得把 PPT 讲解、商务礼仪、金字塔演讲等具体训练内容写死在页面或服务逻辑里；它们应由训练任务模板和发布配置驱动。

## 能力项 (Competency Item)

**定义**：新人训练中可被训练、评分、复核和判定达标状态的最小业务能力单元。

**来源**：第一版能力项来自一套内置的通用新人销售能力模型；训练任务只能选择和引用这些能力项，AI 评分负责按任务评分标准给出分数、证据和反馈，不负责临时发明新的能力项。

**关系**：一个训练任务产生训练证据；评分标准将训练证据映射到一个或多个 **能力项**；**训练达标档案** 汇总每个能力项的达标状态。

**禁止**：
- 不得把课程模块、训练任务或考试题目直接当作能力项。
- 不得只用总分替代能力项达标判断。

## 金字塔演讲训练 (Pyramid Speech Drill)

**定义**：围绕“结论先行、分点支撑、案例证明、行动收束”训练新人结构化表达能力的独立训练关卡。

**关系**：**金字塔演讲训练** 是第一版新人训练路径中的一个训练任务；其评分方法可复用于 PPT 讲解、产品介绍和未来真实语音对练。

**禁止**：
- 不得把金字塔演讲只做成一次性文案课程。
- 不得让金字塔演讲评分只沉淀为单次任务分数，而不回流到 **结构化讲解**、**表达清晰度** 等能力项。

## 通用新人销售能力模型 (General Newcomer Sales Competency Model)

**定义**：企业新人训练路径第一版内置的一组稳定能力指标，用于跨训练任务汇总新人是否具备基础销售上岗能力。

**第一版能力项**：表达清晰度、结构化讲解、产品理解、客户视角、需求识别、异议回应、商务礼仪与职业表达。

**关系**：一个 **通用新人销售能力模型** 包含 6-8 个 **能力项**；一个训练任务模板引用其中若干能力项；AI 评分按任务评分标准为被引用能力项给出分数和证据。

**禁止**：
- 不得让每个训练任务各自定义一套互不兼容的能力指标。
- 不得把 AI 生成的自由文本弱项直接写成新的能力项。

---

## 发布治理修订模型 (Governed Revision Model)

**定义**：面向新人训练路径、课程闭环、题库、学习内容、Prompt、评分规则和可配置运行时资产的统一治理语言。它解决“已发布后不可自然编辑、只能复制草稿和手动换绑”的管理体验问题，同时保证历史考试、录音、评分和会话快照不被未来发布污染。

| 术语 | 含义 |
|------|------|
| `logical_id` | 业务对象的稳定身份，例如“商务技巧考卷”或“新人训练路径配置”。 |
| `revision_id` | 一次不可变内容修订的身份。已发布 revision 不允许原地改 payload。 |
| `active_revision` | 当前只对未来请求生效的 revision 指针。发布或回滚只移动该指针。 |
| `working_revision` | 管理员保存修改后生成、尚未发布的待发布 revision。 |
| `snapshot` | attempt、submission、session、result 创建时冻结的运行时内容副本。 |
| `binding_revision` | 模块绑定文章、考卷绑定题目、模板绑定案例等引用关系的修订。 |
| `audit_event` | 记录 actor、action、target、before、after、reason、trace_id 和影响范围的审计事件。 |
| `regrade_run` | 对历史记录执行重新评分的高风险显式动作；不得由发布自动触发。 |

**未来生效规则**：编辑、发布、回滚只影响新学员、新 attempt、新 submission 或新 session。已有记录只能读取创建时冻结的 `snapshot` 或 revision refs；缺少 lineage 的旧数据标记为 `legacy_snapshot_only`，不得伪造 revision。

**高风险字段**：正确答案、分值、通过线、AI 评分 Prompt、评分规则、运行时模型、可见/隐藏信息策略必须被视为高风险。配置不能把这些字段降级为低风险。

**禁止**：
- 不得直接更新已发布 revision payload。
- 不得让历史 attempt、submission、score result 或 `curriculum_snapshot` 从 latest asset 重新拼装展示。
- 不得把 regrade 和 rollback 混为一谈；rollback 只影响未来，regrade 才能生成新的历史评分结果。

---

## 角色 (Persona)

**定义**：平台级 AI 对话人格，是实时 WebSocket 对练中角色提示词、知识库绑定与行为策略的 **source of truth**。

**配置面**：`/admin/personas`，核心字段 `persona_policy`（system prompt、KB 绑定、工具策略）。

**使用路径**：
- **平台直练**：用户选 Agent + Persona 开 session
- **课程闭环**：`PracticeTemplate.persona_id` 引用；`RoleProfile.persona_ref` 可选弱关联

**文件**：`agent/models.py` → `Persona`。

**禁止**：
- 不得将 Persona 与 RoleProfile、CaseItem 的「客户角色」文本字段混为一谈。
- 不得在 Agent 遗留字段中维护 live prompt 或 KB 绑定。

---

## 客户角色画像 (RoleProfile)

**定义**：课程闭环中的 **客户行为画像**——沟通风格、压力等级、知识边界、行为规则，以及可选的 Persona 弱关联。

**配置面**：`/admin/curriculum-practice/role-profiles`。

**与 Persona 的关系**：`persona_ref` 可选指向已启用的 Persona；留空则仅依赖 RoleProfile 自身的行为规则。

**变更工作流**：已发布 RoleProfile 不可原地编辑。变更 = duplicate → 模板换绑 → 模板重发；duplicate 不复制 `voice_id`（需重新 clone）。

**文件**：`curriculum_practice/models.py` → `RoleProfile`。

**禁止**：
- 不得将 RoleProfile 当作平台直练的唯一角色入口（直练走 Persona）。
- 不得将 CaseItem 表单中的「客户角色」文本字段当作 RoleProfile。

---

## 训练案例 (CaseItem)

**定义**：课程闭环中的 **业务剧本**——行业、公司画像、痛点、异议、隐藏信息、披露策略与成功标准。

**配置面**：`/admin/curriculum-practice/case-items`。

**使用路径**：`PracticeTemplate.case_item_id` 绑定（仅 **published** 可选），开练时写入 `curriculum_snapshot`。

**变更工作流**：已发布 CaseItem 不可原地编辑。变更 = **复制为新草稿** → 编辑 → 在模板草稿中换绑 → **重新发布模板**。慎用「退回草稿」：若已发布模板仍引用，学员新开练会在快照阶段失败。

**文件**：`curriculum_practice/models.py` → `CaseItem`。

**禁止**：
- 不得将 CaseItem 的 `customer_role` 文本字段当作 Persona 或 RoleProfile。
- 不得在未绑定 PracticeTemplate 的情况下假设 CaseItem 单独可开练。

---

## 角色扮演情景 (Roleplay Situation)

**定义**：客户对练中的关系史与情景边界配置，描述本轮会谈属于首次拜访、复访、方案评审、价格谈判、续约或投诉安抚等哪一种情境。

**职责范围**：Roleplay Situation 只管关系史事实、允许/禁止事实、可见/隐藏信息范围、冲突响应策略和违规处理策略。

**与 Sales Conversation Stage 的关系**：销售流程阶段仍由 `SalesStageCapability` 维护，Roleplay Situation 不新增第三套 stage。Situation 只能声明 `initial_stage_hint`、`forbidden_stage_codes` 等策略，由运行时 checker 根据 `SalesStageCapability` 的阶段输出判断是否越界。

**配置面**：Situation Pack 短期可由 `BusinessRuleConfig` / `ConfigBundle` ruleset 承载；长期允许演进为一等 `SituationPack` 资产。无论底层存储形态如何，查看、复制、发布、归档、回滚、审计和 Config Center 入口必须复用统一配置治理，不得产生孤立 admin 生命周期。Config Asset Center 的分期落地（Phase A → B1 projection 读权威 → B2 entity 写权威）及 **HITL 审批边界**（SituationPack 发布、Import 冲突、`publish_after_import`、B1 runtime authority 切换的前置条件）见 [ADR 2026-05-27: Config Asset B2 HITL 治理](docs/adr/2026-05-27-config-asset-b2-hitl-governance.md)；B1 切换须满足 #96 定义的 **≥14 日双读零 mismatch** 观察窗后方可人工批准。

**禁止**：
- 不得用长 prompt 代替结构化 relationship context。
- 不得让普通 runtime 函数硬编码“首访不能说什么”等业务策略；这些策略必须来自 Situation Pack 或资产结构化字段。

---

## 角色扮演合同 (Roleplay Contract)

**定义**：一次训练运行时的冻结角色合同，由 Persona、RoleProfile、CaseItem、PracticeTemplate、Situation Pack、ScoringRuleset 编译而来，是 prompt 编译、信息披露、输出守门和报告追踪的运行时权威。

**双轨来源**：
- **课程闭环**：`RuntimeSnapshotService` 在创建会话时写入 `curriculum_snapshot.roleplay_contract`。
- **平台直练**：`VoiceRuntimePolicyService` 在解析策略时写入 `voice_policy_snapshot.roleplay_contract`。

**运行时消费**：StepFun Realtime 只消费 frozen contract 与当前可见 payload，不从 CaseItem、RoleProfile 或 Persona 重新拼装关系史语义。

**禁止**：
- 不得在 StepFun runtime 中 fallback 到 latest assets 重建合同。
- 不得新增并列 prompt compiler；合同渲染进入现有 `VoiceInstructionCompiler`。
- 不得把 `behavior_rules_for_prompt_only` 当作机器 gate 规则。

---

## 关系上下文 (Relationship Context)

**定义**：客户与学员之间的关系史事实，例如是否首次正式沟通、是否看过方案、是否谈过预算、是否已有合作历史。

**机器可校验字段**：`prior_interactions`、`has_prior_meeting`、`has_seen_proposal`、`has_discussed_budget`、`has_existing_partnership`、`meeting_history_summary`。

**底线**：`first_visit` 必须保持 `has_prior_meeting=false` 且 `meeting_history_summary=null`；`follow_up` 必须有可追溯的 `meeting_history_summary`。

---

## 可见信息范围 (Visible Information Scope)

**定义**：当前情景和阶段允许模型看到的字段集合，例如 `company_profile`、`pain_points`、`objections`。

**使用路径**：`CurriculumRuntimeDossierHydrator` 只按 `roleplay_contract.visible_information_scope.initial_visible_keys` 组装初始 StepFun instructions。

**底线**：hidden information 默认不可见。`hidden_information`、预算、决策链、竞品报价等未命中披露策略前不得进入模型上下文。

---

## 隐藏信息范围 (Hidden Information Scope)

**定义**：默认不可见、必须满足披露策略后才可注入模型的字段集合。

**运行时规则**：披露应按 key 切片记录，不能把完整 `hidden_information` blob 直接注入模型。第一阶段 disclosure trigger 可用确定性规则，LLM judge 不进入 StepFun 热路径。

---

## 角色合同遵守 (Roleplay Compliance)

**定义**：运行时对 Roleplay Contract 遵守情况的检测结果，包括关系史矛盾、隐藏信息泄露、禁止话题、禁止阶段和角色漂移。

**热路径策略**：确定性 checker 负责首层检查；blocking 违规最多触发一次修复或自然降级。LLM judge 只用于离线 eval、发布前回归或模型升级门禁。

**观测字段**：运行时记录 `roleplay_contract_hash`、`situation_code`、`violation_count`、`blocking_violation_count`、`regenerate_count`、`cancel_stream_count`、`legacy_contract_used`。

---

## 课程训练模板 (PracticeTemplate)

**定义**：课程闭环的 **组装枢纽**，将 Agent、Persona、CaseItem、RoleProfile、LearningContent、ExaminerAgent、评分规则等资产编排为可发布的训练路径。

**核心字段**：`curriculum_plan`（study → exam → practice → report 阶段图）、`examiner_agent_id`、`learning_content_id`。

**发布门禁**：`PublishingGateService` 校验依赖资产均为 published 且 hash 一致。

**文件**：`curriculum_practice/models.py` → `PracticeTemplate`。

**禁止**：
- 不得绕过 PracticeTemplate 直接从散落资产开练（除非走平台直练轨道）。
- 不得将 PracticeTemplate 与 Agent 壳层混为同一概念。

---

## 知识应答配置：KnowledgeConfigVersion vs RagProfile

**定义**：系统存在 **两层检索配置**，管理员必须区分「改哪生效」：

| 概念 | 范围 | 说明 |
|------|------|------|
| `KnowledgeConfigVersion` | **全局** | 检索策略页（`/admin/retrieval-strategies`）管理的版本化 Pipeline，影响全部 KB 的检索与应答行为 |
| `RagProfile` | **单 KB 遗留** | 知识库详情页 per-KB 下拉绑定的 RAG Profile（`/admin/rag-profiles`），仅作用于该 KB |

**优先级**：运行时以全局 `KnowledgeConfigVersion`（active 版本）为主引擎；per-KB `RagProfile` 为遗留/局部 override，不得假设二者等价。

**文件**：`KnowledgeConfigVersion` → ConfigBundle `domain="knowledge"`；`RagProfile` → `common/knowledge/` 相关模型。

**禁止**：
- 不得在文档或 UI 文案中将「检索策略」描述为某个 KB 的专属配置。
- 不得在未确认 active 版本的情况下假设 per-KB RagProfile 已生效。

---

## 配置双轨 (Configuration Tracks)

**定义**：管理端存在两条并行配置轨道，共用部分资产但组装与消费路径不同。

| 轨道 | 典型入口 | 组装枢纽 | 学员消费路径 |
|------|----------|----------|--------------|
| **平台直练** | 智能体 + Persona + 知识库 | `VoiceRuntimePolicyService` → `voice_policy_snapshot` | 仪表盘「开始训练」→ `/practice/[sessionId]` |
| **课程闭环** | CaseItem/RoleProfile + 课程模板 + 学习/题库 | `PracticeTemplate` + `PublishingGateService` → `curriculum_snapshot` | `/learning-path` → study / exam / practice / report |

**共享资产**：Persona、KnowledgeBase、ScoringRuleset、Agent 壳层可在两轨复用，但 **绑定方式与运行时快照字段不同**。

**权威组装代码**：
- 平台直练：`common/services/practice_session_service.py`、`sales_bot/services/voice_runtime_policy.py`
- 课程闭环：`curriculum_practice/services/session_snapshots.py`、`curriculum_practice/services/examiner_session_assembler.py`

**禁止**：
- 不得在平台直练路径中读取 `curriculum_snapshot` 作为 prompt 权威。
- 不得在课程闭环路径中静默 fallback 到「最新已发布」的散落资产（如 ExaminerAgent）。

---

## 角色配置资产分层 (Roleplay Asset Layers)

**定义**：运营口语中的「多个库绑定到一个人格」，在平台里对应**分层配置资产**，运行时由 **Roleplay Contract** 冻结组装，而不是每次从 Persona 长 prompt 临场拼接。

| 口语库名 | 平台术语 | 职责 |
|----------|----------|------|
| 背景库 | `KnowledgeBase` + `CaseItem` 结构化字段（`company_profile`、`pain_points` 等） | 行业/公司/痛点等**可引用事实**；KB 供检索，CaseItem 供剧本事实 |
| 角色库 | `RoleProfile` + `Persona` | 沟通风格、压力、知识边界；Persona 为实时 WS 的 policy 载体，**不是**关系史与隐藏信息的唯一真源 |
| 情景库 | `Roleplay Situation`（Situation Pack，可由 `BusinessRuleConfig` ruleset 承载，也可演进为一等资产；治理仍接入 ConfigBundle/audit） | 首访/复访等**关系史边界**、可见/隐藏范围、禁止声称、违规策略 |
| 组装结果 | `Roleplay Contract`（会话快照内冻结） | 开练时编译；运行时 prompt、披露与守门**只读合同**，不读 latest 资产 |

**禁止**：
- 不得把「多库绑定 Persona」理解为运行时每次从后台最新配置重拼语义（会导致开练后人设漂移）。
- 不得新建与上表平行的「背景库表/角色库表」替代 `CaseItem` / `RoleProfile` / Situation Pack；Situation Pack 独立实体化必须遵守 ADR 的统一治理约束。

---
