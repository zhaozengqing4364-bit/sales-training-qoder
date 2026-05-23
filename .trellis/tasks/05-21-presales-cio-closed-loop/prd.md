# 售前新人首次拜访制造业 CIO 闭环样板

## Goal

搭建一个可演示、可训练、可复用的“售前新人首次拜访制造业 CIO”闭环样板包。样板需要把一个售前专家、一个售前考官、一个真实虚拟客户、一套题库、一套评分标准、一条新人训练路径串起来，证明系统能完成“学习 → 考核 → 客户对练 → 评分复盘 → 补学”的闭环。

## What I already know

* 用户选择 A 方案：售前新人首次拜访制造业 CIO。
* 用户已确认 MVP 范围：只做“首次拜访需求挖掘”闭环，暂不加入报价谈判、POC 深水区和完整竞品攻防。
* 本任务要深入了解现有项目、数据库和配置能力，并据此搭建场景。
* 目标样板包含六个组成：售前专家、售前考官、真实虚拟客户、题库、评分标准、新人完整训练路径。
* 角色效果需要体现“有来有回”的对练，而不是单向问答。
* 虚拟客户不能只靠泛化提示词自由发挥，必须有稳定的虚拟公司档案、真实需求、隐藏信息和前后一致的回答边界。
* 代码库已存在可承载闭环的配置面：`Agent`、`Persona/persona_policy`、`KnowledgeBase`、`LearningContent`、`QuestionItem`、`ExaminerAgent`、`CaseItem`、`RoleProfile`、`ScoringRuleset`、`PracticeTemplate(mode="mixed_path")`、`curriculum_plan`。
* `backend/scripts/seed_presales_mvp.py` 是现有售前种子数据参考，可作为制造业 CIO 样板的实现模板。

## Assumptions (temporary)

* 优先使用项目现有的 Agent / Persona / Knowledge / Test Bank / Learning Content / Evaluation 能力完成配置和数据搭建；只有现有能力无法闭环时才考虑代码改动。
* MVP 先服务“新人首次拜访”一个主题，不扩展到全销售体系、全行业或多部门训练。
* 样板数据可以先使用虚拟但真实感强的制造业客户与售前材料，不依赖真实客户敏感信息。

## Open Questions

* 无阻塞问题。用户已确认：售前专家纳入学习阶段，直接写入数据库供后续测试。

## Requirements (evolving)

* MVP 主线限定为“首次拜访需求挖掘”：新人需要完成开场、客户背景确认、痛点挖掘、初步价值匹配、约定下一步。
* 配置一个售前专家角色：纳入 study 学习阶段，用于新人学习产品、制造业 CIO 背景、首访流程、客户拜访方法和话术答疑；不为 MVP 新增独立 `expert_qa` 阶段。
* 配置一个售前考官角色：用于主动出题、追问、点评，并判断新人是否具备进入客户模拟的基础能力。
* 配置一个真实虚拟客户角色：制造业 CIO，有公司背景、业务系统、痛点、预算/决策链、隐藏信息和异议策略。
* 准备一套题库：覆盖产品理解、制造业/CIO 背景、需求挖掘、场景判断、下一步推进；异议处理只保留基础边界，不做深水区攻防。
* 准备一套评分标准：覆盖产品理解、需求挖掘、客户信息完整度、初步价值匹配、沟通结构、下一步推进。
* 设计一条新人完整训练路径：前置学习 → 专家答疑 → 考官测验 → 客户模拟 → 报告复盘 → 补学建议。
* 优先通过现有 `PracticeTemplate(mode="mixed_path")` + `curriculum_plan` 编排学习、考核、对练、报告阶段。

## Technical Approach

* 以 `backend/scripts/seed_presales_mvp.py` 为参考，新增或调整一个制造业 CIO 首访样板种子配置，而不是新造训练框架。
* 使用现有配置面搭建资产链：Agent → Persona/persona_policy → KnowledgeBase → LearningContent → QuestionCategory/QuestionItem → ExaminerAgent → CaseItem/RoleProfile → ScoringRuleset → PracticeTemplate/curriculum_plan → TrainingTask。
* 默认路径：study（7章学习 + 专家答疑/确认内容）→ exam（售前考官测验）→ practice（制造业 CIO 客户对练）→ report（评分复盘 + 补学建议）。
* 不新增阶段类型；专家 QA 作为 study 阶段内容和验收说明沉淀，避免扩大实现范围。
* 评分维度以首访需求挖掘为中心：开场与背景确认、需求挖掘深度、制造业/CIO 场景贴合、初步价值匹配、下一步推进。

## Decision (ADR-lite)

**Context**: 用户要的是能演示、能训练、能复用的闭环样板；项目已经有课程、题库、考官、客户角色、评分、路径编排能力。

**Decision**: 第一版采用“配置/种子数据优先”的路线，复用现有 `PracticeTemplate` / `curriculum_plan` / `Persona` / `LearningContent` / `QuestionItem` / `ScoringRuleset`，不新建独立训练框架。售前专家纳入 study 阶段，不新增独立 `expert_qa` 阶段。

**Consequences**: 交付更快、与现有管理端和学员端路径一致；但如果未来要把专家 QA 做成独立实时阶段，可能需要再扩展 curriculum stage 或页面入口。

## Build Plan / Material Structure

详见 [`research/scenario-build-plan.md`](research/scenario-build-plan.md)。核心资产包括：

* 学习内容：`制造业 CIO 首次拜访训练营`，建议 7 章。
* 题库：`制造业 CIO 首访需求挖掘题库`，建议 15–20 题。
* 评分规则：`presales-cio-first-visit-v1`，围绕需求挖掘和下一步推进。
* 考官：`制造业 CIO 首访测评官`，主动提问、追问、纠正。
* 虚拟客户案例：制造业集团 CIO，含公司背景、痛点、隐藏信息、异议和成功标准。
* 角色画像与 Persona：严谨、技术导向、重证据、信息逐步披露。
* 训练模板：学习 → 考核 → 对练 → 报告。

## Acceptance Criteria (evolving)

* [ ] 新人可以按固定路径完成一轮完整训练，而不是只进入一个自由聊天入口。
* [ ] 售前专家回答能基于指定知识材料，不把客户模拟信息和考官题库混在一起。
* [ ] 售前考官能主动提问，并基于评分标准给出点评和薄弱项。
* [ ] 虚拟客户回答保持前后一致，且不会一次性暴露所有隐藏信息。
* [ ] 完成客户对练后能得到可解释的评分/复盘结果，并能指向补学内容。
* [ ] 样板可被业务专家试跑并校准。

## Definition of Done

* 相关配置/数据/文档落地到项目现有承载位置。
* 若涉及代码，相关 lint / typecheck / tests 通过；若仅数据/配置，提供可操作的验收脚本或手工验收清单。
* 文档说明角色、知识库、题库、评分标准、训练路径之间的依赖关系。
* 明确哪些能力是本次 MVP 已覆盖，哪些只是后续扩展。

## Out of Scope (explicit)

* 暂不覆盖全部销售体系课程。
* 暂不做多行业客户库。
* 暂不做真实客户敏感数据导入。
* 暂不覆盖 POC 推进、报价谈判、深度竞品攻防和正式方案汇报。
* 暂不做复杂经理端团队排行榜，除非现有系统已天然支持。
* 暂不引入新的外部训练平台或新模型供应商。

## Technical Notes

* 代码库探索已汇总到 [`research/codebase-surfaces.md`](research/codebase-surfaces.md)。
* Agent 是训练场景壳；Persona 的 `persona_policy` 是角色提示词、知识库绑定和实时行为的 source of truth。
* `CaseItem` 适合承载制造业公司档案、痛点、异议、隐藏信息、成功标准。
* `RoleProfile` 适合承载制造业 CIO 的沟通风格、压力等级、知识边界和行为规则。
* `QuestionItem` / `QuestionCategory` / `ExaminerAgent` 适合承载售前考官题库与主动考核。
* `ScoringRuleset` 适合承载需求挖掘导向评分维度。
* `PracticeTemplate(mode="mixed_path")` + `curriculum_plan` 适合承载 study → exam → practice → report 路径。
* 学员端已有 `/learning-path`、`/study`、`/exam`、`/practice` 路由承载闭环体验。
* 场景搭建方案已汇总到 [`research/scenario-build-plan.md`](research/scenario-build-plan.md)。
