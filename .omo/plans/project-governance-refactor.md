# project-governance-refactor - Work Plan

## TL;DR (For humans)

**What you'll get:** 一套分阶段治理重构方案：先把发布门禁和契约基线修稳，再逐步收敛后端边界、前端路由与 API、配置治理、审计、AI Prompt 和运行时快照。最终目标是让项目从“多个 AI 生成模块能跑”变成“边界清楚、配置可管、发布可验、失败可追踪”的系统。

**Why this approach:** 当前项目已有不少正确局部机制，直接大重写会破坏这些资产；更稳的方式是先统一门禁和治理读面，再用小步 refactor 收紧依赖方向。

**What it will NOT do:** 本计划不扩展新业务功能，不做一次性全量重写，不立即拆 realtime 主干，不破坏现有 URL/API/table 兼容，不把所有配置强行迁入同一张表。

**Effort:** XL
**Risk:** High - 涉及后端组合根、前端 API facade、配置生命周期、权限审计、AI Prompt、CI/migration/release 门禁。
**Decisions I made for you:** 默认采用“守护测试先行、兼容导出保留、adapter/read-model 优先、存储迁移后置、realtime 深层重构最后”的路线。

Your next move: 使用 Ultra Loop 按本计划逐项执行；第一轮必须先完成 Wave 0 的门禁修复。

---

> TL;DR (machine): XL/high-risk governance refactor plan; no product code in this planning turn; execute in seven waves with gate-first sequencing.

## Scope

### Must have

- 修复已知验证红灯，尤其是 Alembic migration graph stale head。
- 固化后端 domain boundary，逐步减少 `common -> concrete domain` 反向依赖。
- 拆分 router mounting 与 domain contributor bootstrap。
- 建立 Sales Trainer 前端 route/capability registry。
- 拆分 Sales Trainer 与 Newcomer Training API facade。
- 将大页面中的业务编排迁移到 hook/workflow/reducer。
- 建立配置治理 inventory/read model，优先复用 `ConfigBundleAdapter`。
- 补齐 AI Coach model config 与 prompt/scoring contract hash 的运行时一致性。
- 统一或桥接审计读取面，先不强迁表。
- 收敛 release truth，明确 `critical-quality-gate.sh` 与 release verification 的关系。
- 为每一轮重构补 focused tests 与可复跑验证命令。
- 重要架构决策落 ADR。

### Must NOT have

- 不做大爆炸式全量重写。
- 不为“未来可能”引入通用框架或大型依赖。
- 不在页面组件继续新增业务规则。
- 不把权限只放在前端隐藏按钮。
- 不让 runtime 读取 latest admin config/prompt 重拼历史 session。
- 不让 admin 手写 runtime contract hash。
- 不把现有有效 store 直接废弃。
- 不在 known-red gate 未修复时开始 migration-heavy work。
- 不删除或弱化失败测试来换绿灯。

## Verification Strategy

> Zero human intervention for automated verification; manual QA gate is still required for UI/admin workflow slices.

- Test decision: characterization-first + tests-after。纯重构任务先用现有行为测试锁定契约；涉及 bug/契约漂移时先补失败用例。
- Evidence root: `.omo/evidence/project-governance-refactor/`
- Quality-gate evidence contract: `scripts/critical-quality-gate.sh` currently writes `.sisyphus/evidence/task-9-quality-gate.txt`. Until the script is parameterized, Task 4 must copy or summarize that artifact into `.omo/evidence/project-governance-refactor/quality-gate/`. Task 22 must make the release-verification record point at the canonical gate artifact and its `.omo` mirror.
- Minimum recurring commands:
  - `git status --short`
  - `cd backend && alembic heads`
  - `cd backend && venv/bin/python -m pytest tests/unit/common/test_alembic_migration_graph.py --no-cov -q`
  - `bash scripts/dependency-governance.sh status`
  - `bash scripts/secret-scan.sh`
  - focused backend pytest for touched services/contracts
  - focused frontend vitest/tsc for touched web modules
  - `bash scripts/critical-quality-gate.sh` before release candidate

## Execution Strategy

### Parallel Execution Waves

- Wave 0: Gate foundation and inventory. Blocks all later waves.
- Wave 1: Backend composition root and dependency boundary. Can partially parallelize with Wave 2 after Wave 0.
- Wave 2: Frontend route/API/state layering. Can parallelize with backend after route/API contracts are frozen.
- Wave 3: Configuration, permission, audit, AI Prompt governance. Depends on inventories from Waves 0-2.
- Wave 4: Runtime contract shared ownership and remaining backend domain boundary debt. Depends on Wave 1 and C governance decisions.
- Wave 5: Scripts, migrations, release workflow hardening. Starts at Wave 0, continues through release.
- Wave 6: Final verification, manual QA, release decision.

### Dependency Matrix

| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | none | 2-24 | none |
| 2 | 1 | 5, 13, 20 | 3, 4 |
| 3 | 1 | 8-12, 14, 23 | 2, 4 |
| 4 | 1 | 5-24 | 2, 3 |
| 5 | 2, 4 | 6, 7, 16-19 | 8, 13, 20 |
| 6 | 4, 5 | 16 | 8-15 |
| 7 | 4, 5 | 16-19 | 8-15 |
| 8 | 3, 4 | 9, 11, 12 | 5, 13 |
| 9 | 3, 4, 8 | 10-12 | 6, 13 |
| 10 | 4, 9 | 11, 12 | 13, 20 |
| 11 | 4, 8-10 | frontend learner smoke | 14, 20, 23 |
| 12 | 4, 8-10 | frontend learner smoke | 14, 20, 23 |
| 13 | 2, 3, 4 | 14, 15 | 5, 8 |
| 14 | 4, 13 | 23 | 11, 12 |
| 15 | 4, 13 | 23 | 20, 21 |
| 16 | 4, 5-7 | 18, 19, 24 | 20, 21 |
| 17 | 4, 7, 13 | 24 | 20, 21 |
| 18 | 4, 16 | 24 | 20, 21 |
| 19 | 4, 16, 17 | 24 | 20, 21 |
| 20 | 4 | 21 | 8-15 |
| 21 | 4, 20 | 22 | 16-19 |
| 22 | 4, 21 | 24 | 16-19 |
| 23 | 14, 15 | 24 | 11, 12, 20-22 |
| 24 | 16-23 | final gate | none |

## Todos

- [ ] 1. Gate Foundation: 修复 Alembic migration graph stale head
  What to do / Must NOT do: 读取 `backend/tests/unit/common/test_alembic_migration_graph.py`，修复其对旧 head 的硬编码；优先断言 `len(script.get_heads()) == 1` 和 revision 唯一性，避免把 `20260616_086` 变成新的易过期硬编码；不得跳过测试或降低断言含义。
  Parallelization: Wave 0 | Blocked by: none | Blocks: all
  References: `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-d-tests-ci-migrations-release-ultraloop-memo.md`; `backend/alembic/AGENTS.md`; current Alembic head `20260616_086`
  Acceptance criteria: `cd backend && venv/bin/python -m pytest tests/unit/common/test_alembic_migration_graph.py --no-cov -q` passes; `cd backend && alembic heads` shows one head; test failure message prints actual heads.
  QA scenarios: command evidence in `.omo/evidence/project-governance-refactor/task-1-migration-graph.txt`
  Commit: Y | `test(migrations): refresh alembic graph invariant`

- [ ] 2. Architecture Inventory: 生成当前治理/边界事实清单
  What to do / Must NOT do: 汇总 composition roots、API domains、config surfaces、audit carriers、quality gates 到文档；不得把聊天结论当唯一依据。
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 5, 13, 20
  References: `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-B-frontend-governance-memo.md`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-c-governance-memo.md`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-d-tests-ci-migrations-release-ultraloop-memo.md`; `.omo/ultraresearch/20260620-184300-project-governance-refactor/SYNTHESIS.md`
  Acceptance criteria: 新增或更新治理 inventory 文档，列出 owner、backing store、lifecycle、permission、audit、snapshot、public projection。
  QA scenarios: `rg "surface_key|backing_store|audit_policy|snapshot_policy" docs .omo -n`
  Commit: Y | `docs(governance): inventory configurable surfaces and gates`

- [ ] 3. Contract Drift Guard: 锁定 Newcomer completion rule 契约
  What to do / Must NOT do: 对比 `docs/api-contract/sales-trainer.md`、backend schemas、frontend types；修正文档或兼容映射；不得无说明改变 API 字段语义。
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 8-12, 14, 23
  References: `docs/api-contract/sales-trainer.md` completion rules; `backend/src/sales_trainer/schemas.py`; `web/src/lib/api/types.ts`
  Acceptance criteria: completion rule 字段在 contract/backend/frontend 一致；如保留旧字段，提供 deprecation/compat note；必须新增或更新可执行 contract/schema/type 测试，覆盖 docs/backend/frontend 三方允许值和兼容 map。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_phase2_projection.py --no-cov -q`; `cd web && npx vitest run src/lib/api/sales-trainer.test.ts`; additional doc-contract assertion test if introduced. Grep evidence alone is not sufficient.
  Commit: Y | `docs(contract): align newcomer completion rule semantics`

- [ ] 4. Ultra Loop Checkpoint Harness: 固定每轮检查命令与证据路径
  What to do / Must NOT do: 建立简单可复跑的 checkpoint 说明或脚本包装，记录 focused gate、slice gate、release gate；不得新增第二套 full release gate；必须明确 `.sisyphus/evidence` 与 `.omo/evidence/project-governance-refactor` 的镜像/索引规则。
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: all
  References: `scripts/critical-quality-gate.sh`; `scripts/AGENTS.md`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-d-tests-ci-migrations-release-ultraloop-memo.md`
  Acceptance criteria: Ultra Loop 每轮能把命令输出保存到 `.omo/evidence/project-governance-refactor/`；如果运行 `critical-quality-gate.sh`，其 `.sisyphus/evidence/task-9-quality-gate.txt` 必须被复制、符号链接或摘要索引到 `.omo/evidence/project-governance-refactor/quality-gate/`。
  QA scenarios: run a dry checkpoint that executes `git status --short` and `cd backend && alembic heads`, then verify evidence file exists under `.omo/evidence/project-governance-refactor/`.
  Commit: Y | `chore(governance): define refactor checkpoint evidence flow`

- [ ] 5. Backend Bootstrap Split: 分离 router mounting 与 domain contributor bootstrap
  What to do / Must NOT do: 从 `backend/src/router_registry.py` 中抽出 contributor registration 组合逻辑到独立 bootstrap 模块；HTTP route mounting 行为保持不变。
  Parallelization: Wave 1 | Blocked by: 2, 4 | Blocks: 6, 7, 16-19
  References: `backend/src/router_registry.py`; `backend/src/common/services/practice_session_ports.py`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`
  Acceptance criteria: 现有 router tests/import tests 通过；新模块有单元测试证明 sales/curriculum/training contributor 注册顺序和语义不变。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py --no-cov -q`; if bootstrap tests are added, run that exact new test file in the same command and save output to `.omo/evidence/project-governance-refactor/task-5-backend-bootstrap.txt`.
  Commit: Y | `refactor(backend): split domain contributor bootstrap from router registry`

- [ ] 6. Backend Reverse Dependency Reduction: 移除 `common/services/session_runtime_repair_service.py -> sales_bot`
  What to do / Must NOT do: 用 port/protocol 或 contributor 提供 domain-specific repair 行为；不要让 `common` 继续直接导入具体 sales runtime。
  Parallelization: Wave 1 | Blocked by: 4, 5 | Blocks: 16
  References: `backend/tests/unit/test_runtime_dependency_contract.py`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`
  Acceptance criteria: runtime dependency contract allowlist 删除对应项并通过 focused test。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py --no-cov -q`
  Commit: Y | `refactor(runtime): remove sales runtime import from common repair service`

- [ ] 7. Backend Boundary ADR: 记录 runtime boundary ownership 与 contributor bootstrap 决策
  What to do / Must NOT do: 新增 ADR，说明 composition root、domain contributor、common port、Roleplay Contract shared ownership 的边界；不得只把理由留在聊天记录。
  Parallelization: Wave 1 | Blocked by: 4, 5 | Blocks: 16-19
  References: `docs/adr/`; `backend/tests/unit/test_runtime_dependency_contract.py`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-c-governance-memo.md`
  Acceptance criteria: ADR 包含背景、决策、备选方案、取舍、影响、回滚。
  QA scenarios: `rg "contributor bootstrap|Roleplay Contract|common port" docs/adr -n`; `rg "回滚|备选方案|影响" docs/adr -n` must find the new ADR sections.
  Commit: Y | `docs(adr): define backend runtime boundary ownership`

- [ ] 8. Frontend Route Registry: 建立 Sales Trainer route/capability 单一来源
  What to do / Must NOT do: 新建 `web/src/lib/sales-trainer/routes.ts` 或同等位置；global sidebar 与 module nav 消费同一 registry；不得在两个组件继续复制 route 文案/权限矩阵。
  Parallelization: Wave 2 | Blocked by: 3, 4 | Blocks: 9, 11, 12
  References: `web/src/components/layout/admin-sidebar.tsx`; `web/src/components/admin/sales-trainer/module-nav.tsx`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-B-frontend-governance-memo.md`
  Acceptance criteria: nav 行为不变；`admin-sidebar.test.tsx` 与 `module-nav.test.tsx` 通过并覆盖 active item/capability visibility。
  QA scenarios: `cd web && npx vitest run src/components/layout/admin-sidebar.test.tsx src/components/admin/sales-trainer/module-nav.test.tsx`; manual browser path `/admin/sales-trainer` verifies global sidebar and module nav active item/capability visibility.
  Commit: Y | `refactor(web): centralize sales trainer route registry`

- [ ] 9. API Facade Split: 拆分 Sales Trainer 与 Newcomer Training domains
  What to do / Must NOT do: 将 `/admin/newcomer-training/*` 调用从 sales-trainer domain 中迁到 newcomer-training domain；保留 public facade 兼容导出直到调用点迁完。
  Parallelization: Wave 2 | Blocked by: 3, 4, 8 | Blocks: 10-12
  References: `web/src/lib/api/domains/sales-trainer.ts`; `web/src/lib/api/domains/newcomer-training.ts`; `web/src/lib/api/client.ts`
  Acceptance criteria: TypeScript 编译通过；调用点不再从 sales-trainer domain 访问 newcomer training API。
  QA scenarios: `cd web && npx vitest run src/lib/api/sales-trainer.test.ts src/lib/api/newcomer-training.test.ts src/lib/api/client-domains.test.ts && npx tsc --noEmit`.
  Commit: Y | `refactor(web-api): split newcomer training domain facade`

- [ ] 10. API Types Partition: 按领域拆分或聚合 types，降低 `types.ts` 单点膨胀
  What to do / Must NOT do: 优先用 re-export/compat barrel 渐进拆分；不得破坏现有 import。
  Parallelization: Wave 2 | Blocked by: 4, 9 | Blocks: 11, 12
  References: `web/src/lib/api/types.ts`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-B-frontend-governance-memo.md`
  Acceptance criteria: old imports still work；new domain modules 可局部导入；`npx tsc --noEmit` passes。
  QA scenarios: `cd web && npx tsc --noEmit`
  Commit: Y | `refactor(web-api): partition sales trainer api types`

- [ ] 11. Admin Path Config Hook: 从 admin path page 抽出数据加载/保存/publish/rollback workflow
  What to do / Must NOT do: 页面保留路由壳；业务编排进入 hook/service；不得改变 path config 的 publish/rollback 语义。
  Parallelization: Wave 2 | Blocked by: 4, 8-10 | Blocks: 23
  References: `web/src/app/admin/sales-trainer/paths/page.tsx`; `web/src/components/admin/sales-trainer/path-config-center.tsx`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-B-frontend-governance-memo.md`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-c-governance-memo.md`
  Acceptance criteria: `paths/page.test.tsx` 与 binding tests 覆盖 loading/error/success/permission denied；UI smoke 通过。
  QA scenarios: `cd web && npx vitest run src/app/admin/sales-trainer/paths/page.test.tsx src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx`; manual browser path `/admin/sales-trainer/paths` verifies load, save draft, publish, rollback, permission-denied state.
  Commit: Y | `refactor(web): extract sales trainer path config workflow hook`

- [ ] 12. Business Skills Workbench Hook: 拆分商务技巧页状态与 quiz/AI Coach 入口 workflow
  What to do / Must NOT do: 把 1000+ 行页面中的加载、quiz 提交、评分状态、错误恢复抽到 hook/reducer；不做视觉 redesign。
  Parallelization: Wave 2 | Blocked by: 4, 8-10 | Blocks: 23
  References: `web/src/app/(dashboard)/sales-trainer/business-skills/page.tsx`; `web/src/app/(dashboard)/sales-trainer/business-skills/coach/coach-session.ts`
  Acceptance criteria: 学员 happy path、empty、error、重复提交防护测试通过。
  QA scenarios: `cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx' 'src/app/(dashboard)/sales-trainer/business-skills/coach/page.test.tsx'`; manual browser paths `/sales-trainer/business-skills` and `/sales-trainer/business-skills/coach` verify loading, empty/error recovery, quiz handoff, and coach session resume.
  Commit: Y | `refactor(web): extract business skills workflow state`

- [ ] 13. Governance Inventory Facade: 为配置面建立统一 read model
  What to do / Must NOT do: 保留 `ConfigBundle`、`SalesTrainerAssetRevision`、`PromptTemplate` 等 backing store；先做 adapter/read model，不做强迁移。
  Parallelization: Wave 3 | Blocked by: 2, 3, 4 | Blocks: 14, 15
  References: `backend/src/admin/config_bundles/adapters.py`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-c-governance-memo.md`
  Acceptance criteria: inventory 能列出 Newcomer Path、AI Coach、Roleplay Situation Pack、ScoringRuleset、PromptTemplate。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_config_bundle_roleplay_situation_packs.py tests/unit/common/test_business_rule_config_service.py --no-cov -q`; add and run the new inventory adapter test file if this todo creates one.
  Commit: Y | `feat(governance): add configurable surface inventory facade`

- [ ] 14. Prompt Permission Boundary: 明确 PromptTemplate admin 与 Sales Trainer manage_prompts 权限契约
  What to do / Must NOT do: 平台模板 CRUD 与 domain binding/change approval 边界写入 ADR/contract；代码检查使用集中权限函数；不得新增页面级权限旁路。
  Parallelization: Wave 3 | Blocked by: 4, 13 | Blocks: 23
  References: `backend/src/prompt_templates/api/routes.py`; `backend/src/sales_trainer/permissions.py`; `backend/src/sales_trainer/ai_coach_policy.py`
  Acceptance criteria: permission tests 覆盖普通 admin、Sales Trainer admin、高风险 prompt 字段。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_permissions.py tests/integration/test_prompt_templates_api_rbac.py --no-cov -q`.
  Commit: Y | `refactor(auth): formalize prompt governance permissions`

- [ ] 15. AI Coach Runtime Prompt/Model Gaps: 修复 model config false-effective 与 scoring hash 持久化
  What to do / Must NOT do: 要么把 `generation_model`/`scoring_model` 接入 LLM runtime，要么从有效配置面隐藏/标注未生效；持久化 compiled scoring contract hash；不得允许 admin 写入真实 hash。
  Parallelization: Wave 3 | Blocked by: 4, 13 | Blocks: 23
  References: `backend/src/sales_trainer/services/ai_coach_chat_generation.py`; `backend/src/sales_trainer/services/ai_coach_session_service.py`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-c-governance-memo.md`
  Acceptance criteria: tests 证明 generation/scoring model 生效或不可配置；short-answer score 可追溯 prompt revision/hash/model。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_ai_coach.py tests/unit/test_sales_trainer_ai_coach_chat.py tests/unit/prompt_templates/test_compiled_prompt_contract.py --no-cov -q`.
  Commit: Y | `fix(ai-coach): persist scoring contract hash and honor model config`

- [ ] 16. Runtime Descriptor Neutral Types: 移动 runtime descriptor/shared types 到中立边界
  What to do / Must NOT do: 只移动类型/协议，不改变 runtime 行为；保留兼容 import。
  Parallelization: Wave 4 | Blocked by: 4, 5-7 | Blocks: 18, 19, 24
  References: `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`; `backend/src/common/services/practice_session_ports.py`
  Acceptance criteria: dependency contract 通过；old imports 有 deprecation path 或兼容 re-export。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py --no-cov -q`; add import-compat tests in the touched module test file and include it in this command.
  Commit: Y | `refactor(runtime): move descriptor contracts to neutral boundary`

- [ ] 17. Roleplay Contract Shared Ownership: 抽出共享 contract primitive
  What to do / Must NOT do: 不改变 compiler/hash/freeze 语义；只把 shared interface/hash helper 移出 curriculum-only ownership。
  Parallelization: Wave 4 | Blocked by: 4, 7, 13 | Blocks: 24
  References: `backend/src/curriculum_practice/services/roleplay_contracts.py`; `backend/src/sales_bot/services/voice_runtime_policy.py`; CONTEXT Roleplay Contract
  Acceptance criteria: roleplay contract tests 与 voice runtime policy tests 通过。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_roleplay_contracts.py tests/unit/test_voice_runtime_policy_service.py --no-cov -q`
  Commit: Y | `refactor(roleplay): move shared contract primitives out of curriculum boundary`

- [ ] 18. Training Task Template Lookup Port: 给 training task 查找建立 port
  What to do / Must NOT do: 移除 shared/common 对 curriculum concrete service 的直接 lookup；不改变训练任务用户可见行为。
  Parallelization: Wave 4 | Blocked by: 4, 16 | Blocks: 24
  References: `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`; runtime dependency contract allowlist
  Acceptance criteria: allowlist 收紧；新增或更新的 training task template lookup 测试与 dependency contract 测试通过。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py --no-cov -q`; add focused training task test file to the same command when this port is implemented.
  Commit: Y | `refactor(training): introduce template lookup port`

- [ ] 19. Adapter Policy Decision: 明确 sales_trainer/curriculum adapter 是受控桥还是待退役债务
  What to do / Must NOT do: 不静默删除桥接；为现有 adapter 写 policy、tests、retirement condition。
  Parallelization: Wave 4 | Blocked by: 4, 16, 17 | Blocks: 24
  References: `backend/tests/unit/test_runtime_dependency_contract.py`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`
  Acceptance criteria: adapter export guard 清楚表达允许范围；ADR 或 docs 记录退役条件。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py --no-cov -q`; `rg "adapter|sales_trainer|curriculum" docs/adr docs -n` must find the documented controlled bridge policy.
  Commit: Y | `docs(runtime): define controlled adapter boundary policy`

- [ ] 20. Script Safety Inventory: 盘点数据脚本安全等级，不阻塞 release bridge
  What to do / Must NOT do: 只读盘点 broad seed/import/repair 脚本，标记是否具备 dry-run/default verify-only/explicit apply/limit/scope/affected counts；不要在本任务里顺手重构 2000+ 行脚本。
  Parallelization: Wave 5 | Blocked by: 4 | Blocks: 21
  References: `backend/scripts/AGENTS.md`; `backend/scripts/seed_newcomer_training_path.py`; `backend/scripts/repair_runtime_snapshots.py`
  Acceptance criteria: 生成脚本安全 inventory，至少覆盖 `seed_newcomer_training_path.py`、`seed_presales_cio_first_visit.py`、`import_coo_learning_content.py`、`repair_runtime_snapshots.py`；高风险脚本各有下一步整改 todo 或明确保留原因。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_repo_hygiene_scripts.py tests/unit/test_seed_newcomer_training_path.py --no-cov -q`; run verify-only/dry-run capable scripts in non-writing mode and save output to `.omo/evidence/project-governance-refactor/task-20-script-inventory.txt`.
  Commit: Y | `docs(scripts): inventory data-changing script safety`

- [ ] 20b. Script Safety Hardening: 只对明确命名脚本补 dry-run/apply 保护
  What to do / Must NOT do: 根据 Task 20 inventory 选择一个高风险脚本做小步整改，优先 `seed_newcomer_training_path.py`；补 `--dry-run` 默认或等价 non-writing 默认、explicit `--apply`、limit/scope、affected counts 和测试；不得同时重写多个大型 seed/import 脚本。
  Parallelization: Wave 5 | Blocked by: 20 | Blocks: optional release hardening, not Task 22
  References: `backend/scripts/seed_newcomer_training_path.py`; `backend/tests/unit/test_seed_newcomer_training_path.py`; `backend/scripts/AGENTS.md`
  Acceptance criteria: 目标脚本默认不写库；写库必须显式 `--apply`；测试覆盖 dry-run/apply/affected counts。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_seed_newcomer_training_path.py --no-cov -q`; script dry-run command writes no DB changes.
  Commit: Y | `refactor(scripts): require explicit apply for newcomer seed`

- [ ] 21. CI Branch and Dependency Governance: 对齐 release-truth 分支与依赖审计
  What to do / Must NOT do: 默认假设当前团队基线 `dev` 是本轮集成分支，并把 release-truth workflow 纳入 `dev` 触发；如果项目维护者明确否定该假设，则改为文档化 PR 必须指向已触发 gate 的分支。修复或记录 `pip_audit`/`pip-licenses` 阻塞。
  Parallelization: Wave 5 | Blocked by: 4, 20 | Blocks: 22
  References: `.github/workflows/release-truth-gate.yml`; `scripts/dependency-governance.sh`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-d-tests-ci-migrations-release-ultraloop-memo.md`
  Acceptance criteria: CI 触发策略与团队实际分支一致；dependency status 不再出现未解释 blocker。
  QA scenarios: `bash scripts/dependency-governance.sh status`; `python3 - <<'PY'\nimport yaml, pathlib\nprint(yaml.safe_load(pathlib.Path('.github/workflows/release-truth-gate.yml').read_text())['on'])\nPY` if PyYAML is available, otherwise inspect the workflow trigger with `sed -n '1,20p' .github/workflows/release-truth-gate.yml`.
  Commit: Y | `ci: align release truth gate with integration branch`

- [ ] 22. Release Verification Bridge: 统一 shell gate 与 admin release verification
  What to do / Must NOT do: 保留 `critical-quality-gate.sh` 为 executable truth；release verification 读取/记录 gate evidence 或明确作为 ledger，不复制第二套权威；必须明确 coverage 是否 release-blocking。如果 critical gate 是权威，则 verification runner 的 70% coverage 阈值只能作为报告项，不能给出独立 Go/No-Go。
  Parallelization: Wave 5 | Blocked by: 4, 21 | Blocks: 24
  References: `scripts/critical-quality-gate.sh`; `backend/src/common/analytics/verification_runner.py`; `docs/api-contract/release-verification.md`
  Acceptance criteria: release candidate report 能引用 gate evidence；不会出现两个互相矛盾的 release truth；coverage blocking 规则只有一个来源。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_verification_runner.py tests/integration/test_release_gate.py tests/contract/test_release_verification_contract.py --no-cov -q`.
  Commit: Y | `chore(release): bridge verification records to quality gate evidence`

- [ ] 23. Learner Public Projection Consolidation: 统一 Sales Trainer learner-safe projection
  What to do / Must NOT do: 将 AI Coach deny-list、unit payload stripping、path projection stripping 收敛到 shared projection module；敏感字段 deny-by-default。
  Parallelization: Wave 3 | Blocked by: 4, 14, 15 | Blocks: 24; frontend learner smoke can run later with 11/12
  References: `backend/src/sales_trainer/ai_coach_api.py`; `backend/src/sales_trainer/services/unit_public_payloads.py`; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-c-governance-memo.md`
  Acceptance criteria: tests 证明 prompt ids、revision ids、hashes、answer keys、rubrics、raw model output 不泄露。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_unit_public_payloads.py tests/unit/test_sales_trainer_path_projection_ai_coach.py tests/unit/test_sales_trainer_phase2_projection.py --no-cov -q`; learner API smoke path `/api/v1/sales-trainer/path` must not include prompt ids, hashes, answer keys, rubrics, or raw model output. Frontend smoke for `/sales-trainer/business-skills` runs after 11/12.
  Commit: Y | `refactor(sales-trainer): centralize learner public projection`

- [ ] 24. Realtime Deep Boundary Slice: characterization 后再拆 StepFun 继承/共享 primitive
  What to do / Must NOT do: 先加 characterization tests，证明 presentation/sales realtime 行为；再拆 presentation handler 对 sales handler 的继承；不得在无测试时重写 realtime 主干。
  Parallelization: Wave 6 | Blocked by: 4, 16-23 | Blocks: final
  References: `backend/src/websocket_routes.py`; presentation/sales StepFun handlers; `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`
  Acceptance criteria: sales/presentation realtime focused tests 通过；依赖方向更清晰；用户可见连接语义不变。
  QA scenarios: `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py tests/unit/test_voice_runtime_policy_service.py --no-cov -q`; if app stack is available, manually start sales and presentation practice sessions and verify terminal/transient failure behavior is unchanged.
  Commit: Y | `refactor(realtime): separate presentation handler from sales runtime inheritance`

## Final Verification Wave

> Runs after all selected todos for a slice. Do not declare release readiness until these finish or failures are classified.

- [ ] F1. Plan compliance audit
  Command: `git diff --name-only` then map each changed file to one todo in `.omo/evidence/project-governance-refactor/f1-plan-compliance.md`.

- [ ] F2. Backend focused gate
  Commands:
  - `cd backend && alembic heads`
  - `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py --no-cov -q`
  - plus touched service/API/contract tests.

- [ ] F3. Frontend focused gate
  Commands:
  - `cd web && npx tsc --noEmit`
  - `cd web && npx vitest run src/components/layout/admin-sidebar.test.tsx src/components/admin/sales-trainer/module-nav.test.tsx src/lib/api/sales-trainer.test.ts src/lib/api/newcomer-training.test.ts src/app/admin/sales-trainer/paths/page.test.tsx 'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx'`
  - browser QA for touched admin/learner routes.

- [ ] F4. Release candidate gate
  Command: `bash scripts/critical-quality-gate.sh`
  Evidence: `.sisyphus/evidence/task-9-quality-gate.txt` plus mirrored/indexed record under `.omo/evidence/project-governance-refactor/quality-gate/`.

- [ ] F5. Manual QA surface
  Evidence: `.omo/evidence/project-governance-refactor/f5-manual-qa.md`
  Mode: Prefer Playwright/browser automation. If required env/accounts/seed data are unavailable, record F5 as external manual gate and do not claim release readiness.
  Preconditions:
  - app stack running with seeded admin and learner users.
  - admin can access `/admin/sales-trainer/paths` and `/admin/sales-trainer/operation-logs`.
  - learner can access `/sales-trainer/business-skills` and `/sales-trainer/business-skills/coach`.
  Steps and expected results:
  - Admin path config: open `/admin/sales-trainer/paths`, load current config, save draft, publish, rollback; expect success feedback and active revision pointer changes only.
  - Learner path: open `/sales-trainer/business-skills`; expect active revision content and no admin-only prompt/hash/rubric fields in network payload.
  - AI Coach: open `/sales-trainer/business-skills/coach`, start/resume session, submit one quiz card, trigger one failure path if possible; expect bounded error recovery and no raw model output leakage.
  - Audit: open `/admin/sales-trainer/operation-logs`; expect publish/rollback/prompt binding/regrade records with actor, target, action, timestamp, trace id or documented trace fallback.

## Commit Strategy

- 一次 todo 一个可回滚 commit，避免跨域巨型提交。
- 先提交测试/门禁修复，再提交结构重构。
- 跨前后端契约变化必须同 commit 或同 PR 内明确兼容窗口。
- ADR/docs 与对应结构变更同 commit 或紧邻 commit。
- 本规划回合不自动提交。

## Success Criteria

- 本轮成功标准：
  - A/B/C/D 四个研究 memo 已收齐。
  - UltraResearch 综合结论已写入。
  - Ultra Loop 可执行计划已写入。
  - Trellis planning task 已激活为 in_progress。
  - 未修改业务代码。

- 后续执行成功标准：
  - 已知 gate 红灯清除或明确归因。
  - 后端 dependency allowlist 逐步减少而不是扩大。
  - 前端 route/API 类型边界可局部推理。
  - 配置面能统一盘点，审计可跨 carrier 查询。
  - AI Prompt/model/hash 的运行时事实和后台配置一致。
  - release truth 只有一个可执行权威。
  - 手动关键路径可通过 UI/API 观察验证。
