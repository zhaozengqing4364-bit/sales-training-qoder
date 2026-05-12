# ADR 2026-05-11: 架构边界与领域契约锁定（PRD #23 Slice 01）

## Status

Accepted. 本 ADR 是 PRD #23 入口 issue #24 的产出，作为 #25-#45 所有下游实现 issue 的规范契约文档。

## Context

系统在 #8-#22 已完成基础闭环：StepFun-only Sales runtime、legacy Sales handlers 物理删除、Evidence → EvaluationRun → TrainingReportSnapshot → diagnostics 链路存在。剩余 #23 架构升级的核心问题是：多个能力岛各自演进，缺少统一的领域边界、配置生命周期和训练主线，导致下游 agent 实现时容易出现 context drift。

本 ADR 在不大改功能的前提下，锁定领域模型、实体关系、共享接口契约、配置迁移规则、HITL/AFK 门禁，确保 #25-#45 的所有 AFK agent 能以一致语言和边界工作。

**参考文档（必读）**：
- `CONTEXT.md`：Phase 4 E2E 领域语言
- `docs/adr/2026-03-14-training-runtime-subject.md`：运行时主语收敛 ADR
- `docs/adr/2026-04-24-scoring-ruleset-governance.md`：评分治理 ADR
- `.sisyphus/drafts/architecture-upgrade-direction.md`：架构升级方向

## Decision

### 1. 核心领域模型边界

#### 1.1 TrainingTask（训练任务）

**定义**：连接用户、训练目标、场景、截止时间和完成标准的顶层任务实体。

**边界**：
- 是训练组织的最小调度单位，不是运行时主语。
- 一个 TrainingTask 可关联 0..N 个 PracticeSession。
- 状态机：`assigned → in_progress → completed | expired | cancelled`。
- 包含字段：`title`、`goal`、`scenario_type`（sales/presentation）、`focus_intent`、`due_date`、`assignee_id`、`status`、`resulting_session_id`。

**归属**：`common/` 平台层，同时服务 Sales Training Flow 和 Presentation Training Flow。

**禁止**：
- 不得把 TrainingTask 和 RetrainingTask 合并成不可回滚的大模型改造。
- 不得在 TrainingTask 内嵌入场景特定字段（sales 的客户角色、PPT 的页级检测规则等）。

#### 1.2 RetrainingTask（复训任务）

**定义**：来源于 supervisor review 判定 `needs_retraining` 或主管手动下发的二次训练任务。

**边界**：
- 与 TrainingTask 之间通过可选 FK `training_task_id` 关联（nullable，保证旧数据兼容）。
- 删除/失效 TrainingTask 不删除关联的 RetrainingTask。
- 拥有自己的 start-session / complete-with-session 生命周期，独立于 TrainingTask 的会话。
- 旧数据（#8-#22 期间创建的）`training_task_id = NULL` 正常返回。

**归属**：`supervisor/` 主管层，同时通过关联引用 `common/` 的 TrainingTask。

**禁止**：
- 不得将 RetrainingTask 重构为 TrainingTask 的子类型（会导致回滚困难）。
- 不得删除现有 retraining task 的生命周期行为。

#### 1.3 PracticeSession（训练会话）

**定义**：一次训练运行的事实锚点。ADR 2026-03-14 已将运行时主语收敛为 `training_scenario_runtime`，PracticeSession 是其物理承载。

**边界**：
- 同时服务 Sales Training Flow 和 Presentation Training Flow。
- 通过 `scenario_type` 字段区分训练场景。
- 对外暴露 `runtime_subject` 和 `runtime_descriptor`。
- 生命周期：`created → in_progress → completed | failed | cancelled`。

**归属**：`common/` 平台层。Sales 和 Presentation 均为该实体上的场景适配，不是独立实体。

**禁止**：
- 不得按 scenario_type 分叉为两套独立会话模型。
- 不得重新引入 Scenario/Agent/Presentation 作为运行时主语。

#### 1.4 EvaluationRun（评估运行）

**定义**：一次基于会话证据的评分/分析执行。

**边界**：
- 接收 SessionEvidence，读取 ConfigVersion，运行 Scoring Engine。
- 记录使用的 `config_bundle_id`（nullable，旧 run 兼容）。
- 不直接生成报告；EvaluationRun 输出被 TrainingReportSnapshot 消费。
- diagnostics API 暴露评估元数据（包括 config 绑定信息）。

**归属**：`evaluation/` 评估层，是统一评估引擎的核心。

**禁止**：
- 不得在 EvaluationRun 内硬编码评分逻辑。
- 不得对 non-evaluable 场景返回伪分（必须返回 reason code）。

#### 1.5 TrainingReportSnapshot（训练报告快照）

**定义**：报告生成时的配置版本与评估结果冻结记录。

**边界**：
- 报告生成时固化：`config_bundle_snapshot`、`ruleset_version`、`score_basis`、`evidence_completeness`。
- 旧报告（#36 之前生成的）展示为 `legacy_unversioned`。
- 配置发布后，旧 Snapshot **不变**。
- 不可评估场景的 Snapshot 记录 `non_evaluable_reason`，不给伪分。

**归属**：`evaluation/` 评估层，是 Report Evidence Chain 的终点。

**禁止**：
- 不得批量迁移/重算历史报告。
- 不得在 evidence 不足时伪造分数或默认分。

#### 1.6 ConfigBundle / ConfigVersion（配置包与配置版本）

**定义**：统一管理所有影响业务口径的配置内容的版本化容器。

**ConfigBundle**：一个业务域的配置集合（如 "Sales Scoring"、"Presentation AI"、"Model Config"）。
**ConfigVersion**：ConfigBundle 的一个具体版本快照，有独立生命周期。

**边界**：
- ConfigVersion 生命周期：`draft → validated → published | rolled_back`。
- 每次 publish/rollback 写入 ConfigAuditLog。
- preview/dry-run **永不修改** active version。
- ConfigBundle 为只读建模提供 domain 分组；ConfigVersion 承载实际内容与状态。

**归属**：`admin/` 配置运营层，属于治理与配置系统。

#### 1.7 ConfigAuditLog（配置审计日志）

**定义**：所有配置变更的不可变审计记录。

**边界**：
- 记录：`actor`、`action`（publish/rollback）、`config_key`、`version_before`、`version_after`、`reason`、`trace_id`、`created_at`。
- 聚合自多个配置域的审计事件，但统一存储格式。
- 审计日志只读，不可编辑/删除。

**归属**：`admin/` 配置运营层。

#### 1.8 Supervisor（主管训练管理）

**定义**：主管视角的训练管理与复训决策能力。

**边界**：
- 团队 insights read model：完成率、个人短板、团队 Top3 共性问题、拜访准备度、复训候选。
- 依赖 TrainingTask 生命周期（#26）和 Snapshot 谱系（#37）。
- Supervisor 后端 (#38) 和前端 (#39) 分离交付。

**归属**：`supervisor/` 主管层。

#### 1.9 AI Governance（AI 治理与可解释性）

**定义**：追溯 AI 决策依据的治理视角。

**边界**：
- 从 session/report 追溯到：model、prompt、RAG、knowledge、scoring、evidence、evaluation、report lineage。
- 只读 API/UI，不提供编辑入口。
- 缺失数据展示可解释错误，不隐藏。

**归属**：`common/` 平台层（治理能力），UI 入口在 admin 区域。

#### 1.10 Sales/PPT Plugin（场景插件层）

**定义**：Sales Training Flow 和 Presentation Training Flow 作为场景插件接入统一平台。

**边界**：
- 两者共用：PracticeSession 生命周期、SessionEvidence 模型、EvaluationRun 评估框架、TrainingReportSnapshot 报告快照、ConfigBundle 配置版本治理。
- 差异点仅在场景插件层：
  - Sales：客户模拟、对话策略、销售评分维度映射。
  - PPT：页级要点检测、禁忌词检测、语义要点追踪。

**归属**：`sales_bot/` 和 `presentation_coach/` 为场景层；`common/` 为平台层。

**禁止**：
- 不得各自造一套完整闭环（各自的生命周期、证据模型、评估逻辑、报告格式）。
- 不得重引入 legacy Sales handlers（`base_sales_handler.py`、`enhanced_handler.py`、`simple_handler.py` 已删除且必须保持不存在）。

---

### 2. 实体关系

```
TrainingTask (1) ──< (0..N) PracticeSession
PracticeSession (1) ──< (0..N) SessionEvidence
SessionEvidence (N) ──> (1) EvaluationRun
EvaluationRun (1) ──> (0..1) TrainingReportSnapshot
EvaluationRun (0..N) ──> (1) ConfigVersion

TrainingTask (1) ──< (0..N) RetrainingTask   [nullable FK, 向后兼容]

ConfigBundle (1) ──< (1..N) ConfigVersion
ConfigVersion (1) ──< (0..N) ConfigAuditLog

PracticeSession ──> ConfigVersion   [通过 EvaluationRun 间接绑定]
TrainingReportSnapshot ──> ConfigVersion   [快照时冻结]
```

**核心闭环**：
```
TrainingTask → PracticeSession → SessionEvidence → EvaluationRun → TrainingReportSnapshot → RetrainingTask → (下一轮) TrainingTask
```

---

### 3. Sales Training Flow 与 Presentation Training Flow 共享契约

#### 3.1 共享接口

| 接口层 | Sales Training Flow | Presentation Training Flow | 共享方式 |
|--------|---------------------|---------------------------|----------|
| 生命周期 | PracticeSession lifecycle API | 同左 | 同一个 API |
| 证据 | SessionEvidence（转写、对话轮次） | SessionEvidence（转写、PPT 页码、要点覆盖） | 同一数据模型，通过 `evidence_type` 区分 |
| 评估 | EvaluationRun + ScoringRuleset | 同左 | 同一评估框架，通过 `subject` 区分 ruleset |
| 报告 | TrainingReportSnapshot | 同左 | 同一快照模型，通过 `scenario_type` 区分展示 |
| 配置 | ConfigBundle/ConfigVersion | 同左 | 同一配置系统，通过 `domain` 区分 |
| WebSocket | `/ws/sales` | `/ws/presentation` | 不同路由，但共享 `training_scenario_runtime` 主语 |

#### 3.2 不可共享部分（场景插件层）

- Sales：客户角色、追问策略、销售评分维度映射 → `sales_bot/`
- Presentation：PPT 页级检测、禁忌词检测、语义要点追踪 → `presentation_coach/`

#### 3.3 插件协议（#41 详细定义）

```
PluginProtocol:
  - lifecycle_hooks: { on_session_start, on_session_end, on_evidence_collect }
  - evaluation_subject: "sales" | "presentation"
  - report_context: { scenario_type, evidence_summary, score_basis }
```

---

### 4. ConfigBundle 迁移适配规则

#### 4.1 现有配置域映射

| 现有配置项 | 适配目标 | 迁移方式 | 实施 issue |
|-----------|---------|---------|-----------|
| BusinessRuleConfig（sales combinations） | ConfigBundle `domain="business_rules"` | 首个只读适配器 (#30)，不改变现有 API | #30 |
| ScoringRuleset | ConfigBundle `domain="scoring"` | 通过 adapter 接入 ConfigVersion 生命周期 | #32 |
| ModelConfig | ConfigBundle `domain="model"` | 纳入 ConfigBundle 只读视图 | #30 |
| KnowledgeConfigVersion | ConfigBundle `domain="knowledge"` | 纳入 ConfigBundle 只读视图 | #30 |
| VoiceRuntimeProfile | ConfigBundle `domain="voice_runtime"` | 纳入 ConfigBundle 只读视图 | #30 |
| Prompt templates / RAG profiles | ConfigBundle `domain="ai_analysis"` | 纳入 ConfigBundle 只读视图 | #30 |

#### 4.2 迁移原则

- **只读先行**（#30）：先建立 ConfigBundle/ConfigVersion 只读模型与首个 adapter，不改现有 API。
- **生命周期后加**（#31）：在只读基础上增加 draft/validate/preview/publish/rollback/audit。
- **接入已有配置**（#32）：ScoringRuleset 通过 adapter 进入统一生命周期。
- **新入口不删旧页面**（#33）：Config Center IA 新增入口，旧 admin pages 保留可访问。
- **API 前缀稳定**：`/api/v1/evaluation/admin/scoring-rulesets` 不迁移、不破坏。

#### 4.3 不可变规则

- dry-run / preview **永远不写** active version。
- 旧报告不重算。
- 配置发布不影响已生成的 Snapshot。
- 旧报告显示 `legacy_unversioned`，新报告显示具体版本信息。

---

### 5. 分层与模块归属

```
体验层 (Web Frontend)
├── 学员端：Dashboard、训练大厅、个人报告、复训任务
├── 主管端：团队报告、个人短板、复训下发
└── 管理端：配置中心、版本发布、审计回滚、AI 治理

业务应用层 (Backend Services)
├── common/        ：平台层 — PracticeSession、Evidence、ConfigBundle、AI Governance
├── sales_bot/     ：场景层 — 销售客户模拟、对话策略
├── presentation_coach/：场景层 — PPT 页级检测、禁忌词
├── evaluation/    ：评估层 — 统一 Scoring Engine、EvaluationRun、Snapshot
├── supervisor/    ：主管层 — 团队 insights、复训、校准
└── admin/         ：配置运营层 — Config Center、RBAC、审计

AI 能力层
├── Dialogue Orchestrator、Realtime Voice Runtime、Evidence Extractor
├── Scoring Engine、Weakness Analyzer、Recommendation Engine

治理与配置层
├── ConfigVersion / ConfigAuditLog / Dry-run / Test-run

基础设施层
├── PostgreSQL、Redis、ChromaDB、Object Storage、Observability
```

---

### 6. HITL 门禁（需人工审核）

以下 issue 在执行过程中必须在关键节点暂停，等待人工确认后方可继续：

| Issue | 标题 | HITL 暂停点 | 审核内容 |
|-------|------|------------|---------|
| #24 | 架构边界与领域契约锁定 | 本文档完成后 | 术语、边界、关系、禁止事项是否准确 |
| #27 | 学员仪表盘 TrainingTask 卡片 | 卡片 UI 实现完成后 | loading/empty/error/started/completed 状态视觉审查 |
| #29 | TrainingTask 详情页 | 详情页路由与 UI 完成后 | 权限、before_after 展示、关联会话展示 |
| #33 | Admin Config Center IA | 配置中心领域卡片实现后 | 领域卡片展示、迁移状态、legacy links 可见 |
| #34 | RBAC action-level 持久化 | 角色约束迁移前 | admin 保底测试、角色矩阵确认 |
| #38 | 主管训练管理中心后端 | 团队 insights API 完成后 | 空数据安全、权限正确、lineage 可解释 |
| #39 | 主管训练管理中心前端 | 主管仪表盘 UI 完成后 | 筛选器、权限、空状态视觉审查 |
| #40 | AI Governance explainability | Governance UI 实现后 | sales/presentation lineage 解释完整性 |
| #45 | Phase 5 Release Gate | Release gate 执行前 | secret scan、日志脱敏、OpenAPI parity、E2E manifest 全部通过 |

**HITL 执行规则**：
- agent 实现到 HITL 暂停点时，必须停止并输出当前状态摘要。
- 等待人工审核确认后，方可标记完成或继续后续步骤。
- HITL issue 的 completion note 必须包含人工审核证据。

---

### 7. AFK 自验标准

以下 issue 可由 AFK agent 自主实施，但必须满足全部自验条件：

| Issue | 标题 | AFK 自验条件 |
|-------|------|-------------|
| #25 | TrainingTask 数据模型/API/types | migration up/down smoke + pytest + tsc noEmit |
| #26 | TrainingTask 会话生命周期 | lifecycle integration tests + legacy handler absence check + regression |
| #28 | RetrainingTask ↔ TrainingTask | migration graph test + old null data compatibility + API tests |
| #30 | ConfigBundle/ConfigVersion 只读适配器 | migration + adapter contract tests + Config Center entry smoke |
| #31 | ConfigVersion 生命周期与 audit | publish/rollback audit tests + preview no-mutation tests |
| #32 | ScoringRuleset adapter/dry-run | dry-run read-only + non-evaluable + API prefix compatibility |
| #35 | 统一审计追踪 | aggregation + filter + pagination + diff tests |
| #36 | EvaluationRun 配置版本绑定 | new run binding + legacy null compatibility + diagnostics tests |
| #37 | TrainingReportSnapshot 谱系硬化 | snapshot immutability after config change + legacy compatibility |
| #41 | Sales/PPT plugin 契约对齐 | Sales/PPT regression + no legacy handler refs + plugin dispatch tests |
| #42 | Phase 4 E2E 基础设施 | manifest generation + provider transcript + DB seed/reset repeatability |
| #43 | Sales E2E | 3_clean_runs + manifest inspection + no socket mock |
| #44 | Presentation E2E | normal PPT path + corrupted PPT degradation + manifest |

**AFK 执行规则**：
- 每个 AFK issue 必须在其 completion note 中附带验证命令与结果。
- 验证失败 ≥3 次不得继续，必须记录为 blocker 并暂停。
- 不可变约束（invariant）被破坏必须立即停止，不得绕过。

---

### 8. 明确禁止的变更

以下变更在 #23 范围内**绝对禁止**，任何 agent 不得实施：

1. **重引入 legacy Sales handlers**：`base_sales_handler.py`、`enhanced_handler.py`、`simple_handler.py` 已删除，代码中不存在，禁止恢复。
2. **修改 Presentation Training Flow 行为**：现有 PPT 训练流程保持原样，仅通过插件协议薄适配。
3. **重算历史报告**：旧报告不批量更新，保持 `legacy_unversioned` 状态。
4. **删除或移动旧 admin config 页面**：Config Center 只新增入口，不删除 `/admin/scoring-rulesets`、`/admin/business-rules/sales-combinations` 等旧路径。
5. **使用 `any` / `@ts-ignore` / `@ts-expect-error` 绕过类型检查**。
6. **移动 scoring rulesets 稳定 API 前缀**：`/api/v1/evaluation/admin/scoring-rulesets` 不可迁移或破坏。
7. **dry-run/preview 写入 active version**。
8. **在证据不足时伪造分数或给默认分**。
9. **修改或关闭 parent issue #23**。
10. **将 TrainingTask 和 RetrainingTask 合并为单一不可回滚的大模型改造**。

---

### 9. 不变约束优先级

当 agent 遇到 PRD、issue body、ADR、CONTEXT 之间的冲突时，按以下优先级裁决：

```
不可变约束 (Section 8) > ADR/CONTEXT > 当前 issue body > PRD 推荐顺序 > agent 推断
```

---

### 10. 下游 issue 引用指南

后续 #25-#45 的 agent 在开始每个 issue 时，必须引用本文档进行自检：

**必读清单**（每个 issue 开始前）：
1. 本文档 `docs/adr/2026-05-11-architecture-boundary-domain-contract.md`
2. `CONTEXT.md`（领域语言）
3. Parent issue #23 body
4. 当前 issue body
5. 上游 blocked issue 的 completion note

**术语使用规则**：
- 实体使用本文档 Section 1 中定义的标准名称。
- 流程使用 CONTEXT.md 中的标准短语。
- 不自行创造新术语；如需新概念，先记录到 `.sisyphus/notepads/prd-23-full-implementation/issues.md` 并标记为 HITL。

**引用示例**：
> "按 ADR 2026-05-11 Section 1.1，TrainingTask 的状态机为 assigned→in_progress→completed，本实现不改变该状态集。"

---

### 11. 与现有 ADR 的关系

本 ADR 是 #23 系列最高层架构决策文档，依赖并扩展以下 ADR：

- **ADR 2026-03-14**（训练运行时主语）：本 ADR 的 PracticeSession 和 Training Flow 共享契约直接引用其结论。
- **ADR 2026-04-24**（评分治理）：本 ADR 的 ConfigBundle 迁移规则和 ScoringRuleset adapter 实现引用其版本化、dry-run、不变约束。

本 ADR 与上述 ADR 无冲突。如下游实施中发现冲突，优先级为：不可变约束 > 本 ADR > 上述 ADR。

---

## Consequences

### Positive

- #25-#45 的所有 agent 能以统一语言和边界实施，减少 context drift。
- 实体边界明确后，模块间不会出现耦合泄漏或重复实现。
- HITL/AFK 门禁清晰，人工审核点精确，AFK agent 自验标准可执行。

### Negative

- 一次性文档编写成本较高，但代价远小于后续 context drift 导致的重写。
- 新加入 agent 需要先阅读本文档（约 10 分钟），但后续所有 issue 可复用同一份知识。

## Follow-up

- 本 ADR 由 #24 完成并 review 后即生效。
- #25 和 #30 直接引用本文档作为实施起点。
- #41 引用本文档 Section 3 定义 Sales/PPT 插件协议。
- 如后续 issue 实施中发现本文档未覆盖的边界歧义，需追加补充 ADR 或记录到 `.sisyphus/notepads/prd-23-full-implementation/issues.md`。
