# 架构审计优化修复计划

## Goal

基于 Brooks 架构审计结果，制定并执行一组可分阶段落地的架构优化计划：优先修复 shared kernel 反向依赖、业务域互相导入、跨域运行态聚合、权限知识重复、前端 API 面过宽与测试 seam 不足，降低后续销售训练和课程训练功能迭代的变更半径。

## What I already know

- 用户要求“制作详细的优化，修复计划”，上下文来自刚完成的 `$brooks-audit` 架构审计。
- 后端是 FastAPI 模块化单体，`backend/src/common/` 是 shared kernel。
- 架构文档明确要求场景隔离：共享逻辑放入 `common/`，场景模块不要互相污染。
- 当前静态扫描发现顶层循环依赖：
  - `common <-> sales_trainer`
  - `common <-> curriculum_practice`
  - `curriculum_practice <-> sales_trainer`
  - `agent <-> common`
  - `support <-> presentation_coach`
- `router_registry.py` 的高 fan-out 属于 composition root，不作为主要问题。
- 当前工作区存在大量未提交改动，本任务默认先规划，不直接改现有功能代码。

## Assumptions (temporary)

- 本次目标是制定可执行修复计划，并在用户确认后进入实现；不是立即大规模重构。
- 优先级应按架构风险排序：先修依赖方向和跨域边界，再处理 API 面宽和局部 seam。
- 现有外部 API 行为应保持兼容；修复应优先通过内部边界调整完成。
- 销售训练相关业务仍在快速迭代，因此计划必须拆成小 PR，避免一次性触碰过多模块。

## Open Questions

- 最终确认：是否按完整优化包 PR1-PR7 进入实现阶段。

## Requirements (evolving)

### MVP scope decision

- 本任务采用完整优化包：PR1-PR7 全部纳入本轮优化计划。
- 范围包含后端依赖边界、support runtime contributor、AI Coach 测试 seam、权限 capability projection、前端 API 第一阶段拆分和组件类型泄漏修复。
- 实施时仍按小 PR / 小提交顺序推进，不做一次性大重构。

### R1. Break shared-kernel reverse dependency

- `common` 不应直接 import `sales_trainer`、`curriculum_practice` 或其他具体业务域。
- Dashboard 推荐逻辑改为通过 provider/registry/port 调用业务域贡献者。
- `sales_trainer` 可实现推荐 provider，但注册发生在组合根或 domain registration 中。
- Dashboard API 响应保持兼容。

### R2. Introduce anti-corruption boundary between `curriculum_practice` and `sales_trainer`

- 不再让 `curriculum_practice` 直接读取 `sales_trainer` 的资产修订 ORM 模型。
- 不再让 `sales_trainer` 直接依赖课程题库 ORM 内部形态作为自身规则边界。
- 建立共享的 asset lineage / question bank port，或者明确一个上游 domain adapter。
- 保留当前业务能力：销售训练可以引用课程题库，课程资产修订可以关联训练资产版本。

### R3. Split support runtime aggregation into contributor model

- `support` 不再直接 import 多个业务域内部服务。
- 各业务域提供 runtime health contributor，返回稳定诊断 payload。
- `support` 只聚合 contributor 输出。
- 保持 `/api/v1/support/runtime` 现有 API 行为兼容。

### R4. Add testability seam for AI Coach orchestration

- `AiCoachChatService` 支持注入 store/runtime/scorer/events/logs/session_creator 等 collaborator。
- 生产默认构造不变，测试可直接注入 fake。
- 现有 AI Coach chat 行为不变。

### R5. Centralize sales trainer permission capabilities

- 后端继续作为权限权威。
- 增加 sales trainer admin capability projection，例如可管理内容、查看记录、全局记录、重试任务、查看日志、管理高风险 prompt。
- 前端 admin sidebar 基于 capability 渲染，不再复制 role string 分支。
- 兼容现有 role 名称和前端显示。

### R6. Narrow frontend API blast radius

- 保留 `api` facade 作为页面入口。
- 将 `types.ts` 和 `client.ts` 内的销售训练、课程训练、support runtime 等 domain 类型/方法逐步拆到 domain files。
- 页面不直接 import domain builder。
- 不做全量一次性拆分，先围绕当前 sales trainer / support / admin domain 做最小可验证切片。

### R7. Fix frontend layer leak

- 将 `AssetRefPickerOption` 从组件文件移动到 `web/src/lib/admin/asset-ref-types.ts` 或同等 contract 文件。
- 组件和 preflight 校验共同依赖 contract 类型。

## Acceptance Criteria (evolving)

- [ ] 静态依赖扫描不再出现 `common -> sales_trainer`。
- [ ] 静态依赖扫描不再出现 `curriculum_practice <-> sales_trainer` 的直接 ORM model 互引；如仍有边，应通过明确 adapter/port 文件表达。
- [ ] `support` runtime service 不直接 import `sales_bot` / `presentation_coach` / `curriculum_practice` 内部服务。
- [ ] AI Coach orchestration tests 可以通过构造参数注入 fake collaborator，不需要写 `service.__dict__` 覆盖内部字段。
- [ ] 前端 admin sidebar 不再重复维护 sales trainer role string 判断，改用后端 capability 或集中权限 projection。
- [ ] 前端 API facade 仍保持现有页面调用方式，但 sales trainer / support / admin 第一阶段 domain 类型和方法从巨型文件中拆出。
- [ ] `web/src/lib/admin/template-form-preflight.ts` 不再从 `components` 层导入类型。
- [ ] 相关后端 unit/integration/contract tests 更新并通过。
- [ ] 相关前端 Vitest/typecheck 更新并通过。
- [ ] API contract 文档更新任何新增 capability/provider payload。

## Definition of Done (team quality bar)

- Tests added/updated (unit/integration where appropriate)
- Lint / typecheck / CI green
- Docs/notes updated if behavior changes
- Rollout/rollback considered if risky
- 依赖方向符合 `backend/src/common/` shared kernel 约束
- 可调整业务规则和权限映射不新增硬编码散落点

## Technical Approach

### Selected roadmap: complete optimization package, boundary-first, small PRs

#### PR1: Dashboard recommendation provider boundary

- Add a recommendation provider port under a neutral layer.
- Move sales-trainer-specific path recommendation out of `common/api/dashboard.py`.
- Register the sales trainer provider from a domain registration or app composition location.
- Add/adjust tests for dashboard recommendation parity.
- Verification:
  - Targeted backend unit/integration tests for dashboard recommendation.
  - Static check: no `sales_trainer` import from `backend/src/common/api/dashboard.py`.

#### PR2: Curriculum / Sales Trainer anti-corruption contracts

- Extract asset lineage access into a neutral service/port.
- Replace direct imports:
  - `curriculum_practice -> sales_trainer.models`
  - `sales_trainer -> curriculum_practice.models`
- Keep current question and revision behavior unchanged.
- Verification:
  - Sales trainer question bank tests.
  - Curriculum revision lineage tests.
  - Static edge scan for direct model imports.

#### PR3: Support runtime contributor registry

- Define `RuntimeHealthContributor` contract.
- Each domain exposes its own contributor module.
- Support runtime aggregates contributor outputs.
- Verification:
  - Support runtime API contract tests.
  - Unit tests for contributor aggregation.

#### PR4: AI Coach dependency injection seam

- Extend `AiCoachChatService.__init__` with optional collaborator parameters.
- Replace tests that patch `__dict__` with explicit fakes.
- Verification:
  - AI Coach unit tests.
  - No behavior change in public session/send/submit flows.

#### PR5: Permission capability projection

- Add backend capability payload for sales trainer admin navigation and scoped actions.
- Update frontend admin sidebar to consume capabilities.
- Keep role labels and existing route guards compatible.
- Verification:
  - Backend permission unit tests.
  - Frontend sidebar tests for admin/content/training lead/ops.

#### PR6: Frontend API narrowing, first slice

- Move sales trainer and support runtime API DTOs/methods into domain-specific files behind the same `api` facade.
- Avoid route/page-level duplicate types.
- Verification:
  - `web/src/lib/api/*` tests.
  - `npx tsc --noEmit`.

#### PR7: Frontend type leak cleanup

- Move `AssetRefPickerOption` to a `lib/admin` contract file.
- Update component and preflight imports.
- Verification:
  - Template preflight tests.
  - Typecheck.

## Decision (ADR-lite)

**Context**: Brooks audit found architecture decay concentrated in dependency direction and bounded-context leakage, not a simple local bug.

**Decision**: Execute the complete optimization package PR1-PR7. The implementation order remains boundary-first: backend dependency cycles first, support/testability/permission governance second, frontend API and type cleanup third.

**Consequences**: This reduces long-term change propagation across backend and frontend, but requires careful sequencing because several fixes touch cross-layer contracts. Some direct imports may remain temporarily as registered adapters, but they must be documented as transitional and not hidden inside shared kernel code.

## Configuration / Governance Judgment

- Stable code logic:
  - Provider registration mechanics.
  - Dependency direction rules.
  - Adapter interfaces and typed payload contracts.
  - Test seam wiring.
- Configurable business rules:
  - Permission-to-navigation mapping should be exposed as backend capability projection or governed policy, not duplicated in page components.
  - Sales trainer thresholds, labels, remediation actions, and policy toggles must stay in `common/business_rules`, not in frontend constants.
- New config required:
  - No new business-rule config is required for PR1-PR4.
  - PR5 may require a capability projection endpoint or inclusion in existing current-user/admin metadata, but not necessarily a new business-rule table.
- Existing config reused:
  - `common/business_rules` for adjustable thresholds/actions.
  - `sales_trainer.permissions` as backend permission authority until capability projection is introduced.
- Missing/invalid config handling:
  - Existing business-rule fallback semantics should remain unchanged.
  - Capability projection should fail closed: absent permission means no privileged action rendered.

## Out of Scope

- Full rewrite of `web/src/lib/api/types.ts`.
- Full extraction of all domain services into separate packages.
- Changing public API response shapes unless required for capability projection and documented.
- Reworking all support runtime diagnostics at once if PR3 can preserve existing payloads through adapters.
- Changing business behavior of AI Coach, dashboard recommendations, training records, or question grading.
- Committing or cleaning unrelated dirty files in the current worktree.

## Technical Notes

- Research reference: `research/codebase-architecture-findings.md`.
- Relevant backend specs:
  - `.trellis/spec/backend/directory-structure.md`
  - `.trellis/spec/backend/business-rule-configs.md`
  - `.trellis/spec/backend/error-handling.md`
  - `.trellis/spec/backend/quality-guidelines.md`
- Relevant frontend specs:
  - `.trellis/spec/frontend/directory-structure.md`
  - `.trellis/spec/frontend/type-safety.md`
  - `.trellis/spec/frontend/state-management.md`
  - `.trellis/spec/frontend/quality-guidelines.md`
- Key files from audit:
  - `backend/src/common/api/dashboard.py`
  - `backend/src/curriculum_practice/services/asset_reference_lineage.py`
  - `backend/src/sales_trainer/services/question_bank_adapter.py`
  - `backend/src/support/services/runtime_status_service.py`
  - `backend/src/sales_trainer/services/ai_coach_chat_service.py`
  - `backend/src/sales_trainer/permissions.py`
  - `web/src/components/layout/admin-sidebar.tsx`
  - `web/src/lib/api/client.ts`
  - `web/src/lib/api/types.ts`
  - `web/src/lib/admin/template-form-preflight.ts`

## Complexity

Complex. The plan spans backend architecture, frontend API boundaries, permission projection, tests, and docs. It will be implemented as the complete PR1-PR7 optimization package, split into small verification checkpoints rather than one large unverified change.
