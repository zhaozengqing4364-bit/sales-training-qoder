# 新人训练完整闭环优化总计划

> **历史 / Superseded（2026-07-16）：** 本任务关于 Realtime 首发、Phase/Module 和 Enrollment rollout 的决策已由 [`../07-16-foundation-contracts-baseline/prd.md`](../07-16-foundation-contracts-baseline/prd.md) 及 [`../../../docs/newcomer-foundation-contract-index.md`](../../../docs/newcomer-foundation-contract-index.md) 取代。本文只保留历史证据，不得作为新实现权威。

## Goal

把新人训练路径从“已有异步训练骨架”升级为可长期运营的完整闭环系统：角色、学员等级、训练阶段都可区分；内容、配置、权限、训练、报告、可视化、审计和测试形成闭环；前后端契约紧密一致；没有伪成功、死数据、不可流通数据和靠前端隐藏的权限。

本任务最初是总规划任务；后续 `/goal` 已扩大为全量实现与验收任务。当前 PRD 保留原始目标、决策和验收口径，真实执行状态以 [`execution-plan.md`](execution-plan.md) 的阶段总账、验证记录和最终门禁证据为准。

## What I Already Know

- 用户明确要求“完整闭环一整个流程训练”，不是只修一个页面。
- 用户确认三类等级都要覆盖：角色等级、学员等级、训练阶段等级。
- 用户确认新人训练路径不用强制顺序解锁。
- 用户确认实时对练要纳入新人训练完整闭环。
- 用户确认 learner 首页 catalog fallback 应废弃，active path revision 成为唯一真源。
- 用户确认 AI Coach 是首版闭环必过能力。
- 10 个 Agent 已完成只读审计，汇总见 [`research/audit-synthesis.md`](research/audit-synthesis.md)。
- 当前系统已有 path revision、材料、文章、考卷、录音评分、AI Coach、训练记录、后台工作台等基础。
- 当前风险集中在单一真源、权限粒度、配置校验、历史快照、前后端契约、UI/UX 可视化和测试门禁。

## Requirements

### R1. 三类等级模型

- 角色等级必须覆盖 learner、content_admin/newcomer_content_admin、training_lead/training_manager/support、ops/operator/sre、admin/super_admin。
- 学员等级必须成为可配置、可展示、可筛选、可授权的业务维度。
- 训练阶段等级必须覆盖未开始、进行中、已完成、未通过需重练、未解锁、已停用、异常等状态。
- 三类等级都必须能进入权限、内容可见性、路径展示、管理筛选和审计语义。

### R2. 路径配置唯一真源

- learner 首页和训练入口只能消费 active path revision projection。
- 旧 catalog fallback / unit backfill 不得继续产生新的正式训练数据。
- 缺 active path revision 时返回可诊断状态，不展示伪成功。
- 旧 fallback 只允许用于迁移、只读诊断和历史兼容。

### R3. 非强制顺序解锁

- 系统不强制学员按顺序完成模块。
- UI 必须展示每个模块的完成条件、当前阶段、可见性、未开放原因、下一步动作。
- 不同模块可以并行进入，但后端仍要校验每个模块自己的必要绑定和发布状态。

### R4. 实时对练纳入闭环

- 实时对练不再长期作为纯 disabled/coming-soon 占位。
- 接入前必须补 ADR、API 契约、运行时边界、权限、配置、发布、回滚、错误语义。
- realtime session 结果必须进入 TrainingJourney、训练记录、管理端可视化和审计。
- 不允许绕开 `sales_trainer` path revision 和权限治理直接创建无治理 `PracticeSession`。

### R5. AI Coach 首版必过

- AI Coach 是完整闭环必过模块。
- AI Coach 配置必须校验 prompt/scoring prompt 真实存在、已发布、用途匹配。
- 模型、temperature、timeout、retry、max tokens、成本阈值、降级策略必须集中治理。
- AI Coach 输出失败必须有可恢复 UI 和后台诊断。
- AI Coach session 必须写入 journey、训练记录、可视化和审计。

### R6. 后端权限和对象级授权

- 后端接口必须 fail-closed，不能只靠前端隐藏。
- 材料文件、文章、考卷、录音、测验记录、AI Coach、实时对练都要校验用户是否可访问当前路径、单元、学员等级和训练对象。
- content_admin 不得查看学员训练记录。
- training_lead/training_manager/support 只看部门范围训练记录，不看全局日志和系统设置。
- ops 可看全局记录、日志、配置健康、重试/重评，但不能改内容。
- admin/super_admin 全量管理。

### R7. 配置治理

- 可调整业务规则必须有默认值、校验、fallback、读取层、诊断和审计。
- path payload 必须校验 path_key、module_key、order_index、completion_rule、module_type、绑定对象、learning_units。
- 发布必须有 impact preview。
- rollback 必须保留 preview、reason、trace_id。
- provider/ASR/Deucate/上传限制必须形成统一运行时配置快照或明确 env-only 运维边界。

### R8. 内容资产和历史快照

- 历史结果展示必须 snapshot-first。
- 音频评分必须使用 submission 创建时冻结的 prompt 内容或 prompt revision。
- 历史材料即使当前归档，也必须可通过正式回放接口只读访问。
- 资产归档必须检查 active path/template 引用。
- 无法完整回填的历史数据必须显式标记 legacy_snapshot_only 或 regrade_unavailable。

### R9. TrainingJourney 聚合

- 新增或明确一个新人训练 journey aggregate。
- 聚合 path revision、module progress、audio submission、paper attempt、business etiquette quiz、AI Coach session、realtime session、remediation、regrade、retry。
- 状态机集中管理，前端消费机器可读状态策略，不自行推断业务状态。

### R10. 前后端契约一致

- 前端 DTO 不得允许构造后端必拒的数据。
- admin 页面不能用 learner 接口推断后台绑定状态。
- 错误码、trace_id、fallback_applied、fallback_reason 必须稳定传递。
- capability 必须控制 sidebar、workbench card、module nav、按钮和直链页。

### R11. UI/UX 和可视化

- learner 首页升级为训练看板，展示全部可访问内容、核心路径、三类等级、阶段状态、未开放原因、下一步。
- 管理端提供新人训练分析页或强化工作台，至少包含完成漏斗、模块通过率、能力弱项热图、风险学员队列、部门/等级对比、趋势。
- 管理列表必须支持分页、时间范围、部门、学员、角色等级、学员等级、训练阶段、模块、状态、通过结果、是否补救等筛选。
- 移动端不能表格破版，复杂表格必须卡片化或提供明确横向滚动。

### R12. 测试与发布门禁

- 必须新增完整新人训练 E2E。
- 必须覆盖权限矩阵、配置缺失/非法/disabled/fallback、历史快照、dead data、AI Coach、实时对练。
- 销售训练核心测试必须进入 CI gate。
- 真实 provider 测试纳入 nightly/release 策略。

## Acceptance Criteria

- [x] 文档记录所有 10 个 Agent 审计发现和用户最新决策。
- [x] 文档明确 P0/P1/P2 风险分级。
- [x] 文档明确三类等级模型。
- [x] 文档明确无需强制顺序解锁的产品行为。
- [x] 文档明确实时对练纳入完整闭环的 ADR/契约前置要求。
- [x] 文档明确 AI Coach 首版必过的治理要求。
- [x] 文档明确废弃 learner catalog fallback 和 active path revision 唯一真源策略。
- [x] 文档拆出可执行阶段路线。
- [x] 文档列出可拆分后续任务。
- [x] 文档列出测试和验收矩阵。
- [x] Trellis implement/check context 已登记相关 spec 和研究文件。

## Implementation Status

- 原规划验收项已闭环到 [`execution-plan.md`](execution-plan.md) 的“审计问题归属总账”“已执行验证记录”和“Phase 9 Final Gate 记录”。
- 逐项审计索引见 [`audit-closure-matrix.md`](audit-closure-matrix.md)。
- 最终验收报告见 [`final-verification-report.md`](final-verification-report.md)。
- 外部凭证与生产回填执行路径见 [`external-verification-runbook.md`](external-verification-runbook.md)。
- 完整门禁证据：`.sisyphus/evidence/task-9-quality-gate.txt`，`bash scripts/critical-quality-gate.sh` 已通过。
- 外部 provider 执行状态：
  - AI Coach real provider stream：2026-06-29 06:06 CST 已使用真实 DeepSeek/OpenAI-compatible provider 执行通过，证据为 `.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json`；复跑需要真实 `LLM_API_KEY` 或 `OPENAI_API_KEY`。
  - Realtime real provider gate：2026-06-29 06:05 CST 已使用 `step-audio-2.3` 执行到 StepFun 上游，但上游返回 HTTP 401 `upstream_auth_rejected`；开放平台 URL 与候选 Step Plan URL 均复现，复跑和闭环通过需要有效且已授权 realtime/model 的 `STEPFUN_API_KEY`。
- 仍需产品/运维决策才能进入生产治理闭环：
  - 学员等级首版枚举与人工/自动来源。
  - 历史生产数据回填策略与不可回填数据标记口径。
  - git 历史疑似 secret/token 的轮换、清史和回写判定。

## Technical Approach

采用“总计划 + 分阶段任务拆解”的方式推进：

1. 先固化契约和 ADR，避免继续在旧 fallback 和新 revision 之间摇摆。
2. 先修权限和对象级授权，再扩展内容和 UI。
3. 先收口 active path revision，再建立 TrainingJourney。
4. AI Coach 和实时对练都进入完整闭环，但通过分阶段接入，避免一次性大爆炸。
5. 每个阶段都要求测试先行或至少补覆盖关键风险的测试。

## Decision (ADR-lite)

### Context

当前系统已有大量销售训练和新人训练能力，但多个 Agent 审计显示：路径真源、权限、配置、内容快照、前端契约和测试门禁仍存在结构性风险。若直接继续加功能，会把完整闭环建立在兼容层和伪配置上，后续难以审计和回滚。

### Decision

- active path revision 是 learner 路径唯一真源。
- 三类等级都纳入系统模型。
- 不强制顺序解锁。
- 实时对练纳入新人训练闭环，但先补契约和 ADR。
- AI Coach 首版必过。
- 先做规划文档和任务拆分，再逐阶段实施。

### Consequences

- 短期会增加契约、迁移和测试工作量。
- 可以避免继续扩大前后端漂移和历史数据不可解释问题。
- 后续实现必须按 P1 风险优先，不应先做纯视觉优化。

## Implementation Plan

### Milestone 0：契约冻结

- 更新 ADR 和 `docs/api-contract/sales-trainer.md`。
- 定义 TrainingJourney、ModuleProgress、ModuleOutcome、RoleCapability、LearnerLevel、TrainingStage。

### Milestone 1：权限与安全

- 修材料对象级授权。
- 收紧 logs/settings。
- 修商务礼仪测验记录权限。
- 修 article-progress 任意内容访问。
- 加 manager roles allowlist。
- 加审计。

### Milestone 2：配置与路径真源

- 禁止 learner fallback 伪成功。
- 补 path payload validation。
- 加 publish impact preview。
- 加 config health/dependency graph。
- 统一 provider readiness。

### Milestone 3：内容快照与死数据

- 音频 prompt revision/snapshot。
- 历史材料回放。
- 资产引用归档保护。
- legacy 数据标记与 backfill。
- dead data dashboard。

### Milestone 4：TrainingJourney

- 建 journey aggregate。
- 集中模块状态机。
- 纳入 audio、paper、business etiquette、AI Coach、realtime。

### Milestone 5：AI Coach 必过

- 配置治理。
- session 入 journey。
- 失败兜底。
- 管理端诊断。

### Milestone 6：实时对练

- ADR。
- runtime binding。
- 权限与配置。
- 结果入 journey/dashboard。

### Milestone 7：前端和可视化

- capability 五层 fail-closed。
- learner 训练看板。
- admin analytics。
- 列表治理。
- 移动端和 a11y 验收。

### Milestone 8：测试门禁

- 后端 closed-loop integration。
- Playwright E2E。
- contract tests。
- CI gate。
- nightly/release provider smoke。

## Out of Scope

- 不提交生产破坏性迁移。
- 不操作真实生产数据。
- 不内置真实第三方 API 密钥。
- 不解决与新人训练闭环无关的既有 dirty worktree 改动。

## Technical Notes

- 关键研究汇总：[`research/audit-synthesis.md`](research/audit-synthesis.md)。
- 主要契约：`docs/api-contract/sales-trainer.md`。
- 主要架构：`docs/architecture.md`、`docs/architecture/config-asset-center.md`。
- 后端规范：`.trellis/spec/backend/index.md`、`.trellis/spec/backend/business-rule-configs.md`、`.trellis/spec/backend/error-handling.md`、`.trellis/spec/backend/logging-guidelines.md`。
- 前端规范：`.trellis/spec/frontend/index.md`、`.trellis/spec/frontend/admin-console-patterns.md`、`.trellis/spec/frontend/type-safety.md`、`.trellis/spec/frontend/quality-guidelines.md`。
- 跨层思考：`.trellis/spec/guides/cross-layer-thinking-guide.md`。

## Open Questions

- 学员等级的首版枚举和来源：用户表字段、组织分层、后台配置，还是训练数据自动计算。
- 历史生产数据回填策略：哪些记录可回填 revision，哪些只能标记 `legacy_snapshot_only` 或 `regrade_unavailable`。
- 真实 provider smoke 的凭证来源、secret 轮换和是否在人工 release dispatch 时强制启用真实 provider required 模式。

## Definition of Done

- PRD、审计总账、执行计划和验证证据落盘。
- P0/P1/P2 审计问题均在执行计划中标记处理结果、验证命令和剩余外部条件。
- 新人训练完整闭环进入 `scripts/critical-quality-gate.sh` 并通过本地 deterministic 门禁。
- 未执行的真实第三方 provider 路径明确列为外部凭证项，不被计作绿色完成。
