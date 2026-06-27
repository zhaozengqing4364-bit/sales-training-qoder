# ULW All Task Plans Execution

## TL;DR
> Summary:      将 7 份既有计划合并为一个 HEAVY ULW 实施总计划：先修门禁和契约/现状校准，再用最小切片把新人训练路径路径级 active revision 做成真源，最后扩展到资产迁移、自然编辑、权限审计、诊断、课程闭环和发布门禁。
> Deliverables:
> - 可执行依赖波次、任务、验收、QA 和证据路径
> - 第一实施切片：Wave 1 门禁/契约/证据通道 + Wave 2 路径配置真源最小闭环
> - 每个任务的精确首读文件、验证命令、QA 场景和提交指令
> Effort:       XL
> Risk:         High - 计划触及 revision 真源、历史快照、权限、审计、回滚、迁移和跨前后端 UI/API。

## Scope
### Must have
- 以这些计划为事实源：`.omo/plans/project-governance-refactor.md`、`.omo/plans/newcomer-training-path-plan.md`、`.omo/plans/published-governance-revision-plan.md`、`.omo/plans/published-governance-revision-execution-pack.md`、`.omo/plans/published-governance-revision-acceptance-checklist.md`、`.omo/plans/published-governance-revision-test-matrix.md`、`.omo/plans/published-governance-revision-risk-register.md`。
- 先完成 Wave 1：门禁修复、契约/现状校准、draft-only 锁点盘点、ULW 证据通道；它阻塞后续所有产品改造。
- Wave 2 是最小第一产品切片：确认或补齐 `newcomer_training_path_v1` 路径级 active revision 真源、legacy unit projection、学员端 path active revision 读取、管理端 path save/publish/rollback、旧 attempt 不变。
- 每个任务必须自己包含实现和测试，不能拆成“先实现、另起任务补测试”。
- 所有证据写入 `.omo/evidence/ulw-all-task-plans/`；若全量质量门失败，保存完整输出并标明是否既有失败。
- 执行前优先读：`AGENTS.md`、`CLAUDE.md`、`docs/AGENTS.md`、`docs/architecture.md`、`docs/api-contract/README.md`、`docs/api-contract/sales-trainer.md`、`backend/AGENTS.md`、`backend/src/sales_trainer/AGENTS.md`、`web/AGENTS.md`、`web/src/app/admin/sales-trainer/AGENTS.md`、`.trellis/workflow.md`、`.trellis/spec/backend/index.md`、`.trellis/spec/frontend/index.md`、`scripts/AGENTS.md`。

### Must NOT have (guardrails, anti-slop, scope boundaries)
- 不做大爆炸式全量重写；不得先改 UI 文案再补 revision/snapshot/audit 语义。
- 不把 `ConfigVersion` 直接照搬为 immutable revision；只能复用生命周期经验。
- 不让 `SalesTrainerUnit.config.path` 继续作为新写入真源；它只能是 legacy projection/兼容 alias。
- 不让历史 attempt/session/result 从 latest asset 重拼；历史读取必须优先 snapshot/revision refs。
- 不把权限只放在前端隐藏按钮；发布、回滚、归档、重评必须后端拦截并审计。
- 不在 route handler 直接改 ORM 绕过 service、门禁、审计。
- 不跳过、删除、弱化失败测试来换绿灯。
- 不引入大型新依赖来解决局部治理问题。

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: TDD + characterization-first + tests-after；重构先锁定当前行为，契约/bug 变更先捕获 RED，再最小 GREEN。
- QA policy: every task has agent-executed scenarios
- Evidence: `.omo/evidence/task-<N>-<slug>.<ext>`；本计划统一落到 `.omo/evidence/ulw-all-task-plans/task-<N>-<slug>.<ext>`

## Execution strategy
### Parallel execution waves
> Target 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks to maximize parallelism.

Wave 1 (no dependencies):
- Task 1: 计划真相和当前实现校准
- Task 2: Alembic/质量门基础修复
- Task 3: 发布治理契约和 draft-only 锁点基线
- Task 4: Newcomer domain/completion 契约漂移防线
- Task 5: ULW 证据通道和 checkpoint harness

Wave 2 (after Wave 1):
- Task 6: depends [1, 3, 5] - revision/audit service gap close
- Task 7: depends [1, 3, 4, 6] - 路径配置 active revision 真源最小闭环
- Task 8: depends [4, 7] - 学员端 path projection 和 legacy fallback
- Task 9: depends [5, 7] - 管理端 path save/publish/rollback workflow
- Task 10: depends [6, 7, 8, 9] - 旧 attempt/snapshot 不变与新学员未来生效证明

Wave 3 (after Wave 2):
- Task 11: depends [6, 10] - sales_trainer 资产 revision lineage 迁移
- Task 12: depends [8, 9, 11] - 管理端自然编辑 UI 和技术字段隐藏
- Task 13: depends [6, 9, 11] - 权限、审计、诊断、回滚、重评
- Task 14: depends [6, 10] - curriculum_practice 对齐
- Task 15: depends [5, 11, 12, 13, 14] - release/script/CI bridge 和全量试运行准备

Critical path: Task 2 -> Task 5 -> Task 6 -> Task 7 -> Task 10 -> Task 11 -> Task 13 -> Task 15 -> Final verification

Smallest first implementation slice: complete Tasks 1-5, then Tasks 6-10 only for path-level `newcomer_training_path_v1` true-source behavior. Do not start paper/question/prompt/material broad migration until Task 10 proves old attempt remains unchanged and new learner reads the active path revision.

### Dependency matrix
| Task | Depends on | Blocks | Can parallelize with |
|------|------------|--------|----------------------|
| 1 | none | 6, 7, 11-15 | 2, 3, 4, 5 |
| 2 | none | 5, 15 | 1, 3, 4 |
| 3 | none | 6, 7, 11-14 | 1, 2, 4, 5 |
| 4 | none | 7, 8, 12 | 1, 2, 3, 5 |
| 5 | none | 6-15 | 1, 2, 3, 4 |
| 6 | 1, 3, 5 | 7, 10, 11, 13, 14 | none |
| 7 | 1, 3, 4, 6 | 8, 9, 10, 11 | none |
| 8 | 4, 7 | 10, 12 | 9 |
| 9 | 5, 7 | 10, 12, 13 | 8 |
| 10 | 6, 7, 8, 9 | 11, 14, final QA | none |
| 11 | 6, 10 | 12, 13, 15 | 14 |
| 12 | 8, 9, 11 | 15, final browser QA | 13, 14 |
| 13 | 6, 9, 11 | 15 | 12, 14 |
| 14 | 6, 10 | 15 | 11, 12, 13 |
| 15 | 5, 11, 12, 13, 14 | final | none |

## Todos
> Implementation + Test = ONE task. Never separate.
> Every task MUST have: References + Acceptance Criteria + QA Scenarios + Commit.

- [ ] 1. 计划真相和当前实现校准

  What to do: 读取 7 份计划与首读文件集合，生成当前状态校准文档，标记每个计划项为 `done-evidence`、`gap`、`needs-verification` 或 `superseded-by-current-code`。必须用当前仓库证据判断，不得重复实现已存在的 revision/path/audit 能力。
  Must NOT do: 不改产品代码；不把计划中的未勾选项机械当成未实现；不把子代理或聊天结论当唯一事实源。

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [6, 7, 11, 12, 13, 14, 15] | Blocked by: []

  References (executor has NO interview context - be exhaustive):
  - Pattern:  `.omo/plans/project-governance-refactor.md:23` - must-have/must-not-have 总纲。
  - Pattern:  `.omo/plans/project-governance-refactor.md:69` - Wave 0 blocks later work.
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:79` - 阶段 0 盘点和契约基线。
  - Pattern:  `.omo/plans/published-governance-revision-plan.md:215` - 发布治理阶段依赖图。
  - Pattern:  `backend/src/sales_trainer/AGENTS.md:29` - service/permission/rules 职责边界。
  - Pattern:  `web/src/app/admin/sales-trainer/AGENTS.md:19` - 管理端首读 surface。
  - Test:     `.omo/plans/published-governance-revision-test-matrix.md:5` - 命令真实性和失败记录要求。
  - External: `none` - 外部资料不作为本计划事实源。

  Acceptance criteria (agent-executable only):
  - [ ] `test -s .omo/evidence/ulw-all-task-plans/task-1-state-calibration.md`
  - [ ] `rg -n "done-evidence|gap|needs-verification|superseded-by-current-code" .omo/evidence/ulw-all-task-plans/task-1-state-calibration.md`
  - [ ] `rg -n "AGENTS.md|CLAUDE.md|docs/api-contract/sales-trainer.md|backend/src/sales_trainer/AGENTS.md|web/src/app/admin/sales-trainer/AGENTS.md" .omo/evidence/ulw-all-task-plans/task-1-state-calibration.md`

  QA scenarios (MANDATORY - task incomplete without these):
  > Name the exact tool AND its exact invocation - not "verify it works". Browser use: use Chrome to drive the page; if Chrome is not available, download and use agent-browser (https://github.com/vercel-labs/agent-browser). Computer use: OS-level GUI automation for a non-browser desktop app.
  ```
  Scenario: first-read map exists
    Tool:     bash
    Steps:    bash -lc 'mkdir -p .omo/evidence/ulw-all-task-plans && rg -n "AGENTS.md|CLAUDE.md|docs/api-contract/sales-trainer.md|backend/src/sales_trainer/AGENTS.md|web/src/app/admin/sales-trainer/AGENTS.md" .omo/evidence/ulw-all-task-plans/task-1-state-calibration.md | tee .omo/evidence/ulw-all-task-plans/task-1-first-read-map.txt'
    Expected: command exits 0 and output contains all five path families.
    Evidence: .omo/evidence/ulw-all-task-plans/task-1-first-read-map.txt

  Scenario: no product-code drift in calibration task
    Tool:     bash
    Steps:    bash -lc 'git diff --name-only | rg -v "^(\\.omo/evidence/ulw-all-task-plans/|docs/|CONTEXT.md|\\.omo/plans/)" | tee .omo/evidence/ulw-all-task-plans/task-1-no-product-code.txt'
    Expected: output is empty for this task.
    Evidence: .omo/evidence/ulw-all-task-plans/task-1-no-product-code.txt
  ```

  Commit: YES | Message: `docs(governance): calibrate ulw implementation state` | Files: [`docs/**`, `CONTEXT.md`, `.omo/evidence/ulw-all-task-plans/task-1-*`]

- [ ] 2. Alembic/质量门基础修复

  What to do: 修复或确认 Alembic migration graph invariant，记录 quality gate 当前基线。若 `tests/unit/common/test_alembic_migration_graph.py` 仍硬编码旧 head，改为断言唯一 head 和可诊断失败消息。
  Must NOT do: 不跳过 Alembic 测试；不把新 head 写成另一个易过期硬编码；不在 known-red gate 未记录时进入 migration-heavy work。

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [5, 15] | Blocked by: []

  References:
  - Pattern:  `.omo/plans/project-governance-refactor.md:110` - Gate Foundation 任务定义。
  - Pattern:  `.omo/plans/project-governance-refactor.md:57` - recurring commands。
  - Pattern:  `backend/AGENTS.md:46` - 后端验证 surface。
  - API/Type: `backend/alembic/versions/` - migration authority。
  - Test:     `backend/tests/unit/common/test_alembic_migration_graph.py` - stale head invariant。
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/alembic heads` shows exactly one head.
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/common/test_alembic_migration_graph.py --no-cov -q` exits 0.
  - [ ] `.omo/evidence/ulw-all-task-plans/task-2-migration-graph.txt` exists and contains both commands.

  QA scenarios:
  ```
  Scenario: migration graph is single-head
    Tool:     bash
    Steps:    bash -lc 'mkdir -p .omo/evidence/ulw-all-task-plans && { cd backend && venv/bin/alembic heads && venv/bin/python -m pytest tests/unit/common/test_alembic_migration_graph.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-2-migration-graph.txt'
    Expected: command exits 0; evidence contains one Alembic head and pytest passes.
    Evidence: .omo/evidence/ulw-all-task-plans/task-2-migration-graph.txt

  Scenario: basic release guard baseline is recorded
    Tool:     bash
    Steps:    bash -lc '{ git status --short; bash scripts/dependency-governance.sh status; bash scripts/secret-scan.sh; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-2-release-guard-baseline.txt'
    Expected: command exits 0 or exits non-zero with full output preserved; result explicitly labels unrelated pre-existing failures before downstream work continues.
    Evidence: .omo/evidence/ulw-all-task-plans/task-2-release-guard-baseline.txt
  ```

  Commit: YES | Message: `test(migrations): refresh alembic graph invariant` | Files: [`backend/tests/unit/common/test_alembic_migration_graph.py`, `.omo/evidence/ulw-all-task-plans/task-2-*`]

- [ ] 3. 发布治理契约和 draft-only 锁点基线

  What to do: 建立或更新发布治理契约，覆盖 `logical_id`、`revision_id`、`active_revision_id`、`working_revision_id`、`snapshot`、`binding_revision`、`rollback`、`regrade_run`、`audit_event`；同时盘点 `draft/published/archived` 对象和当前 draft-only 锁点。
  Must NOT do: 不写“后续支持版本”但没有机器语义；不遗漏 `ConfigVersion` 不可直接照搬风险；不改产品行为。

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [6, 7, 11, 13, 14] | Blocked by: []

  References:
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:83` - 阶段 0 目标。
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:99` - 必须列出 draft-only 锁点。
  - Pattern:  `.omo/plans/published-governance-revision-risk-register.md:15` - `ConfigVersion` 风险。
  - API/Type: `docs/api-contract/sales-trainer.md` - 新人训练路径契约权威。
  - Test:     `.omo/plans/published-governance-revision-test-matrix.md:20` - 后端治理测试矩阵。
  - External: `none`

  Acceptance criteria:
  - [ ] `rg -n "logical_id|revision_id|active_revision|working_revision|snapshot|binding_revision|rollback|regrade_run|audit_event" docs/api-contract docs/adr CONTEXT.md` exits 0.
  - [ ] `rg -n "只有 draft|不可直接修改|复制为新草稿|NOT_EDITABLE|SCORING_PROMPT_NOT_EDITABLE" backend/src/sales_trainer web/src/app/admin/sales-trainer web/src/components/admin/sales-trainer web/src/lib/sales-trainer` exits 0 and output is saved.
  - [ ] Contract text states `ConfigVersion` lifecycle may be referenced but immutable revision writes must not reuse mutable snapshot update paths.

  QA scenarios:
  ```
  Scenario: governance terms are discoverable
    Tool:     bash
    Steps:    bash -lc 'rg -n "logical_id|revision_id|active_revision|working_revision|snapshot|binding_revision|rollback|regrade_run|audit_event" docs/api-contract docs/adr CONTEXT.md 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-3-governance-terms.txt'
    Expected: output includes governance contract hits for revision, active pointer, rollback, regrade, audit.
    Evidence: .omo/evidence/ulw-all-task-plans/task-3-governance-terms.txt

  Scenario: draft-only locks are inventoried
    Tool:     bash
    Steps:    bash -lc 'rg -n "只有 draft|不可直接修改|复制为新草稿|NOT_EDITABLE|SCORING_PROMPT_NOT_EDITABLE" backend/src/sales_trainer web/src/app/admin/sales-trainer web/src/components/admin/sales-trainer web/src/lib/sales-trainer 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-3-draft-locks.txt'
    Expected: output lists current lock strings or no-lock evidence with explicit notes in the calibration document.
    Evidence: .omo/evidence/ulw-all-task-plans/task-3-draft-locks.txt
  ```

  Commit: YES | Message: `docs(governance): define published revision contract baseline` | Files: [`docs/api-contract/**`, `docs/adr/**`, `CONTEXT.md`, `.omo/evidence/ulw-all-task-plans/task-3-*`]

- [ ] 4. Newcomer domain/completion 契约漂移防线

  What to do: 对齐 `docs/api-contract/sales-trainer.md`、backend schemas/service、frontend API types 的新人训练路径命名、模块 completion rule、实时对练边界和兼容字段。若现有代码已对齐，只补 contract/schema/type 断言和证据。
  Must NOT do: 不改 API 字段语义而不写兼容说明；不把 `sales_bot`/`practice_sessions` 实时 runtime 混入 `sales_trainer` 异步新人路径。

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [7, 8, 12] | Blocked by: []

  References:
  - Pattern:  `.omo/plans/project-governance-refactor.md:126` - Contract Drift Guard。
  - Pattern:  `.omo/plans/newcomer-training-path-plan.md:151` - domain boundary docs。
  - Pattern:  `.omo/plans/newcomer-training-path-plan.md:189` - module configuration contract。
  - Pattern:  `web/AGENTS.md:56` - 新人训练路径与实时对练分离。
  - API/Type: `backend/src/sales_trainer/schemas.py` - backend DTO。
  - API/Type: `web/src/lib/api/types.ts` - frontend DTO。
  - Test:     `backend/tests/unit/test_sales_trainer_phase2_projection.py`; `web/src/lib/api/sales-trainer.test.ts`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_phase2_projection.py --no-cov -q` exits 0.
  - [ ] `cd web && npx vitest run src/lib/api/sales-trainer.test.ts` exits 0, or if file missing, executor adds the contract/type test before GREEN.
  - [ ] `rg -n "新人训练路径|sales_bot|practice_sessions|sales_trainer|实时对练|realtime_placeholder|article_exam" CONTEXT.md docs/api-contract backend/src/sales_trainer web/src/lib` exits 0.

  QA scenarios:
  ```
  Scenario: backend/frontend completion contract is executable
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_phase2_projection.py --no-cov -q; cd ../web && npx vitest run src/lib/api/sales-trainer.test.ts; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-4-completion-contract.txt'
    Expected: both focused commands exit 0; if a test was missing at RED, evidence includes RED then GREEN artifacts.
    Evidence: .omo/evidence/ulw-all-task-plans/task-4-completion-contract.txt

  Scenario: realtime boundary remains explicit
    Tool:     bash
    Steps:    bash -lc 'rg -n "新人训练路径|sales_bot|practice_sessions|实时对练|realtime_placeholder|article_exam" CONTEXT.md docs/api-contract backend/src/sales_trainer web/src/lib 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-4-domain-boundary.txt'
    Expected: output includes newcomer path contract hits and realtime contrast hits.
    Evidence: .omo/evidence/ulw-all-task-plans/task-4-domain-boundary.txt
  ```

  Commit: YES | Message: `docs(contract): align newcomer completion rule semantics` | Files: [`docs/api-contract/**`, `CONTEXT.md`, `backend/src/sales_trainer/**`, `web/src/lib/api/**`, tests]

- [ ] 5. ULW 证据通道和 checkpoint harness

  What to do: 建立 `.omo/evidence/ulw-all-task-plans/` 证据路径和 checkpoint 说明或轻量脚本包装，固定 focused gate、slice gate、release gate 的证据命名；把 `.sisyphus/evidence/task-9-quality-gate.txt` 与 `.omo/evidence/ulw-all-task-plans/quality-gate/` 的镜像/摘要规则写清楚。
  Must NOT do: 不新增第二套 full release gate；不宣称未运行命令通过；不覆盖 `.sisyphus` 既有证据。

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [6, 7, 8, 9, 10, 15] | Blocked by: []

  References:
  - Pattern:  `.omo/plans/project-governance-refactor.md:134` - Ultra Loop Checkpoint Harness。
  - Pattern:  `.omo/plans/project-governance-refactor.md:55` - evidence root 和 quality-gate mirror。
  - Pattern:  `.omo/plans/published-governance-revision-test-matrix.md:88` - final quality gate。
  - Pattern:  `scripts/AGENTS.md` - script governance。
  - API/Type: `scripts/critical-quality-gate.sh` - release truth。
  - Test:     `package.json:5` - root release-check command。
  - External: `none`

  Acceptance criteria:
  - [ ] `test -d .omo/evidence/ulw-all-task-plans`
  - [ ] `test -s .omo/evidence/ulw-all-task-plans/task-5-checkpoint-dry-run.txt`
  - [ ] If `bash scripts/critical-quality-gate.sh` is run, output is copied, symlinked, or summarized under `.omo/evidence/ulw-all-task-plans/quality-gate/`.

  QA scenarios:
  ```
  Scenario: dry checkpoint captures first-wave commands
    Tool:     bash
    Steps:    bash -lc 'mkdir -p .omo/evidence/ulw-all-task-plans/quality-gate && { git status --short; cd backend && venv/bin/alembic heads; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-5-checkpoint-dry-run.txt'
    Expected: command exits 0 and evidence contains git status plus Alembic heads output.
    Evidence: .omo/evidence/ulw-all-task-plans/task-5-checkpoint-dry-run.txt

  Scenario: quality gate mirror rule is documented
    Tool:     bash
    Steps:    bash -lc 'rg -n "task-9-quality-gate|quality-gate|\\.sisyphus/evidence|\\.omo/evidence/ulw-all-task-plans" docs .omo/plans .omo/evidence/ulw-all-task-plans 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-5-quality-gate-mirror-rule.txt'
    Expected: output states the mirror or summary rule for quality gate evidence.
    Evidence: .omo/evidence/ulw-all-task-plans/task-5-quality-gate-mirror-rule.txt
  ```

  Commit: YES | Message: `chore(governance): define ulw evidence checkpoint flow` | Files: [`docs/**`, `.omo/evidence/ulw-all-task-plans/task-5-*`]

- [ ] 6. revision/audit service gap close

  What to do: Compare existing `SalesTrainerAssetRevisionService`, path/prompt/unit/paper revision services, operation logs, and any common governance modules against the Stage 1 contract. Fill only the smallest missing gap for immutable payload, active pointer movement, field risk class, audit metadata, rollback/history/diff/impact-preview needed by path true-source slice.
  Must NOT do: Do not force a premature cross-domain generic framework if existing `sales_trainer` services satisfy the first slice; do not mutate published revision payloads in place.

  Parallelization: Can parallel: NO | Wave 2 | Blocks: [7, 10, 11, 13, 14] | Blocked by: [1, 3, 5]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:128` - Stage 1 infrastructure goal.
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:145` - required service operations.
  - Pattern:  `.omo/plans/published-governance-revision-risk-register.md:15` - immutable revision risk.
  - API/Type: `backend/src/sales_trainer/services/asset_revision_service.py` - existing revision service.
  - API/Type: `backend/src/sales_trainer/services/operation_log_service.py` - audit carrier.
  - API/Type: `backend/src/sales_trainer/models.py` - revision/audit backing rows.
  - Test:     `backend/tests/unit/test_newcomer_training_path_config_revision.py`; `backend/tests/unit/test_newcomer_training_path_audit_logs.py`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_audit_logs.py --no-cov -q` exits 0.
  - [ ] Tests prove published revision payload cannot be mutated in place and active pointer movement records before/after/reason/trace metadata.
  - [ ] Any new migration applies with `cd backend && venv/bin/alembic upgrade head`.

  QA scenarios:
  ```
  Scenario: immutable revision and audit unit tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_config_revision.py tests/unit/test_newcomer_training_path_audit_logs.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-6-revision-audit-tests.txt'
    Expected: pytest exits 0 and includes immutable revision plus audit tests.
    Evidence: .omo/evidence/ulw-all-task-plans/task-6-revision-audit-tests.txt

  Scenario: migration remains applicable
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/alembic upgrade head; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-6-alembic-upgrade.txt'
    Expected: Alembic exits 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-6-alembic-upgrade.txt
  ```

  Commit: YES | Message: `feat(governance): close revision audit service gaps` | Files: [`backend/src/sales_trainer/**`, `backend/src/common/**`, `backend/alembic/versions/**`, `backend/tests/**`, `docs/api-contract/**`]

- [ ] 7. 路径配置 active revision 真源最小闭环

  What to do: Make `newcomer_training_path_v1` path config active revision the source of truth for new reads/writes. Existing unit-derived path config must remain read-only legacy fallback/projection. Include backfill or verify-only migration path if needed.
  Must NOT do: Do not continue writing new path truth into `SalesTrainerUnit.config.path`; do not migrate paper/question/prompt/material broadly in this slice.

  Parallelization: Can parallel: NO | Wave 2 | Blocks: [8, 9, 10, 11] | Blocked by: [1, 3, 4, 6]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-plan.md:792` - recommended first execution slice.
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:179` - Stage 2 path true-source.
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:80` - path config center true-source acceptance.
  - API/Type: `backend/src/sales_trainer/services/path_config_service.py` - path active projection.
  - API/Type: `backend/src/sales_trainer/services/path_config_operations.py` - path revision operations.
  - API/Type: `backend/src/sales_trainer/services/path_service.py` - learner path read path.
  - API/Type: `backend/src/sales_trainer/path_config_api.py` - admin/API surface.
  - Test:     `backend/tests/unit/test_newcomer_training_path_boundary.py`; `backend/tests/integration/test_newcomer_training_path_config_api.py`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py --no-cov -q` exits 0.
  - [ ] Tests prove path active revision is used when present, legacy unit config is fallback only, and new writes create working/published path revision.
  - [ ] Backfill/verify-only evidence shows `newcomer_training_path_v1` can be derived without writing unless explicitly requested.

  QA scenarios:
  ```
  Scenario: backend path true-source tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_boundary.py tests/unit/test_newcomer_training_path_config_revision.py tests/integration/test_newcomer_training_path_config_api.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-7-path-true-source-tests.txt'
    Expected: pytest exits 0 and covers active revision source plus legacy fallback.
    Evidence: .omo/evidence/ulw-all-task-plans/task-7-path-true-source-tests.txt

  Scenario: path source inspection shows no new unit-path write authority
    Tool:     bash
    Steps:    bash -lc 'rg -n "SalesTrainerUnit\\.config|config\\.path|active_projection|newcomer_training_path_v1|legacy" backend/src/sales_trainer/services/path_config_service.py backend/src/sales_trainer/services/path_service.py backend/src/sales_trainer/path_config_api.py 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-7-path-source-inspection.txt'
    Expected: output shows active projection authority and legacy fallback; no route-level direct ORM writes.
    Evidence: .omo/evidence/ulw-all-task-plans/task-7-path-source-inspection.txt
  ```

  Commit: YES | Message: `feat(newcomer-path): make path revision the config source` | Files: [`backend/src/sales_trainer/**`, `backend/alembic/versions/**`, `backend/tests/**`, `docs/api-contract/**`]

- [ ] 8. 学员端 path projection 和 legacy fallback

  What to do: Ensure learner `/sales-trainer` path reads backend path active revision for module order/title/description/button/binding/disabled state, while keeping safe fallback when no active path revision exists. Frontend module labels must come from API/config or centralized mapping, not scattered TSX strings.
  Must NOT do: Do not make module 4 start realtime sessions; do not expose prompt IDs, hashes, answer keys, rubrics, or raw model output to learner-safe projection.

  Parallelization: Can parallel: YES | Wave 2 | Blocks: [10, 12] | Blocked by: [4, 7]

  References:
  - Pattern:  `.omo/plans/newcomer-training-path-plan.md:381` - learner module flows.
  - Pattern:  `.omo/plans/project-governance-refactor.md:295` - learner public projection consolidation.
  - Pattern:  `web/AGENTS.md:56` - learner/admin route distinction.
  - API/Type: `backend/src/sales_trainer/services/path_projection_payloads.py` - backend path payload.
  - API/Type: `backend/src/sales_trainer/services/unit_public_payloads.py` - learner-safe projection.
  - API/Type: `web/src/lib/sales-trainer/module-path.ts` - frontend module mapping.
  - API/Type: `web/src/app/(dashboard)/sales-trainer/page.tsx` - learner homepage.
  - Test:     `backend/tests/unit/test_sales_trainer_unit_public_payloads.py`; `backend/tests/unit/test_sales_trainer_path_projection_ai_coach.py`; `web/src/lib/sales-trainer/module-path.test.ts`; `web/src/app/(dashboard)/sales-trainer/page.test.tsx`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_unit_public_payloads.py tests/unit/test_sales_trainer_path_projection_ai_coach.py --no-cov -q` exits 0.
  - [ ] `cd web && npx vitest run 'src/lib/sales-trainer/module-path.test.ts' 'src/app/(dashboard)/sales-trainer/page.test.tsx'` exits 0.
  - [ ] Learner projection does not include prompt ids, hashes, answer keys, rubrics, or raw model output.

  QA scenarios:
  ```
  Scenario: learner projection unit and UI tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_unit_public_payloads.py tests/unit/test_sales_trainer_path_projection_ai_coach.py --no-cov -q; cd ../web && npx vitest run "src/lib/sales-trainer/module-path.test.ts" "src/app/(dashboard)/sales-trainer/page.test.tsx"; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-8-learner-projection-tests.txt'
    Expected: all focused tests exit 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-8-learner-projection-tests.txt

  Scenario: learner-safe API payload excludes sensitive fields
    Tool:     curl
    Steps:    bash -lc 'curl -i http://localhost:3444/api/v1/sales-trainer/path 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-8-learner-path-http.txt'
    Expected: HTTP response is 200/401 depending local auth setup; if 200, body does not contain prompt_revision_id, answer_key, rubric, raw_model_output, or scoring_prompt. If local auth blocks, evidence records the exact status and a focused backend projection test is the pass gate.
    Evidence: .omo/evidence/ulw-all-task-plans/task-8-learner-path-http.txt
  ```

  Commit: YES | Message: `feat(newcomer-path): read learner path from active revision` | Files: [`backend/src/sales_trainer/**`, `web/src/lib/sales-trainer/**`, `web/src/app/(dashboard)/sales-trainer/**`, tests]

- [ ] 9. 管理端 path save/publish/rollback workflow

  What to do: Ensure `/admin/sales-trainer/paths` can load active/working revision, save working revision, publish active revision, rollback to a published revision, show dependency gate/impact/reason/audit feedback, and hide technical fields by default.
  Must NOT do: Do not bypass `web/src/lib/api` with page-local fetch; do not rely on front-end-only permission hiding; do not expose raw JSON as the normal admin path.

  Parallelization: Can parallel: YES | Wave 2 | Blocks: [10, 12, 13] | Blocked by: [5, 7]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:297` - Stage 4 natural editing UI.
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:13` - admin natural edit acceptance.
  - Pattern:  `web/src/app/admin/sales-trainer/AGENTS.md:31` - page composition conventions.
  - API/Type: `web/src/app/admin/sales-trainer/paths/page.tsx`
  - API/Type: `web/src/components/admin/sales-trainer/path-config-center.tsx`
  - API/Type: `web/src/lib/sales-trainer/config-center.ts`
  - API/Type: `web/src/lib/api/client-domains.ts`
  - Test:     `web/src/app/admin/sales-trainer/paths/page.test.tsx`; `web/src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx`; `web/src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx`; `web/src/lib/sales-trainer/config-center.test.ts`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd web && npx vitest run 'src/app/admin/sales-trainer/paths/page.test.tsx' 'src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx' 'src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx' 'src/lib/sales-trainer/config-center.test.ts'` exits 0.
  - [ ] `cd web && npx tsc --noEmit` exits 0.
  - [ ] Browser QA captures save/publish/rollback path with audit or operation log confirmation.

  QA scenarios:
  ```
  Scenario: admin path workflow tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd web && npx vitest run "src/app/admin/sales-trainer/paths/page.test.tsx" "src/app/admin/sales-trainer/paths/page-audio-bindings.test.tsx" "src/app/admin/sales-trainer/paths/page-business-bindings.test.tsx" "src/lib/sales-trainer/config-center.test.ts" && npx tsc --noEmit; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-9-admin-path-tests.txt'
    Expected: Vitest and TypeScript exit 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-9-admin-path-tests.txt

  Scenario: admin path browser smoke
    Tool:     playwright(real Chrome)
    Steps:    bash -lc 'cd web && npx playwright test tests/e2e/admin-sales-trainer-path-revision.spec.ts --project=chromium --output=../.omo/evidence/ulw-all-task-plans/task-9-playwright'
    Expected: test exits 0 and screenshot/action trace under `.omo/evidence/ulw-all-task-plans/task-9-playwright` shows load, save working revision, publish, rollback, and permission/error state.
    Evidence: .omo/evidence/ulw-all-task-plans/task-9-playwright
  ```

  Commit: YES | Message: `feat(web): support path revision admin workflow` | Files: [`web/src/app/admin/sales-trainer/paths/**`, `web/src/components/admin/sales-trainer/**`, `web/src/lib/sales-trainer/**`, `web/src/lib/api/**`, tests]

- [ ] 10. 旧 attempt/snapshot 不变与新学员未来生效证明

  What to do: Add or confirm tests proving path publish/rollback only affects future learners/new attempts. Existing attempts, audio submissions, quiz answers, training records, and session snapshots must continue to read frozen snapshot/revision refs or `legacy_snapshot_only` markers.
  Must NOT do: Do not backfill unverifiable historical lineage; do not read latest active revision when displaying old records.

  Parallelization: Can parallel: NO | Wave 2 | Blocks: [11, 14, final QA] | Blocked by: [6, 7, 8, 9]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:47` - historical snapshot immutable acceptance.
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:64` - future effective acceptance.
  - Pattern:  `.omo/plans/published-governance-revision-risk-register.md:17` - attempt lineage risk.
  - API/Type: `backend/src/sales_trainer/services/path_attempt_context_service.py`
  - API/Type: `backend/src/sales_trainer/services/training_record_lineage.py`
  - API/Type: `backend/src/sales_trainer/services/quiz_attempt_payloads.py`
  - Test:     `backend/tests/unit/test_newcomer_training_path_attempt_lineage.py`; `backend/tests/unit/test_newcomer_training_path_record_lineage.py`; `backend/tests/integration/test_newcomer_training_path_config_api.py`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py tests/unit/test_newcomer_training_path_record_lineage.py tests/integration/test_newcomer_training_path_config_api.py --no-cov -q` exits 0.
  - [ ] Tests include old attempt before path publish, new learner after publish, rollback future-only, and legacy snapshot-only case.
  - [ ] No historical display code falls back to latest active revision when snapshot/revision refs exist.

  QA scenarios:
  ```
  Scenario: future-only lineage tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py tests/unit/test_newcomer_training_path_record_lineage.py tests/integration/test_newcomer_training_path_config_api.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-10-future-only-lineage.txt'
    Expected: pytest exits 0 and names old attempt/new learner/rollback/legacy cases.
    Evidence: .omo/evidence/ulw-all-task-plans/task-10-future-only-lineage.txt

  Scenario: no latest-rebuild historical fallback
    Tool:     bash
    Steps:    bash -lc 'rg -n "legacy_snapshot_only|path_revision_id|paper_revision_id|active_projection|latest" backend/src/sales_trainer/services/training_record_lineage.py backend/src/sales_trainer/services/path_attempt_context_service.py backend/src/sales_trainer/services/quiz_attempt_payloads.py 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-10-history-source-inspection.txt'
    Expected: output shows snapshot/revision refs and any latest lookup is not used to override existing historical refs.
    Evidence: .omo/evidence/ulw-all-task-plans/task-10-history-source-inspection.txt
  ```

  Commit: YES | Message: `test(newcomer-path): prove path revisions are future only` | Files: [`backend/src/sales_trainer/**`, `backend/tests/**`, `docs/api-contract/**`]

- [ ] 11. sales_trainer 资产 revision lineage 迁移

  What to do: Extend the Wave 2 pattern to paper/question/article binding/prompt/score standard/material/unit assets. Published edits create working revisions, publish moves active pointer, rollback validates dependencies, and attempts/submissions freeze revision refs/snapshots.
  Must NOT do: Do not migrate all assets in one oversized commit; split per asset family if the diff becomes large, but keep each asset task implementation+tests atomic.

  Parallelization: Can parallel: YES | Wave 3 | Blocks: [12, 13, 15] | Blocked by: [6, 10]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:236` - Stage 3 asset migration.
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:30` - automatic revision generation.
  - API/Type: `backend/src/sales_trainer/services/exam_paper_revision_workflow.py`
  - API/Type: `backend/src/sales_trainer/services/question_bank/revision_service.py`
  - API/Type: `backend/src/sales_trainer/services/prompt_revision_service.py`
  - API/Type: `backend/src/sales_trainer/services/material_publish_workflow.py`
  - Test:     `backend/tests/unit/test_newcomer_training_path_papers.py`; `backend/tests/unit/test_newcomer_training_path_articles.py`; `backend/tests/unit/test_newcomer_training_path_questions.py`; `backend/tests/unit/test_newcomer_training_path_score_prompts.py`; `backend/tests/unit/test_newcomer_training_path_material_governance.py`
  - External: `none`

  Acceptance criteria:
  - [ ] Focused backend asset tests exit 0.
  - [ ] Published edit on each migrated asset creates working revision and does not modify active payload.
  - [ ] Archive/delete is blocked when active path references the asset.

  QA scenarios:
  ```
  Scenario: sales trainer asset revision suite passes
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_papers.py tests/unit/test_newcomer_training_path_articles.py tests/unit/test_newcomer_training_path_questions.py tests/unit/test_newcomer_training_path_score_prompts.py tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_paper_api.py tests/integration/test_newcomer_training_path_article_api.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-11-asset-revision-suite.txt'
    Expected: pytest exits 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-11-asset-revision-suite.txt

  Scenario: archive guard inspection
    Tool:     bash
    Steps:    bash -lc 'rg -n "archive|active.*binding|dependency|REVISION_DEPENDENCY_INVALID|published revision" backend/src/sales_trainer/services backend/tests/unit/test_newcomer_training_path_material_governance.py backend/tests/unit/test_newcomer_training_path_papers.py 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-11-archive-guard.txt'
    Expected: output shows dependency/active binding guard tests or service checks.
    Evidence: .omo/evidence/ulw-all-task-plans/task-11-archive-guard.txt
  ```

  Commit: YES | Message: `feat(newcomer-path): migrate assets to revision lineage` | Files: [`backend/src/sales_trainer/**`, `backend/alembic/versions/**`, `backend/tests/**`, `docs/api-contract/**`]

- [ ] 12. 管理端自然编辑 UI 和技术字段隐藏

  What to do: Update admin screens for units, papers, questions, score standards/prompts, articles, materials, path config, logs, records so the main workflow is edit/save working revision/publish/history/rollback/regrade where applicable. Technical fields default hidden, visible only in diagnostics/operations disclosure.
  Must NOT do: Do not redesign unrelated visuals; do not scatter business copy/rules in TSX; do not introduce page-local fetch or front-end-only policy.

  Parallelization: Can parallel: YES | Wave 3 | Blocks: [15] | Blocked by: [8, 9, 11]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:13` - admin natural editing.
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:165` - technical field hiding.
  - Pattern:  `web/src/app/admin/sales-trainer/AGENTS.md:31` - admin page conventions.
  - API/Type: `web/src/app/admin/sales-trainer/papers/[paperId]/edit/page.tsx`
  - API/Type: `web/src/app/admin/sales-trainer/units/page.tsx`
  - API/Type: `web/src/lib/sales-trainer/admin-display.ts`
  - Test:     `web/src/app/admin/sales-trainer/papers/page.test.tsx`; `web/src/app/admin/sales-trainer/papers/[paperId]/edit/page.test.tsx`; `web/src/app/admin/sales-trainer/score-standards/page.test.tsx`; `web/src/lib/sales-trainer/admin-display.test.ts`
  - External: `none`

  Acceptance criteria:
  - [ ] Focused admin Vitest suite exits 0.
  - [ ] `cd web && npx tsc --noEmit` exits 0.
  - [ ] Default admin main flow contains no raw `module_key`, `unit_id`, `paper_key`, `path_key`, `sales_trainer`, or raw JSON unless in diagnostics/ops disclosure.

  QA scenarios:
  ```
  Scenario: admin natural edit test suite passes
    Tool:     bash
    Steps:    bash -lc '{ cd web && npx vitest run "src/app/admin/sales-trainer/papers/page.test.tsx" "src/app/admin/sales-trainer/papers/[paperId]/edit/page.test.tsx" "src/app/admin/sales-trainer/score-standards/page.test.tsx" "src/app/admin/sales-trainer/units/page.test.tsx" "src/lib/sales-trainer/admin-display.test.ts" && npx tsc --noEmit; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-12-admin-ui-tests.txt'
    Expected: Vitest and TypeScript exit 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-12-admin-ui-tests.txt

  Scenario: technical fields are not default admin copy
    Tool:     bash
    Steps:    bash -lc 'rg -n "module_key|unit_id|paper_key|path_key|sales_trainer|raw JSON" web/src/app/admin/sales-trainer web/src/components/admin/sales-trainer web/src/lib/sales-trainer 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-12-tech-field-scan.txt'
    Expected: hits are limited to DTO/test/diagnostics disclosure paths and are explained in evidence notes.
    Evidence: .omo/evidence/ulw-all-task-plans/task-12-tech-field-scan.txt
  ```

  Commit: YES | Message: `feat(web): make published governance edits natural` | Files: [`web/src/app/admin/sales-trainer/**`, `web/src/components/admin/sales-trainer/**`, `web/src/lib/sales-trainer/**`, tests]

- [ ] 13. 权限、审计、诊断、回滚、重评

  What to do: Centralize backend permission decisions for configure/publish/rollback/archive/regrade/log view, extend audit events with before/after/reason/trace/impact, implement diagnostics and regrade preview/append-only run semantics.
  Must NOT do: Do not allow publish/rollback/regrade from frontend-only checks; do not auto-regrade on prompt/scoring changes.

  Parallelization: Can parallel: YES | Wave 3 | Blocks: [15] | Blocked by: [6, 9, 11]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:112` - high-risk regrade audit.
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:128` - permission interception.
  - Pattern:  `.omo/plans/published-governance-revision-acceptance-checklist.md:146` - operational diagnostics.
  - Pattern:  `.omo/plans/published-governance-revision-risk-register.md:20` - concurrent edit and permission risks.
  - API/Type: `backend/src/sales_trainer/permissions.py`
  - API/Type: `backend/src/sales_trainer/services/operation_log_service.py`
  - API/Type: `backend/src/sales_trainer/services/regrade_service.py`
  - API/Type: `web/src/app/admin/sales-trainer/settings/page.tsx`
  - API/Type: `web/src/app/admin/sales-trainer/operation-logs/page.tsx`
  - Test:     `backend/tests/unit/test_newcomer_training_path_permissions.py`; `backend/tests/integration/test_newcomer_training_path_rbac_api.py`; `backend/tests/unit/test_newcomer_training_path_audit_logs.py`; `backend/tests/integration/test_newcomer_training_path_regrade_api.py`
  - External: `none`

  Acceptance criteria:
  - [ ] Backend permission/audit/regrade tests exit 0.
  - [ ] Frontend diagnostics/log/regrade tests exit 0.
  - [ ] Regrade requires permission, preview, reason, trace id, and appends result instead of overwriting original.

  QA scenarios:
  ```
  Scenario: backend governance control tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_permissions.py tests/integration/test_newcomer_training_path_rbac_api.py tests/unit/test_newcomer_training_path_audit_logs.py tests/integration/test_newcomer_training_path_regrade_api.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-13-backend-controls.txt'
    Expected: pytest exits 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-13-backend-controls.txt

  Scenario: admin diagnostics and logs tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd web && npx vitest run "src/app/admin/sales-trainer/settings/page.test.tsx" "src/app/admin/sales-trainer/operation-logs/page.test.tsx" "src/app/admin/sales-trainer/score-results/page.test.tsx" "src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx"; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-13-admin-diagnostics.txt'
    Expected: Vitest exits 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-13-admin-diagnostics.txt
  ```

  Commit: YES | Message: `feat(governance): enforce permissions audit diagnostics and regrade` | Files: [`backend/src/sales_trainer/**`, `backend/tests/**`, `web/src/app/admin/sales-trainer/**`, `web/src/lib/sales-trainer/**`, tests]

- [ ] 14. curriculum_practice 对齐

  What to do: Align curriculum practice assets with revision/snapshot semantics without breaking existing `published_asset_refs` and `curriculum_snapshot`. Parser must accept existing refs and new revision/hash refs; session creation freezes current refs/snapshot.
  Must NOT do: Do not break existing practice template/session creation; do not rewrite curriculum runtime beyond necessary adapters.

  Parallelization: Can parallel: YES | Wave 3 | Blocks: [15] | Blocked by: [6, 10]

  References:
  - Pattern:  `.omo/plans/published-governance-revision-execution-pack.md:354` - Stage 5 curriculum alignment.
  - Pattern:  `.omo/plans/published-governance-revision-risk-register.md:33` - curriculum refs compatibility risk.
  - API/Type: `backend/src/curriculum_practice/services/published_asset_refs.py`
  - API/Type: `backend/src/curriculum_practice/services/snapshots.py`
  - API/Type: `backend/src/curriculum_practice/services/publishing_gates.py`
  - Test:     `backend/tests/unit/test_practice_template_published_asset_refs.py`; `backend/tests/integration/test_curriculum_practice_session_snapshot.py`; `backend/tests/integration/test_curriculum_snapshot_immutability.py`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/test_practice_template_published_asset_refs.py tests/integration/test_curriculum_practice_session_snapshot.py tests/integration/test_curriculum_snapshot_immutability.py --no-cov -q` exits 0.
  - [ ] Existing refs and new refs are both accepted.
  - [ ] Old sessions keep old `curriculum_snapshot` after asset revision changes.

  QA scenarios:
  ```
  Scenario: curriculum refs remain compatible
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_practice_template_published_asset_refs.py tests/integration/test_curriculum_practice_session_snapshot.py tests/integration/test_curriculum_snapshot_immutability.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-14-curriculum-refs.txt'
    Expected: pytest exits 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-14-curriculum-refs.txt

  Scenario: curriculum latest rebuild is not used for old snapshots
    Tool:     bash
    Steps:    bash -lc 'rg -n "published_asset_refs|curriculum_snapshot|revision|hash|latest" backend/src/curriculum_practice/services backend/tests/integration/test_curriculum_snapshot_immutability.py 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-14-curriculum-source-inspection.txt'
    Expected: output supports old snapshot immutability and compatibility notes.
    Evidence: .omo/evidence/ulw-all-task-plans/task-14-curriculum-source-inspection.txt
  ```

  Commit: YES | Message: `feat(curriculum): align published asset refs with revisions` | Files: [`backend/src/curriculum_practice/**`, `backend/tests/**`, `docs/api-contract/**`]

- [ ] 15. release/script/CI bridge 和全量试运行准备

  What to do: Align release truth, script safety, dependency governance, and final quality evidence. Inventory data-changing scripts, harden the smallest high-risk script if needed, ensure `critical-quality-gate.sh` remains the release truth and release verification references its evidence rather than conflicting with it.
  Must NOT do: Do not refactor multiple large scripts in one task; do not create two contradictory release gates; do not claim full gate pass if existing unrelated failures remain.

  Parallelization: Can parallel: NO | Wave 3 | Blocks: [final] | Blocked by: [5, 11, 12, 13, 14]

  References:
  - Pattern:  `.omo/plans/project-governance-refactor.md:263` - script safety inventory.
  - Pattern:  `.omo/plans/project-governance-refactor.md:278` - CI/dependency governance.
  - Pattern:  `.omo/plans/project-governance-refactor.md:287` - release verification bridge.
  - Pattern:  `.omo/plans/published-governance-revision-test-matrix.md:88` - complete quality gate.
  - API/Type: `scripts/critical-quality-gate.sh`
  - API/Type: `scripts/dependency-governance.sh`
  - API/Type: `backend/src/common/analytics/verification_runner.py`
  - Test:     `backend/tests/unit/test_repo_hygiene_scripts.py`; `backend/tests/unit/test_verification_runner.py`; `backend/tests/integration/test_release_gate.py`; `backend/tests/contract/test_release_verification_contract.py`
  - External: `none`

  Acceptance criteria:
  - [ ] `cd backend && venv/bin/python -m pytest tests/unit/test_repo_hygiene_scripts.py tests/unit/test_verification_runner.py tests/integration/test_release_gate.py tests/contract/test_release_verification_contract.py --no-cov -q` exits 0.
  - [ ] `bash scripts/dependency-governance.sh status` exits 0 or evidence documents existing blocker and owner.
  - [ ] `bash scripts/critical-quality-gate.sh` output is captured under `.sisyphus/evidence/` and mirrored/summarized under `.omo/evidence/ulw-all-task-plans/quality-gate/`.

  QA scenarios:
  ```
  Scenario: release bridge tests pass
    Tool:     bash
    Steps:    bash -lc '{ cd backend && venv/bin/python -m pytest tests/unit/test_repo_hygiene_scripts.py tests/unit/test_verification_runner.py tests/integration/test_release_gate.py tests/contract/test_release_verification_contract.py --no-cov -q; } 2>&1 | tee .omo/evidence/ulw-all-task-plans/task-15-release-bridge-tests.txt'
    Expected: pytest exits 0.
    Evidence: .omo/evidence/ulw-all-task-plans/task-15-release-bridge-tests.txt

  Scenario: complete quality gate evidence is preserved
    Tool:     bash
    Steps:    bash -lc 'mkdir -p .omo/evidence/ulw-all-task-plans/quality-gate && bash scripts/critical-quality-gate.sh 2>&1 | tee .omo/evidence/ulw-all-task-plans/quality-gate/task-15-critical-quality-gate.txt'
    Expected: command exits 0; if it exits non-zero, full output remains captured and the executor labels each failure as introduced vs pre-existing before final review.
    Evidence: .omo/evidence/ulw-all-task-plans/quality-gate/task-15-critical-quality-gate.txt
  ```

  Commit: YES | Message: `chore(release): bridge governance run to quality gate evidence` | Files: [`scripts/**`, `.github/workflows/**`, `backend/src/common/analytics/**`, `backend/tests/**`, `docs/api-contract/release-verification.md`]

## Final verification wave (MANDATORY - after all implementation tasks)
> Runs in PARALLEL. ALL must APPROVE. Surface results to the caller and wait for an explicit "okay" before declaring complete.
- [ ] F1. Plan compliance audit - every task done, every acceptance criterion met
- [ ] F2. Code quality review - diagnostics clean, idioms match, no dead code
- [ ] F3. Real manual QA - every QA scenario executed with evidence captured
- [ ] F4. Scope fidelity - nothing extra shipped beyond Must-Have, nothing Must-NOT-Have introduced

## Commit strategy
- One logical change per commit. Conventional Commits (`<type>(<scope>): <subject>` body + footer).
- Atomic: every commit builds and passes tests on its own.
- No "WIP" / "fix typo squash later" commits on the final branch - clean up before merge.
- Reference the plan file path in the final commit footer: `Plan: .omo/plans/ulw-all-task-plans-execution.md`.

## Success criteria
- All Must-Have shipped; all QA scenarios pass with captured evidence; F1-F4 approved; commit history clean.
