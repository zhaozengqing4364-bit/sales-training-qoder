# 课程化销售训练系统详细架构规格：StepFun 实时对话 + 受控 LLM 智能节点

> 状态：Detailed Architecture Spec  
> 日期：2026-05-11  
> 来源：细化 `docs/plans/2026-05-11-curriculum-practice-stepfun-llm-architecture-draft.md`  
> 关系：本规格建立在 PRD #23 已形成的 `TrainingTask / ConfigBundle / ConfigVersion / EvaluationRun / TrainingReportSnapshot / Supervisor / AI Governance / StepFun-only runtime` 底座之上。  
> 核心结论：新增 `curriculum_practice` 内容与训练编排域；内容资产是事实源，运行时会话快照是执行事实，Evidence/Evaluation/Report Snapshot 是评价事实；StepFun 只管实时对话，LLM 只作为受控非实时智能节点。
> Oracle 审查修订：本版本已按深度审查收敛 PRD #23 不变量：不改变 `TrainingTask.status`，不改变 `PracticeSession.status` DB 状态集，不一次性扩大 ConfigBundle 生命周期，不直接扩展 `User.role`，Phase 1 拆为 tracer-bullet。

---

## 1. 架构目标、非目标与边界

### 1.1 目标

本规格把现有销售训练系统升级为课程化、资产化、版本化、可审核、可复训、可追溯的训练平台。系统必须支持：

1. 课程、课节、知识点、题库、案例库、角色库、评分标准等训练资产的版本化治理。
2. `PracticeTemplate` 作为一次训练如何组装内容、角色、知识库、运行时和评分规则的权威编排入口。
3. 会话创建时冻结所有运行依赖，确保运行时永远读 snapshot，不读 latest。
4. StepFun 只负责实时语音/实时对话运行，不承担正式内容生产、内容发布或最终评分裁决。
5. LLM 只作为受控节点用于内容草稿、结构化抽取、质检、专家问答、开放题语义建议、报告解释。
6. 任意报告都能追溯到会话证据、内容资产版本、rubric 版本、模型配置、prompt contract 和 EvaluationRun。
7. 部门能够自维护内容，但创建、审核、发布、共享、回滚、导出都必须有权限与审计。

### 1.2 非目标

本规格不重做以下已由 PRD #23 或现有系统覆盖的底座能力：

- 不重做 StepFun-only Sales runtime，不恢复 legacy Sales handler。
- 不替代已有 `TrainingTask` 任务主线；只在其上挂接课程化训练入口。
- 不替代已有 `PracticeSession` 运行事实锚点；只扩展其课程化 snapshot 引用。
- 不替代 `EvaluationRun` 和 `TrainingReportSnapshot`；只补充内容资产和 rubric 版本引用。
- 不把 `RetrainingTask` 合并进 `TrainingTask`；继续保留主管复训的独立生命周期。
- 不一次性迁移所有旧配置页面；旧 Agent、Persona、Knowledge、Scoring、Prompt 通过适配器逐步接入。
- 不改变 Presentation Training Flow 既有行为；PPT 训练只通过共享生命周期、证据、评估和报告契约薄适配。
- 不修改现有 `PracticeSession.status` 的数据库约束；课程化预检、重连、阶段状态进入 `runtime_state` 或独立阶段运行记录。

### 1.3 与 PRD #23 的关系

PRD #23 解决训练运营平台底座：TrainingTask、ConfigBundle/ConfigVersion、EvaluationRun 配置绑定、ReportSnapshot 谱系、Supervisor 管理中心、AI Governance、E2E 和 Release Gate。

本规格解决 PRD #23 之后的新增课程化域：

```text
PRD #23 底座：TrainingTask → PracticeSession → Evidence → EvaluationRun → TrainingReportSnapshot → RetrainingTask

本规格新增：Content Assets → PracticeTemplate → Runtime Snapshot → StepFun / LLM Nodes → Evidence / Evaluation / Report
```

---

## 2. 总体分层

```text
体验层
  ├─ 学员：课程任务、预检、学习、知识检查、口语考官、客户对练、报告、复训
  ├─ 主管：团队完成度、薄弱点、报告复核、复训派发
  └─ 管理员：内容资产、训练模板、审核发布、权限、审计、AI 治理

应用层
  ├─ curriculum_practice：内容资产、训练模板、快照、学习路径、内容发布
  ├─ common：TrainingTask、PracticeSession、SessionEvidence、ConfigBundle、AI Governance
  ├─ sales_bot：StepFun 实时销售对练、客户模拟、语音策略
  ├─ evaluation：EvaluationRun、ScoringRuleset/Rubric adapter、TrainingReportSnapshot
  ├─ supervisor：SupervisorReview、RetrainingTask、校准与复训闭环
  └─ admin：RBAC、Config Center、审计、模型配置

AI 能力层
  ├─ StepFun realtime：实时语音、实时对话、实时打断、实时转写
  └─ Controlled LLM：内容草稿、内容质检、专家问答、语义建议、报告解释

治理层
  ├─ Content lifecycle：draft / review / approved / published / superseded / archived
  ├─ Config lifecycle：draft / validated / published / rolled_back / archived
  ├─ Audit log：内容发布、配置发布、LLM 调用、报告导出、权限变更
  └─ Observability：trace、成本、失败、证据完整性、运行时故障
```

---

## 3. `curriculum_practice` 模块边界

### 3.1 后端目录建议

```text
backend/src/curriculum_practice/
  __init__.py
  models.py
  schemas.py
  api.py
  services/
    content_assets.py
    publishing.py
    publishing_gates.py
    practice_templates.py
    snapshots.py
    learning_path.py
    llm_drafts.py
    evidence_lineage.py
    permissions.py
```

### 3.2 职责

`curriculum_practice` 只负责内容资产与训练编排，不直接执行实时对话、不直接评分、不直接生成最终报告。

它负责：

- 定义课程化训练资产。
- 管理资产生命周期与版本。
- 生成训练模板。
- 构建会话 runtime snapshot。
- 声明训练阶段和通过条件。
- 为 EvaluationRun 和 TrainingReportSnapshot 提供内容版本引用。
- 为 LLM draft / suggestion / explanation 提供输入约束和输出校验。

它不负责：

- StepFun WebSocket 协议细节。
- Scoring engine 内部算法。
- 主管复训任务生命周期。
- ConfigBundle 的通用配置发布生命周期。
- KnowledgeAnswerEngine 的检索实现。

### 3.3 Deep module seam

外部模块不得直接拼接课程、题目、案例、角色和 rubric JSON。`curriculum_practice` 对外只暴露稳定深模块接口：

```text
PracticeTemplateService.publish_template(template_id, actor_id) -> PublishedTemplateRef
PracticeTemplateService.resolve_for_task(training_task_id) -> PublishedTemplateRef
RuntimeSnapshotService.build_for_session(template_ref, training_task_ref, actor_id) -> CurriculumRuntimeSnapshot
LearningPathService.advance(run_id, event) -> StageTransitionResult
```

其中 `RuntimeSnapshotService.build_for_session()` 是进入 StepFun、EvaluationRun 和 TrainingReportSnapshot 的唯一课程化 snapshot 生成入口。

### 3.4 统一版本引用结构

所有 `*_ref`、`*_refs` 使用统一结构，不允许各模块自定义 JSON：

```json
{
  "asset_type": "curriculum|lesson|knowledge_point|question_bank|question_item|case_item|role_profile|rubric_set|scoring_ruleset|knowledge_base|prompt_contract|model_config",
  "asset_id": "uuid-string",
  "version": 1,
  "hash": "sha256:...",
  "snapshot_label": "published|superseded|legacy_unversioned"
}
```

`content_hash` 统一按规范化 JSON 计算：字段按 key 排序，排除 `created_at / updated_at / published_at / actor_id / trace_id` 等审计字段，使用 SHA-256。

---

## 4. 领域模型规格

### 4.1 通用建模规则

所有内容资产模型遵循以下规则：

- 主键使用 `String(36)` UUID。
- 所有可发布实体包含 `version`、`content_hash`、`status`、`created_by`、`updated_by`、`published_by`、`published_at`、`created_at`、`updated_at`。
- 所有可被运行时引用的实体必须支持 `published` 版本读取。
- 运行时只允许引用 `published` 版本。
- 版本发布后不可原地修改；修改必须创建新版本。
- 旧版本被新版本替代后进入 `superseded`，历史会话仍可读取 snapshot。
- 每个资产默认属于 `department_id`，跨部门复用通过 `shared_scope` 控制。

### 4.2 ContentSource

原始内容来源，例如优秀销售视频、讲义、AB 卷、专家文档、真实案例复盘。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 来源 ID |
| `source_type` | enum | `video / document / transcript / exam_paper / expert_note / customer_case` |
| `storage_uri` | string | 对象存储或内部文件 URI |
| `owner_department_id` | UUID string | 归属部门 |
| `created_by` | UUID string | 上传人 |
| `source_metadata` | JSON | 文件名、大小、时长、页数、语言、业务标签 |
| `status` | enum | `uploaded / parsing / parsed / parse_failed / archived` |
| `evidence_hash` | string | 来源内容哈希 |
| `parse_error` | string nullable | 解析失败原因 |
| `retention_policy_id` | UUID string nullable | 留存策略 |

约束：

- `storage_uri + evidence_hash` 唯一，避免重复上传。
- 解析失败不得自动删除原始文件。
- 来源内容用于生成 draft，但不会直接成为 published 训练资产。

### 4.3 KnowledgePoint

可教学、可提问、可评分的最小知识单元。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 知识点 ID |
| `title` | string | 标题 |
| `description` | text | 说明 |
| `canonical_answer` | text | 标准解释 |
| `common_misunderstandings` | JSON array | 常见误区 |
| `source_refs` | JSON array | ContentSource 引用与证据片段 |
| `sales_stage` | enum/string | 销售阶段 |
| `difficulty` | enum | `beginner / intermediate / advanced` |
| `tags` | JSON array | 标签 |
| `department_id` | UUID string | 归属部门 |
| `version` | int | 版本号 |
| `content_hash` | string | 内容哈希 |
| `status` | enum | 内容生命周期状态 |

约束：

- `published` 知识点必须有至少一个有效 `source_ref`。
- `canonical_answer` 不允许由 LLM 直接发布；LLM 只能生成 draft。
- 知识点可以被 Lesson、QuestionItem、RubricDimension 引用。

### 4.4 Curriculum / Lesson

课程和课节结构。

```text
Curriculum
  └─ Lesson
       ├─ KnowledgePoint refs
       ├─ LearningMaterial refs
       ├─ KnowledgeCheck refs
       └─ PracticeTemplate refs
```

Curriculum 关键字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 课程 ID |
| `name` | string | 课程名 |
| `description` | text | 课程说明 |
| `target_audience` | JSON | 适用岗位、职级、部门 |
| `learning_objectives` | JSON array | 学习目标 |
| `department_id` | UUID string | 归属部门 |
| `version` | int | 版本号 |
| `status` | enum | 生命周期状态 |

Lesson 关键字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 课节 ID |
| `curriculum_id` | FK | 所属课程 |
| `title` | string | 课节标题 |
| `sequence` | int | 课节顺序 |
| `learning_objectives` | JSON array | 课节目标 |
| `prerequisite_refs` | JSON array | 前置知识点或课节 |
| `material_refs` | JSON array | 讲义、视频、文档引用 |
| `knowledge_point_refs` | JSON array | 知识点版本引用 |
| `key_talk_tracks` | JSON array | 关键话术 |
| `negative_examples` | JSON array | 反例 |
| `pass_criteria` | JSON | 通过标准 |
| `estimated_minutes` | int | 预计时长 |
| `version` | int | 版本号 |
| `status` | enum | 生命周期状态 |

约束：

- 已发布 Lesson 只能引用已发布 KnowledgePoint 或冻结的 KnowledgePoint snapshot。
- 课程发布时必须校验所有 Lesson 的通过标准和引用完整性。
- Lesson 版本变更不自动重算历史训练结果。

### 4.5 QuestionBank / QuestionItem

题库与题目。题库是组织容器，题目是可评分实体。

QuestionBank 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 题库 ID |
| `name` | string | 题库名 |
| `description` | text | 题库说明 |
| `department_id` | UUID string | 归属部门 |
| `version` | int | 版本号 |
| `status` | enum | 生命周期状态 |

QuestionItem 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 题目 ID |
| `question_bank_id` | FK | 所属题库 |
| `question_type` | enum | `single_choice / multiple_choice / short_answer / scenario_response / oral_exam_prompt / roleplay_trigger` |
| `question_text` | text | 题干 |
| `expected_answer` | JSON/text | 标准答案或评分参考 |
| `choices` | JSON nullable | 客观题选项 |
| `rubric_refs` | JSON array | RubricSet 或 RubricDimension 版本引用 |
| `knowledge_point_refs` | JSON array | 知识点版本引用 |
| `difficulty` | enum | 难度 |
| `answer_evidence_refs` | JSON array | 答案证据来源 |
| `scoring_policy` | JSON | 判分策略 |
| `review_notes` | text nullable | 审核说明 |
| `version` | int | 版本号 |
| `status` | enum | 生命周期状态 |

约束：

- 开放题、场景题、口语题必须绑定 rubric。
- 客观题必须有确定答案和解释。
- 题目发布前必须通过答案唯一性、rubric 可评分性和证据引用校验。
- `roleplay_trigger` 不直接驱动 StepFun；必须经过 PracticeTemplate 编排后进入 runtime snapshot。

### 4.6 CaseBank / CaseItem

案例库与客户背景。

CaseItem 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 案例 ID |
| `case_bank_id` | FK | 所属案例库 |
| `industry` | string | 行业 |
| `company_profile` | JSON | 公司画像 |
| `customer_role` | string | 客户角色 |
| `pain_points` | JSON array | 痛点 |
| `budget_context` | JSON | 预算与采购条件 |
| `decision_process` | JSON | 决策链 |
| `objections` | JSON array | 常见异议 |
| `hidden_information` | JSON | 训练中可逐步透露的信息 |
| `success_criteria` | JSON | 成功标准 |
| `allowed_disclosure_policy` | JSON | 可透露/不可透露规则 |
| `conversation_phase_plan` | JSON | 对话阶段规划 |
| `source_refs` | JSON array | 来源证据 |
| `version` | int | 版本号 |
| `status` | enum | 生命周期状态 |

约束：

- `hidden_information` 必须有披露策略，禁止在 StepFun 初始指令中一次性暴露全部隐藏信息。
- 跨部门共享前必须脱敏客户名称、报价、联系人、真实项目编号。
- 发布前必须通过敏感信息检测。

### 4.7 RoleProfile

角色画像，承载客户、考官、专家、教练的行为规则。实现时优先复用现有 Persona 能力，通过 RoleProfile 管理课程化训练所需的版本化角色资产。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 角色 ID |
| `role_type` | enum | `customer / examiner / expert / coach` |
| `role_name` | string | 角色名 |
| `persona_ref` | UUID nullable | 现有 Persona 引用 |
| `persona_traits` | JSON | 性格与行为特征 |
| `communication_style` | JSON | 交流风格 |
| `pressure_level` | enum/int | 压力等级 |
| `knowledge_boundary` | JSON | 知识边界 |
| `tool_policy` | JSON | 工具使用规则 |
| `voice_style_hint` | JSON | 语音风格提示 |
| `behavior_rules` | JSON array | 行为规则 |
| `version` | int | 版本号 |
| `status` | enum | 生命周期状态 |

约束：

- 实时角色必须能编译进入 `voice_policy_snapshot`。
- 专家角色用于 Expert QA 时必须绑定知识库范围。
- 角色画像发布后不可被训练中会话动态更新。

### 4.8 RubricSet / RubricDimension

评分标准集是评价事实链的一等实体。现有 `ScoringRuleset` 可以通过 adapter 接入，但课程化训练需要更细的 rubric 维度。

RubricSet 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | RubricSet ID |
| `name` | string | 名称 |
| `description` | text | 说明 |
| `score_scale` | JSON | 分制 |
| `pass_threshold` | numeric | 通过线 |
| `disqualifying_patterns` | JSON array | 一票否决项 |
| `calibration_examples` | JSON array | 校准样例 |
| `scoring_ruleset_ref` | UUID nullable | 现有 ScoringRuleset 引用 |
| `version` | int | 版本号 |
| `status` | enum | 生命周期状态 |

RubricDimension 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 维度 ID |
| `rubric_set_id` | FK | 所属 RubricSet |
| `name` | string | 维度名 |
| `description` | text | 维度说明 |
| `weight` | numeric | 权重 |
| `criteria` | JSON array | 分档标准 |
| `evidence_requirements` | JSON | 证据要求 |
| `min_evidence_quotes` | int | 最小证据引用数 |
| `llm_assist_policy` | JSON | LLM 辅助判定策略 |

约束：

- 每个开放题或场景题评分必须引用具体 RubricSet 版本。
- LLM 只能输出 rubric 维度下的 suggestion，不直接生成最终分。
- 高分或通过结论必须附带证据引用。

---

## 5. PracticeTemplate 契约

### 5.1 定义

`PracticeTemplate` 定义一次训练如何组装内容、角色、知识库、运行时和评分。它是课程化训练进入运行时的唯一编排入口。

### 5.2 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 模板 ID |
| `name` | string | 模板名 |
| `description` | text | 模板说明 |
| `department_id` | UUID string | 归属部门 |
| `mode` | enum | `learning / expert_qa / examiner / customer_roleplay / mixed_path` |
| `scenario_type` | enum | `sales / presentation`；第一阶段课程化实时对练以 `sales` 为主，`presentation` 只允许薄适配 |
| `curriculum_version_ref` | JSON nullable | 课程版本引用 |
| `lesson_version_refs` | JSON array | 课节版本引用 |
| `question_bank_version_ref` | JSON nullable | 题库版本引用 |
| `case_item_version_ref` | JSON nullable | 案例版本引用 |
| `role_profile_version_ref` | JSON nullable | 角色版本引用 |
| `rubric_set_version_ref` | JSON nullable | rubric 版本引用 |
| `knowledge_base_refs` | JSON array | 知识库与文档版本引用 |
| `agent_id` | UUID string | 现有 Agent 引用 |
| `persona_id` | UUID string | 现有 Persona 引用 |
| `runtime_profile_id` | UUID string | VoiceRuntimeProfile 引用 |
| `voice_mode` | enum | 第一阶段固定 `stepfun_realtime` |
| `stage_plan` | JSON | 训练阶段和跳转规则 |
| `completion_policy` | JSON | 完成条件 |
| `report_policy` | JSON | 报告策略 |
| `llm_node_policy_refs` | JSON array | 非实时 LLM 节点配置引用 |
| `version` | int | 版本号 |
| `content_hash` | string | 模板哈希 |
| `status` | enum | 生命周期状态 |

### 5.3 模式约束

| 模式 | 必填引用 | 运行时 |
|---|---|---|
| `learning` | curriculum/lesson | 文本/页面学习，可无 StepFun |
| `expert_qa` | knowledge_base_refs、expert role | KnowledgeAnswerEngine + LLM，必须 citations |
| `examiner` | question_bank、rubric、examiner role | 口语考官走 StepFun，异步语义建议走 LLM |
| `customer_roleplay` | case、customer role、rubric、runtime profile | StepFun realtime |
| `mixed_path` | stage_plan 中声明每阶段依赖 | 分阶段执行 |

### 5.4 发布门禁

PracticeTemplate 发布前必须检查：

- 所有引用资产均为 `published`。
- `customer_roleplay` 与实时 `examiner` 必须绑定 `voice_mode=stepfun_realtime`。
- Expert QA 必须绑定知识库引用和 citations 策略。
- 所有开放题/场景题必须绑定 RubricSet。
- `stage_plan` 不允许死循环，所有终态必须可达。
- `completion_policy` 必须声明最低完成条件。
- `report_policy` 不允许覆盖 EvaluationRun 事实字段。

### 5.5 与现有 TrainingTask / PracticeSession 的兼容

- 新 TrainingTask 可选绑定 `practice_template_id`，但 `TrainingTask.status` 仍保持 PRD #23 约束的 `assigned / in_progress / completed / expired / cancelled`。
- 创建 PracticeSession 时可读取 PracticeTemplate 构建 `curriculum_snapshot`，但不改变 `PracticeSession.status` 的现有数据库状态集。
- `scenario_type=sales` 的模板可以驱动 StepFun 客户对练或口语考官。
- `scenario_type=presentation` 的模板不得改变现有 PPT 上传、WebSocket 和报告行为；只允许在报告 lineage 中补充模板引用。

---

## 6. 内容生命周期与发布门禁

### 6.1 状态机

```text
draft
  -> review_pending
  -> changes_requested
  -> review_pending
  -> approved
  -> publish_pending
  -> published
  -> superseded
  -> archived

publish_pending -> publish_failed
published -> rollback_pending -> published
```

### 6.2 状态语义

| 状态 | 语义 | 运行时可读 |
|---|---|---:|
| `draft` | 作者编辑中 | 否 |
| `review_pending` | 等待审核 | 否 |
| `changes_requested` | 审核退回 | 否 |
| `approved` | 审核通过，等待发布 | 否 |
| `publish_pending` | 发布任务执行中 | 否 |
| `publish_failed` | 发布失败，可重试 | 否 |
| `published` | 已发布，可绑定模板和运行时快照 | 是 |
| `superseded` | 被新版本替代，历史可读 | 仅历史 snapshot |
| `archived` | 归档，不可新绑定 | 仅历史 snapshot |

### 6.3 发布门禁服务

新增 `PublishingGateService`，每个门禁返回结构化结果：

```text
GateResult:
  gate_name: string
  status: passed | failed | warning
  reason_code: string
  message: string
  evidence_refs: array
  trace_id: string
```

默认门禁：

1. Schema 校验。
2. 来源证据引用校验。
3. 敏感信息与隐私检测。
4. 重复内容检测。
5. Rubric 可评分性校验。
6. 跨部门共享脱敏校验。
7. 审核人数校验。
8. 运行时引用完整性校验。

### 6.4 审计

所有 create/update/review/approve/publish/rollback/archive/share/export 写入审计日志。审计事件包含：

- `actor_id`
- `action`
- `asset_type`
- `asset_id`
- `version_before`
- `version_after`
- `before_snapshot`
- `after_snapshot`
- `reason`
- `trace_id`
- `created_at`

---

## 7. 三层状态机

草案中的 12 个状态不能直接塞进 `TrainingTask.status` 或 `PracticeSession.status`。系统采用三层状态机。

### 7.1 任务级：TrainingTask

沿用 PRD #23 约束：

```text
assigned -> in_progress -> completed
assigned -> expired
assigned -> cancelled
in_progress -> cancelled
```

课程化新增字段建议只限调度引用和摘要，不存放运行态：

- `practice_template_id`
- `latest_session_id`
- `completion_summary`

不得加入 `current_stage_key`、`preflight_status` 这类运行态字段；这些属于 StageRun 或 PracticeSession runtime_state。

### 7.2 会话级：PracticeSession

继续表达运行事实，但不得改变现有 `PracticeSession.status` DB 状态集。现有状态保持：

```text
preparing -> in_progress -> paused -> in_progress -> scoring -> completed
```

新增字段建议：

- `practice_template_id`
- `curriculum_snapshot`
- `runtime_state`
- `preflight_snapshot`
- `reconnect_policy_snapshot`
- `non_evaluable_reason`

`runtime_state` 保存课程化运行状态，不参与现有 `PracticeSession.status` check constraint：

```json
{
  "preflight_status": "not_started|passed|failed|expired",
  "stage_status": "not_started|running|blocked|completed|failed",
  "current_stage_key": "customer_roleplay",
  "reconnect_state": "connected|reconnecting|resumable|expired",
  "recovery_window_expires_at": "2026-05-11T10:30:00Z",
  "non_evaluable_reason": null
}
```

如果未来确需新增 `PracticeSession.status` 枚举，必须另开 ADR 修改平台级生命周期和 DB constraint。

### 7.3 阶段级：LearningPath / StagePlan

阶段级由 PracticeTemplate 的 `stage_plan` 驱动：

```text
learning -> knowledge_check -> examiner_practice -> customer_roleplay -> scoring -> report_ready
```

每个阶段包含：

- `stage_key`
- `stage_type`
- `entry_conditions`
- `completion_conditions`
- `failure_policy`
- `runtime_mode`
- `evidence_requirements`
- `next_stage_rules`

阶段运行态存放在 `LearningPathRun` 或 `PracticeSession.runtime_state`。第一阶段优先使用 `runtime_state` JSON，避免新增复杂表；当需要多课节并行、阶段重试历史、主管复核历史时，再升级为独立 `LearningPathRun` 表。

### 7.4 预检

`preflight_check` 必须覆盖：

- 训练目标确认。
- 预计时长确认。
- 录音、转写、评分、主管可见范围告知。
- 麦克风权限。
- 网络检测。
- StepFun 连接可用性检测。
- 失败恢复入口。

预检结果冻结到 `preflight_snapshot`，用于审计和问题排查。

---

## 8. Runtime Snapshot 契约

### 8.1 快照内容

会话创建时必须冻结：

| 类别 | 内容 |
|---|---|
| Template | `practice_template_id/version/hash` |
| Curriculum | `curriculum_version_ref`、`lesson_version_refs`、`knowledge_point_refs` |
| Question | `question_bank_version_ref`、被抽取题目版本 |
| Case | `case_item_version_ref`、案例披露策略 |
| Role | `role_profile_version_ref`、行为规则、voice hint |
| Rubric | `rubric_set_version_ref`、维度、证据要求 |
| Knowledge | `knowledge_base_refs`、文档版本引用 |
| Runtime | `agent_id`、`persona_id`、`runtime_profile_id`、`voice_policy_snapshot`、`instruction_contract_hash` |
| LLM | 非实时节点的 `model_config_ref`、`prompt_contract_hash`、预算策略 |
| Governance | `department_id`、`created_by`、`trace_id` |

### 8.1.1 Runtime Snapshot JSON schema

`curriculum_snapshot` 必须使用统一 schema，存放在 `PracticeSession.curriculum_snapshot` 或等价 JSON 字段中：

```json
{
  "schema_version": 1,
  "snapshot_hash": "sha256:...",
  "created_at": "2026-05-11T10:00:00Z",
  "trace_id": "trace-id",
  "training_task": {
    "id": "uuid-string",
    "scenario_type": "sales"
  },
  "practice_template": {
    "asset_type": "practice_template",
    "asset_id": "uuid-string",
    "version": 1,
    "hash": "sha256:...",
    "snapshot_label": "published"
  },
  "content_assets": [
    {
      "asset_type": "lesson",
      "asset_id": "uuid-string",
      "version": 1,
      "hash": "sha256:...",
      "snapshot_label": "published"
    }
  ],
  "rubric": {
    "asset_type": "rubric_set",
    "asset_id": "uuid-string",
    "version": 1,
    "hash": "sha256:...",
    "snapshot_label": "published"
  },
  "runtime": {
    "agent_id": "uuid-string",
    "persona_id": "uuid-string",
    "runtime_profile_id": "uuid-string",
    "voice_policy_snapshot_hash": "sha256:...",
    "instruction_contract_hash": "sha256:..."
  },
  "llm_nodes": [
    {
      "node_key": "expert_qa",
      "model_config_id": "uuid-string",
      "prompt_contract_hash": "sha256:...",
      "budget_policy_ref": "policy-key"
    }
  ]
}
```

约束：

- `snapshot_hash` 按规范化 JSON 计算，排除 `snapshot_hash` 自身。
- 第一阶段建议将 snapshot 控制在 256KB 以内；大文本内容只存版本引用和 hash，不直接内嵌全文。
- 构建失败返回明确错误码：`template_unpublished / asset_unpublished / asset_hash_mismatch / rubric_missing / voice_policy_unavailable / prompt_contract_missing`。
- snapshot 构建发生在 `PracticeSessionCreateService` 创建会话过程中；如果通过 `TrainingTask.start-session` 进入，则先解析 PracticeTemplate，再创建 PracticeSession。

### 8.2 运行时读取规则

1. StepFun 只读取冻结后的 `voice_policy_snapshot` 和 curriculum snapshot 中允许进入实时指令的字段。
2. 训练中途发布新课程、新案例、新角色、新 rubric，不影响已开始会话。
3. EvaluationRun 读取同一条 session evidence 和 curriculum snapshot。
4. TrainingReportSnapshot 固化 EvaluationRun 输出、内容资产版本、rubric 版本和配置版本。
5. 历史报告不因内容或配置发布而重算。

### 8.3 Snapshot mismatch

如果会话中的 `instruction_contract_hash`、`voice_policy_snapshot` 或内容版本引用不一致：

- 阻止会话开始，记录 `snapshot_mismatch`。
- 如果会话已开始，终止评分并返回 `non_evaluable_reason=snapshot_mismatch`。
- 保留原会话用于审计，不自动删除。

---

## 9. StepFun 与 LLM 权威边界

### 9.1 StepFun 负责

- 客户角色实时语音对练。
- 口语考官实时追问。
- 实时打断、澄清、控场。
- 实时转写和回合事件。
- 实时工具调用事件记录。

### 9.2 StepFun 不负责

- 发布课程、题目、案例、角色、rubric。
- 动态读取 latest 内容。
- 修改运行时快照。
- 直接裁定最终分数。
- 生成不可审计的报告结论。

### 9.3 LLM 负责

- 内容抽取 draft。
- 题目、案例、角色草稿。
- 内容质检 review signal。
- Expert QA 回答，必须引用 citations。
- 开放题/场景题语义判断 suggestion。
- 报告解释 report_explanation。

### 9.4 LLM 不负责

- 直接发布正式内容。
- 覆盖 EvaluationRun 最终分。
- 绕过 `CompiledPromptContract` 自由生成。
- 在实时对话中改写 StepFun 指令。
- 引用 snapshot 之外的内容解释历史报告。

---

## 10. LLM 节点治理

### 10.1 节点类型

| 节点 | 输出类型 | 是否可进入正式事实 |
|---|---|---:|
| Content Extraction LLM | `draft` | 否 |
| Content Draft LLM | `draft` | 否 |
| Content QA LLM | `review_signal` | 否 |
| Expert QA LLM | `answer_with_citations` | 否，作为问答记录 |
| Exam Evaluation LLM | `suggestion` | 否，需 EvaluationRun 归一化 |
| Report Writer LLM | `report_explanation` | 否，只解释 Snapshot 事实 |

### 10.2 调用记录

每次 LLM 调用必须记录：

- `llm_node_key`
- `model_config_id`
- `prompt_contract_hash`
- `input_hash`
- `output_hash`
- `schema_validation_status`
- `evidence_validation_status`
- `cost`
- `latency_ms`
- `actor_id`
- `department_id`
- `trace_id`
- `created_at`

LLM 调用记录可以先进入 AI Governance 既有读模型或新增 `LLMCallLog`。无论存放位置如何，必须能被 `trace_id / session_id / report_snapshot_id / llm_node_key` 查询。

### 10.3 失败策略

| 场景 | 策略 |
|---|---|
| 内容草稿失败 | 标记 `draft_generation_failed`，允许人工手写 |
| 内容质检失败 | 保留人工审核，不阻断编辑 |
| Expert QA 检索不足 | 返回证据不足，不自由发挥 |
| 开放题建议失败 | 进入人工复核队列 |
| 报告解释失败 | 展示结构化 EvaluationRun 基础报告 |
| 超预算 | 进入人工队列或禁用低优先级节点 |
| kill switch 触发 | 节点立即停止新调用，已有结果保留审计 |

---

## 11. 权限、部门与共享

### 11.1 部门模型

新增 `Department` 作为内容归属和访问隔离边界。第一阶段只作为内容归属字段和查询过滤条件，不实现完整组织树授权引擎。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID string | 部门 ID |
| `name` | string | 部门名 |
| `parent_id` | UUID nullable | 上级部门 |
| `status` | enum | `active / archived` |

### 11.2 角色

不直接扩展现有 `User.role` 数据库约束。课程化权限通过 action-level RBAC 表达，现有 `admin / support / content_admin / operations / readonly_auditor` 等角色映射到下列权限 action。

| 权限 action | 职责 |
|---|---|
| `curriculum.asset.create` | 创建 draft |
| `curriculum.asset.update` | 编辑 draft / changes_requested |
| `curriculum.asset.review` | 审核内容、退回修改 |
| `curriculum.asset.publish` | 发布、回滚、归档 |
| `curriculum.template.manage` | 配置 PracticeTemplate |
| `curriculum.template.publish` | 发布 PracticeTemplate |
| `curriculum.training.assign` | 派发课程化训练任务 |
| `curriculum.evidence.read` | 按权限读取会话证据 |
| `curriculum.report.export` | 审批和导出报告 |
| `curriculum.ai_governance.read` | 只读查看模型、prompt、RAG、评分、证据链 |

默认角色映射建议：

| 现有角色 | 默认课程化权限 |
|---|---|
| `admin` | 全部 action |
| `content_admin` | asset create/update/review、template manage |
| `operations` | template manage、training assign、evidence read |
| `support` | evidence read、ai governance read |
| `readonly_auditor` | ai governance read、审计只读 |
| `user` | 仅访问被分配训练和自己的报告 |

### 11.3 共享范围

`shared_scope` 取值：

- `private_department`：仅归属部门可见。
- `department_tree`：归属部门及子部门可见。
- `cross_department_approved`：跨部门共享，需额外审核和脱敏。
- `global_published`：全局可见，仅管理员可发布。

### 11.4 对象级权限矩阵

| 对象 | create | read | update | review | publish | rollback | share | export |
|---|---|---|---|---|---|---|---|---|
| 内容资产 | author/admin | owner dept/reviewer | author | reviewer | publisher | publisher | publisher/admin | admin |
| PracticeTemplate | training_admin | owner dept | training_admin | reviewer | publisher | publisher | training_admin | admin |
| Runtime 配置 | admin | admin/governance | admin | admin | admin | admin | 不允许跨部门直接共享 | admin |
| LLM 配置 | admin | admin/governance | admin | admin | admin | admin | 不允许 | admin |
| 会话证据 | learner/supervisor/admin 按范围 | learner/supervisor/admin 按范围 | 不允许 | supervisor | 不适用 | 不适用 | 不允许 | admin 审批 |
| 报告 | learner/supervisor/admin 按范围 | learner/supervisor/admin 按范围 | 不允许 | supervisor | 不适用 | 不适用 | supervisor/admin | admin 审批 |

---

## 12. Evidence、Evaluation 与报告

### 12.1 Evidence 要求

StepFun 输出进入 evidence：

- transcript。
- turn events。
- interruption events。
- tool usage events。
- retrieval events。
- timing metrics。
- reconnect/failure events。

### 12.2 EvaluationRun 输入

EvaluationRun 必须读取：

- session evidence。
- curriculum snapshot。
- rubric version/hash。
- config bundle/version。
- LLM suggestion 记录。
- non-evaluable reason。

课程化 lineage 采用统一 JSON，第一阶段优先写入 `EvaluationRun.input_evidence_reference.curriculum_lineage`，并在报告生成时复制到 `TrainingReportSnapshot.report_payload.lineage`：

```json
{
  "practice_template": {
    "id": "uuid-string",
    "version": 1,
    "hash": "sha256:..."
  },
  "content_assets": [
    {
      "asset_type": "case_item",
      "asset_id": "uuid-string",
      "version": 2,
      "hash": "sha256:..."
    }
  ],
  "rubric": {
    "rubric_set_id": "uuid-string",
    "version": 3,
    "hash": "sha256:..."
  },
  "llm_suggestions": [
    {
      "node_key": "exam_evaluation",
      "call_id": "uuid-string",
      "output_hash": "sha256:..."
    }
  ]
}
```

如果后续查询压力变大，再新增 `EvaluationRun.curriculum_lineage_snapshot` 字段；第一阶段不强行扩表。

### 12.3 Report Snapshot 输出

TrainingReportSnapshot 必须固化：

- 总分和分维度得分。
- 每个低分维度的证据引用。
- 扣分原因和 rubric 条款。
- 优秀表达样例和需改进表达样例。
- 下一步训练建议。
- 是否触发主管复核或复训派发。
- 低置信度/争议项标记。
- 内容资产版本、rubric 版本、EvaluationRun id、ConfigBundle snapshot。

---

## 13. 证据检查视图/API

新增只读证据检查入口，用于运维和 AI Governance 排查“为什么不能评分/不能出报告”。

最小字段：

- `session_id`
- `learner_id`
- `department_id`
- `practice_template_version`
- `stepfun_connection_timeline`
- `transcript_completeness`
- `turn_events_count`
- `missing_turn_ranges`
- `interruption_events`
- `retrieval_events`
- `tool_events`
- `evidence_completeness_score`
- `non_evaluable_reason`
- `evaluation_run_id`
- `training_report_snapshot_id`
- `trace_id`
- `error_refs`

标准 `non_evaluable_reason`：

- `missing_transcript`
- `insufficient_turns`
- `runtime_disconnected`
- `snapshot_mismatch`
- `rubric_unavailable`
- `knowledge_evidence_missing`
- `llm_evaluation_failed`
- `preflight_not_completed`
- `consent_missing`

---

## 14. 隐私、留存与导出

### 14.1 隐私告知

训练前必须展示：

- 是否录音。
- 是否转写。
- 是否用于评分。
- 主管可见范围。
- 管理员审计范围。
- 数据保留期限。
- 导出审批规则。

### 14.2 留存策略

建议新增数据留存策略：

| 数据类型 | 默认策略 |
|---|---|
| 原始录音 | 到期归档或删除 |
| 转写文本 | 到期脱敏或归档 |
| 报告快照 | 长期保留，按权限可见 |
| LLM 调用日志 | 保留审计字段，敏感输入可脱敏 |
| ContentSource | 归属部门可归档 |

### 14.3 导出审计

报告、证据、内容资产导出必须记录：

- actor。
- 时间。
- 对象范围。
- 导出原因。
- 脱敏版本。
- 审批人。

---

## 15. 迁移与兼容

### 15.1 迁移原则

- 只读适配先行，不破坏现有 API。
- 新字段允许 nullable，旧会话正常展示。
- 历史报告不重算。
- 旧 Agent/Persona/Knowledge/Scoring/Prompt 通过 adapter 接入 PracticeTemplate。
- 新训练优先使用 PracticeTemplate；旧入口保留兼容期。

### 15.2 适配映射

| 现有能力 | 新域映射 | 策略 |
|---|---|---|
| Agent | PracticeTemplate.agent_id | 直接引用 |
| Persona | RoleProfile.persona_ref / PracticeTemplate.persona_id | 引用 + 版本化角色扩展 |
| KnowledgeBase | PracticeTemplate.knowledge_base_refs | 冻结文档版本引用 |
| ScoringRuleset | RubricSet.scoring_ruleset_ref | adapter 方式接入 |
| VoiceRuntimeProfile | PracticeTemplate.runtime_profile_id | 直接引用 |
| PromptTemplate | LLM node prompt contract | 编译后哈希引用 |
| TrainingTask | practice_template_id | 新任务绑定模板 |
| PracticeSession | curriculum_snapshot | 会话创建时冻结 |

### 15.3 ConfigBundle 适配边界

不把所有旧能力一次性纳入 ConfigBundle 生命周期。边界如下：

| 能力 | 是否进入 ConfigBundle | 说明 |
|---|---:|---|
| ScoringRuleset | 是 | 延续 PRD #23 adapter 模式，可用于 scoring domain |
| ModelConfig | 是/只读 | 作为 model domain 的只读或治理视图 |
| KnowledgeConfigVersion | 是/只读 | 作为 knowledge domain 的只读视图 |
| VoiceRuntimeProfile | 是/只读 | 作为 voice_runtime domain 的只读视图 |
| Agent | 否 | PracticeTemplate 直接 FK 引用，不强行迁移生命周期 |
| Persona | 否 | RoleProfile 可引用 Persona，不强行迁移生命周期 |
| PracticeTemplate | 否 | 属于 `curriculum_practice` 自有内容发布生命周期 |
| Curriculum / Lesson / QuestionBank / CaseBank / RoleProfile / RubricSet | 否 | 属于内容资产生命周期，不进入 ConfigBundle |

ConfigBundle 继续作为训练行为配置底座；课程化内容资产由 `curriculum_practice` 自己管理发布、回滚和审计。

---

## 16. 可观测性与告警

### 16.1 指标

最小指标：

- 课程完成率。
- 训练开始成功率。
- 预检失败率。
- StepFun 建连失败率。
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

### 16.2 告警

| 告警 | 对象 |
|---|---|
| StepFun 连接失败或重连率异常 | 技术运维 |
| 预检失败率异常 | 训练平台负责人 |
| evidence 完整率下降 | 训练平台负责人 |
| LLM 成本超预算 | AI 治理/管理员 |
| 内容发布失败或回滚率异常 | 内容运营负责人 |
| 报告生成 SLA 超时 | 技术运维 + 训练平台负责人 |

---

## 17. 测试策略

### 17.1 单元测试

- 内容资产模型校验。
- 生命周期状态跳转。
- 发布门禁聚合。
- PracticeTemplate 发布约束。
- Snapshot 构建。
- LLM 节点输出 schema 校验。

### 17.2 集成测试

- `TrainingTask -> PracticeTemplate -> PracticeSession -> Runtime Snapshot`。
- `StepFun evidence -> EvaluationRun -> TrainingReportSnapshot`。
- 内容发布后历史会话 snapshot 不变。
- Expert QA citations 不足时拒答。
- 开放题 LLM suggestion 被 EvaluationRun 归一化。
- 主管复核和复训派发。

### 17.3 权限测试

- 作者只能编辑 draft。
- 审核人不能发布。
- 发布人能发布和回滚。
- 学员只能读取被分配的 published training path。
- 跨部门共享必须脱敏和双人审核。
- 直接访问无权限 API 返回 403。

### 17.4 E2E 测试

- 学员从 TrainingTask 进入课程化训练。
- 完成 preflight。
- 执行 StepFun 客户对练。
- 断线时 `PracticeSession.runtime_state.reconnect_state` 记录 `reconnecting/resumable`，不改变 `PracticeSession.status`。
- 结束后生成 evidence、EvaluationRun、TrainingReportSnapshot。
- 主管查看报告并派发复训。
- 管理员查看 evidence check 和 AI governance lineage。

---

## 18. 分期实施

### Phase 1：课程化编排最小闭环

目标：建立可以穿透现有系统的一条 tracer-bullet，不一次性交付全部 LMS 内容平台。

交付：

1. `PracticeTemplate` 最小骨架：只引用现有 Agent、Persona、KnowledgeBase、ScoringRuleset、VoiceRuntimeProfile。
2. `RuntimeSnapshotService.build_for_session()`：生成符合 §8.1.1 的最小 `curriculum_snapshot`。
3. PracticeSession 增加 `practice_template_id` 和 `curriculum_snapshot`，不改变 `PracticeSession.status`。
4. TrainingTask start-session 可选读取 `practice_template_id`，旧任务保持兼容。
5. 最小发布门禁：模板引用存在、引用对象可读、voice mode 为 StepFun、rubric/scoring 引用存在。
6. 测试证明：内容或模板更新后，历史 session snapshot 不变。

明确不在 Phase 1 做：完整 ContentSource、完整 QuestionBank、完整 CaseBank、完整 RoleProfile、完整 RubricSet、部门组织树、LLM 节点治理、证据检查 UI。

### Phase 1b：最小内容资产试点

目标：在 Phase 1 tracer-bullet 稳定后，选择一个内容资产方向试点，不全量铺开。

候选切片：

1. `KnowledgePoint + Lesson`：用于学习和知识检查。
2. `CaseItem + RoleProfile`：用于客户对练。
3. `RubricSet adapter`：用于 EvaluationRun/Report lineage。

每个切片必须独立具备：模型、只读 API、发布状态、snapshot 引用、兼容测试。

### Phase 2：内容生命周期与权限治理

目标：补齐 draft/review/publish/rollback/archive、部门隔离、对象级权限和审计。

交付：

1. ContentAssetLifecycleService。
2. PublishingGateService。
3. Department 与 shared_scope。
4. 内容角色与权限矩阵。
5. 审计日志。

### Phase 3：训练路径、预检与 StepFun 恢复语义

目标：补齐三层状态机、preflight、reconnecting/resumable、evidence check。

交付：

1. StagePlan / LearningPath 编排。
2. Preflight Check API。
3. runtime_state 持久化。
4. StepFun failure events。
5. Evidence Check API。

### Phase 4：受控 LLM 节点

目标：引入 LLM draft、QA、Expert QA、Exam Evaluation suggestion、Report Explanation。

交付：

1. LLMNode 调用记录。
2. 节点级预算、限流、kill switch。
3. Content draft 生成。
4. Expert QA citations 强制。
5. 开放题 suggestion。
6. 报告解释。

### Phase 5：运营、隐私、留存与发布门禁

目标：将课程化训练纳入生产可运营状态。

交付：

1. 运营指标。
2. 告警规则。
3. 留存策略。
4. 导出审计。
5. Release Gate。
6. 真实 E2E。

---

## 19. 验收标准

全量架构落地后必须满足：

1. 任意训练会话都能追溯到 PracticeTemplate 版本。
2. 任意实时对话都能追溯到 StepFun 使用的 `voice_policy_snapshot`。
3. 任意报告都能追溯到 session evidence、内容资产版本、rubric 版本、EvaluationRun 和 ConfigBundle snapshot。
4. 新发布内容不影响历史会话和历史报告。
5. LLM 生成内容在人工发布前不会被训练运行时读取。
6. LLM suggestion 不直接成为最终评分。
7. evidence 不足时系统返回不可评估原因，不生成伪分。
8. 部门可以自维护内容，但发布、共享、回滚、导出都有权限和审计。
9. 学员首次进入实时训练前必须完成目标确认、设备预检和隐私授权。
10. StepFun 中断后有明确恢复、终止或重新派发路径。
11. 报告必须提供证据、扣分原因、好/坏例句、下一步建议和复训状态。
12. 内容发布必须经过 schema、证据、敏感信息、审核和审计门禁。
13. LLM 节点必须有模型白名单、预算、限流、灰度和紧急停用机制。
14. 运维必须能通过证据检查视图定位不可评分原因。
15. 录音、转写、报告和 LLM 调用日志必须有可配置留存与脱敏策略。

---

## 20. 不可违反原则

1. StepFun 管实时对话，LLM 管受控非实时智能处理。
2. 内容资产是事实源，LLM 输出只是草稿、建议或解释。
3. 运行时永远读 snapshot，不读 latest。
4. 评分由 rubric、ScoringRuleset adapter 和 EvaluationRun 裁决。
5. 报告是快照，不是自由文本临时生成物。
6. 所有配置和内容变更必须可审核、可回滚、可追溯。
7. 不把任务状态、会话状态、训练阶段状态混成一个字段。
8. 不重算历史报告。
9. 不恢复 legacy Sales runtime。
10. 不用 LLM 绕过发布门禁或人工审核。
