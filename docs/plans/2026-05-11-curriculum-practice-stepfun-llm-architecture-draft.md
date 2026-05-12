# 课程化销售训练系统架构草稿：StepFun 实时对话 + LLM 受控智能节点

> 状态：Draft  
> 日期：2026-05-11  
> 目标：在现有销售训练系统上，补全课程、题库、案例库、角色库、AI 考官、客户对练、专家问答、评分报告与部门自维护能力的全量架构设计。  
> 关键前提：**运行时实时对话使用 StepFun；其他非实时智能处理使用受控 LLM。**

---

## 1. 背景与结论

现有系统已经具备 `Agent / Persona / KnowledgeBase / PromptTemplateService / CompiledPromptContract / VoiceInstructionCompiler / voice_policy_snapshot / KnowledgeAnswerEngine / ScoringRulesetService / EvaluationRun / TrainingReportSnapshot / StepFun realtime voice runtime` 等基础能力。

本次需求不是新增一个孤立训练页面，而是把销售/售前训练升级为“课程化、资产化、版本化、可审核、可复训、可追溯”的完整训练平台。

核心结论：

1. 新增 `curriculum_practice` 内容编排域，承载课程、课节、知识点、题库、案例库、角色库、训练模板和训练路径。
2. 内容资产是事实源；Prompt 是编译产物；运行时会话快照是执行事实；Evidence/Report Snapshot 是评价事实。
3. StepFun 只负责实时语音/实时对话运行时，不承担正式内容生产、最终评分裁决或内容发布。
4. LLM 只作为受控节点使用，负责内容草稿、结构化抽取、质检、专家问答、开放题语义判断建议、报告解释等非实时或旁路智能能力。
5. 所有正式资产必须经过 `draft -> review -> published -> archived` 生命周期；运行时只能读取已发布版本，并在会话开始时冻结为 snapshot。

---

## 2. 对前序方案的审计补全

### 2.1 已覆盖内容

前序方案已经覆盖：

- 课程、课节、知识点的内容资产化。
- 题库、案例库、角色库、rubric 的版本化管理。
- AI 考官、专家问答、客户角色对练的训练模式区分。
- `PracticeTemplate` 作为课程、题库、案例、角色、Agent、Persona、知识库、评分规则的编排入口。
- `Runtime Snapshot` 冻结运行时所需版本、hash、模型配置、知识库引用。
- `EvaluationRun` 与 `TrainingReportSnapshot` 负责评价和报告事实链。
- LLM 输出不能直接成为正式事实源。

### 2.2 需要补全/修正的点

| 遗漏或风险 | 补全设计 |
|---|---|
| “客户角色对练使用 LLM”表述容易混淆 | 实时客户对话必须走 StepFun；LLM 只生成离线角色草稿、案例草稿、会后分析和报告解释。 |
| “AI 考官”可能既有实时口语追问，也有异步文本判题 | 实时口语考官走 StepFun；异步出题、开放题语义判断、解析生成走受控 LLM。 |
| 缺少 StepFun 与 LLM 的权威边界表 | 新增运行时/非运行时责任矩阵，避免 PromptTemplate、Persona、StepFun 指令合同混用。 |
| 缺少内容资产发布门禁 | 所有课程/题目/案例/角色/rubric 必须通过 schema 校验、证据引用校验、人工审核、发布审计。 |
| 缺少部门自维护权限模型 | 新增组织/部门/角色权限：作者、审核人、发布人、训练管理员、主管、学员。 |
| 缺少多版本回滚与历史会话稳定性 | 运行时只读 published version；会话冻结 snapshot；发布后不重算历史报告。 |
| 缺少成本、限流、失败降级 | LLM 节点需要模型配置、限流、预算、重试、降级、人工处理队列；StepFun 需要连接失败、重连、超时策略。 |
| 缺少证据链和内容迭代闭环 | 每个报告问题必须能追溯到会话证据、题目版本、案例版本、角色版本、rubric 版本和模型调用记录。 |
| 缺少训练状态机 | 新增学习、知识检查、考官练习、客户对练、评分、报告、主管复核、复训派发状态流。 |
| 缺少数据迁移路径 | 先以只读适配现有 Agent/Persona/Knowledge/Scoring/Prompt，再逐步接入 ConfigBundle/ConfigVersion 生命周期。 |
| 缺少学员首次进入和设备预检 | 增加 `preflight_check`，覆盖目标说明、预计时长、麦克风权限、录音隐私告知、网络检测和失败恢复入口。 |
| 缺少会话中断后的用户恢复语义 | 增加 `reconnecting/resumable/expired` 等状态，明确断线续跑、重试上限、证据拼接和重新派发规则。 |
| 报告缺少可执行反馈要求 | 报告必须包含证据引用、扣分原因、好/坏例句、下一步练习建议和复训触发结果。 |
| 缺少模型治理与紧急停用 | 每个 LLM 节点必须绑定模型白名单、预算、限流、灰度和 kill switch。 |
| 缺少证据完整性排障入口 | 增加会话证据检查视图/API，展示 transcript、turn events、retrieval events、缺失字段和 `non_evaluable_reason`。 |
| 缺少隐私与留存策略 | 增加录音、转写、报告、导出、脱敏、跨部门共享和数据保留期限规则。 |

---

## 3. 权威边界：StepFun 与 LLM 分工

### 3.1 总原则

实时对话的执行权威是：

```text
PracticeTemplate / Agent / Persona / Knowledge / Runtime Profile
  -> VoiceRuntimePolicyService
  -> VoiceInstructionCompiler
  -> voice_policy_snapshot
  -> StepFun realtime session
```

非实时智能处理的执行权威是：

```text
Published Content / Evidence / Rubric / PromptTemplate
  -> CompiledPromptContract
  -> LLMService
  -> schema validation / evidence validation / business validation
  -> draft / suggestion / EvaluationRun / TrainingReportSnapshot
```

### 3.2 责任矩阵

| 能力 | 使用 StepFun | 使用 LLM | 事实源 |
|---|---:|---:|---|
| 客户角色实时语音对练 | 是 | 否 | `voice_policy_snapshot` + published role/case snapshot |
| AI 考官实时口语追问 | 是 | 否 | `voice_policy_snapshot` + question/rubric snapshot |
| 实时打断、追问、控场 | 是 | 否 | StepFun runtime instruction contract |
| 课程讲义抽取 | 否 | 是 | LLM 生成 draft，人工审核后 published |
| 题目草稿生成 | 否 | 是 | LLM 生成 draft，题库发布后才是事实源 |
| 案例草稿生成 | 否 | 是 | LLM 生成 draft，案例库发布后才是事实源 |
| 角色画像草稿生成 | 否 | 是 | LLM 生成 draft，角色库发布后才是事实源 |
| 专家问答/RAG | 否 | 是 | KnowledgeAnswerEngine + citations |
| 开放题语义判断建议 | 否 | 是 | Rubric + evidence，LLM 输出为 suggestion |
| 最终评分 | 否 | 可辅助 | ScoringRuleset/EvaluationRun 是事实源 |
| 综合报告解释 | 否 | 是 | TrainingReportSnapshot 是事实源 |
| 内容质检 | 否 | 是 | 质检结果是 review signal，不自动发布 |

### 3.3 禁止事项

- 禁止让 LLM 在运行时动态读取 `latest` 课程/题库/案例/角色。
- 禁止让 LLM 绕过 `voice_policy_snapshot` 修改 StepFun 实时指令。
- 禁止把 StepFun 对话结果直接当作最终评分；必须进入 evidence -> EvaluationRun。
- 禁止将 PromptTemplate 当成实时 StepFun 主指令权威；实时主指令权威是 `VoiceRuntimePolicyService + VoiceInstructionCompiler + voice_policy_snapshot`。
- 禁止 LLM 直接发布正式课程、题目、案例、角色或 rubric。

---

## 4. 新增领域：`curriculum_practice`

`curriculum_practice` 是内容与训练编排域，不替代现有 `sales_bot`、`agent`、`knowledge`、`evaluation`，而是连接它们。

建议模块边界：

```text
backend/src/curriculum_practice/
  models.py              # 课程、课节、知识点、题库、案例库、角色库、训练模板
  schemas.py             # API schema 与版本快照 schema
  api.py                 # 管理端与训练端 API
  services/
    content_assets.py    # 内容资产生命周期
    publishing.py        # review/publish/archive/rollback
    practice_templates.py# 训练模板编排
    snapshots.py         # runtime snapshot 构建
    learning_path.py     # 学习路径与状态机
    llm_drafts.py        # LLM 草稿生成与校验
```

---

## 5. 内容资产模型

### 5.1 ContentSource

原始内容来源，例如优秀销售视频、讲义、AB 卷、专家文档、真实案例复盘。

关键字段：

- `source_type`: `video | document | transcript | exam_paper | expert_note | customer_case`
- `storage_uri`
- `owner_department_id`
- `created_by`
- `source_metadata`
- `status`: `uploaded | parsed | failed | archived`
- `evidence_hash`

### 5.1.1 内容资产生命周期

基础状态不只使用 `draft -> review -> published -> archived`，实现时应保留更细运维状态：

```text
draft
  -> review_pending
  -> changes_requested
  -> approved
  -> publish_pending
  -> published
  -> superseded
  -> archived

publish_pending -> publish_failed
published -> rollback_pending -> published
```

状态约束：

- `draft`：仅作者和同部门审核人可见。
- `review_pending`：禁止训练运行时读取。
- `changes_requested`：必须记录退回原因和审核人。
- `approved`：表示内容可发布，但还未生效。
- `publish_pending`：等待定时生效或异步发布任务完成。
- `published`：唯一可被 `PracticeTemplate` 绑定和 runtime snapshot 冻结的状态。
- `superseded`：被新版本替代；历史会话仍可通过 snapshot 读取。
- `publish_failed`：必须记录失败原因、trace_id 和可重试动作。

发布门禁：

- schema 校验通过。
- 来源证据引用完整。
- 敏感信息/隐私信息检测通过或已脱敏。
- 重复内容检测通过。
- rubric 可评分性校验通过。
- 至少一名审核人批准；高风险跨部门共享内容需要双人审核。

版本字段：

- `version`
- `content_hash`
- `effective_at`
- `published_by`
- `superseded_by`
- `rollback_from`
- `review_notes`

### 5.2 KnowledgePoint

可教学、可提问、可评分的最小知识单元。

关键字段：

- `title`
- `description`
- `source_refs`
- `canonical_answer`
- `common_misunderstandings`
- `sales_stage`
- `difficulty`
- `tags`
- `version`
- `status`

### 5.3 Curriculum / Lesson

课程与课节结构。

```text
Curriculum
  -> Lesson
    -> KnowledgePoint
    -> LearningMaterial
    -> KnowledgeCheck
```

Lesson 需要包含：

- 学习目标
- 前置知识
- 讲义/视频片段
- 关键话术
- 反例
- 随堂题
- 通过标准

### 5.4 QuestionBank / QuestionItem

题库与题目。

题目类型：

- `single_choice`
- `multiple_choice`
- `short_answer`
- `scenario_response`
- `oral_exam_prompt`
- `roleplay_trigger`

关键字段：

- `question_text`
- `expected_answer`
- `rubric_refs`
- `knowledge_point_refs`
- `difficulty`
- `answer_evidence_refs`
- `scoring_policy`
- `review_notes`
- `version`
- `status`

### 5.5 CaseBank / CaseItem

案例库与客户背景。

关键字段：

- `industry`
- `company_profile`
- `customer_role`
- `pain_points`
- `budget_context`
- `decision_process`
- `objections`
- `hidden_information`
- `success_criteria`
- `allowed_disclosure_policy`
- `conversation_phase_plan`
- `version`
- `status`

### 5.6 RoleBank / RoleProfile

角色库与客户/考官/专家画像。

角色类型：

- `customer`
- `examiner`
- `expert`
- `coach`

关键字段：

- `role_name`
- `persona_traits`
- `communication_style`
- `pressure_level`
- `knowledge_boundary`
- `tool_policy`
- `voice_style_hint`
- `behavior_rules`
- `version`
- `status`

### 5.7 RubricSet

评分规则集。

关键字段：

- `rubric_dimensions`
- `score_scale`
- `evidence_requirements`
- `pass_threshold`
- `disqualifying_patterns`
- `calibration_examples`
- `version`
- `status`

---

## 6. PracticeTemplate 契约

`PracticeTemplate` 定义一次训练如何组装内容、角色、知识库、运行时和评分。

关键字段：

```ts
interface PracticeTemplate {
  id: string;
  name: string;
  department_id: string;
  mode: 'learning' | 'expert_qa' | 'examiner' | 'customer_roleplay' | 'mixed_path';
  curriculum_version_id?: string;
  lesson_version_ids?: string[];
  question_bank_version_id?: string;
  case_bank_version_id?: string;
  role_profile_version_id?: string;
  rubric_set_version_id?: string;
  knowledge_base_ids: string[];
  agent_id: string;
  persona_id: string;
  runtime_profile_id: string;
  voice_mode: 'stepfun_realtime';
  completion_policy: Record<string, unknown>;
  report_policy: Record<string, unknown>;
  status: 'draft' | 'review' | 'published' | 'archived';
}
```

约束：

- `customer_roleplay` 和实时 `examiner` 模式必须绑定 `voice_mode='stepfun_realtime'`。
- `expert_qa` 可以是文本异步模式，走 `KnowledgeAnswerEngine + LLMService`，必须有 citations。
- `mixed_path` 必须声明状态机和每个阶段的通过条件。

---

## 7. Runtime Snapshot 契约

会话创建时必须冻结：

- `practice_template_id/version/hash`
- `curriculum_version_id/hash`
- `lesson_version_ids/hash`
- `question_bank_version_id/hash`
- `case_bank_version_id/hash`
- `role_profile_version_id/hash`
- `rubric_set_version_id/hash`
- `knowledge_base_ids + document version refs`
- `agent_id/persona_id/persona_policy_hash`
- `runtime_profile_id/runtime_policy_hash`
- `voice_policy_snapshot`
- `instruction_contract_hash`
- `model_config_refs`，仅用于非实时 LLM 节点
- `created_by/department_id/trace_id`

运行时读取规则：

1. StepFun 只读取会话冻结的 `voice_policy_snapshot` 和相关 snapshot refs。
2. 训练中途发布新课程或新案例，不影响已开始会话。
3. 报告生成读取同一条 session evidence 和 snapshot refs。
4. 历史报告不因配置发布而重算。

---

## 8. 训练状态机

建议状态：

```text
assigned
  -> preflight_check
  -> ready
  -> learning
  -> knowledge_check
  -> examiner_practice
  -> customer_roleplay
  -> reconnecting
  -> resumable
  -> scoring
  -> report_ready
  -> supervisor_review
  -> retraining_assigned
  -> completed
```

可跳转规则：

- `assigned -> preflight_check`：学员打开训练任务。
- `preflight_check -> ready`：完成课程目标确认、预计时长确认、录音/隐私授权、麦克风权限、网络检测。
- `ready -> learning`：设备和授权满足训练要求。
- `learning -> knowledge_check`：课节学习完成。
- `knowledge_check -> examiner_practice`：客观题达到通过线；开放题可进入人工/LLM 辅助判定。
- `examiner_practice -> customer_roleplay`：口语考官通过或主管放行。
- `examiner_practice/customer_roleplay -> reconnecting`：StepFun 会话中途断连。
- `reconnecting -> resumable`：在重试窗口内恢复连接，保留原 session snapshot。
- `resumable -> examiner_practice/customer_roleplay`：继续原训练并拼接 evidence。
- `reconnecting -> failed/expired`：超过重试次数或恢复窗口，记录 `non_evaluable_reason`，允许重新派发。
- `customer_roleplay -> scoring`：StepFun 会话结束且 evidence 完整。
- `scoring -> report_ready`：EvaluationRun 完成。
- `report_ready -> supervisor_review`：主管需要复核或低分触发。
- `supervisor_review -> retraining_assigned`：主管判定需要复训。
- `supervisor_review -> completed`：主管确认通过。

---

## 9. LLM 使用节点设计

所有 LLM 节点必须纳入模型治理：

- 绑定允许使用的模型白名单。
- 绑定 `CompiledPromptContract` 或等价 prompt contract hash。
- 配置节点级预算、QPS、最大 token、超时、重试次数。
- 支持灰度开关和紧急停用开关。
- 记录 `model_config_id`、prompt hash、input hash、output hash、cost、latency、actor、trace_id。
- 超预算或失败时进入人工处理队列，不得静默降级为无约束生成。

### 9.1 Content Extraction LLM

用途：从视频转写、讲义、AB 卷、专家笔记中提取知识点、题目候选、案例候选、话术候选。

输出：只进入 draft。

校验：

- JSON schema 校验
- 来源引用校验
- 重复检测
- 敏感信息检测
- 人工审核

### 9.2 Content Draft LLM

用途：生成课程讲义草稿、题目草稿、案例草稿、角色画像草稿。

限制：不得直接发布。

### 9.3 Content QA LLM

用途：发现内容缺口、题目歧义、答案不唯一、rubric 不可评分、案例背景不完整。

输出：review signal。

### 9.4 Expert QA LLM

用途：学员围绕课程/产品/销售方法提问。

约束：

- 必须通过 `KnowledgeAnswerEngine` 检索。
- 必须返回 citations。
- 命中不足时明确“不足以回答”，不能自由发挥。

### 9.5 Exam Evaluation LLM

用途：开放题、场景题、口语考官会话后的语义判断建议。

约束：

- 输入必须包含题目版本、标准答案、rubric、学员答案、证据。
- 输出必须是结构化 suggestion。
- 最终分数由 `ScoringRulesetService / EvaluationRun` 归一化。

### 9.6 Report Writer LLM

用途：把 EvaluationRun 结果解释成学员可读报告。

约束：

- 不产生新分数。
- 不引用 snapshot 之外的内容。
- 不得覆盖 `TrainingReportSnapshot` 的事实字段。

报告展示最低要求：

- 总分和分维度得分。
- 每个低分维度的证据引用。
- 扣分原因和对应 rubric 条款。
- 至少一条优秀表达样例和一条需改进表达样例。
- 下一步训练建议。
- 是否触发主管复核或复训派发。
- 低置信度/争议项标记与人工复核入口。

---

## 10. StepFun 实时运行时设计

实时模式包括：

- 客户角色对练
- AI 考官口语追问
- 实时打断、澄清、控场
- 实时转写、实时回合管理

StepFun 输入必须来自冻结快照：

- 角色行为规则
- 案例背景
- 可透露/不可透露信息
- 考官追问策略
- 知识库/工具策略
- runtime guardrail
- voice style hint

StepFun 输出进入 evidence：

- transcript
- turn events
- interruption events
- tool usage events
- retrieval events
- timing metrics
- reconnect/failure events

StepFun 不负责：

- 发布内容资产
- 直接裁定最终分数
- 修改课程/题库/案例/rubric
- 动态读取 latest 内容

### 10.1 StepFun 故障分型与运维 runbook

| 故障类型 | 用户侧表现 | 系统动作 | 运维动作 |
|---|---|---|---|
| `failed_to_start` | 无法开始训练 | 保持 session 未开始，允许重试 | 告警 StepFun/API key/网络配置，生成故障事件 |
| `mid_session_disconnect` | 训练中断 | 进入 `reconnecting`，保留 snapshot 和已收集 evidence | 观察重连率，必要时联系学员重新训练 |
| `timeout` | 长时间无响应 | 结束实时会话并标记超时原因 | 检查 StepFun latency、客户端网络、turn detection 配置 |
| `evidence_incomplete` | 可回放但不可评分 | EvaluationRun 返回 `non_evaluable_reason` | 使用证据检查视图定位缺失 transcript/turn/retrieval |
| `instruction_contract_mismatch` | 指令合同不一致 | 阻断会话开始 | 检查 `voice_policy_snapshot` 与 `instruction_contract_hash` |

故障处理要求：

- 每次故障必须有 `trace_id`、session_id、runtime_profile_hash、instruction_contract_hash。
- 可恢复故障优先续跑原 snapshot，不创建新内容版本。
- 不可恢复故障允许重新派发训练，但必须保留原失败 session 作为审计记录。

---

## 11. 权限、审核与多部门治理

角色：

- `content_author`：创建/编辑 draft。
- `content_reviewer`：审核内容、退回修改。
- `content_publisher`：发布/归档/回滚。
- `training_admin`：配置 PracticeTemplate 和训练任务。
- `supervisor`：查看团队报告、派发复训。
- `learner`：学习与训练。
- `ai_governance_viewer`：只读查看模型、prompt、RAG、评分、证据链。

部门隔离：

- 内容资产默认归属 `department_id`。
- 可通过 `shared_scope` 控制跨部门复用。
- 跨部门发布需要额外审核。
- 学员只能访问被分配的 published training path。

审计：

- 所有 publish/rollback/archive 写入 audit log。
- 所有 LLM draft generation 写入 model、prompt、input hash、output hash、cost、actor。
- 所有 StepFun session 写入 snapshot refs、instruction hash、runtime profile hash。

### 11.1 对象级权限矩阵

| 对象 | create | read | update | review | publish | rollback | share | export |
|---|---|---|---|---|---|---|---|---|
| 内容资产 | author/admin | owner dept/reviewer | author | reviewer | publisher | publisher | publisher/admin | admin |
| PracticeTemplate | training_admin | owner dept | training_admin | reviewer | publisher | publisher | training_admin | admin |
| Runtime 配置 | admin | admin/governance | admin | admin | admin | admin | 不允许跨部门直接共享 | admin |
| LLM 模型配置 | admin | admin/governance | admin | admin | admin | admin | 不允许 | admin |
| 会话证据 | learner/supervisor/admin 按范围 | learner/supervisor/admin 按范围 | 不允许 | supervisor | 不适用 | 不适用 | 不允许 | admin 审批 |
| 报告 | learner/supervisor/admin 按范围 | learner/supervisor/admin 按范围 | 不允许 | supervisor | 不适用 | 不适用 | supervisor/admin | admin 审批 |

### 11.2 隐私、共享与留存

- 训练开始前必须展示录音、转写、评分和主管可见范围告知。
- 学员默认可见自己的报告和回放；主管默认可见团队成员报告摘要和必要证据片段；管理员可按审计权限查看完整证据。
- 跨部门共享内容资产必须脱敏客户名称、报价、联系人、真实项目编号等敏感字段。
- 报告导出必须记录 actor、时间、范围和导出原因。
- 录音、转写、报告、LLM 调用日志需要配置保留期限；到期后归档或脱敏删除。
- 历史会话使用旧 snapshot 展示，不因新内容发布被重算。

---

## 12. 失败降级、成本与可观测性

### 12.1 LLM 失败策略

- 内容草稿生成失败：保留任务为 `draft_generation_failed`，允许人工手写。
- 专家问答检索不足：返回证据不足，不调用或不信任生成答案。
- 开放题判定失败：进入人工复核队列。
- 报告解释失败：展示结构化 EvaluationRun 基础报告。

### 12.2 StepFun 失败策略

- 建连失败：会话保持 `created/failed_to_start`，可重试。
- 中途断连：记录 reconnect event。
- evidence 不完整：EvaluationRun 返回 `non_evaluable_reason`，不得伪分。

### 12.3 成本与限流

- LLM 按节点配置模型、预算、QPS、最大 token。
- 大批量内容抽取进入后台队列。
- 同一来源内容重复生成需走 hash 去重。
- 报告生成可异步，避免阻塞训练结束。

### 12.4 可观测性

必须能按 session/report 追溯：

- 内容版本
- StepFun instruction hash
- Persona policy hash
- Knowledge citations
- LLM model config
- Prompt contract hash
- EvaluationRun id
- TrainingReportSnapshot id
- 成本、耗时、失败原因

### 12.5 会话证据检查视图/API

运维和治理侧需要一个只读证据检查入口，用于定位“为什么不能评分/不能出报告”。

最小字段：

- session_id、learner_id、department_id、practice_template_version。
- StepFun connection timeline。
- transcript 完整度。
- turn events 数量与缺失区间。
- interruption events。
- retrieval/tool events。
- evidence completeness score。
- `non_evaluable_reason` 分类。
- EvaluationRun id 与 TrainingReportSnapshot id。
- 关联 trace_id 和错误日志。

`non_evaluable_reason` 至少包括：

- `missing_transcript`
- `insufficient_turns`
- `runtime_disconnected`
- `snapshot_mismatch`
- `rubric_unavailable`
- `knowledge_evidence_missing`
- `llm_evaluation_failed`

### 12.6 运营指标与告警

最小指标集：

- 课程完成率。
- 训练开始成功率。
- StepFun 重连率。
- StepFun 会话超时率。
- evidence 完整率。
- EvaluationRun 成功率。
- 报告生成 SLA。
- 人工复核率。
- 内容发布失败率。
- 内容回滚率。
- LLM 成本/节点/部门。
- LLM 失败率和超预算次数。

告警对象：

- StepFun 连接失败或重连率异常 -> 技术运维。
- 内容发布失败或回滚率异常 -> 内容运营负责人。
- LLM 成本超预算 -> AI 治理/管理员。
- evidence 完整率下降 -> 训练平台负责人。

---

## 13. 实施顺序建议

虽然目标是全量完整系统，工程落地仍应按可验证切片推进：

1. 建立 `curriculum_practice` 内容资产模型和只读 API。
2. 接入 draft/review/published/archive 生命周期和 audit log。
3. 建立 `PracticeTemplate` 与 Runtime Snapshot 构建服务。
4. 将 published snapshot 接入现有 `PracticeSession` 创建流程。
5. 为客户对练和口语考官接入 StepFun runtime snapshot。
6. 建立 LLM draft generation 节点，先只生成 draft。
7. 建立 Expert QA 节点，强制 citations。
8. 建立开放题/场景题 EvaluationRun suggestion 节点。
9. 建立报告解释节点，输出 `TrainingReportSnapshot` 旁路解释。
10. 建立主管复核、复训派发和内容迭代闭环。

---

## 14. 验收标准

架构落地后必须满足：

- 任意一次实时对话都能追溯到 StepFun 使用的 `voice_policy_snapshot`。
- 任意一次 LLM 输出都能追溯到模型配置、prompt contract、输入 hash、输出 hash、校验结果。
- 任意一份报告都能追溯到 session evidence、rubric 版本、内容资产版本和 EvaluationRun。
- 新发布的课程/题库/案例/角色不影响历史会话和历史报告。
- LLM 生成的内容在人工发布前不会被训练运行时读取。
- evidence 不足时系统返回不可评估原因，不生成伪分。
- 部门可以自维护内容，但发布、共享、回滚都有权限与审计。
- 学员首次进入训练前必须完成目标确认、设备预检和隐私授权。
- StepFun 中断后必须有明确恢复、终止或重新派发路径。
- 报告必须提供证据、扣分原因、下一步建议和复训状态。
- 内容发布必须经过 schema、证据、敏感信息、审核与审计门禁。
- LLM 节点必须有模型白名单、预算、限流、灰度和紧急停用机制。
- 运维必须能通过证据检查视图定位不可评分原因。
- 录音、转写、报告和 LLM 调用日志必须有可配置留存与脱敏策略。

---

## 15. 最终架构原则

1. **StepFun 管实时对话，LLM 管受控智能处理。**
2. **内容资产是事实源，LLM 输出只是草稿或建议。**
3. **运行时永远读 snapshot，不读 latest。**
4. **评分由 rubric 和 EvaluationRun 裁决，LLM 只能辅助解释和建议。**
5. **报告是快照，不是临时生成的自由文本。**
6. **所有配置变更必须可审核、可回滚、可追溯。**
7. **先建立深模块边界，再扩展训练形态。**
