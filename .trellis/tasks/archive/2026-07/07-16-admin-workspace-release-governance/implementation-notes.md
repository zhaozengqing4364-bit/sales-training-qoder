# 切片 6 实施记录

## 页面与业务合同

- 用户：培训负责人、内容编辑、训练管理员、达标复核员、系统管理员；所有可见区域与命令以后端 Capability 和组织/对象范围为准。
- 主流程：从 `/admin/newcomer-training` 的待办进入工作对象，在同一工作区完成路径/资源/班级/评测/复核处理，经 ReleasePlan 预览与校验后发布；需要时预览影响并回滚到已知稳定发布。
- 可验证结果：管理入口按任务组织；资源可在路径编辑上下文内选择或快速创建；高风险命令具备 preview/confirm/reason/audit；发布不产生半发布；新 PathRevision 不自动迁移活跃 Enrollment；重要异步结果有持久位置。
- 页面模型：总览为 Dashboard–Drilldown（只展示可行动队列）；路径为 Editor–Preview（三栏）；内容、题目、班级、评测为 List–Detail/任务队列；发布为 Process–Approval；设置为 Settings–Configuration。
- 主操作：各工作区只有一个与当前对象相符的主操作；发布页主操作为“校验发布计划/发布版本”，回滚、失效、取消等风险动作降级并要求显式预览确认。

## 唯一写权威

- `newcomer_training`：Path/PathRevision/Stage/ActivityDefinition、Cohort、Enrollment、显式 Enrollment Revision 迁移。
- `learning`：Source/LearningUnit/QuestionCandidate/Question/Quiz 修订。
- `audio_assessment`、`ai_coach`、`task_runtime`、`readiness`：各自业务对象与状态；管理工作台只调用公开应用命令，不复制状态机或跨域 ORM 写入。
- 本切片新增的 ReleasePlan/发布激活/回滚由新人训练发布治理应用服务统一编排；各领域只通过稳定发布端口参与。切片 2 的临时直接发布入口在 ReleasePlan 消费方切换完成后封存/删除，不保留双写。
- Capability projection 是管理端可见性与动作权限的唯一前端依据；服务端命令仍执行同一权限和组织/对象范围校验。

## 数据、API、权限与状态影响

- 数据：已新增可追溯 `NewcomerReleasePlan`、`EnrollmentImportPreview` 和 Candidate bulk-review preview；计划冻结目标修订、依赖图、校验、影响、合同 hash、版本和审计。发布 Revision 只读，回滚通过重新激活稳定计划。
- API：已在 `/api/v1/admin/newcomer-training/**` 挂载 capability、overview、路径/班级工作区、ReleasePlan preview/publish/rollback、Source 上传解析、题目生成批次、Candidate 批量审核和 Enrollment 批量导入/迁移等业务对象接口；严格 schema、幂等键、`If-Match`/影响 hash 和用户安全错误保持在服务端。
- 权限：至少覆盖总览、路径、内容、题目审核、Cohort/Enrollment、任务修复、重评/失效、达标复核、发布/回滚、Prompt/模型治理、敏感审计；跨组织访问拒绝并留痕。
- 状态：Capability、总览队列、批量操作和发布命令覆盖 loading/empty/no-result/error/permission/partial/stale/conflict/submitting/success/cancelled/retrying；异步任务状态来自持久化 Task，不在页面猜测。
- 兼容性：已冻结 Enrollment 保持原 PathRevision；发布新版只改变后续显式绑定；现有 UI token、Shell、表格、Drawer、ConfirmDialog 和状态组件继续使用，不建立新视觉体系。

## 实施结果

1. [x] 用 CodeGraph 和源码核实现有 v2 管理链路，复用 Path、资源、Cohort/Enrollment、Candidate、Task、Readiness 和审计领域服务；未复制领域模型或状态机。
2. [x] 建立集中 Capability/Overview 投影，并以同一服务端能力保护查询和命令；前端导航与动作不再从 role string 推断。
3. [x] 实现 ReleasePlan 持久模型、完整依赖预览、原子闭包发布、并发/幂等防护、失败保旧、回滚和审计。发布顺序为 Source/Question → LearningUnit/Quiz → Path；现有 Enrollment 不自动迁移。
4. [x] 组合 `/admin/newcomer-training` 统一入口与总览、路径、内容、题目、班级、评测、复核、发布和设置工作区，复用现有 Shell、token、表单、表格、Drawer、ConfirmDialog 和状态组件。
5. [x] 补齐上下文内完成：资源搜索/快速新建/自动绑定、Source 上传与持久解析、Source Anchor、题目生成批次和安全策略选择、Candidate 批量预览确认、Enrollment ID/email/CSV 预览确认与逐项结果。
6. [x] 将 Path/资源直发 HTTP route 封存为固定 409 `[NEWCOMER_RELEASE_PLAN_REQUIRED]` 墓碑；正式发布只从 ReleasePlan 进入，内部领域发布端口仅供发布编排器调用。
7. [x] 同步 API 合同、Accepted ADR、Trellis backend/frontend spec、发布回滚 runbook 和父任务验收证据。
8. [x] 路径编辑器的未保存离开从浏览器原生 `window.confirm` 收口为现有 `ConfirmDialog`，保留 `beforeunload` 防护并增加键盘/可访问确认测试。
9. [x] 为路径编辑器资源 Drawer 增加上下文内完成回归：精确工作修订可直接绑定；快速创建来源失败时保留学习单元、来源名称与来源地址，不关闭当前编辑流。

## 关键实现落点

- 后端组合与权限：`foundation_admin_api.py`、`foundation_admin_permissions.py`、`foundation_admin_workspace.py`、`foundation_release_composition.py`。
- 发布权威：`newcomer_training/release.py`、`newcomer_training/models.py`、`newcomer_training/application.py`、`newcomer_training/ports.py`。
- 内容与题目：`learning/application.py`、`learning/admin_queries.py`、`learning/question_generation.py`、`learning/source_ingestion.py`、`foundation_question_generation.py`、`common/knowledge/processor.py`。
- 数据库：`20260717_1500_006_admin_release_governance.py`。
- 前端：`app/admin/newcomer-training/**`、`components/admin/newcomer-training/**`、`lib/api/domains/newcomer-training.ts`、`lib/api/types/newcomer-training.ts`、管理侧栏。

## 最小验证范围

- 后端：变更文件 Ruff/mypy；Capability/对象级权限；ReleasePlan 原子性、并发、失败保旧、回滚、幂等、审计；Candidate/Enrollment 批量预览与部分失败；受影响的路由/OpenAPI 合同测试。
- 前端：变更文件 ESLint/TypeScript；统一入口、权限、三栏 dirty/conflict、上下文资源绑定、partial/long-task/rollback 交互的聚焦 Vitest。
- 影响选择：实现后运行 CodeGraph `impact/affected`，只补充其直接指向的回归测试。切片 6 不运行全量测试、全量构建、全库格式化。
- 实际浏览器：优先执行目标管理路径的渲染、窄屏、200% zoom、键盘/焦点检查；若运行环境缺少浏览器系统依赖，记录为切片 8 发布门禁待验证，不安装无关依赖。

## 已执行验证

- 后端变更文件 Ruff 和 mypy 已通过；覆盖 ReleasePlan、API、学习资源闭包、Source 解析和题目生成策略组合。
- 聚焦 pytest 已通过：ReleasePlan 原子发布/失败保旧/回滚/并发/幂等、发布闭包、管理权限/API、Source 上传解析、QuestionGeneration 策略与 Candidate/Enrollment 批量工作流。
- 前端变更文件 ESLint 和 TypeScript 已通过；聚焦 Vitest 已通过统一导航、路径编辑/资源 Drawer、内容、题目、班级、评测、发布和侧栏入口。
- 资源 Drawer 新增的 2 条聚焦 Vitest 已通过，覆盖工作修订绑定与快速创建失败后的输入保留；对应 ESLint 和 TypeScript 检查通过。
- Alembic head 为 `20260717_1500_006`；隔离 PostgreSQL schema 完成 fresh upgrade、006→005 downgrade、005→006 re-upgrade，并清理临时 schema。
- 浏览器插件在当前会话不可用，按前端测试调试规范使用仓库 `run_playwright` 等价包装执行一条临时、仓库外的 Chromium 聚焦检查：登录 → `/admin/newcomer-training` → 键盘聚焦并进入“发布记录” → 390×844 + CSS 200% zoom。页面身份、非空、无 framework overlay、console/page error、焦点激活、关键操作可见和页面级横向溢出均通过；桌面与窄屏截图保存在 `/tmp` 作为本次临时证据，不写入仓库。
- 本切片未运行全量测试、全量构建、全库扫描或全项目格式化；按照父任务约束，最终 OpenAPI parity、生产构建、全量 Playwright、真实大数据量和完整发布回滚演练留给 Slice 8 总门禁。

### 收口命令与结果

- `./.venv/bin/ruff check <Slice 6 backend sources/tests>`：通过。
- `./.venv/bin/mypy <15 个受影响 backend source files>`：通过。
- `./.venv/bin/pytest --no-cov -q tests/unit/newcomer_training/test_release_plan.py tests/unit/newcomer_training/test_foundation_release_composition.py tests/unit/newcomer_training/test_foundation_question_generation.py tests/unit/newcomer_training/test_admin_permissions.py tests/unit/newcomer_training/test_admin_api.py tests/unit/newcomer_training/test_route_contract.py tests/unit/learning/test_source_question_governance.py`：`26 passed`，仅有 1 条既有 passlib deprecation warning。
- `npx eslint src/components/admin/newcomer-training/activity-resource-drawer.test.tsx`：通过。
- `npx tsc --noEmit`：通过。
- `npx vitest run src/components/admin/newcomer-training/workspace-nav.test.tsx src/components/admin/newcomer-training/v2-path-editor.test.tsx src/components/admin/newcomer-training/activity-resource-drawer.test.tsx src/components/admin/newcomer-training/content-workspace.test.tsx src/components/admin/newcomer-training/question-review-workspace.test.tsx src/components/admin/newcomer-training/cohort-detail-workspace.test.tsx src/components/admin/newcomer-training/assessment-operations-workspace.test.tsx src/components/admin/newcomer-training/release-workspace.test.tsx src/components/layout/admin-sidebar.test.tsx`：`9 files / 25 tests passed`。
- `python3 ./.trellis/scripts/task.py validate .trellis/tasks/07-16-admin-workspace-release-governance`：`implement.jsonl` 9 项、`check.jsonl` 3 项全部通过。
- 隔离 PostgreSQL schema 上执行 Alembic fresh upgrade、`006 → 005` downgrade、`005 → 006` re-upgrade：通过，临时 schema 已清理。
- 仓库外临时 Playwright 聚焦检查：`1 passed`；覆盖登录、统一入口、键盘进入发布记录、390×844、CSS 200% zoom、无关键横向溢出和无运行时错误。

## 回滚与降级

- 数据库 migration 可 downgrade；新表/字段不破坏前置切片的已发布数据。
- 发布失败或功能开关关闭时继续读取当前 active ReleasePlan/已发布修订；不回退到双写。
- 回滚命令只重新激活已知稳定计划并保留历史；活跃 Enrollment 默认保持冻结修订。
- UI 新入口可受 feature flag/capability 隐藏，但服务端旧正式数据仍可读；不得通过手工改表恢复。

## 保守假设

- 父任务与 2026-07-16/17 Accepted ADR 是产品和领域权威；不重新讨论已冻结方向。
- 前置切片 0–5 的 v2 写权威已完成，本切片通过组合与治理复用，不复制领域模型。
- Realtime 客户语音对练、通用低代码/任意工作流编辑器和全站视觉重做均不在范围。
- 题目生成当前只允许已发布 Source 和 LearningUnit。异步任务若直接读取 mutable working revision 会在排队期间发生内容漂移；在未来引入冻结 working 内容快照/hash 和完整血缘合同前，不放宽这一边界。

## 历史问题与未纳入范围

- `.trellis/spec/*/index.md` 与各级 `AGENTS.md` 引用的 `.kiro/steering/backend-principles.md`、`.kiro/steering/frontend-principles.md` 在当前仓库不存在；本切片遵循现存 `AGENTS.md`、`DESING.md` 与 Trellis Spec，不顺带补建缺失文档。
- 工作区存在大量前置切片/用户未提交改动；只修改本切片必要文件，不回滚、不清理、不格式化无关内容。
- 使用 SQLite 执行整条 Alembic 链时在切片 1 的历史 migration 失败；该失败发生在本切片 revision 之前且与当前修改无关，未顺手修复。当前 migration 已用目标 PostgreSQL 完成 upgrade/downgrade/re-upgrade 验证。
- 首次聚焦 pytest 受仓库全局 coverage addopts 影响，即使目标用例通过也因未运行全库而失败；后续聚焦验证使用 `--no-cov`。这不是产品代码失败，也没有为满足局部测试改动全局 coverage 配置。
- `dev-smoke-up.sh` 在服务已启动并成功引导管理员后，旧 `bootstrap_smoke_practice_evidence.py` 因重复 `voice_runtime_profiles.name` 触发唯一键冲突；该脚本/Realtime profile 不属于本切片，未顺手修复。浏览器聚焦检查使用已启动服务完成，随后由 `dev-smoke-stop.sh` 正常停止。
- Chromium 运行容器没有可用中文字体，截图中的中文呈缺字方框；DOM 文本、accessible name、布局、焦点和交互断言均通过，但字体视觉与长中文最终截图仍需在 Slice 8 的发布环境复核。

## 计划偏差

- 原计划把“Source working revision → 题目生成”理解为可直接使用当前 working 内容；真实持久任务合同没有冻结 working 文本快照/hash。为避免输入漂移，收窄为先通过 ReleasePlan 发布 Source/Unit，再启动题目生成；该约束已写入 ADR 和 API/Trellis 合同。
- 直发 Path/资源路由没有立即从 route inventory 物理删除，而是改成无写入的 409 compatibility tombstone，避免当前开发期未完成的消费者 inventory 产生不可定位 404。Slice 8 必须在 OpenAPI/importer inventory 证明无消费者后删除；期间它们不是发布权威，也不转发。
- 实际浏览器已完成统一入口与发布页的桌面、窄屏、200% zoom 和焦点聚焦检查；完整材料上传→发布、Cohort→Enrollment、Dossier→补练 E2E、真实大数据量和中文字体视觉仍按父任务分工留到 Slice 8 总门禁。
- `$trellis-finish-work` 默认要求提交并让归档脚本自动提交；本 GOAL 明确禁止自动 commit，因此按更高优先级约束使用 `task.py archive --no-commit` 收口，不创建 session journal commit。
