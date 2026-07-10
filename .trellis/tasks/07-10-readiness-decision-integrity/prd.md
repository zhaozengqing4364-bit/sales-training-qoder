# Readiness 复核决策完整性

## Goal

把“确认达标、要求重练、人工跟进”从复用记录读取权限和通用 OperationLog 的浅实现，收敛为权限独立、对象范围明确、幂等、并发安全、可审计、可回滚的 Readiness 决策闭环，确保真人语音对练闸门只能由可信人工决定驱动。

## What I Already Know

- 当前 `admin_create_readiness_review_action` 使用 `_require_records_viewer`；`operations/ops/sre` 具备 `view_records`，因此读取权限可执行复核写动作。
- 当前 `ReadinessDossierService.create_review_action()` 直接把业务状态写入 `SalesTrainerOperationLog.metadata`，并以时间戳生成重练任务 ID。
- 当前请求的 `request_id` 是 trace id，不是幂等键；重复点击、网络重试和并发提交没有业务去重或版本冲突语义。
- 当前 Dossier 只读取最近有限数量的通用日志来重建复核状态。
- 当前前端复核表单默认选择 `approve`，直接提交，没有高风险决定确认步骤。
- 已有详细实施计划：`docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`。
- 该任务是新人训练 P0/P1 修复总计划的第一项，路径前置闸门和学习专题 Attempt 证据在独立任务处理。

## Assumptions (Temporary)

- 新建专用 `sales_trainer_readiness_review_actions` 表作为新决策业务真源；OperationLog 只作为同事务审计 Adapter。
- 历史 OperationLog 不删除；Dossier 在兼容期双读，并通过 `audit_log_id` 去重。
- additive migration 在生产回滚时保留；只有尚未产生新业务数据的环境执行 schema downgrade。

## Open Questions

- 无。

## Requirements (Evolving)

### 权限与对象范围

- `view_records` 只允许读取，不授予任何 Readiness 写动作。
- 新增独立 capability `review_readiness` 和后端 guard。
- 平台管理员拥有全局 `review_readiness`。
- 培训负责人拥有部门范围 `review_readiness`，只能复核与自己部门相同的 learner；具体兼容角色继续由现有 `is_sales_trainer_manager()` 和 `SALES_TRAINER_MANAGER_ROLES` allowlist 决定，不新增第二套角色映射。
- ops 可以继续查看全局训练记录和 Dossier，但 `review_readiness=false`。
- 内容管理员、普通用户和其他无复核责任角色不得执行 Readiness 写动作。
- 后端业务 Module 必须再次校验 actor 权限和 learner 部门范围，不能只依赖前端隐藏或 route guard。
- 越权访问返回稳定业务错误，不泄露其他部门 learner 是否存在。

### 决策持久化

- 新建专用 Readiness review action 表，保存 learner、actor、角色、decision、reason、能力项、证据、重练任务、幂等信息、前一版本、审计日志引用和创建时间。
- `approve`、`require_retraining`、`mark_manual_follow_up` 是唯一允许的决定。
- MVP 采用 append-only history；后续合法决定成为最新状态，不提供撤销动作或复核人委派。
- 重练任务 ID 使用稳定 action ID 派生，不使用浮点时间戳。
- 新业务状态只写专用表；同 transaction 写 OperationLog。

### 幂等与并发

- `idempotency_key` 和 `expected_latest_review_action_id` 在新契约中直接设为必填；后端、第一方 Web 页面和测试在同一发布切片协调升级。
- `expected_latest_review_action_id` 的请求 key 必须存在；没有历史决定时值为 `null`，不能通过省略字段绕过并发前置检查。
- 同一 `actor_id + idempotency_key` 只产生一条业务决策和一条对应审计记录。
- 幂等重放必须比较请求 hash；相同 key 携带不同业务内容返回 409。
- 每次写入携带 `expected_latest_review_action_id`；与当前最新动作不一致时返回 `[READINESS_REVIEW_VERSION_CONFLICT]`。
- 并发版本基线同时考虑专用 action 与历史 OperationLog；历史最新动作使用其 `log_id`，新 action 的审计镜像不重复参与版本选择。
- 同一 learner 的写入使用数据库行锁串行化。
- 网络失败重试复用原 token；用户修改 decision/reason/evidence/capability 后生成新 token。

### 兼容读取与 UI

- Dossier 合并专用表和历史 OperationLog，按时间倒序，并按 audit log 去重。
- ops 可以查看 Dossier，但看不到复核表单，也不能直接调用写 API。
- approve、require_retraining 和 manual follow-up 提交前展示明确确认内容；不得使用模糊“确定”。
- 409 冲突时刷新 Dossier，提示用户重新确认，不自动覆盖或自动重放。
- 普通管理 UI 不展示 `state_storage`、内部 task ID、raw JSON 或 trace id。

### 审计与发布

- 审计包含 actor、角色、learner、decision、requestId、IP、User-Agent、证据和能力项引用，不记录敏感训练原文。
- 权限矩阵、幂等、并发、双读、直接 API 越权和前端确认测试进入 `critical-quality-gate.sh`。
- API 契约和新人训练闭环 ADR 同步更新。

## Acceptance Criteria (Evolving)

- [ ] `operations` 的 `view_records=true`、`review_readiness=false`，POST review action 返回 403。
- [ ] 平台管理员可复核任意部门 learner。
- [ ] 培训负责人只能复核本部门 learner；跨部门返回 404。
- [ ] `support`、`training_lead`、`training_manager` 按现有 manager allowlist 获得相同部门范围；allowlist 配置为空时 fail-closed。
- [ ] 相同 actor、相同 idempotency key、相同请求重复提交返回同一 action，数据库只存在一条业务记录和一条审计日志。
- [ ] 相同 idempotency key 携带不同请求内容返回 `[READINESS_IDEMPOTENCY_KEY_REUSED]` 409。
- [ ] 陈旧 `expected_latest_review_action_id` 返回 `[READINESS_REVIEW_VERSION_CONFLICT]` 409，原决定不被覆盖。
- [ ] 存在 legacy OperationLog 最新决定时，携带其 action/log ID 可以创建第一条专用 action；错误地携带 `null` 返回 409。
- [ ] approve 仍要求 Dossier 为 `pending_review` 且存在有效证据。
- [ ] approve 成功后 realtime gate 开放；require retraining/manual follow-up 后 gate 保持关闭。
- [ ] 历史 OperationLog 动作仍可见，新动作以专用表为状态来源，且不会双重显示。
- [ ] 前端首次操作进入明确确认状态，确认后才发送请求；提交中禁止重复点击。
- [ ] 所有定向 backend/frontend tests、Ruff、ESLint、TypeScript type-check 通过。
- [ ] 新测试进入 critical quality gate，migration upgrade 和安全回滚策略得到验证。

## Definition of Done

- Tests added/updated: permission unit tests, decision service unit tests, Dossier unit tests, API integration tests, frontend Vitest tests.
- Ruff、相关 mypy、ESLint、`tsc --noEmit` 和定向测试通过。
- API contract、ADR、Trellis executable spec 根据最终实现更新。
- Migration、部署顺序、应用回滚和兼容双读得到验证。
- 实施开始时重新读取 Alembic head；migration revision/down_revision 必须基于当时真实 head，不能盲用计划中的预留编号。
- 无新增第三方依赖，无无关重构，无普通 UI 内部字段泄露。

## Expansion Sweep

### Future Evolution

- 未来可能需要委派复核人、二级审批或按部门配置 reviewer；MVP 只保留 capability 和 actor 字段的演进空间，不实现审批流引擎。
- 专用决策表未来可支持撤销/替代关系；MVP 使用 append-only action history 和 expected latest id。

### Related Scenarios

- Readiness 决策继续驱动 realtime gate 和 retraining projection，不能在本任务中改变主路径完成算法。
- 工作台分页/规模化统计是独立问题，本任务只保证单 learner 决策正确性和读取兼容。

### Failure and Edge Cases

- 重复点击、网络超时重试、同 key 异内容、两名培训负责人并发决定、跨部门对象、历史日志双读去重、migration 回滚。
- 审计日志写入失败必须让整个决策 transaction 失败，不能出现“业务成功但无审计”。
- 决策 transaction 只包含数据库校验、行锁、action 写入和审计 flush，不加入通知、HTTP 或其他慢速外部 IO。

## Out of Scope

- 新人路径 `unlock_after_unit_ids` 闸门修复。
- 商务礼仪/客户问答 Learning Topic Attempt 统一。
- Readiness Workbench 前 100 人、内存筛选和串行查询性能整改。
- 通用审批流、多人会签、撤销决定、通知系统。
- 复核人委派、转交和按 learner 指派 reviewer。
- 修改 AI 评分 Prompt、模型配置或通过线。
- 重构整个 `ReadinessDossierService`、`TrainingJourneyService` 或全局 RBAC。

## Technical Approach

- 建立 `ReadinessReviewActionService` 深 Module，集中权限、对象范围、行锁、幂等、并发、状态写入和审计。
- 建立专用 ORM model 和 additive Alembic migration；旧 OperationLog 保持只读兼容来源。
- `ReadinessDossierService` 负责证据与 approve 前置校验，然后调用决策 Module；不再直接写 OperationLog。
- 前端继续允许有 `view_records` 的角色访问档案，但只对 `review_readiness` 展示写表单。
- API 请求增加 `idempotency_key`、`expected_latest_review_action_id`，响应兼容保留现有展示字段并扩展状态来源。

## Research References

- [`research/repository-write-integrity-patterns.md`](research/repository-write-integrity-patterns.md) — 仓库现有 client token、append-only revision、专用业务记录和 OperationLog 模式支持“专用 action 表 + 审计 Adapter”的方案。

调用方扫描只发现第一方 Web domain/page、后端测试和 API 契约，没有发现第二个运行时客户端。因此 MVP 采用协调发布的强契约，不保留缺少幂等/并发前置字段的静默兼容写入口。

## Decision (ADR-lite)

**Context:** 通用审计日志无法稳定承载业务状态、幂等唯一约束和并发版本；复用记录读取权限也无法表达复核责任。

**Decision:** 新建专用 append-only Readiness review action Module/table，使用独立写 capability、请求 hash 幂等和 expected-latest 乐观并发；OperationLog 降为同事务审计 Adapter，Dossier 在兼容期双读。`review_readiness` 只授予平台管理员和培训负责人：平台管理员为全局范围，培训负责人为本部门范围；ops 保持记录只读。`idempotency_key` 和 `expected_latest_review_action_id` 采用前后端协调发布的必填契约。MVP 仅支持 `approve`、`require_retraining`、`mark_manual_follow_up` 三种 append-only 决策，不实现撤销或复核人委派。

**Consequences:** 增加一个 additive table 和协调发布字段；换来明确权限、可靠状态、可追溯并发和可测试回滚。历史日志不会自动获得完整 lineage，只作为 `operation_log` legacy action 展示。

## Technical Notes

- 现有 route：`backend/src/sales_trainer/api.py::admin_create_readiness_review_action`
- 现有权限：`backend/src/sales_trainer/permissions.py::can_view_sales_trainer_records`
- 现有状态写入：`backend/src/sales_trainer/services/readiness_dossier_service.py::create_review_action`
- 现有审计 Adapter：`backend/src/sales_trainer/services/operation_log_service.py`
- 现有前端：`web/src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx`
- 实施计划：`docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`
- 总计划：`docs/superpowers/plans/2026-07-10-newcomer-training-p0-p1-remediation-index.md`
- 相关领域契约：`CONTEXT.md`、`docs/product/newcomer-training-v0.9-usable-loop.md`、`docs/adr/2026-06-27-newcomer-training-closed-loop.md`

## Implementation Plan (Small PRs)

- **PR1 — 权限契约**：新增 `review_readiness`、后端 guard、部门范围角色矩阵、前端只读/可写能力投影。
- **PR2 — 决策持久化**：additive migration、专用 action model、请求 hash、learner row lock、幂等和 expected-latest 冲突测试。
- **PR3 — Dossier 兼容**：Dossier 编排新 Module、领域错误转换、新表/legacy OperationLog 双读和 audit-log 去重。
- **PR4 — 前端安全提交**：必填 token/version、明确确认、网络重试复用 token、编辑后换 token、409 刷新。
- **PR5 — 治理门禁**：API 契约、ADR、critical gate、migration upgrade/应用回滚验证。
