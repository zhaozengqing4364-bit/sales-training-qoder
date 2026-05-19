# ADR 2026-05-11: 课程化域架构边界与契约锁定（PRD #46 Slice 01）

## Status

Accepted. 本 ADR 是 PRD #46 入口 issue #47 的 HITL 产出，作为 #48-#54 所有下游实现 issue 的规范契约文档。

## Context

PRD #23 已完成 `TrainingTask → PracticeSession → Evidence → EvaluationRun → TrainingReportSnapshot → RetrainingTask` 底座闭环。PRD #46 在此基础上新增 `curriculum_practice` 课程化域：内容资产（Content Assets）、PracticeTemplate 训练模板、RuntimeSnapshotService 运行时快照、StagePlan 训练阶段编排、LearningPath 学习路径。

**核心架构要求**：新增 `curriculum_practice` 域，负责内容资产与训练编排；现有 `TrainingTask`、`PracticeSession`、`EvaluationRun`、`TrainingReportSnapshot`、`ConfigBundle`、StepFun runtime、RBAC 只通过明确接口薄集成。运行时永远读取冻结 snapshot，不读取 latest content。

**参考文档（必读）**：
- `docs/superpowers/plans/2026-05-11-prd46-curriculum-practice-issues-closure.md`：issues #47-#54 实施计划
- `docs/adr/2026-05-11-architecture-boundary-domain-contract.md`：PRD #23 底座边界契约

## Decision

### 1. `curriculum_practice` 模块所有权边界

#### 1.1 curriculum_practice 负责

`curriculum_practice` 是新增的课程化内容与训练编排域，只负责以下能力，不直接执行实时对话、不直接评分、不直接生成最终报告：

| 职责 | 说明 |
|------|------|
| **内容资产** | `ContentSource`、`KnowledgePoint`、`Curriculum`/`Lesson`、`QuestionBank`/`QuestionItem`、`CaseBank`/`CaseItem`、`RoleProfile`、`RubricSet`/`RubricDimension` 的模型定义、生命周期管理与版本治理 |
| **PracticeTemplate** | 训练模板的创建、编辑、发布与引用解析，是一次训练如何组装内容、角色、知识库、运行时和评分的唯一编排入口 |
| **发布门禁（Publishing Gates）** | 内容资产和 PracticeTemplate 的发布前置校验：schema 校验、引用完整性、Rubric 绑定、敏感信息检测、审核人数等 |
| **RuntimeSnapshotService** | 会话创建时冻结所有运行依赖，生成确定性 `curriculum_snapshot`。它是对外暴露的唯一课程化 snapshot 构建入口 |
| **StagePlan / LearningPath** | 训练阶段编排与学习路径推进 |
| **内容权限** | action-level RBAC 权限检查（不改 `User.role` DB constraint） |

**归属**：`backend/src/curriculum_practice/`，独立包。

#### 1.2 curriculum_practice 明确不负责

`curriculum_practice` 不得实现、不得耦合、不得内嵌以下能力：

| 不负责 | 归属 | 说明 |
|--------|------|------|
| **StepFun WebSocket 协议** | `sales_bot/` | 实时语音/实时对话/实时打断/实时转写由 StepFun runtime 负责，curriculum_practice 只提供 snapshot 引用 |
| **Scoring Engine 内部算法** | `evaluation/` | 评分引擎内部实现（如分维度打分逻辑、证据匹配算法）不属于课程化域 |
| **主管复训任务生命周期** | `supervisor/` | `RetrainingTask` 的创建、派发、完成生命周期属于主管层 |
| **ConfigBundle 通用配置生命周期** | `admin/` | ConfigBundle/ConfigVersion 的 draft/validate/publish/rollback/audit 生命周期属于配置运营层 |
| **KnowledgeAnswerEngine 检索实现** | `sales_bot/` 或独立 knowledge 域 | 知识库检索、向量匹配、文档召回的具体实现不属于课程化域 |

**接口原则**：外部模块不得直接拼接课程、题目、案例、角色和 rubric JSON。`curriculum_practice` 对外只暴露稳定深模块接口（见 Section 4）。

---

### 2. 统一版本引用结构

所有 `*_ref`、`*_refs` 使用统一 JSON 结构，不允许各模块自定义格式：

```json
{
  "asset_type": "practice_template | curriculum | lesson | knowledge_point | question_bank | question_item | case_item | role_profile | rubric_set | scoring_ruleset | knowledge_base | prompt_contract | model_config",
  "asset_id": "uuid-string",
  "version": 1,
  "hash": "sha256:<hex-digest>",
  "snapshot_label": "published | superseded | legacy_unversioned"
}
```

**允许的 `asset_type` 枚举**：

| asset_type | 对应实体 |
|------------|---------|
| `practice_template` | PracticeTemplate |
| `curriculum` | Curriculum |
| `lesson` | Lesson |
| `knowledge_point` | KnowledgePoint |
| `question_bank` | QuestionBank |
| `question_item` | QuestionItem |
| `case_item` | CaseItem |
| `role_profile` | RoleProfile |
| `rubric_set` | RubricSet |
| `scoring_ruleset` | ScoringRuleset（现有 adapter 映射） |
| `knowledge_base` | KnowledgeBase |
| `prompt_contract` | CompiledPromptContract |
| `model_config` | ModelConfig |

**哈希规则**：
- `hash` 按规范化 JSON 计算：字段按 key 排序，排除 `created_at`、`updated_at`、`published_at`、`actor_id`、`trace_id` 等审计字段。
- 使用 SHA-256。
- `snapshot_label` 取值：`published`（当前发布版本）、`superseded`（被新版本替代，历史可读）、`legacy_unversioned`（无版本化历史的旧数据）。

---

### 3. `PracticeSession.curriculum_snapshot` 与 `PracticeSession.runtime_state` 职责划分

`PracticeSession` 继续表达运行事实，但新增字段必须遵守职责分离：

| 字段 | 类型 | 职责 | 写入时机 | 是否参与 `PracticeSession.status` |
|------|------|------|---------|----------------------------------|
| `practice_template_id` | UUID nullable | 关联的 PracticeTemplate | 会话创建（有模板时） | 否 |
| `curriculum_snapshot` | JSON nullable | 冻结的课程化运行依赖版本引用 | 会话创建（有模板时），由 `RuntimeSnapshotService.build_for_session()` 生成 | 否 |
| `runtime_state` | JSON nullable | 课程化运行状态（preflight、stage、reconnect） | 运行时动态更新 | **否，严格禁止参与 check constraint** |
| `preflight_snapshot` | JSON nullable | 预检结果冻结 | 预检完成 | 否 |
| `reconnect_policy_snapshot` | JSON nullable | 重连策略冻结 | 会话创建 | 否 |
| `non_evaluable_reason` | string nullable | 不可评估原因 | 评分前判定 | 否 |

**`curriculum_snapshot` 职责（不可变）**：
- 存储 PracticeTemplate 版本引用、内容资产版本引用、rubric 版本引用、运行时配置引用。
- 会话创建时一次性写入，之后只读。
- 是 EvaluationRun 和 TrainingReportSnapshot 的输入事实源之一。
- 格式见架构详细规格 §8.1.1。

**`runtime_state` 职责（可变）**：
- 存储 preflight_status、stage_status、current_stage_key、reconnect_state 等运行时状态。
- 可以随会话进行更新。
- 不得将 `runtime_state` 中的状态语义混入 `PracticeSession.status` 的 DB check constraint。

**关键约束**：`PracticeSession.status` 保持 PRD #23 定义的 `preparing → in_progress → paused → in_progress → scoring → completed`，不新增课程化专属状态。所有课程化运行时态（preflight、stage、reconnect）只能进入 `runtime_state` JSON。

---

### 4. 深模块接口契约

`curriculum_practice` 对外只暴露以下稳定深模块接口。外部模块不得绕过这些接口直接操作内容资产或快照。

#### 4.1 PracticeTemplateService

```text
PracticeTemplateService.publish_template(template_id: UUID, actor_id: UUID) -> PublishedTemplateRef
```

- **职责**：校验发布门禁并发布模板。
- **门禁**：所有引用资产均为 `published`、voice_mode 为 `stepfun_realtime`（实时场景）、rubric/scoring 引用存在、stage_plan 无死循环、completion_policy 声明最低完成条件。
- **返回**：`PublishedTemplateRef` 包含 asset_type、asset_id、version、hash、snapshot_label。
- **失败**：返回结构化 `GateResult` 含 gate_name、status、reason_code、message。

```text
PracticeTemplateService.resolve_for_task(training_task_id: UUID) -> PublishedTemplateRef | None
```

- **职责**：根据 TrainingTask 解析绑定的已发布模板引用。
- **返回**：若 TrainingTask 未绑定 `practice_template_id` 或其模板未发布，返回 `None`。

#### 4.2 RuntimeSnapshotService

```text
RuntimeSnapshotService.build_for_session(
    template_ref: PublishedTemplateRef,
    training_task_ref: TrainingTaskRef,
    actor_id: UUID
) -> CurriculumRuntimeSnapshot
```

- **职责**：冻结 PracticeTemplate、所有引用内容资产、rubric、运行时配置为 `curriculum_snapshot`。
- **流程**：
  1. 校验 template 为 published。
  2. 解析所有引用资产（content_assets、rubric、runtime、llm_nodes）。
  3. 逐资产校验 published 状态和 hash 完整性。
  4. 构建规范化 snapshot JSON。
  5. 计算 snapshot_hash（排除自身字段）。
- **失败码**：`template_unpublished`、`asset_unpublished`、`asset_hash_mismatch`、`rubric_missing`、`voice_policy_unavailable`、`prompt_contract_missing`。
- **唯一入口原则**：这是进入 StepFun、EvaluationRun 和 TrainingReportSnapshot 的唯一课程化 snapshot 生成入口。其他模块不得自行构造 snapshot。

#### 4.3 接口隔离规则

- `common/` 层通过 `PracticeTemplateService.resolve_for_task()` 获取模板引用，通过 `RuntimeSnapshotService.build_for_session()` 获取 snapshot。不直接读取 `curriculum_practice` 内部模型。
- `evaluation/` 层读取 `PracticeSession.curriculum_snapshot` 获取内容版本引用，不调用 `curriculum_practice` 内部 API。
- `sales_bot/` 层只读取 `curriculum_snapshot` 中允许进入实时指令的字段，不读取 latest content。
- StepFun 初始输入只从 `voice_policy_snapshot` 和 `curriculum_snapshot` allowlist 编译，不包含 `hidden_information`。

---

### 5. PRD #23 不变量

以下不变量来自 PRD #23 底座，PRD #46 所有实施必须严格遵守：

| # | 不变量 | 说明 |
|---|--------|------|
| 1 | 不改变 `TrainingTask.status` 枚举 | 保持 `assigned → in_progress → completed | expired | cancelled` |
| 2 | 不改变 `PracticeSession.status` 枚举 | 保持 `preparing → in_progress → paused → in_progress → scoring → completed` |
| 3 | 不扩展 `ConfigBundle` 生命周期 | 内容资产、PracticeTemplate、CaseItem、RoleProfile 不纳入 ConfigBundle 生命周期 |
| 4 | 不扩展 `User.role` DB constraint | 课程化权限通过 action-level RBAC 或现有角色映射表达 |
| 5 | 不恢复 legacy Sales runtime | 不恢复或引用 `base_sales_handler.py`、`enhanced_handler.py`、`simple_handler.py` |
| 6 | 不重算历史报告 | 不批量更新、不迁移、不重算历史 `TrainingReportSnapshot` |
| 7 | 不创建 `SessionV2` | 不引入新的会话根模型或并行会话模型 |
| 8 | 不使用类型绕过 | 禁止 `as any`、`@ts-ignore`、`@ts-expect-error` |
| 9 | StepFun 不读 latest content | 运行时只能读冻结 snapshot，不允许 LLM 输出直接成为 published content 或最终评分 |
| 10 | 不把运行态塞入任务/会话状态 | preflight、stage、reconnect 状态只能进入 `PracticeSession.runtime_state`，不进入 `TrainingTask.status` 或 `PracticeSession.status` |

**不变约束优先级**：当 ADR、issue body、实施计划之间出现冲突时：
```
PRD #23 不变量 > 本 ADR > 架构详细规格 > 实施计划 > agent 推断
```

---

### 6. HITL 确认清单（Issue #47）

本 ADR 是 issue #47 的 HITL 产出。在标记 #47 完成前，必须通过以下人工审核清单：

| # | 确认项 | 状态 |
|---|--------|------|
| 1 | `curriculum_practice` 所有权边界准确：内容资产、PracticeTemplate、发布门禁、RuntimeSnapshotService、StagePlan | ☐ 待确认 |
| 2 | `curriculum_practice` 非所有权边界准确：StepFun WebSocket、Scoring Engine、Supervisor RetrainingTask、ConfigBundle 通用生命周期、KnowledgeAnswerEngine 检索 | ☐ 待确认 |
| 3 | 统一版本引用结构中的 `asset_type` 枚举完整且无歧义 | ☐ 待确认 |
| 4 | 深模块接口签名精确：`publish_template`、`resolve_for_task`、`build_for_session` | ☐ 待确认 |
| 5 | `PracticeSession.curriculum_snapshot`（不可变）与 `runtime_state`（可变）职责分离正确 | ☐ 待确认 |
| 6 | PRD #23 十条不变量全部确认未被本 ADR 违反 | ☐ 待确认 |
| 7 | Slice 08 第一条试点选型确认：`CaseItem + RoleProfile` | ☐ 待确认 |
| 8 | 确认本 ADR 不涉及代码实现、不修改 GitHub issues、不关闭 #47、不触及 #48-#54 | ☐ 待确认 |

### 7. Slice 08 第一条试点选型

**决策**：Phase 1b 最小内容资产试点选择 **`CaseItem + RoleProfile`**（客户案例 + 角色画像），用于 `customer_roleplay` 模式的客户对练场景。

**理由**：
- 客户对练是销售训练最高频、最高价值的场景。
- `CaseItem` 和 `RoleProfile` 构成客户对练的最小完整内容组合。
- 它们直接对接 StepFun realtime runtime，能端到端验证 RuntimeSnapshotService 的冻结与编译链路。
- 字段粒度和披露策略已在架构详细规格 §4.6 / §4.7 定义，可在 #54 HITL 时进一步确认。

**不在第一阶段试点**：完整 ContentSource、完整 QuestionBank、完整 RubricSet、完整部门组织树、LLM 节点治理、证据检查 UI。

---

## Consequences

### Positive

- #48-#54 的所有 agent 能以统一边界和接口契约实施，减少 context drift。
- `curriculum_practice` 域边界清晰，不会因后续实施蔓延污染现有 `common/`、`evaluation/`、`admin/` 模块。
- 深模块接口契约确保外部模块只能通过稳定入口访问课程化能力，降低耦合风险。
- PRD #23 不变量被明确写入，所有下游 agent 可自检。

### Negative

- 本 ADR 是一次性文档投入，但代价远小于后续边界漂移导致的重写。
- HITL 门禁强制人工审核，可能延迟 AFK 实施启动。

### Risk

| 风险 | 缓解 |
|------|------|
| #47 边界未锁定就开工 | #47 必须 HITL 通过后才能启动 #48 |
| 下游 agent 绕过深模块接口 | 本 ADR 明确唯一入口原则，code review 和 contract test 校验 |
| CaseItem/RoleProfile 字段在 #54 被调整 | #54 是独立 HITL gate，调整仅影响内容资产试点，不影响 #48-#53 主链路 |

## Follow-up

- 本 ADR 由 #47 完成并 HITL 确认后即生效。
- #48 直接引用本文档作为 `PracticeTemplate` 最小骨架的接口契约起点。
- #49 引用本文档 Section 4.2 定义 `RuntimeSnapshotService.build_for_session()` 实现规范。
- #50 引用本文档 Section 3 定义 `PracticeSession.curriculum_snapshot` 持久化规范。
- #54 引用本文档 Section 7 作为 `CaseItem + RoleProfile` 试点范围边界。
- 如后续 issue 实施中发现本文档未覆盖的边界歧义，需追加补充 ADR。
