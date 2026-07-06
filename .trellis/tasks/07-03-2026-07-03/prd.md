# 复核并修订 2026-07-03 架构审计报告

## Goal

对 `docs/project-analysis/audit-2026-07-03-independent-architecture-review.md` 做二次架构审计复核，吸收多 Agent 审查结论和主 Agent 复核判断，修正文档中的过度定性、错误路径、证据不足和遗漏风险，形成可作为后续整改输入的最终版风险地图。

## What I already know

- 用户要求使用多个 Agent 深入分析审计文稿，并至少经过一轮重复审查后修改当前文档。
- 目标文档是项目分析报告，不是 API 契约或 ADR；修改应以事实校准和证据补强为主。
- 上一轮多 Agent 复核已发现：总体方向成立，但权限、审计、IDOR、前端体验、测试覆盖、Prometheus 指标、ADR 状态等部分需要修正。
- 本轮已创建 4 个只读子 Agent，分别复核架构、后端/安全、前端体验、测试/CI。

## Assumptions

- 本任务只修改审计报告文档，不修改业务代码、测试或配置。
- 目标不是美化原文，而是把报告改成可执行、可复核、不过度断言的最终版。
- 对无法在当前仓库证实的结论，应降级为“风险/需验证”，而不是保留为确定缺陷。

## Requirements

- 保留成立的主判断：治理骨架存在，执行债集中在可观测性、异步可靠性、WebSocket/Redis 运行时、CI/文档纪律。
- 修正不成立或证据不足判断：`require_role`、IDOR、审计表数量、Prometheus “全死”、supervisor 测试、presentation_coach 无测试、前端后台体验低估等。
- 补充遗漏风险：WebSocket 多实例连接权威、ADR 状态混淆、跨域边界门禁不足、角色模型与管理 UI 漂移、审计 API 测试缺口。
- 文档中给出证据质量声明，区分“已证实缺陷 / 高置信风险 / 需验证假设”。

## Acceptance Criteria

- [ ] 目标文档已更新为最终修订版。
- [ ] 文档明确说明本次为多 Agent 二次复核后的版本。
- [ ] 文档内高风险问题不再把缺证项写成已证实漏洞。
- [ ] 文档保留后续整改优先级和 Task Brief，但修正验收标准与测试命令。
- [ ] 未修改业务代码。

## Out of Scope

- 不实现报告中的任何整改项。
- 不提交 git commit。
- 不新增 ADR。
- 不重排 `.trellis/tasks` 既有任务生命周期。

## Technical Notes

- 相关文档规则：`docs/AGENTS.md`。
- 相关技能：`agent-teams`。
- 当前工作区存在大量既有未提交变更，必须只触碰目标审计报告和本任务的 Trellis 记录。
