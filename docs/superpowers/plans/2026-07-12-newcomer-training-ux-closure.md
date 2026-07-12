# Newcomer Training UX Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not dispatch subagents for this plan.

**Goal:** 完整修复新人训练学员端、路径管理端和运营工作台的易用性、资源治理、发布安全与闭环体验。

**Architecture:** 保留活动注册表和不可变路径修订，向 Journey 投影补充展示字段；管理端使用候选校验与带期望修订号的原子发布；前端按学员执行、路径编排、运营查看三个意图拆分页面。

**Tech Stack:** FastAPI、Pydantic 2、SQLAlchemy async、Next.js 16、React 19、TypeScript、Tailwind、Vitest、pytest、Playwright。

## Global Constraints

- 内容身份只能是配置数据；不得新增产品/PPT/Demo 代码分支。
- 页面调用必须经过 `@/lib/api/client`；后端权限和审计不可省略。
- 不新增数据库表，不引入新依赖。
- 先写失败测试并确认 RED，再实现最小代码并确认 GREEN。
- 不修改用户已有的 `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md` 变更。

---

### Task 1: 修订并发、候选检查与原子发布

**Files:**
- Modify: `backend/src/sales_trainer/orchestration/admin_api.py`
- Modify: `backend/src/sales_trainer/orchestration/revision_service.py`
- Modify: `backend/src/sales_trainer/orchestration/errors.py`
- Test: `backend/tests/unit/test_newcomer_training_orchestration_revision_service.py`
- Test: `backend/tests/integration/test_newcomer_training_orchestration_api.py`

**Interfaces:**
- `save_draft(..., expected_revision_id: str | None)` 显式拒绝陈旧修订。
- `validate_candidate(payload)` 只读校验候选内容。
- `publish_candidate(payload, expected_revision_id, actor, reason, trace_id)` 在同一事务创建并激活修订。

- [ ] 写候选检查无写入、陈旧修订返回冲突、发布失败不留下半成品修订的失败测试。
- [ ] 运行聚焦 pytest，确认分别因接口缺失/行为不符失败。
- [ ] 实现服务方法和稳定 409 错误码 `[NEWCOMER_PATH_REVISION_CONFLICT]`。
- [ ] 更新 API 请求 DTO，并保持旧的仅发布工作草稿调用兼容。
- [ ] 运行聚焦测试并确认通过。

### Task 2: Journey 展示合同与下一步语义

**Files:**
- Modify: `backend/src/sales_trainer/orchestration/contracts.py`
- Modify: `backend/src/sales_trainer/orchestration/journey_service.py`
- Modify: `web/src/lib/api/types/newcomer-training.ts`
- Test: `backend/tests/unit/test_newcomer_training_orchestration_journey.py`
- Test: `web/src/components/newcomer-training/journey-home.test.tsx`

**Interfaces:**
- `JourneyActivityProgress.estimated_minutes`、`JourneyModuleProgress.estimated_minutes`。
- 前端 `activityActionLabel(activity_type)` 生成明确主操作文案。

- [ ] 写预计用时跨层投影、只有一个“当前主线”、录音任务显示“开始录音讲解”的失败测试。
- [ ] 确认后端与前端测试均按预期失败。
- [ ] 补充 DTO 投影与集中展示映射。
- [ ] 更新首页和模块页，默认只展开主线阶段。
- [ ] 运行聚焦测试确认通过。

### Task 3: 录音执行器与活动完成闭环

**Files:**
- Create: `web/src/components/newcomer-training/activity-runners/use-browser-audio-recorder.ts`
- Create: `web/src/components/newcomer-training/activity-runners/use-browser-audio-recorder.test.ts`
- Create: `web/src/components/newcomer-training/activity-result-panel.tsx`
- Create: `web/src/components/newcomer-training/activity-result-panel.test.tsx`
- Modify: `web/src/components/newcomer-training/activity-runners/audio-assessment-runner.tsx`
- Modify: `web/src/components/newcomer-training/activity-shell.tsx`
- Modify: `web/src/lib/api/types/newcomer-training.ts`

**Interfaces:**
- `useBrowserAudioRecorder(): { state, durationSeconds, audioFile, audioUrl, start, stop, reset, error }`。
- `ActivityResultPanel` 根据活动状态显示处理中、完成、失败和返回模块/下一步动作。

- [ ] 写麦克风拒绝、开始/停止生成 File、重录释放 URL、文件兜底的失败测试。
- [ ] 写材料预览链接、录音试听、提交后状态和下一步面板失败测试。
- [ ] 实现最小 MediaRecorder hook，复用现有麦克风错误文案映射。
- [ ] 重构录音 runner 和公共活动壳，避免原生英文文件选择成为主路径。
- [ ] 运行全部 newcomer activity Vitest。

### Task 4: 管理端资源加载韧性与安全原地创建

**Files:**
- Modify: `web/src/app/admin/newcomer-training/path/page.tsx`
- Modify: `web/src/components/admin/newcomer-training/path-editor.tsx`
- Modify: `web/src/components/admin/newcomer-training/resource-picker-drawer.tsx`
- Modify: `web/src/components/admin/newcomer-training/activity-editors/editor-fields.tsx`
- Test: corresponding co-located tests

**Interfaces:**
- 资源目录以 `Promise.allSettled` 独立加载，失败项形成 `resourceWarnings`。
- 快速建课要求非空正文；快速组卷接收显式 `question_ids`；评分标准接收显式维度。

- [ ] 写单资源失败仍渲染路径编辑器的失败测试。
- [ ] 写空正文拒绝发布、未选题拒绝组卷、评分维度显式提交的失败测试。
- [ ] 实现局部目录状态、搜索选择和直接进入表单的快速创建。
- [ ] 保留失败输入并提供对应目录重试。
- [ ] 运行页面、资源抽屉和 API facade 测试。

### Task 5: 可扩展路径大纲与完整模块规则编辑

**Files:**
- Modify: `web/src/components/admin/newcomer-training/path-outline.tsx`
- Modify: `web/src/components/admin/newcomer-training/path-inspector.tsx`
- Create: `web/src/components/admin/newcomer-training/path-rule-editor.tsx`
- Test: `web/src/components/admin/newcomer-training/path-editor.test.tsx`

**Interfaces:**
- 大纲提供 `query`、折叠状态和问题过滤。
- `PathRuleEditor` 编辑 `audience_rule`、module/activity prerequisites 和 `completion_policy`。

- [ ] 写折叠、搜索、无结果、40px 操作目标和规则 round-trip 失败测试。
- [ ] 实现大纲工具栏、折叠状态和可访问按钮。
- [ ] 实现依赖多选、适用对象标签输入和完成策略。
- [ ] 运行编辑器状态与组件测试。

### Task 6: 保存、发布确认与历史恢复

**Files:**
- Modify: `web/src/lib/api/domains/newcomer-training.ts`
- Modify: `web/src/components/admin/newcomer-training/path-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/path-revision-history.tsx`
- Test: `web/src/lib/api/newcomer-training-orchestration.test.ts`
- Test: `web/src/components/admin/newcomer-training/path-editor.test.tsx`

**Interfaces:**
- `saveDraft(payload, reason, expectedRevisionId)`。
- `validateCandidate(payload)`。
- `publishCandidate(payload, reason, expectedRevisionId)`。
- 历史面板使用现有 `listRevisions` / `restoreRevision`。

- [ ] 写请求体、冲突保留本地内容、发布确认和恢复历史失败测试。
- [ ] 更新 API facade 和编辑器修订状态。
- [ ] 增加离开页面保护、发布影响说明和历史恢复确认。
- [ ] 运行 API 与编辑器测试。

### Task 7: 新人训练运营工作台

**Files:**
- Create: `web/src/app/admin/newcomer-training/learners/page.tsx`
- Create: `web/src/app/admin/newcomer-training/learners/page.test.tsx`
- Create: `web/src/app/admin/newcomer-training/learners/[learnerId]/page.tsx`
- Create: `web/src/app/admin/newcomer-training/learners/[learnerId]/page.test.tsx`
- Modify: `web/src/lib/sales-trainer/routes.ts`

**Interfaces:**
- 列表消费 `api.admin.newcomerTraining.listJourneys`。
- 详情消费 `getLearnerJourney`，只展示权威状态并链接现有记录、录音和达标验收。

- [ ] 写列表加载/空/错误/分页/部门筛选和详情状态测试。
- [ ] 实现独立运营列表与详情页面。
- [ ] 将“学员进度”加入新人训练导航和权限根。
- [ ] 运行路由、导航和类型测试。

### Task 8: 合同、浏览器回归与质量门禁

**Files:**
- Modify: `docs/api-contract/sales-trainer.md`
- Modify: `web/tests/e2e/newcomer-training-admin.spec.ts`
- Modify: `web/tests/e2e/newcomer-training-learner.spec.ts`
- Modify: `.trellis/spec/backend/newcomer-training-activity-orchestration.md` if executable contract changes require it

- [ ] 更新 API 合同和并发/候选发布错误矩阵。
- [ ] 扩展 Playwright 覆盖学员录音入口、管理员局部资源失败、发布确认和运营详情。
- [ ] 运行后端聚焦测试、Ruff、Mypy。
- [ ] 运行前端 Vitest、TypeScript、ESLint、production build。
- [ ] 运行新人训练 Playwright 与项目关键质量门禁。
- [ ] 检查工作树，只提交本任务文件，不包含用户已有修改。

