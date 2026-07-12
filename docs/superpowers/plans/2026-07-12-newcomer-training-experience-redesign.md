# Newcomer Training Task-first Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not dispatch subagents for this plan.

**Goal:** 将新人训练学员端改成具体、清晰的任务体验，并把管理端改成可配置、低噪、可真实预览的两栏编排器。

**Architecture:** 保留活动编排和不可变修订；在 `v1` JSON 配置与 Journey DTO 中向后兼容地增加学员表达字段；使用共享 `LearnerMissionViewModel` 同时驱动真实学员页和候选预览。

**Tech Stack:** FastAPI、Pydantic 2、SQLAlchemy async、Next.js 16、React 19、TypeScript、Tailwind、Vitest、pytest、Playwright。

## Global Constraints

- 范围只包括新人训练学员路径、活动页和路径管理；不重做全站页面。
- 不新增活动类型、数据库表或第三方依赖。
- 内容字段只接受纯文本/字符串列表，不允许动态组件、HTML、CSS 或脚本。
- 先写失败测试并确认 RED，再实现并确认 GREEN。
- 不修改或提交用户已有的 `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md` 变更。

---

### Task 1: 向后兼容的学员表达合同

**Files:**
- Modify: `backend/src/sales_trainer/orchestration/contracts.py`
- Modify: `backend/src/sales_trainer/orchestration/journey_service.py`
- Modify: `web/src/lib/api/types/newcomer-training.ts`
- Test: `backend/tests/unit/test_newcomer_orchestration_journey_service.py`

**Interfaces:**
- `PhaseConfig.outcome`、`ModuleConfig.outcome`。
- `ActivityBase.objective`、`why_it_matters`、`steps`、`success_criteria`、`primary_action_label`。
- Journey progress DTO 对应投影字段。

- [x] 写新字段解析、旧 payload 兼容和 Journey 完整投影失败测试。
- [x] 运行聚焦 pytest，确认因字段缺失而失败。
- [x] 添加有界长度、默认值和投影实现。
- [x] 同步 TypeScript DTO，运行聚焦测试和类型检查。

### Task 2: 共享任务 ViewModel 与学员首页

**Files:**
- Create: `web/src/lib/newcomer-training/learner-mission.ts`
- Create: `web/src/lib/newcomer-training/learner-mission.test.ts`
- Create: `web/src/components/newcomer-training/learner-mission-card.tsx`
- Modify: `web/src/components/newcomer-training/journey-home.tsx`
- Modify: `web/src/components/newcomer-training/journey-outline.tsx`
- Test: `web/src/components/newcomer-training/journey-home.test.tsx`

**Interfaces:**
- `LearnerMissionViewModel` 聚合任务位置、目标、价值、步骤、标准、用时和唯一主操作。
- `missionFromJourney(journey)` 对旧 revision 提供活动类型默认回退。
- `missionFromCandidate(path)` 为管理预览生成新学员初始视角。

- [x] 写 ViewModel 新/旧合同、首页具体任务和唯一主操作失败测试。
- [x] 运行 Vitest，确认 RED。
- [x] 实现纯函数适配器与共享任务卡。
- [x] 重排首页，移除巨大深色 Hero，将抽象阶段降为弱位置提示。
- [x] 更新路径大纲展示阶段/模块 outcome 并保持折叠。
- [x] 运行聚焦测试、语义化可访问性断言和移动布局检查。

### Task 3: 目标—材料—执行—反馈活动页

**Files:**
- Modify: `web/src/components/newcomer-training/activity-shell.tsx`
- Modify: `web/src/components/newcomer-training/activity-runners/audio-assessment-runner.tsx`
- Test: corresponding co-located tests

- [x] 写目标、步骤、通过标准和材料确认用户文案失败测试。
- [x] 运行聚焦 Vitest，确认 RED。
- [x] 在公共活动壳展示任务说明，并让执行器只负责能力交互。
- [x] 将“已发布版本”等治理术语替换为学员语言，保留材料读取确认语义。
- [x] 验证处理、失败、重试、完成和下一步状态。

### Task 4: 管理员可配置学员内容

**Files:**
- Modify: `web/src/components/admin/newcomer-training/path-inspector.tsx`
- Modify: `web/src/components/admin/newcomer-training/path-editor-state.ts`
- Create: `web/src/components/admin/newcomer-training/string-list-field.tsx`
- Test: `web/src/components/admin/newcomer-training/path-editor.test.tsx`

- [x] 写阶段 outcome、模块 outcome、活动目标/价值/步骤/标准 round-trip 失败测试。
- [x] 运行 Vitest，确认 RED。
- [x] 实现基础内容字段与可访问的字符串列表编辑器。
- [x] 保持适用对象、前置依赖、完成策略和资源绑定在高级规则区。
- [x] 新建节点写入兼容默认值，验证保存和重新加载不丢字段。

### Task 5: 两栏编辑器、操作降噪与真实预览

**Files:**
- Modify: `web/src/components/admin/newcomer-training/path-editor.tsx`
- Modify: `web/src/components/admin/newcomer-training/path-outline.tsx`
- Modify: `web/src/components/admin/newcomer-training/path-preview.tsx`
- Test: corresponding co-located tests

- [x] 写两栏结构、按需预览、共享任务卡、草稿无需理由和低频操作可聚焦测试。
- [x] 运行 Vitest，确认 RED。
- [x] 将预览从常驻第三栏迁到大对话框，复用 `missionFromCandidate` 与任务卡。
- [x] 默认只展开首个分支；行操作悬停/聚焦出现，键盘仍可用。
- [x] 将保存/检查/发布移至顶部操作区；保存使用稳定审计说明，发布说明保持必填。
- [x] 校验与历史进入次级折叠区，避免压缩主编辑区。

### Task 6: 默认内容与合同文档

**Files:**
- Modify: `backend/scripts/seed_newcomer_training_path.py`
- Modify: `docs/api-contract/sales-trainer.md`
- Modify: `.trellis/spec/backend/newcomer-training-activity-orchestration.md`
- Test: relevant seed/contract tests

- [x] 为默认三阶段和核心活动补充具体 outcome、目标、步骤与通过标准。
- [x] 保证 seed 幂等且不覆盖管理员已发布内容。
- [x] 更新 API 合同和 Trellis 可执行规范，记录字段限制与回退语义。
- [x] 验证新环境 seed 和旧 revision 解析。

### Task 7: 全量验证、浏览器验收与提交

**Files:**
- Modify: newcomer-focused Playwright specs when needed

- [x] 运行后端 newcomer 聚焦 pytest、Ruff、Mypy（聚焦文件通过；全仓 Mypy 存在既有基线错误）。
- [x] 运行前端 newcomer Vitest、TypeScript、ESLint、production build。
- [x] 运行桌面/移动学员路径和桌面管理编排 Playwright。
- [x] 在实际运行页面检查主操作、移动首屏、编辑字段、真实预览和发布说明。
- [x] 使用 CodeGraph affected/impact 选择补充回归并运行。
- [x] 删除临时 `implementation-notes.md`，检查工作树，仅提交本任务文件。
