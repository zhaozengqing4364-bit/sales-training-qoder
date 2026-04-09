# S01: SYSTEM_AUDIT_REPORT 条目归一化

**Goal:** 对 SYSTEM_AUDIT_REPORT 全文逐条建立 disposition：already-fixed / actionable-now / needs-discovery / deferred-by-product / contradicted-by-project-knowledge
**Demo:** After this: 归一化矩阵覆盖所有 audit section，每个条目有 disposition、证据路径和后续 slice 归属

## Tasks
- [x] **T01: Normalized all 51 SYSTEM_AUDIT_REPORT findings into a disposition matrix and synced the rollup counts back into the architecture scan.** — 逐条阅读 SYSTEM_AUDIT_REPORT、PROJECT、REQUIREMENTS、KNOWLEDGE、M012 路线图，建立 audit section → finding → disposition 的原始矩阵；每条 finding 至少记录一条代码/文档证据路径，避免把已修项或 deferred 项混入 actionable backlog。
  - Estimate: 45m
  - Files: SYSTEM_AUDIT_REPORT.md, .gsd/PROJECT.md, .gsd/REQUIREMENTS.md, .gsd/KNOWLEDGE.md, .gsd/milestones/M012/M012-ROADMAP.md
  - Verify: rg -n "already-fixed|actionable-now|needs-discovery|deferred-by-product|contradicted-by-project-knowledge" .gsd/plans/GSD_PLAN_system-audit-repair.md
- [ ] **T02: 补齐 disposition 证据与冲突来源** — 对每个 section 的 disposition 进行复核：已修项补代码证据，deferred 项补冲突来源，needs-discovery 项补后续归属；确保不存在未分类 finding。
  - Estimate: 30m
  - Files: .gsd/plans/GSD_PLAN_system-audit-repair.md
  - Verify: rg -n "deferred-by-product|contradicted-by-project-knowledge|needs-discovery" .gsd/plans/GSD_PLAN_system-audit-repair.md
- [ ] **T03: 把归一化 finding 映射到后续 milestones/slices** — 按后续执行面把 actionable-now 与 needs-discovery finding 重新映射到 M014-M018 的具体 slices，形成可直接消费的 backlog 对照表。
  - Estimate: 30m
  - Files: .gsd/plans/GSD_PLAN_system-audit-repair.md
  - Verify: rg -n "M014|M015|M016|M017|M018" .gsd/plans/GSD_PLAN_system-audit-repair.md
