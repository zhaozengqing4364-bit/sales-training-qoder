# Architecture Optimization Repair Plan

## Goal

基于 Brooks architecture audit，把当前模块化单体里的关键架构债拆成可执行的小 PR：先修复 `common` 反向依赖具体业务运行时的问题，再降低前端 API facade 的变更半径，并补上依赖方向 guardrail，避免同类边界回归。

## What I already know

* 用户要求：使用 `trellis-brainstorm` 制作详细的优化、修复计划。
* Brooks 审计健康分为 69/100，主要风险集中在后端 shared kernel 反向依赖、前端 API facade 高 fan-in、`sales_trainer` 与 `curriculum_practice` adapter 仍泄漏 ORM/领域模型。
* 后端是 FastAPI 模块化单体；架构文档要求共享逻辑进入 `common/`，核心场景隔离。
* 前端是 Next.js/React 纯消费 Python 后端，`web/src/lib/api/*` 和 `web/src/hooks/*` 是高影响稳定表面。
* 当前 Trellis 任务：`.trellis/tasks/06-14-architecture-optimization-repair-plan`。

## Assumptions (temporary)

* 计划目标是准备后续实现，不在本 brainstorm 轮直接改业务代码。
* 优先级按架构风险排序：`common` 依赖方向 > 测试 guardrail > 前端 API 拆分 > bounded context 细分。
* 后续实现应以小 PR 递进，避免一次性大重构破坏现有运行时路径。
* 用户已指定完整优化包：做 PR1-PR7，并包含前端 API 拆分和类型泄漏处理。

## Open Questions

* 是否确认按本 PRD 进入实现阶段，并从 PR1 开始。

## Requirements (evolving)

* 输出可执行的分 PR 优化计划，每个 PR 包含目标、涉及文件、设计策略、测试与验收标准。
* 保持现有 API/WS 行为兼容，不在架构优化中改变用户可见流程。
* 不把可配置业务规则、权限、文案、阈值散落到页面或服务函数中。
* 新增或调整跨域边界时，需要有测试锁住依赖方向。
* 复用仓库已有 port/contributor/registry 模式，不引入新框架或新部署形态。
* 计划必须覆盖后端 `common` 反向依赖、跨域 adapter 类型泄漏、前端 API facade 过大、依赖方向测试缺失。

## Acceptance Criteria (evolving)

* [ ] PRD 记录完整优化范围、拆分顺序、验收标准与风险。
* [ ] 每个 PR 都能独立 review、独立验证，并说明回滚方式。
* [ ] 计划覆盖 Brooks audit 中的 Critical/Warning/Suggestion。
* [ ] 计划明确哪些内容本轮不做，避免无边界重构。
* [ ] 后续实现完成后，`backend/src/common/**` 不再直接 import 具体业务运行时包，白名单除外且有说明。
* [ ] 后续实现完成后，前端新增 API 域不再继续扩大 `client.ts` / `client-domains.ts`。
* [ ] 后续实现完成后，依赖方向 contract test 会阻止 `common -> domain` 和 `sales_trainer -> realtime runtime` 回归。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky
* 依赖方向和配置化边界有自动化校验或明确文档约束

## Out of Scope (explicit)

* 不重命名公开 API 路由或产品命名。
* 不迁移数据库 schema，除非后续实现阶段发现防腐层必须新增持久化结构。
* 不一次性拆分服务或改部署形态；本计划仍以模块化单体为目标架构。
* 不把 `web/src/lib/api/types.ts` 按域拆分；该文件当前是约定的中心类型源。
* 不改变现有用户角色、权限语义、业务阈值、评分规则、文案模板或后台配置入口。

## Stable Logic vs Configurable Rules

### Stable code logic

* 依赖方向：`common` 定义稳定端口/DTO/注册表，具体领域实现只能从领域模块注册进来。
* 运行时 gate/admission 的接口形状：`RuntimeGateResult`、`RuntimeAdmissionDecision`、close-code/error-code 分类属于跨端契约。
* 前端 API transport primitives：认证、CSRF、trace headers、session-expired handling、loopback retry、`ApiRequestError`。
* 测试 guardrail：import graph contract、domain factory tests、API normalizer tests。

### Configurable business rules

* 本计划不新增可调整业务规则。
* 现有业务策略继续通过既有配置体系管理：业务规则、AI Coach 配置、语音运行时策略、评分提示词、训练路径配置、材料/考卷/题库发布状态等。
* 若实现过程中触及阈值、提示文案、权限映射、排序、模块启停，必须停下来复用现有配置/字典/权限模块，不得为了架构修复写死新策略。

### New config items

* 预计无新增配置项。
* 如实现阶段发现需要开关式迁移，只允许使用短期技术迁移开关，需明确默认值、读取位置、权限、审计和删除计划。

### Missing or illegal config handling

* 本计划不改变业务配置读取语义。
* 架构修复中新增的 contributor/port 缺失应 fail closed：返回明确 typed error、空贡献或测试失败，而不是隐式绕过业务规则。

## Research References

* [`research/repo-architecture-patterns.md`](research/repo-architecture-patterns.md) — 仓库已有的 port/contributor/registry 模式足以承载本轮修复，无需引入新框架。

## Expansion Sweep

### Future evolution

* `RuntimeGate` 可演进成多 runtime admission registry，后续新增 curriculum、sales、presentation 运行时只注册 evaluator，不修改 `common` 主体。
* 前端 API 可从“一个巨型 facade”演进到“兼容 facade + 领域文件 + 域内测试”，未来逐步减少 `client.ts` 直接增长。

### Related scenarios

* REST preflight、WebSocket admission、session repair、report generation 都需要共享同一套 typed failure 语义，不能只修一个入口。
* Sales Trainer 与 Curriculum 的题库/修订/内容绑定需要保持异步学习边界，不能借架构修复把 realtime `sales_bot` 概念引入 `sales_trainer`。

### Failure / edge cases

* contributor 未注册、重复注册、注册顺序不稳定、异常贡献者不能导致核心 release-health 或 runtime admission 崩溃。
* 前端拆分必须保证 session-expired、CSRF、trace header、loopback retry 仍只在 central request seam 维护。

## Technical Approach

### Approach A: Guardrail first + incremental ports (Recommended)

How it works:

* 先添加 import graph contract test，记录当前允许例外。
* 逐 PR 把 `common` 对具体领域的 direct import 替换成 port/contributor。
* 每移除一类反向依赖，就收紧测试白名单。
* 前端先拆出域文件并保持 `api` 兼容导出，再迁移域内实现。

Pros:

* 每个 PR 小、可验证、可回滚。
* 符合现有 `support.runtime_contributors`、`common.question_bank.ports` 模式。
* 可以边修边防止回归。

Cons:

* 总 PR 数更多。
* 中间阶段会有临时 adapter/compat 文件，需要清晰标注。

### Approach B: Big-bang package split

How it works:

* 一次性重组 `common/services`、`sales_trainer/services`、`web/src/lib/api`。

Pros:

* 最终目录形态更快接近理想状态。

Cons:

* 风险高，涉及 REST、WS、support、report、frontend，多入口回归概率大。
* 难以在当前已有脏工作区中判断哪些失败来自本轮。

### Approach C: Documentation-only exception registry

How it works:

* 不重构代码，只在 docs/spec 中登记允许的反向依赖。

Pros:

* 成本最低。

Cons:

* Brooks Critical 不会被实质修复。
* 无法阻止后续继续扩大 shared-kernel 污染。

## Decision (ADR-lite)

Context: Brooks audit 指出 `common` shared kernel 被具体领域运行时反向依赖污染；前端 `api` facade 体量和 fan-in 过高；跨域 adapter 没有真正防腐。

Decision: 推荐采用 Approach A：guardrail first + incremental ports。先测试锁边界，再逐步抽端口，最后做前端 API 文件拆分和 bounded-context 清理。

Consequences: 会产生多个小 PR 和短期兼容层，但每个 PR 都能独立验证；后续实现完成后，架构约束会从“人工记忆”变成“CI 可见失败”。

## Implementation Plan (small PRs)

### PR1: Dependency Guardrail Baseline

Goal:

* 建立 import graph contract，先让架构边界可测量、可回归检测。

Likely files:

* `backend/tests/unit/test_runtime_dependency_contract.py`
* Optional: `docs/architecture.md` or `.trellis/spec/backend/directory-structure.md` if a temporary allowlist needs documentation.

Implementation:

* 增加扫描工具函数，解析 `backend/src` 的 top-level package imports。
* 先记录当前 `common -> domain` 例外白名单，按后续 PR 逐步收紧。
* 增加禁止项：
  * `sales_trainer -> sales_bot`
  * `sales_trainer -> training_runtime`
  * `sales_trainer -> common.api.practice` / practice runtime 创建路径
  * 非组合根 `support -> concrete runtime` 直接依赖，必须经 contributor registry。

Verification:

* `cd backend && ./venv/bin/pytest tests/unit/test_runtime_dependency_contract.py`

Rollback:

* 删除新增测试或恢复 allowlist，不影响运行时代码。

### PR2: RuntimeGate Port Extraction

Goal:

* 修复最关键的 `common/services/runtime_gate.py` 对 `curriculum_practice` 的直接依赖。

Likely files:

* `backend/src/common/services/runtime_gate.py`
* New: `backend/src/common/runtime_admission/ports.py` or `backend/src/common/services/runtime_gate_ports.py`
* New/changed: `backend/src/curriculum_practice/services/runtime_gate_contributor.py`
* `backend/src/router_registry.py`
* `backend/src/websocket_routes.py`
* `backend/src/curriculum_practice/websocket/router.py`
* Relevant runtime preflight / websocket tests.

Implementation:

* `common` 定义 `RuntimeGateContributor` Protocol，输入 `AsyncSession` + `PracticeSession`，输出 `RuntimeGateResult` / `RuntimeAdmissionDecision` / optional runtime builder。
* 将 examiner/curriculum-specific 检查、snapshot stale、asset resolution、examiner runtime builder 移入 `curriculum_practice` contributor。
* `RuntimeGate` 只做通用 session 查找、scenario dispatch、typed failure 合并。
* 从组合根注册 contributor；测试里提供 clear/reset helper，避免跨测试污染。

Verification:

* `cd backend && ./venv/bin/pytest tests/unit/test_runtime_preflight_service.py tests/integration/test_runtime_preflight_api.py tests/unit/test_examiner_websocket_router.py tests/unit/test_sales_websocket_router.py tests/unit/test_main_presentation_ws_runtime.py`
* PR1 dependency test 白名单移除 `common/services/runtime_gate.py -> curriculum_practice`。

Rollback:

* contributor 注册可回退为旧 direct import；保留测试 allowlist 变更单独 revert。

### PR3: Practice Session Service Boundary

Goal:

* 降低 `common/services/practice_session_service.py` 对 sales/presentation/curriculum/training_runtime 的直接依赖，让 session create/lifecycle 保留为通用流程，领域 runtime assembly 下沉到 domain contributor。

Likely files:

* `backend/src/common/services/practice_session_service.py`
* `backend/src/common/services/practice_service.py`
* `backend/src/sales_bot/services/practice_session_contributor.py`
* `backend/src/presentation_coach/services/practice_session_contributor.py`
* `backend/src/curriculum_practice/services/practice_session_contributor.py`
* `backend/src/training_runtime/plugins.py`
* `backend/tests/contract/test_practice_evidence_contract.py`
* `backend/tests/integration/test_practice_evidence_flow.py`

Implementation:

* 抽出 `PracticeSessionAssembler` / `RuntimePolicyResolver` port。
* Sales voice policy 由 `sales_bot` provider 注册；presentation session 创建由 `presentation_coach` provider 注册；curriculum template snapshot 由 `curriculum_practice` provider 注册。
* `common.services.practice_service.build_practice_route_services()` 只组装通用服务和 provider registry，不直接 import `VoiceRuntimePolicyService`。
* 保持 REST `/api/v1/practice/*` 响应与错误码不变。

Verification:

* `cd backend && ./venv/bin/pytest tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_session_runtime_lifecycle_flow.py tests/unit/test_session_runtime_authority.py`
* PR1 dependency test 继续收紧 `common/services/practice_session_service.py`、`practice_service.py`。

Rollback:

* provider 注册点可恢复旧 implementation；因为外部 API 不变，回滚不需要数据迁移。

### PR4: Report / Evidence / Knowledge Boundary Cleanup

Goal:

* 清理剩余 `common` 对 `evaluation`、`prompt_templates`、`presentation_coach`、`support`、`agent` 的反向依赖。

Likely files:

* `backend/src/common/services/practice_report_service.py`
* `backend/src/common/conversation/session_evidence.py`
* `backend/src/common/conversation/replay.py`
* `backend/src/common/knowledge/api.py`
* `backend/src/common/db/voice_policy_snapshot.py`
* New ports/contributors under `common/**/ports.py` or existing support/knowledge surfaces.

Implementation:

* 将 report generation trigger、presentation review、prompt-template enrichment 改为 contributor/port。
* `common/knowledge/api.py` 不直接 import support runtime service；若知识库页面需要 asset governance，改由 support 或 admin 层调用专用 read model。
* 对 agent model 的 late import 做 DTO/read-model seam；必要时保留迁移白名单，但需注释和测试锁定。

Verification:

* `cd backend && ./venv/bin/pytest tests/contract/ tests/unit/test_support_runtime_service.py tests/integration/test_knowledge_flow.py`
* PR1 dependency test 目标：`common -> domain` 只剩被明确批准的 stable model/type imports，最好为 0。

Rollback:

* 每个 contributor 独立回退；不改变数据库。

### PR5: Cross-Domain Adapter Anti-Corruption

Goal:

* 修复 `sales_trainer` 与 `curriculum_practice` adapter 只是重导出 ORM/服务的类型泄漏。

Likely files:

* `backend/src/sales_trainer/services/curriculum_practice_adapter.py`
* `backend/src/curriculum_practice/services/sales_trainer_revision_adapter.py`
* `backend/src/sales_trainer/services/question_contracts.py`
* `backend/src/curriculum_practice/services/learning_content_revision_payloads.py`
* Existing `common/question_bank/ports.py`
* Tests under `backend/tests/unit/test_sales_trainer_services.py`, `backend/tests/integration/test_sales_trainer_api.py`

Implementation:

* 将 adapter 输出改成 DTO / Protocol / method facade，禁止直接暴露 `QuestionItem`、`LearningContent`、`SalesTrainerAssetRevision`。
* 优先复用 `common.question_bank.ports.ResolvedQuestion`；新增 revision/audit port 时只表达需要的字段与行为。
* 更新服务调用方，不再 type hint 具体 ORM model。

Verification:

* `cd backend && ./venv/bin/pytest tests/unit/test_sales_trainer_services.py tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_dashboard_recommendation.py`
* 新增测试扫描 adapter，禁止 `__all__` 暴露跨域 ORM model。

Rollback:

* 回滚 adapter DTO 层和调用点即可；不改变 API/DB。

### PR6: Frontend API Domain File Split

Goal:

* 降低 `web/src/lib/api/client.ts` 和 `client-domains.ts` 的增长压力，同时保持页面继续通过 `api` facade 消费。

Likely files:

* `web/src/lib/api/client.ts`
* `web/src/lib/api/client-domains.ts`
* New:
  * `web/src/lib/api/domains/support-runtime.ts`
  * `web/src/lib/api/domains/sales-trainer.ts`
  * `web/src/lib/api/domains/newcomer-training.ts`
  * `web/src/lib/api/domains/practice.ts`
  * `web/src/lib/api/domains/shared.ts`
* `web/src/lib/api/client-domains.test.ts` or new co-located tests.

Implementation:

* 先迁移已抽出的 domain builders 到独立文件，`client-domains.ts` 做兼容 re-export。
* `client.ts` 继续只创建 `api` 对象和 shared request primitives。
* 禁止新 domain 方法继续写入 `client.ts` 的大型 `api.admin` 内联对象；新增 domain 走独立 builder。
* API types 仍留在 `types.ts`，不做类型大拆分。

Verification:

* `cd web && npx tsc --noEmit`
* `cd web && npm test -- --run src/lib/api/client-domains.test.ts src/lib/api/client.auth.test.ts src/lib/api/client-governance.test.ts`
* 可选新增 import contract：页面不得直接 import `client-domains` 或 `domains/*`。

Rollback:

* 独立文件可 re-inline 回 `client-domains.ts`，外部页面 import 不变。

### PR7: Sales Trainer Package Interior Cleanup

Goal:

* 在不重命名产品/API 的前提下，降低 `sales_trainer` 113 文件大包内部认知负载。

Likely files:

* `backend/src/sales_trainer/services/**`
* `backend/src/sales_trainer/*_api.py`
* `backend/src/sales_trainer/router_registration.py`
* `docs/api-contract/sales-trainer.md` only if response/error semantics change; otherwise不改。

Implementation:

* 只做目录/入口级整理，不改行为：
  * `services/ai_coach/*`
  * `services/audio_scoring/*`
  * `services/path_config/*`
  * `services/question_bank/*`
  * `services/revision/*`
* 每个子包保留 facade import，减少一次性更新所有调用点。
* 禁止把新业务规则塞进目录整理 PR。

Verification:

* `cd backend && ./venv/bin/pytest tests/unit/test_sales_trainer_ai_coach_chat.py tests/unit/test_sales_trainer_services.py tests/integration/test_sales_trainer_api.py`
* `cd backend && ruff check src/sales_trainer tests/unit/test_sales_trainer_services.py`

Rollback:

* 目录整理必须机械、无行为变化；可以按子包单独 revert。

## PR Order and Risk

1. PR1 first because it creates visibility and rollback-safe guardrails.
2. PR2 before PR3 because `RuntimeGate` is the Brooks Critical and touches both HTTP preflight and WS admission.
3. PR3 after PR2 because session creation/lifecycle providers need the same contributor conventions.
4. PR4 cleans the remaining `common` leakage after the two largest seams are stable.
5. PR5 handles bounded-context anti-corruption once shared-kernel direction is controlled.
6. PR6 can run after PR1 or in parallel with backend PRs if no backend API shape changes.
7. PR7 last because it is mostly maintainability and easiest to defer.

## Verification Matrix

Backend focused:

* `cd backend && ./venv/bin/pytest tests/unit/test_runtime_dependency_contract.py`
* `cd backend && ./venv/bin/pytest tests/unit/test_runtime_preflight_service.py tests/integration/test_runtime_preflight_api.py`
* `cd backend && ./venv/bin/pytest tests/unit/test_sales_websocket_router.py tests/unit/test_examiner_websocket_router.py tests/unit/test_main_presentation_ws_runtime.py`
* `cd backend && ./venv/bin/pytest tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
* `cd backend && ./venv/bin/pytest tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py`
* `cd backend && ruff check src/ tests/`

Frontend focused:

* `cd web && npx tsc --noEmit`
* `cd web && npm test -- --run src/lib/api/client-domains.test.ts src/lib/api/client.auth.test.ts src/lib/api/client-governance.test.ts`
* `cd web && npm run lint -- --quiet`

Full release confidence:

* Backend unit + contract suite after PR4/PR5.
* Frontend typecheck + API domain tests after PR6.

## Rollout / Rollback Strategy

* All PRs are code-only architecture changes unless implementation discovers a real contract mismatch.
* Keep public API/WS paths stable; no migration required.
* Each contributor registry must have clear/reset helpers in tests to avoid global-state leakage.
* Temporary allowlists in dependency tests must shrink PR by PR and should be removed or justified before final completion.
* If a runtime path regresses, revert the specific provider extraction PR; because external contracts stay stable, rollback does not require data repair.

## Technical Notes

* Brooks audit 发现的关键文件：
  * `backend/src/common/services/runtime_gate.py`
  * `backend/src/common/services/practice_session_service.py`
  * `backend/src/common/services/practice_service.py`
  * `backend/src/support/services/runtime_contributors.py`
  * `backend/src/sales_trainer/services/curriculum_practice_adapter.py`
  * `backend/src/curriculum_practice/services/sales_trainer_revision_adapter.py`
  * `web/src/lib/api/client.ts`
  * `web/src/lib/api/client-domains.ts`
  * `backend/tests/unit/test_runtime_dependency_contract.py`
  * `web/src/lib/api/client-domains.test.ts`
* Relevant Trellis specs to inspect before implementation:
  * `.trellis/spec/backend/index.md`
  * `.trellis/spec/frontend/index.md`
  * `.trellis/spec/guides/cross-layer-thinking-guide.md`
  * `.trellis/spec/guides/code-reuse-thinking-guide.md`
* Additional inspected files:
  * `backend/src/common/AGENTS.md`
  * `backend/src/sales_bot/AGENTS.md`
  * `backend/src/curriculum_practice/AGENTS.md`
  * `backend/src/sales_trainer/AGENTS.md`
  * `backend/src/support/AGENTS.md`
  * `.trellis/spec/backend/directory-structure.md`
  * `.trellis/spec/backend/error-handling.md`
  * `.trellis/spec/backend/quality-guidelines.md`
  * `.trellis/spec/frontend/directory-structure.md`
  * `.trellis/spec/frontend/type-safety.md`
  * `.trellis/spec/frontend/quality-guidelines.md`
  * `web/src/lib/AGENTS.md`
  * `backend/src/common/question_bank/ports.py`
  * `backend/src/curriculum_practice/services/question_bank_provider.py`
  * `backend/src/sales_trainer/services/question_bank_adapter.py`
  * `backend/src/training_runtime/plugins.py`
