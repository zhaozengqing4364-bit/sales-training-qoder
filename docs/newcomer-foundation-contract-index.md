# 新人销售基础训练权威合同索引

> 状态：Foundation 首发运行闭环已完成（2026-07-18）；管理员真实内容生产与 Legacy PPT/Demo 迁移于 2026-07-20 重新打开。首发证据继续保留，但不得再用 Seed、路由或可绑定已有资源证明 Authoring 完整；勘误见归档验收矩阵和下列新 ADR。

后续维护必须先读取本索引，并以以下文件为准：

- 产品边界：[`adr/2026-07-16-newcomer-foundation-product-boundary.md`](adr/2026-07-16-newcomer-foundation-product-boundary.md)
- 领域与模块：[`adr/2026-07-16-newcomer-foundation-domain-and-modules.md`](adr/2026-07-16-newcomer-foundation-domain-and-modules.md)
- Enrollment 冻结：[`adr/2026-07-16-enrollment-revision-freeze.md`](adr/2026-07-16-enrollment-revision-freeze.md)
- AI 与持久化任务：[`adr/2026-07-16-governed-ai-and-durable-tasks.md`](adr/2026-07-16-governed-ai-and-durable-tasks.md)
- 能力证据与人工复核：[`adr/2026-07-17-competency-evidence-readiness-review.md`](adr/2026-07-17-competency-evidence-readiness-review.md)
- 管理工作台与发布治理：[`adr/2026-07-17-foundation-admin-release-governance.md`](adr/2026-07-17-foundation-admin-release-governance.md)
- 内容生产与 Legacy 迁移权威：[`adr/2026-07-20-foundation-authoring-and-legacy-migration-authority.md`](adr/2026-07-20-foundation-authoring-and-legacy-migration-authority.md)
- 共享领域语言：[`../CONTEXT.md`](../CONTEXT.md)
- 领域词典：[`domain-glossary.md`](domain-glossary.md)
- 模块、对象与接口：[`architecture/newcomer-foundation-contract.md`](architecture/newcomer-foundation-contract.md)
- 状态机：[`architecture/newcomer-foundation-state-machines.md`](architecture/newcomer-foundation-state-machines.md)
- 公开事件：[`architecture/newcomer-foundation-events.md`](architecture/newcomer-foundation-events.md)
- API 与 ViewModel：[`api-contract/newcomer-training-v2.md`](api-contract/newcomer-training-v2.md)
- 前端 ViewModel、状态与隐私安全 UX 事件：[`../.trellis/spec/frontend/newcomer-foundation-view-models.md`](../.trellis/spec/frontend/newcomer-foundation-view-models.md)
- 权限与安全：[`security.md`](security.md)
- AI 治理：[`ai-governance.md`](ai-governance.md)
- 干净切换：[`architecture/newcomer-foundation-clean-cut.md`](architecture/newcomer-foundation-clean-cut.md)
- Legacy 内容字段映射：[`architecture/newcomer-foundation-legacy-authoring-mapping.md`](architecture/newcomer-foundation-legacy-authoring-mapping.md)
- 测试与 SLO：[`testing.md`](testing.md)
- Guard 机器规则设计：[`architecture/newcomer-foundation-guard-policy.yaml`](architecture/newcomer-foundation-guard-policy.yaml)
- 持久任务 Worker：[`setup/durable-task-worker-runbook.md`](setup/durable-task-worker-runbook.md)
- 录音评测运行、清理与回滚：[`setup/foundation-audio-assessment-runbook.md`](setup/foundation-audio-assessment-runbook.md)
- 发布与回滚：[`setup/foundation-release-runbook.md`](setup/foundation-release-runbook.md)

冲突时，2026-07-16 起的 Accepted ADR、本文索引和上述合同优先于旧计划与 Legacy 历史。运行时 OpenAPI、架构 Guard 和发布门禁是“已实现”的机器证据；后续若代码与合同出现偏差，必须显式记录并阻断发布，不得恢复旧写权威或永久兼容层。
