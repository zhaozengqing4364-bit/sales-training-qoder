# 新人训练后台治理二期：模块内一页式配置闭环

## Goal

将新人训练后台从“模块归位”继续推进到“模块内闭环配置”：管理员进入录音管理或学习专题后，优先通过选择已有资源完成配置；缺资源时在当前页面用抽屉/弹窗/内联区域快速新建，并自动刷新、选中、绑定，避免为了材料、评分标准、单元、题目、考卷、文章在多个资源页面之间跳转。

## What I Already Know

- 上一轮已经将后台顶层治理为录音管理、学习专题、路径与达标、系统治理，并保留旧路由兼容。
- 当前录音任务详情页已经能选择已发布单元、材料、评分标准并保存发布，但缺资源时仍使用跳转链接。
- 当前材料页和评分标准页各自有完整 CRUD，但它们应降级为查看全部/高级管理，不应成为主流程必经路径。
- 评分标准表单当前默认暴露 JSON、system prompt、output schema 等工程字段，需要改为普通模式结构化配置，高级模式折叠。
- 学习专题需要以专题详情为工作台，在专题内管理文章/章节、小测/考卷、AI 教练、得分展示和发布。

## Requirements

- 录音管理首页从入口目录升级为任务配置工作台，支持切换 PPT 讲解、公司产品 Demo、金字塔演讲。
- 录音任务配置页必须在当前页面内完成训练单元、任务材料、评分标准选择与缺失资源快速新建。
- 快速新建材料、上传版本、快速新建评分标准、快速新建录音单元成功后必须刷新候选项、自动选中并绑定到当前任务。
- 评分标准普通模式使用结构化表单，不默认展示 JSON / system prompt / output schema；高级模式可折叠展示。
- 学习专题详情页必须能在专题内完成文章/章节、小测/考卷、AI 教练、得分展示规则和发布配置的闭环入口。
- 独立资源页继续保留，但作为查看全部/高级管理/旧路由兼容；主流程不能强依赖跳转。
- 权限以后端能力为准，前端只做展示过滤和权限不足状态。
- 发布、回滚、审计、材料版本快照、评分标准版本快照语义保持不变。

## Acceptance Criteria

- [x] 管理员配置一个录音任务时，不需要跳转到多个页面即可完成单元、材料、评分标准配置。
- [x] 录音任务页支持选择已有资源，也支持就地快速新建缺失资源。
- [x] 快速新建成功后自动刷新、自动选择、自动绑定。
- [x] 评分标准普通模式不默认暴露 JSON / system prompt / output schema。
- [x] 学习专题详情页能在专题内完成文章、章节、小测/考卷、AI 教练、得分规则、发布配置。
- [x] 独立资源页仍可访问，旧 URL 不 404。
- [x] 权限不足、加载失败、提交失败、发布成功均有可见状态。
- [x] 更新相关 Vitest 测试、类型检查、lint、Next build 并通过。
- [x] 更新 API 契约和 Trellis 文档，说明一页式配置原则、兼容路由、风险与回滚。

## Technical Approach

- 在 `components/admin/sales-trainer/` 下抽取可嵌入的快速创建组件和结构化评分标准 ViewModel，复用现有 API facade、Toast、GlassCard、Dialog/Drawer 组件。
- 录音任务详情页保留现有路径配置 workflow 作为保存/发布编排层，新增就地创建后更新当前 `PathAudioScenarioValue` 的绑定字段。
- 录音管理首页优先展示任务工作台和当前任务配置入口，配套管理降级为“查看全部/高级管理”。
- 学习专题先以当前已有业务能力为边界，新增专题详情工作台聚合现有文章、题库、考卷、AI 教练、发布治理入口与就地快捷操作；不引入数据库迁移。
- 旧路由继续保留兼容，不改变后端 API 权限和审计模型。

## Out of Scope

- 不做数据库 schema migration。
- 不重写后端发布、回滚、评分、重评或审计服务。
- 不移除旧资源路由。
- 不把所有高级管理列表合并到一个页面；独立资源页继续作为高级管理存在。

## Definition of Done

- CodeGraph impact/affected 用于影响面和测试选择。
- 关键页面和组件测试覆盖选择优先、就地新建、自动绑定、权限/错误/成功状态。
- `npx vitest run` 覆盖相关测试通过。
- `npx eslint` 覆盖变更 TS/TSX 文件通过。
- `npx tsc --noEmit` 通过。
- `npx next build` 通过。
- 文档和 Trellis implementation notes 更新。
- 任务提交并归档。

## Technical Notes

- 适用规范：`.trellis/spec/frontend/index.md`、`admin-console-patterns.md`、`component-guidelines.md`、`state-management.md`、`type-safety.md`、`quality-guidelines.md`、`web/AGENTS.md`、`web/src/app/admin/sales-trainer/AGENTS.md`。
- 目标文件族：`web/src/app/admin/sales-trainer/audio/*`、`materials/*`、`score-standards/*`、`learning-topics/*`、`articles/*`、`papers/*`、`questions/*`、`components/admin/sales-trainer/*`、`lib/sales-trainer/routes.ts`、`docs/api-contract/sales-trainer.md`。
