---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: 建立 audit 条目原始归一化矩阵

逐条阅读 SYSTEM_AUDIT_REPORT、PROJECT、REQUIREMENTS、KNOWLEDGE、M012 路线图，建立 audit section → finding → disposition 的原始矩阵；每条 finding 至少记录一条代码/文档证据路径，避免把已修项或 deferred 项混入 actionable backlog。

## Inputs

- `SYSTEM_AUDIT_REPORT.md`
- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M012/M012-ROADMAP.md`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_SYSTEM_AUDIT_2026-04-08.md`
- `.gsd/plans/GSD_PLAN_system-audit-repair.md`

## Verification

rg -n "already-fixed|actionable-now|needs-discovery|deferred-by-product|contradicted-by-project-knowledge" .gsd/plans/GSD_PLAN_system-audit-repair.md

## Observability Impact

none
