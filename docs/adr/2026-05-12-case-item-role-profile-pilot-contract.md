# ADR 2026-05-12: CaseItem + RoleProfile 最小内容资产试点契约（PRD #46 Issue #54 HITL）

## Status

**Proposed — 待人工确认。** 本文档是 PRD #46 issue #54 的 HITL 产出，在人工确认前不进入实现阶段。

## Context

PRD #46 实施计划将 issue #54 定为 HITL gate：在 `PracticeTemplate`（#48）完成后，必须人工确认 `CaseItem` 和 `RoleProfile` 的字段粒度、披露策略和发布门禁，方可进入实现。

`CaseItem + RoleProfile` 是 Slice 08 第一条内容资产试点，服务 `customer_roleplay` 模式下客户对练场景，为 `RuntimeSnapshotService` 的冻结与编译链路提供端到端验证。

**参考文档**：
- `docs/superpowers/plans/2026-05-11-prd46-curriculum-practice-issues-closure.md`（Task 8: #54）
- `docs/adr/2026-05-11-curriculum-practice-boundary-contract.md`（#47 ADR，Section 7: Slice 08 试点选型）
- `docs/adr/2026-05-11-architecture-boundary-domain-contract.md`（PRD #23 底座契约）

## Purpose

本文档定义 `CaseItem` 和 `RoleProfile` 最小内容资产的字段契约、披露策略、发布门禁和试点范围边界。人工确认通过后，本文档将成为 issue #54 实现的规范依据。

---

## Decision

### 1. CaseItem 最小字段定义

`CaseItem` 描述一个客户对练场景中的案例上下文。最小试点版本仅包含以下字段，不添加超出客户对练必需的任何字段。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `industry` | string | 是 | 行业标签（如"金融"、"医疗"、"IT"）。用于模板匹配和统计分组。 |
| `company_profile` | string | 是 | 公司画像。简要描述目标公司的规模、业务模式和关键特征，为学员提供场景入口上下文。 |
| `customer_role` | string | 是 | 客户角色（如"CTO"、"采购经理"、"运营总监"）。描述学员需要对练的客户身份。 |
| `pain_points` | list[string] | 是 | 痛点列表。描述该客户角色在当前场景中面临的业务痛点，用于生成对练中的异议和追问。 |
| `objections` | list[string] | 是 | 异议列表。学员可能遇到的具体客户反对意见，StepFun runtime 可以引用用于模拟客户行为。 |
| `hidden_information` | string | 是 | 隐藏信息。学员在训练开始时不可见、需要在对练过程中通过提问挖掘的信息。仅对评分引擎和主管报告可见，不得进入 StepFun 初始输入。 |
| `success_criteria` | list[string] | 是 | 成功标准列表。定义该案例的通过条件（如"成功获取客户预算信息"、"完成至少一次异议处理闭环"）。 |
| `allowed_disclosure_policy` | json | 是 | 允许信息披露策略。定义哪些字段允许在哪个对话阶段向 StepFun runtime 暴露（详见 Section 4）。 |
| `version` | int | 是 | 内容版本号，从 1 开始递增。 |
| `content_hash` | string | 是 | 内容确定性哈希（SHA-256），按规范化 JSON 计算，排除 `version`、`created_at`、`updated_at` 等审计字段。 |
| `status` | enum | 是 | 生命周期状态：`draft`、`published`、`archived`。 |

### 2. RoleProfile 最小字段定义

`RoleProfile` 描述客户对练场景中 AI 应扮演的客户角色画像。最小试点版本不复制完整的 Persona 平台，仅通过 `persona_ref` 引用现有 Persona。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role_type` | string | 是 | 角色类型（如"customer"、"partner"、"competitor"）。试点阶段仅支持 `customer`。 |
| `role_name` | string | 是 | 角色名称（如"谨慎型 CFO"、"技术导向 CTO"），用于模板选择和管理展示。 |
| `persona_ref` | uuid | 否 | 对现有 Persona 的引用。当角色的人格特征已由已有 Persona 覆盖时使用，避免重复定义人格平台。 |
| `communication_style` | string | 是 | 沟通风格描述（如"直接果断、用数据说话"、"迂回委婉、情感驱动"）。用于 StepFun voice prompt 的角色风格注入。 |
| `pressure_level` | enum | 是 | 压力等级：`low`（配合型）、`medium`（标准型）、`high`（挑战型）。影响异议频率和严重程度。 |
| `knowledge_boundary` | list[string] | 是 | 知识边界列表。明确该角色"知道什么"和"不知道什么"（如"了解公司预算流程，但不知道实际预算数字"），确保 AI 角色行为一致。 |
| `behavior_rules` | list[string] | 是 | 行为规则列表。自然语言描述角色的行为约束（如"只回答被直接提问的问题"、"被质疑价格时会先反驳再让步"）。 |
| `voice_style_hint` | string | 是 | 声音风格提示。传递给 StepFun voice runtime 的风格元数据（如"语速较快、语调上扬"）。 |
| `version` | int | 是 | 内容版本号，从 1 开始递增。 |
| `content_hash` | string | 是 | 内容确定性哈希（SHA-256），规则同 CaseItem。 |
| `status` | enum | 是 | 生命周期状态：`draft`、`published`、`archived`。 |

### 3. Persona 复用策略

**决策**：`RoleProfile` 可通过 `persona_ref` 引用现有 Persona 实体，不复制或内嵌完整的 Persona 平台。

**规则**：
- `persona_ref` 为可选字段。当填入时，表示角色的基础人格特征由已有 Persona 定义。
- `RoleProfile` 字段（`communication_style`、`pressure_level`、`knowledge_boundary`、`behavior_rules`、`voice_style_hint`）是对 `persona_ref` 的**场景特化覆盖**，不是重复定义。
- 当 `persona_ref` 为空时，`RoleProfile` 的所有字段必须自完整。
- 如果引用的 Persona 被删除或下线，已发布的 `RoleProfile` 不受影响，但新发布校验应阻止引用不可用 Persona。

**不在此试点范围**：
- 不创建新的 Persona 管理页面。
- 不扩展 Persona 模型。
- 不将 RoleProfile 行为规则反向写入 Persona。

### 4. StepFun 初始信息披露白名单

**决策**：StepFun runtime 的初始 prompt/payload 只能包含以下 CaseItem 和 RoleProfile 字段，严格禁止一次性暴露 `hidden_information`。

#### 4.1 允许进入 StepFun 初始输入的字段

| 来源 | 允许字段 |
|------|---------|
| CaseItem | `industry`、`company_profile`、`customer_role`、`pain_points`、`objections`、`success_criteria` |
| RoleProfile | `role_type`、`role_name`、`communication_style`、`pressure_level`、`knowledge_boundary`、`behavior_rules`、`voice_style_hint` |

#### 4.2 明确禁止进入 StepFun 初始输入的字段

| 来源 | 禁止字段 | 原因 |
|------|---------|------|
| CaseItem | `hidden_information` | 隐藏信息只能通过学员对练中的有效提问渐进解锁，一次性暴露会破坏训练目的 |
| CaseItem | `allowed_disclosure_policy` | 披露策略是元数据，不应进入 runtime prompt |
| CaseItem / RoleProfile | `version`、`content_hash`、`status` | 版本治理字段，与训练内容无关 |

#### 4.3 实施约束

- `RuntimeSnapshotService` 构建 `curriculum_snapshot` 时，不将 `hidden_information` 写入可供 StepFun 读取的 snapshot 分区。
- StepFun 初始 payload 编译器必须使用白名单过滤，不允许通过配置绕过。
- 必须编写测试验证 StepFun 初始输入中不存在 `hidden_information` 以及运行时状态字段。

### 5. `allowed_disclosure_policy` 语义

**定义**：`allowed_disclosure_policy` 是一个 JSON 结构，定义 `hidden_information` 在何种条件下可以向 StepFun runtime 渐进披露。

**试点阶段策略结构**：

```json
{
  "phases": [
    {
      "trigger": "学员提问匹配关键词",
      "keywords": ["预算", "决策流程", "痛点具体"],
      "disclose": "部分预算相关信息"
    },
    {
      "trigger": "学员完成异议处理闭环",
      "min_closed_objections": 2,
      "disclose": "决策者偏好信息"
    }
  ],
  "max_disclosure_scope": "除最终报价外可全部披露"
}
```

**核心规则**：
- `hidden_information` 默认对 StepFun runtime **不可见**。
- 当对话状态满足 `allowed_disclosure_policy` 中某个 phase 的 `trigger` 条件时，该 phase 对应的 `disclose` 范围内的隐藏信息才向 StepFun runtime 开放。
- 即使所有 phase 条件都满足，`max_disclosure_scope` 之外的信息也永远不向 StepFun 开放。
- 试点阶段 `allowed_disclosure_policy` 为人工编辑字段，不在此试点实现自动化条件评估引擎。条件评估逻辑属于 `sales_bot/` runtime 层的职责。

### 6. 发布门禁最小集合

`CaseItem` 和 `RoleProfile` 发布（`draft → published`）时必须通过以下门禁：

| # | 门禁 | 说明 |
|---|------|------|
| G1 | **引用完整性** | 若 `RoleProfile.persona_ref` 非空，引用的 Persona 必须存在且为 published。 |
| G2 | **content_hash 一致性** | 提交的 `content_hash` 必须与当前字段内容（排除审计字段）的 SHA-256 一致。 |
| G3 | **披露白名单完整性** | `CaseItem.allowed_disclosure_policy` 必须为有效 JSON 且包含至少一个 phase。 |
| G4 | **敏感信息检测（可选）** | 如检测能力已有，对 `company_profile`、`pain_points`、`objections` 字段做简单模式匹配（手机号、身份证号、邮箱），发现疑似敏感信息时标记为 warning（不阻断发布）。如果检测能力尚未就绪，此门禁为 skip。 |

**非试点门禁**（以下不在 #54 试点范围）：
- 审核工作流（多人审核）。
- 跨部门脱敏校验。
- 与 StagePlan/LearningPath 的联动校验。

### 7. 试点范围边界

#### 7.1 在本试点范围内

- `CaseItem` 和 `RoleProfile` 的 ORM 模型、Pydantic schema、migration。
- `CaseItem` 和 `RoleProfile` 的最小 CRUD API（只读查询 + 后台创建/编辑/发布）。
- `PracticeTemplate` 引用已发布 `CaseItem` 和 `RoleProfile` 的能力。
- `RuntimeSnapshotService` 将 `CaseItem`/`RoleProfile` 版本引用写入 `curriculum_snapshot`。
- StepFun 初始输入的白名单过滤逻辑。
- 发布门禁 G1-G4 的实现。
- 对应的单元测试和集成测试。

#### 7.2 明确不在本试点范围内

| 不在范围 | 原因 |
|---------|------|
| 完整 CaseBank / RoleBank 管理 UI | 试点只做后台 API，完整 UI 属于后续切片 |
| 脱敏后的跨部门案例分享 | 数据治理能力建设属于后续切片 |
| 批量导入（Excel / CSV / API batch） | 试点阶段手动创建即可 |
| 完整的 ContentSource / QuestionBank / RubricSet 内容资产 | 各属独立试点 |
| `allowed_disclosure_policy` 的自动化条件评估引擎 | 属于 `sales_bot/` runtime 层，不在 curriculum 域 |
| `hidden_information` 在 StepFun 对话中渐进披露的 runtime 逻辑 | 同上，runtime 层实现 |

### 8. 与 PRD #23 不变量的对齐

本试点严格遵守 PRD #23 十条不变量，特别确认：

- **不变量 3**：`CaseItem` 和 `RoleProfile` 不纳入 `ConfigBundle` 生命周期，拥有独立的版本管理与发布门禁。
- **不变量 9**：StepFun 运行时只能读冻结 snapshot，不允许 LLM 输出直接成为 published content。
- **不变量 10**：试点不引入新的会话状态或扩展 `PracticeSession.status`。CaseItem/RoleProfile 的运行时引用仅存在于 `curriculum_snapshot` 中。

---

## Human Confirmation Checklist

在标记 #54 可进入实现阶段前，必须逐项人工确认：

| # | 确认项 | 状态 |
|---|--------|------|
| C1 | `CaseItem` 11 个字段粒度合适，无缺失、无冗余 | ☐ 待确认 |
| C2 | `RoleProfile` 11 个字段粒度合适，Persona 引用策略合理 | ☐ 待确认 |
| C3 | `persona_ref` 为可选字段，不强制绑定 Persona | ☐ 待确认 |
| C4 | StepFun 初始输入白名单中允许和禁止的字段正确 | ☐ 待确认 |
| C5 | `hidden_information` 不进入 StepFun 初始输入的原则认可 | ☐ 待确认 |
| C6 | `allowed_disclosure_policy` 的 JSON 结构和渐进披露语义可行 | ☐ 待确认 |
| C7 | 发布门禁 G1-G4 的最小集合合理（G4 为可选项） | ☐ 待确认 |
| C8 | 试点范围边界准确，不遗漏关键能力、不膨胀到完整平台 | ☐ 待确认 |
| C9 | 无与 PRD #23 不变量的冲突 | ☐ 待确认 |
| C10 | 确认本提案不包含代码实现，仅为契约文档 | ☐ 待确认 |

---

## Consequences

### Positive

- `CaseItem` 和 `RoleProfile` 字段契约在实现前锁定，减少实现阶段的字段漂移。
- StepFun 披露白名单和 `allowed_disclosure_policy` 语义明确，保证训练公平性和内容安全。
- 试点范围边界清晰，KISS 原则约束下不会膨胀为完整平台。

### Negative

- HITL 门禁要求人工审核本提案，延迟 #54 实现启动。
- 字段确认后如后续发现需要调整，需追加补充 ADR。

### Risk

| 风险 | 缓解 |
|------|------|
| 字段确认后客户对练场景变化需要新增字段 | 新增字段通过后续 ADR 追加，不影响本试点的最小字段集 |
| `allowed_disclosure_policy` JSON 结构在运行时无法满足复杂场景 | 试点阶段 policy 为人工编辑，结构可迭代；自动化评估引擎独立于本试点 |
| Persona 引用关系在 Persona 变更后断裂 | 发布门禁 G1 校验 Persona 可用性；已发布 RoleProfile 不受影响 |

## Follow-up

- 人工确认本提案全部 C1-C10 后，即可启动 #54 实现。
- #54 实现完成后，其 completion note 必须包含本提案的 HITL reviewer、确认日期和所有确认项。
- 如下游实施发现本文档未覆盖的边界，追加补充 ADR。

---

> **HITL 提示**：本文档是 issue #54 的 HITL 产出。请在逐项确认 Checklist 后明确回复"确认，可以开始实现"或指出需调整的项。确认前不进行任何代码实现。
