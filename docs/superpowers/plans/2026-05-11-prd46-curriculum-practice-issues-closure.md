# PRD #46 Curriculum Practice Issues Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按依赖顺序安全闭环 GitHub issues #47-#54，建立课程化销售训练的 `PracticeTemplate -> RuntimeSnapshotService -> PracticeSession -> EvaluationRun -> TrainingReportSnapshot` 最小可验证链路。

**Architecture:** 新增 `curriculum_practice` 课程化域，负责内容资产、PracticeTemplate、发布门禁、runtime snapshot 与课程化 lineage；现有 `TrainingTask`、`PracticeSession`、`EvaluationRun`、`TrainingReportSnapshot`、`ConfigBundle`、StepFun runtime、RBAC 只通过明确接口薄集成。运行时永远读取冻结 snapshot，不读取 latest content。

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / Pydantic / pytest / ruff / mypy / Next.js / TypeScript / Vitest / ESLint / GitHub Issues。

---

## 0. 全局不变量

所有切片实施和关闭前都必须确认：

- 不改变 `TrainingTask.status` 枚举、DB 约束或状态机。
- 不改变 `PracticeSession.status` 枚举、DB check constraint 或生命周期语义。
- 不把课程内容资产、`PracticeTemplate`、`CaseItem`、`RoleProfile` 纳入 `ConfigBundle` 生命周期。
- 不扩展 `User.role` DB constraint；课程化权限只能通过 action-level RBAC 或现有角色映射表达。
- 不恢复 legacy Sales runtime；不得恢复或引用 `base_sales_handler.py`、`enhanced_handler.py`、`simple_handler.py`。
- 不重算、不迁移、不批量更新历史 `TrainingReportSnapshot`。
- 不创建 `SessionV2`、场景专用 session root 或并行会话模型。
- 不让 StepFun 在运行中读取 latest curriculum/practice content；运行时只能读冻结 snapshot。
- 不允许 LLM 输出直接成为 published content 或最终评分。
- 不使用 `as any`、`@ts-ignore`、`@ts-expect-error`。
- 不删除、不移动旧 admin config 页面或稳定 API 前缀。
- 不把 preflight、stage、reconnect 状态塞进 `TrainingTask.status` 或 `PracticeSession.status`；这些只能进入 `PracticeSession.runtime_state` 或未来 stage run 模型。

---

## 1. 分支、提交与检查点策略

### 推荐分支

- `plan/prd46-47-boundary`
- `feat/prd46-48-practice-template`
- `feat/prd46-49-runtime-snapshot`
- `feat/prd46-50-session-snapshot`
- `feat/prd46-51-task-template-binding`
- `feat/prd46-52-curriculum-lineage`
- `test/prd46-53-snapshot-stepfun-regression`
- `feat/prd46-54-case-role-pilot`

不要默认把 #47-#54 全部放进一个分支。#47 和 #54 是 HITL gate，必须有人工确认点；#48-#53 可 AFK，但每个 issue 都要独立 evidence。

### 每个 issue 的闭环节奏

- [ ] 检查工作区：`git status --short`，确认没有无关变更。
- [ ] 读取 issue body、PRD #46、#47 addendum、PRD #23 ADR。
- [ ] 写最小失败测试或架构验收清单。
- [ ] 运行 targeted test，确认 red 是预期缺失能力。
- [ ] 做最小实现。
- [ ] 运行 targeted test，确认 green。
- [ ] 运行该 issue 的验证命令族。
- [ ] 检查 PRD #23 不变量。
- [ ] 原子提交。
- [ ] 写 issue completion evidence。
- [ ] HITL issue 停止等待人工确认；通过后再关闭。

### 推荐提交信息

```bash
test(curriculum): add PracticeTemplate publish gate tests
feat(curriculum): add PracticeTemplate model and migration
feat(curriculum): expose PracticeTemplate admin API
feat(web): add PracticeTemplate admin page
test(curriculum): pin runtime snapshot hashing behavior
feat(curriculum): add RuntimeSnapshotService
feat(common): persist curriculum snapshot on PracticeSession
feat(common): bind TrainingTask to PracticeTemplate
feat(evaluation): propagate curriculum lineage to report snapshots
test(runtime): cover snapshot immutability and StepFun boundaries
feat(curriculum): add CaseItem and RoleProfile pilot
```

---

## 2. 依赖图与关闭顺序

```text
#47 HITL: 架构边界与契约锁定
  |
  v
#48 AFK: PracticeTemplate 最小骨架
  | \
  |  \
  |   v
  |  #54 HITL: CaseItem + RoleProfile 最小内容资产试点
  |
  v
#49 AFK: RuntimeSnapshotService 与 snapshot schema
  |
  v
#50 AFK: PracticeSession 快照持久化
  |
  v
#51 AFK: TrainingTask 可选 PracticeTemplate 绑定
  |
  v
#52 AFK: EvaluationRun / TrainingReportSnapshot lineage 传播
  |
  v
#53 AFK: 快照不可变性与 StepFun 边界回归测试
```

必须关闭顺序：`#47 -> #48 -> #49 -> #50 -> #51 -> #52 -> #53`。

特殊规则：#54 被 #48 阻塞；#54 关闭前必须人工确认 `CaseItem + RoleProfile` 字段粒度和披露策略。

---

## 3. 预计文件结构

### 课程化域

- Create: `backend/src/curriculum_practice/__init__.py` — 课程化域包入口。
- Create: `backend/src/curriculum_practice/models.py` — `PracticeTemplate`、`CaseItem`、`RoleProfile` ORM 模型。
- Create: `backend/src/curriculum_practice/schemas.py` — Pydantic schemas、snapshot schema、错误结构。
- Create: `backend/src/curriculum_practice/api.py` — PracticeTemplate / content asset API router。
- Create: `backend/src/curriculum_practice/permissions.py` — action-level 权限检查，不改 `User.role` DB constraint。
- Create: `backend/src/curriculum_practice/services/practice_templates.py` — PracticeTemplate CRUD、发布与引用解析。
- Create: `backend/src/curriculum_practice/services/publishing_gates.py` — 发布门禁。
- Create: `backend/src/curriculum_practice/services/snapshots.py` — `RuntimeSnapshotService` 与 deterministic hash。
- Create: `backend/src/curriculum_practice/services/content_assets.py` — `CaseItem`、`RoleProfile` 最小资产服务。

### 共享后端集成

- Modify: `backend/src/common/db/models.py` — 增加 nullable FK / JSON 字段，禁止改状态枚举。
- Modify: `backend/src/common/db/schemas.py` — session response 向后兼容暴露课程化字段。
- Modify: `backend/src/common/services/practice_session_service.py` — template-backed session 创建时调用 snapshot service。
- Modify: `backend/src/common/training_tasks/schemas.py` — task request/response 支持 optional `practice_template_id`。
- Modify: `backend/src/common/training_tasks/service.py` — start-session 解析 template 并创建 snapshot session。
- Modify: `backend/src/common/api/training_tasks.py` — API 入参/出参薄集成。
- Modify: `backend/src/evaluation/services/evaluation_run_service.py` — 传播 curriculum lineage。
- Modify: `backend/src/evaluation/services/training_report_snapshot_service.py` — 报告 snapshot 复制 lineage。
- Modify: `backend/src/router_registry.py` / `backend/src/app_factory.py` — 注册课程化 router。
- Create/Modify: `backend/alembic/versions/*` — 每个 DB 变更独立 migration。

### 前端集成

- Modify: `web/src/lib/api/types.ts` — PracticeTemplate / content asset / snapshot 类型。
- Modify: `web/src/lib/api/client.ts` / `web/src/lib/api/client-domains.ts` — API client。
- Modify: `web/src/app/admin/page.tsx` — admin 入口链接。
- Modify: `web/src/components/layout/admin-sidebar.tsx` — sidebar 入口。
- Create: `web/src/app/admin/curriculum-practice/templates/page.tsx` — PracticeTemplate 最小管理页。
- Create: `web/src/app/admin/curriculum-practice/templates/page.test.tsx` — Admin 页面测试。

### 测试

- Create: `backend/tests/unit/test_curriculum_publish_gates.py`
- Create: `backend/tests/integration/test_practice_template_api.py`
- Create: `backend/tests/unit/test_curriculum_runtime_snapshot_service.py`
- Create: `backend/tests/integration/test_curriculum_runtime_snapshot_service.py`
- Create: `backend/tests/integration/test_curriculum_practice_session_snapshot.py`
- Modify: `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- Modify/Create: `backend/tests/contract/test_sessions.py`
- Modify/Create: `backend/tests/integration/test_training_tasks_api.py`
- Create: `backend/tests/integration/test_curriculum_lineage_flow.py`
- Create: `backend/tests/integration/test_curriculum_snapshot_immutability.py`
- Create: `backend/tests/integration/test_curriculum_report_lineage_immutability.py`
- Create/Modify: `backend/tests/unit/test_stepfun_payload_snapshots.py`
- Create: `backend/tests/unit/test_case_item_role_profile_assets.py`
- Create: `backend/tests/integration/test_case_role_template_snapshot.py`

---

## 4. Issue-by-Issue 实施计划

### Task 1: #47 课程化域架构边界与契约锁定（HITL）

**Files:**
- Create or Modify: `docs/adr/2026-05-11-curriculum-practice-boundary-contract.md`
- Reference: `docs/plans/2026-05-11-curriculum-practice-stepfun-llm-architecture-detailed.md`
- Reference: `docs/adr/2026-05-11-architecture-boundary-domain-contract.md`

- [ ] **Step 1: 写架构边界 addendum**

  内容必须明确：`curriculum_practice` 负责内容资产、`PracticeTemplate`、发布门禁、`RuntimeSnapshotService`、learning path；不负责 StepFun WebSocket 协议、评分引擎内部算法、复训任务生命周期、ConfigBundle 通用生命周期、KnowledgeAnswerEngine 检索实现。

- [ ] **Step 2: 固化统一版本引用结构**

  ```json
  {
    "asset_type": "practice_template|curriculum|lesson|knowledge_point|question_bank|question_item|case_item|role_profile|rubric_set|scoring_ruleset|knowledge_base|prompt_contract|model_config",
    "asset_id": "uuid-string",
    "version": 1,
    "hash": "sha256:...",
    "snapshot_label": "published|superseded|legacy_unversioned"
  }
  ```

- [ ] **Step 3: 固化深模块接口**

  ```python
  PracticeTemplateService.publish_template(template_id, actor_id)
  PracticeTemplateService.resolve_for_task(training_task_id)
  RuntimeSnapshotService.build_for_session(template_ref, training_task_ref, actor_id)
  ```

- [ ] **Step 4: 验证 issue 和工作区**

  Run:

  ```bash
  gh issue view 47 --json number,title,state,labels,body,comments
  git status --short
  ```

  Expected: issue 存在且为 HITL；工作区只包含 #47 文档变更。

- [ ] **Step 5: 提交**

  ```bash
  git add docs/adr/2026-05-11-curriculum-practice-boundary-contract.md
  git commit -m "docs(curriculum): lock PRD46 boundary contract"
  ```

- [ ] **Step 6: 写 completion evidence 并等待人工确认**

  Evidence 必须包含 reviewer、review date、确认的边界、不变量、`RuntimeSnapshotService` 唯一入口、`CaseItem + RoleProfile` 作为 Slice 08 pilot。

**Closure Gate:** 人工确认完成后才能关闭 #47，且关闭后才能启动 #48。

**Rollback:** 若人工否决边界，只修改 addendum，不进入 #48。

---

### Task 2: #48 PracticeTemplate 最小骨架（AFK）

**Files:**
- Create: `backend/src/curriculum_practice/*`
- Modify: `backend/src/common/db/models.py`
- Modify: `backend/src/router_registry.py`
- Modify: `backend/src/app_factory.py`
- Create: `backend/alembic/versions/*practice_template*.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/lib/api/client-domains.ts`
- Create: `web/src/app/admin/curriculum-practice/templates/page.tsx`
- Create: `web/src/app/admin/curriculum-practice/templates/page.test.tsx`

- [ ] **Step 1: 写失败测试：发布门禁**

  Test file: `backend/tests/unit/test_curriculum_publish_gates.py`

  覆盖：引用不存在失败、非 StepFun voice mode 失败、缺 scoring/rubric 失败、published 成功。

- [ ] **Step 2: 写失败测试：PracticeTemplate API**

  Test file: `backend/tests/integration/test_practice_template_api.py`

  覆盖：create/read/update/publish、publish gate failure reason。

- [ ] **Step 3: 运行后端测试确认 red**

  ```bash
  cd backend && pytest tests/unit/test_curriculum_publish_gates.py -v
  cd backend && pytest tests/integration/test_practice_template_api.py -v
  ```

  Expected: FAIL，原因是模块/API/model 尚未存在。

- [ ] **Step 4: 实现最小后端模型、schema、service、router、migration**

  最小生命周期：`draft`、`published`、`archived`。引用现有 Agent、Persona、KnowledgeBase、ScoringRuleset、VoiceRuntimeProfile。

- [ ] **Step 5: 注册 router 并运行 migration**

  ```bash
  cd backend && alembic upgrade head
  ```

  Expected: PASS。

- [ ] **Step 6: 后端测试 green**

  ```bash
  cd backend && pytest tests/unit/ -k "practice_template or curriculum" -v
  cd backend && pytest tests/integration/ -k "practice_template or curriculum" -v
  cd backend && pytest tests/contract/ -k "curriculum or practice_template" -v
  ```

- [ ] **Step 7: 写前端失败测试**

  Test file: `web/src/app/admin/curriculum-practice/templates/page.test.tsx`

  覆盖：列表、创建、编辑、发布、展示发布门禁失败原因。

- [ ] **Step 8: 实现前端 types/client/Admin 页面**

  只做基础 Admin 页面，不做完整内容资产平台。

- [ ] **Step 9: 前端验证**

  ```bash
  cd web && npx vitest run src/app/admin/curriculum-practice
  cd web && npx vitest run src/lib/api
  cd web && npx tsc --noEmit
  cd web && npx eslint . --quiet
  ```

- [ ] **Step 10: 全局不变量检查**

  ```bash
  cd backend && ruff check src tests
  cd backend && mypy src
  grep -R "@ts-ignore\|@ts-expect-error\|as any" web/src backend/src backend/tests || true
  grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src backend/tests || true
  git status --short
  ```

- [ ] **Step 11: 提交并写 issue evidence**

  ```bash
  git add backend/src/curriculum_practice backend/src/common/db/models.py backend/src/router_registry.py backend/src/app_factory.py backend/alembic/versions web/src
  git commit -m "feat(curriculum): add PracticeTemplate skeleton"
  ```

**Closure Gate:** PracticeTemplate model/API/publish gates/Admin 页面完成，测试通过，不包含完整内容资产平台扩展。

**Rollback:** migration 失败则回滚 migration commit 并 `alembic downgrade -1`；Admin UI 出错则先回滚 UI commit。

---

### Task 3: #49 RuntimeSnapshotService 与课程化快照 Schema（AFK）

**Files:**
- Create/Modify: `backend/src/curriculum_practice/services/snapshots.py`
- Modify: `backend/src/curriculum_practice/schemas.py`
- Test: `backend/tests/unit/test_curriculum_runtime_snapshot_service.py`
- Test: `backend/tests/integration/test_curriculum_runtime_snapshot_service.py`

- [ ] **Step 1: 写失败测试：hash 稳定性与 volatile 字段排除**

  覆盖：相同输入生成相同 hash；timestamp、actor_id、trace_id 改变不影响 hash。

- [ ] **Step 2: 写失败测试：稳定错误码**

  覆盖：`template_unpublished`、`asset_unpublished`、`asset_hash_mismatch`、`rubric_missing`、`voice_policy_unavailable`、`prompt_contract_missing`。

- [ ] **Step 3: 运行测试确认 red**

  ```bash
  cd backend && pytest tests/unit/test_curriculum_runtime_snapshot_service.py -v
  ```

- [ ] **Step 4: 实现 snapshot schema、hash helper、RuntimeSnapshotService**

  快照只保存版本引用和 hash，不内嵌大文本；第一阶段目标大小小于 256KB。

- [ ] **Step 5: 运行 targeted tests**

  ```bash
  cd backend && pytest tests/unit/ -k "runtime_snapshot or curriculum_snapshot" -v
  cd backend && pytest tests/integration/ -k "runtime_snapshot or curriculum_snapshot" -v
  cd backend && ruff check src tests
  cd backend && mypy src
  ```

- [ ] **Step 6: 提交并写 issue evidence**

  ```bash
  git add backend/src/curriculum_practice backend/tests/unit/test_curriculum_runtime_snapshot_service.py backend/tests/integration/test_curriculum_runtime_snapshot_service.py
  git commit -m "feat(curriculum): add RuntimeSnapshotService"
  ```

**Closure Gate:** `RuntimeSnapshotService` 是唯一快照构建入口；schema 遵守统一 ref shape；本 slice 不持久化到 `PracticeSession`。

**Rollback:** hash 不稳定则回滚 hash helper 和 service commit；schema 泄露正文则恢复引用-only。

---

### Task 4: #50 PracticeSession 快照持久化（AFK）

**Files:**
- Modify: `backend/src/common/db/models.py`
- Modify: `backend/src/common/db/schemas.py`
- Modify: `backend/src/common/services/practice_session_service.py`
- Create: `backend/alembic/versions/*practice_session_curriculum_snapshot*.py`
- Test: `backend/tests/integration/test_curriculum_practice_session_snapshot.py`
- Modify: `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- Modify/Create: `backend/tests/contract/test_sessions.py`

- [ ] **Step 1: 写失败测试：旧 session 创建兼容**

  无 template 创建 session 必须保持旧行为和旧 response contract。

- [ ] **Step 2: 写失败测试：template-backed session 持久化 snapshot**

  有 published template 创建 session 时，调用 `RuntimeSnapshotService.build_for_session()` 并保存 `curriculum_snapshot`。

- [ ] **Step 3: 写失败测试：status constraint 不变**

  `PracticeSession.status` 不允许新增课程化状态。

- [ ] **Step 4: 运行测试确认 red**

  ```bash
  cd backend && pytest tests/integration/test_curriculum_practice_session_snapshot.py -v
  cd backend && pytest tests/contract/test_sessions.py -v
  ```

- [ ] **Step 5: 增加 nullable 字段与 migration**

  字段：`practice_template_id`、`curriculum_snapshot`、`runtime_state`。

- [ ] **Step 6: 修改 session creation service**

  有 template path 调用 snapshot service；无 template path 完全保持旧行为。

- [ ] **Step 7: 验证**

  ```bash
  cd backend && alembic upgrade head
  cd backend && pytest tests/integration/test_voice_runtime_session_snapshot.py -v
  cd backend && pytest tests/integration/ -k "practice_session and curriculum" -v
  cd backend && pytest tests/contract/test_sessions.py -v
  cd backend && ruff check src tests
  cd backend && mypy src
  ```

- [ ] **Step 8: 提交并写 issue evidence**

  ```bash
  git add backend/src/common backend/alembic/versions backend/tests/integration backend/tests/contract
  git commit -m "feat(common): persist curriculum snapshot on PracticeSession"
  ```

**Closure Gate:** 有 template 和无 template session 创建都通过；旧 API 不破坏前端；`PracticeSession.status` 不变有测试证明。

**Rollback:** migration 失败则回滚 migration commit；旧 session 兼容失败则回滚 service/schema 改动。

---

### Task 5: #51 TrainingTask 可选 PracticeTemplate 绑定（AFK）

**Files:**
- Modify: `backend/src/common/db/models.py`
- Modify: `backend/src/common/training_tasks/schemas.py`
- Modify: `backend/src/common/training_tasks/service.py`
- Modify: `backend/src/common/api/training_tasks.py`
- Create: `backend/alembic/versions/*training_task_practice_template*.py`
- Test: `backend/tests/integration/test_training_tasks_api.py`
- Modify/Create: `backend/tests/contract/test_training_tasks.py`

- [ ] **Step 1: 写失败测试：无 template 旧路径不变**

  `TrainingTask` start-session 未绑定 template 时行为不变。

- [ ] **Step 2: 写失败测试：绑定 published template**

  start-session 生成带 `curriculum_snapshot` 的 `PracticeSession`。

- [ ] **Step 3: 写失败测试：非法 template 拒绝**

  未发布、不存在、不可读 template 返回稳定 4xx。

- [ ] **Step 4: 写不变量测试**

  `TrainingTask.status` 仍按现有生命周期，不包含 preflight/stage/reconnect 字段。

- [ ] **Step 5: 运行测试确认 red**

  ```bash
  cd backend && pytest tests/integration/ -k "training_task and start_session" -v
  ```

- [ ] **Step 6: 增加 nullable `practice_template_id` 与 schema/API/service 集成**

- [ ] **Step 7: 验证**

  ```bash
  cd backend && alembic upgrade head
  cd backend && pytest tests/integration/ -k "training_task and start_session" -v
  cd backend && pytest tests/contract/ -k "training_task" -v
  cd backend && ruff check src tests
  cd backend && mypy src
  ```

- [ ] **Step 8: 提交并写 issue evidence**

  ```bash
  git add backend/src/common backend/alembic/versions backend/tests/integration backend/tests/contract
  git commit -m "feat(common): bind TrainingTask to PracticeTemplate"
  ```

**Closure Gate:** 绑定和未绑定 template 的 start-session 都有测试；`TrainingTask.status` 未扩展；没有把课程阶段状态混入 task。

**Rollback:** unbound path 被破坏则立即回滚整个 slice。

---

### Task 6: #52 EvaluationRun 与 TrainingReportSnapshot 课程化 Lineage 传播（AFK）

**Files:**
- Modify: `backend/src/evaluation/services/evaluation_run_service.py`
- Modify: `backend/src/evaluation/services/training_report_snapshot_service.py`
- Test: `backend/tests/unit/test_evaluation_run_service.py`
- Test: `backend/tests/unit/test_training_report_snapshot_service.py`
- Create: `backend/tests/integration/test_curriculum_lineage_flow.py`

- [ ] **Step 1: 写失败测试：从 session snapshot 提取 lineage**

  `practice_template`、`content_assets`、`rubric`、`llm_suggestions` 应进入 `EvaluationRun.input_evidence_reference`。

- [ ] **Step 2: 写失败测试：TrainingReportSnapshot 复制 lineage**

  `report_payload.lineage` 和 EvaluationRun lineage 一致。

- [ ] **Step 3: 写失败测试：旧 run/report 兼容**

  没有 curriculum snapshot 的旧 run/report 正常显示，不回填、不重算。

- [ ] **Step 4: 运行测试确认 red**

  ```bash
  cd backend && pytest tests/unit/ -k "curriculum_lineage or report_snapshot" -v
  cd backend && pytest tests/integration/test_curriculum_lineage_flow.py -v
  ```

- [ ] **Step 5: 实现 lineage extractor 与 service propagation**

  不新增并行 report model；不强制新增独立 lineage 表。

- [ ] **Step 6: 验证**

  ```bash
  cd backend && pytest tests/unit/ -k "curriculum_lineage or report_snapshot" -v
  cd backend && pytest tests/integration/ -k "evaluation_run or training_report_snapshot or curriculum_lineage" -v
  cd backend && pytest tests/contract/test_admin_governance_contract.py -v
  cd backend && ruff check src tests
  cd backend && mypy src
  ```

- [ ] **Step 7: 提交并写 issue evidence**

  ```bash
  git add backend/src/evaluation backend/tests/unit backend/tests/integration
  git commit -m "feat(evaluation): propagate curriculum lineage"
  ```

**Closure Gate:** 新 lineage 写入和报告复制都有测试；旧数据兼容；历史 report immutability 有测试。

**Rollback:** 若 report API 被破坏，回滚 report propagation commit；若出现历史回填逻辑，立即 revert。

---

### Task 7: #53 快照不可变性与 StepFun 边界回归测试（AFK）

**Files:**
- Create: `backend/tests/integration/test_curriculum_snapshot_immutability.py`
- Create: `backend/tests/integration/test_curriculum_report_lineage_immutability.py`
- Create/Modify: `backend/tests/unit/test_stepfun_payload_snapshots.py`
- Modify: `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- Create/Modify: `backend/tests/unit/test_runtime_dependency_contract.py`

- [ ] **Step 1: 写 snapshot immutability 测试**

  template v1 创建 session，template v2 发布后旧 session `curriculum_snapshot` 不变。

- [ ] **Step 2: 写 report lineage immutability 测试**

  report snapshot 创建后更新 template/content/config，旧 report lineage 不变。

- [ ] **Step 3: 写 StepFun boundary 测试**

  初始输入只读 `voice_policy_snapshot` 和 curriculum snapshot allowlist，不读取 latest curriculum/practice content。

- [ ] **Step 4: 写状态与 legacy absence 测试**

  确认 `TrainingTask.status`、`PracticeSession.status` 无课程化污染；legacy Sales handlers 未恢复。

- [ ] **Step 5: 运行测试确认 red 或确认现有行为已满足**

  ```bash
  cd backend && pytest tests/integration/ -k "snapshot and immutable" -v
  cd backend && pytest tests/unit/test_stepfun_payload_snapshots.py -v
  ```

- [ ] **Step 6: 做最小 seam 修复**

  只修复测试暴露的边界缺口，不新增业务能力。

- [ ] **Step 7: 验证**

  ```bash
  cd backend && pytest tests/integration/ -k "snapshot and immutable" -v
  cd backend && pytest tests/unit/test_stepfun_payload_snapshots.py -v
  cd backend && pytest tests/integration/test_voice_runtime_session_snapshot.py -v
  cd backend && pytest tests/contract/test_sessions.py -v
  cd backend && pytest tests/contract/test_admin_governance_contract.py -v
  grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src backend/tests || true
  cd backend && ruff check src tests
  cd backend && mypy src
  ```

- [ ] **Step 8: 提交并写 issue evidence**

  ```bash
  git add backend/tests backend/src
  git commit -m "test(runtime): cover PRD46 snapshot and StepFun boundaries"
  ```

**Closure Gate:** 所有 regression tests 通过；没有 skip/flaky；如果不变量失败，回到对应上游 slice 修复。

**Rollback:** 测试暴露上游 bug 时不回滚测试，回到对应 issue 修复；测试不稳定时修正测试设计，不跳过。

---

### Task 8: #54 CaseItem + RoleProfile 最小内容资产试点（HITL）

**Files:**
- Modify: `backend/src/curriculum_practice/models.py`
- Modify: `backend/src/curriculum_practice/schemas.py`
- Create: `backend/src/curriculum_practice/services/content_assets.py`
- Modify: `backend/src/curriculum_practice/services/practice_templates.py`
- Modify: `backend/src/curriculum_practice/services/snapshots.py`
- Create: `backend/alembic/versions/*case_item_role_profile*.py`
- Test: `backend/tests/unit/test_case_item_role_profile_assets.py`
- Test: `backend/tests/integration/test_case_role_template_snapshot.py`
- Modify: `backend/tests/unit/test_stepfun_payload_snapshots.py`

- [ ] **Step 1: 写字段/披露策略 proposal 并等待 HITL**

  `CaseItem` 最小字段：industry、company_profile、customer_role、pain_points、objections、hidden_information、success_criteria、allowed_disclosure_policy、version、content_hash、status。

  `RoleProfile` 最小字段：role_type、role_name、persona_ref、communication_style、pressure_level、knowledge_boundary、behavior_rules、voice_style_hint、version、content_hash、status。

- [ ] **Step 2: 人工确认后写失败测试**

  覆盖：schema validation、published-only reference、unpublished asset publish gate rejection、snapshot 只写版本引用、StepFun initial input 不包含 `hidden_information`。

- [ ] **Step 3: 运行测试确认 red**

  ```bash
  cd backend && pytest tests/unit/test_case_item_role_profile_assets.py -v
  cd backend && pytest tests/integration/test_case_role_template_snapshot.py -v
  ```

- [ ] **Step 4: 实现 model/migration/schema/service**

  只做最小资产，不建设完整 CaseBank/RoleBank 平台，不做完整管理 UI、脱敏分享、批量导入。

- [ ] **Step 5: 接入 PracticeTemplate 与 RuntimeSnapshotService**

  `PracticeTemplate` 可引用已发布 `CaseItem` 和 `RoleProfile`；snapshot 写入版本引用；StepFun 初始输入只包含允许披露字段。

- [ ] **Step 6: 验证**

  ```bash
  cd backend && alembic upgrade head
  cd backend && pytest tests/unit/ -k "case_item or role_profile" -v
  cd backend && pytest tests/integration/ -k "case_item or role_profile or practice_template" -v
  cd backend && pytest tests/unit/test_stepfun_payload_snapshots.py -v
  cd backend && ruff check src tests
  cd backend && mypy src
  ```

- [ ] **Step 7: 提交并写 issue evidence**

  ```bash
  git add backend/src/curriculum_practice backend/alembic/versions backend/tests
  git commit -m "feat(curriculum): add CaseItem and RoleProfile pilot"
  ```

**Closure Gate:** 人工确认字段和披露策略；published-only reference 有测试；hidden information 不进入 StepFun 初始输入有测试；不扩展成完整内容平台。

**Rollback:** 字段设计被否决则停止实现；hidden information 泄露测试失败则回滚 StepFun input 编译逻辑；误接入 ConfigBundle 则立即 revert。

---

## 5. Issue Completion Evidence 模板

每个 AFK issue 关闭前都必须贴类似证据：

```markdown
## Completion Evidence

### Scope Delivered
- <实际交付项 1>
- <实际交付项 2>
- <实际交付项 3>

### Verification
- `<command>`: PASS
- `<command>`: PASS
- `<command>`: PASS

### PRD #23 Invariants
- TrainingTask.status unchanged.
- PracticeSession.status unchanged.
- ConfigBundle lifecycle not expanded.
- User.role DB constraint unchanged.
- Legacy Sales handlers not restored.
- Historical reports not recalculated.
- SessionV2 not introduced.
- No type-safety suppressions introduced.

### Rollback Note
- Revert commit(s): <commit sha list>
```

HITL issue 必须额外包含：

```markdown
### HITL Review
- Reviewer:
- Review date:
- Human confirmed:
  - <confirmation item 1>
  - <confirmation item 2>
  - <confirmation item 3>
```

---

## 6. 最终 Release / Readiness Checklist

- [ ] #47 已完成 HITL architecture boundary review。
- [ ] #48 已交付 `PracticeTemplate` 最小模型、API、发布门禁、Admin 页面。
- [ ] #49 已交付 deterministic `RuntimeSnapshotService`。
- [ ] #50 已实现 `PracticeSession` nullable snapshot persistence，旧路径兼容。
- [ ] #51 已实现 `TrainingTask` optional template binding，旧 start-session 兼容。
- [ ] #52 已实现 EvaluationRun 和 TrainingReportSnapshot curriculum lineage。
- [ ] #53 已通过 snapshot immutability 和 StepFun boundary regression tests。
- [ ] #54 若纳入本轮关闭，已完成 HITL 字段/披露策略确认。
- [ ] Backend migrations 可从当前 head 成功升级。
- [ ] Backend unit/integration/contract targeted suites 通过。
- [ ] Frontend Vitest、TypeScript、ESLint 通过相关 touched surfaces。
- [ ] API contract / OpenAPI 如有变更已同步。
- [ ] `TrainingTask.status` 未变。
- [ ] `PracticeSession.status` 未变。
- [ ] `ConfigBundle` 生命周期未扩大。
- [ ] `User.role` DB constraint 未变。
- [ ] legacy Sales handlers 未恢复。
- [ ] 历史 reports 未回填、未重算。
- [ ] 没有 `SessionV2`。
- [ ] 没有 type-safety suppressions。
- [ ] 每个 issue completion comment 都包含命令、结果、不变量确认。
- [ ] HITL issue completion comment 包含人工 reviewer 和确认项。
- [ ] 工作区只包含本轮预期变更。
- [ ] 如果 PRD #23/#45 仍 open，确认未依赖未通过的 release gate 结果关闭 PRD #46。

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| #47 边界未锁定就开工 | 下游实现 drift，后续返工 | #47 必须 HITL 通过后才能启动 #48 |
| PracticeTemplate 过度设计成完整 LMS | 范围膨胀，拖慢主链路 | #48 只引用现有 Agent/Persona/Knowledge/Scoring/VoiceRuntimeProfile |
| Snapshot hash 不稳定 | 历史追溯不可信 | #49 必须测试 sorted-key normalization 和 volatile field exclusion |
| 旧 session 创建被破坏 | 现有训练入口回归 | #50 必须有无 template 旧路径兼容测试 |
| TrainingTask 被塞入运行态 | 破坏 PRD #23 任务边界 | #51 明确禁止 preflight/stage/reconnect 字段进入 TrainingTask |
| Report lineage 写入导致历史报告变化 | 违反不可重算历史报告 | #52 只对新 report 写入，旧 report 兼容，不回填 |
| StepFun 读取 latest 内容 | 运行中内容变化影响公平性 | #53 写 snapshot-only boundary regression tests |
| #54 hidden_information 泄露给 StepFun | 内容治理和训练公平性风险 | HITL 明确 disclosure allowlist，测试初始输入不含 hidden information |
| RBAC 通过扩展 `User.role` 实现 | 破坏 DB 约束和 PRD #23 | 只用 action-level permissions 或现有角色映射 |
| Dirty worktree 混入无关变更 | review 和 rollback 困难 | 每个 issue 开工和提交前检查 `git status --short` |
| 测试失败后强行关闭 issue | 质量门禁失效 | AFK issue 失败 3 次暂停，记录 blocker，不关闭 |
| 前端类型用 suppressions 绕过 | 后续 runtime bug | 禁止 `as any`、`@ts-ignore`、`@ts-expect-error` |
| PRD #23/#45 交互未处理 | 共享底座未稳定导致 PRD #46 建在浮动目标上 | 关闭 #50-#53 前确认相关 PRD #23 release gate 不阻塞 |

---

## 8. 自审结果

- Spec coverage：#47-#54 均有独立任务、验证、completion evidence、closure gate、rollback。
- Placeholder scan：未使用 TBD / TODO / implement later 作为交付占位；代码实施内容留到后续 TDD 执行阶段。
- Type consistency：计划中统一使用 `PracticeTemplate`、`RuntimeSnapshotService`、`curriculum_snapshot`、`runtime_state`、`practice_template_id`、`curriculum_lineage`。
- Scope discipline：#47/#54 明确 HITL；#48-#53 明确 AFK；#54 不扩展成完整内容资产平台。
