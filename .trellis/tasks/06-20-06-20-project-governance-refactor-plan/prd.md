# 全面项目治理重构计划

## Goal

把当前由多轮 AI 快速开发堆叠出的前后端、配置、权限、审计、Prompt、测试和发布流程重新收敛为可持续演进的架构治理计划。此任务只产出调研、PRD 和 Ultra Loop 可执行计划，不直接改业务代码。

## What I already know

* 当前系统不是单点坏掉，而是多个增长方向同时推进：新人训练路径、实时 WebSocket 对练、AI Coach、Prompt 治理、课程/题库、后台配置、seed/backfill 脚本。
* 后端 composition roots 包括 `backend/src/app_factory.py`、`backend/src/router_registry.py`、`backend/src/websocket_routes.py` 和 lifespan/registry/contributor 相关文件。
* 前端热点包括 `web/src/lib/api/types.ts`、`web/src/lib/api/domains/sales-trainer.ts`、`web/src/app/(dashboard)/sales-trainer/business-skills/page.tsx` 和 admin sales-trainer 配置页面。
* 项目已有 `backend/tests/unit/test_runtime_dependency_contract.py`，说明依赖治理不是从零开始，应该收紧现有 guardrail。
* Trellis 当前已有多个未完成架构/路线任务，本任务需要作为总治理计划，避免继续叠加无执行闭环的文档。

## Assumptions

* 默认不做 big-bang rewrite。
* 默认先加边界和验证护栏，再迁移代码。
* 默认保留现有 URL、API 门面和数据表兼容层，逐步收敛内部结构。
* 默认先治理 sales-trainer/newcomer path 的前端和 API 层，再动高风险 WebSocket runtime。

## Requirements

* 产出一份 `.omo/plans/project-governance-refactor.md`，可由后续 Ultra Loop 执行。
* 计划必须覆盖后端边界、前端层级、配置治理、权限/状态/审计、Prompt/AI、测试/CI、迁移/脚本、发布回滚。
* 每个执行 todo 必须有引用、验收标准、happy/failure QA 场景和提交策略。
* 明确 Must NOT：不推倒重来、不先拆所有大文件、不把 `common/` 当垃圾桶、不让 `sales_trainer` 引入实时 runtime 概念。

## Acceptance Criteria

* [x] `.omo/plans/project-governance-refactor.md` 存在且包含 Scope、Verification strategy、Execution strategy、Todos、Final verification wave、Commit strategy、Success criteria。
* [x] `.omo/drafts/project-governance-refactor.md` 记录组件、假设、发现和决策。
* [x] `.omo/ultraresearch/20260620-184300-project-governance-refactor/` 包含研究日志和 synthesis。
* [x] 团队 artifacts 至少覆盖 A/B/C/D 四个研究轴，或在 synthesis 中明确说明未返回的轴和补救。
* [x] 计划不要求后续执行者再询问架构方向。

## Definition of Done

* 调研证据落盘。
* 计划文件落盘。
* 不修改产品代码。
* 不自动启动实施。
* 最终中文说明给出计划路径、核心路线和未执行项。

## Out of Scope

* 本轮不写业务代码。
* 本轮不启动 Ultra Loop 实施。
* 本轮不提交 git commit。
* 本轮不做数据库 migration 或数据修复。

## Technical Notes

* OMO draft: `.omo/drafts/project-governance-refactor.md`
* OMO plan: `.omo/plans/project-governance-refactor.md`
* Ultraresearch session: `.omo/ultraresearch/20260620-184300-project-governance-refactor/`
* Team state: `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/`
