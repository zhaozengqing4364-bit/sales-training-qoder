---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: 把归一化 finding 映射到后续 milestones/slices

按后续执行面把 actionable-now 与 needs-discovery finding 重新映射到 M014-M018 的具体 slices，形成可直接消费的 backlog 对照表。

## Inputs

- `.gsd/plans/GSD_PLAN_system-audit-repair.md`
- `.gsd/milestones/M013/M013-ROADMAP.md`

## Expected Output

- `.gsd/plans/GSD_PLAN_system-audit-repair.md`

## Verification

rg -n "M014|M015|M016|M017|M018" .gsd/plans/GSD_PLAN_system-audit-repair.md

## Observability Impact

none
