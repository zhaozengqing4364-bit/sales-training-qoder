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
