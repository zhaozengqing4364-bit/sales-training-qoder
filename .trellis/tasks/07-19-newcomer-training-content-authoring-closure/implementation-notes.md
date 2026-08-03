# Implementation Notes

## Scope

依次完成十个 Foundation 内容配置闭环子任务；每个子任务只做其 PRD 明确范围，并按 `execution-policy.md` 运行最小相关验证。

## Decisions

- 继续以 Foundation 为新人训练唯一写权威；Legacy 仅用于只读清点、迁移与历史审计。
- 内容、题目、录音、Coach、异步场景均复用现有领域模型和运行时，不另建平行 Runtime。
- 管理端保持一个“新人训练”产品入口，入口内按业务对象与任务拆分模块。
- 实时客户对练继续延期，不进入本批实现、导航、路径联合或发布依赖。
- 多媒体内容沿用 `learning` 的 `SourceDocument`/`LearningUnit` 权威，additive 扩展来源元数据与封闭 `content_blocks`；PPT/媒体处理继续接入现有 DurableTask。
- 手工题必须从“保存即 approved”改成 working→人工审核/批准；导入候选先落受治理批次，确认后生成 working revision。
- PPT/Demo 录音和异步三段场景继续复用 `audio_assessment` Pipeline；结构化 Coach 继续复用 `ai_coach` Session/Pipeline。

## Deviations

- 十个子任务属于同一用户授权的连续实施批次，且工作树已有大量用户未提交改动。为避免每个子任务中断并误纳入无关文件，子任务通过质量门后使用 `task.py archive --no-commit` 记录完成；只在全部十项完成后基于精确文件清单向用户提交一次批量 commit 计划，未获得确认前不暂存或提交。

## Historical / Unrelated Findings

- 当前工作树包含大量既有未提交改动；所有实现按文件级证据收敛，禁止重置、覆盖或顺带整理无关变更。
- `web/src/app/AGENTS.md` 与前端索引引用的 `.kiro/steering/frontend-principles.md` 当前不存在；本批 UI 以根 `DESING.md`、Trellis `product-design-engineering.md`、`admin-console-patterns.md` 和现有组件模式为准，不为此补造无关规范文件。
