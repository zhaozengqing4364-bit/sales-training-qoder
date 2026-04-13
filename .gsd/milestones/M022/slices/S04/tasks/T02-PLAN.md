---
estimated_steps: 2
estimated_files: 4
skills_used: []
---

# T02: 设计保持单体边界的 org-boundary migration path

- 设计 modular monolith 下的迁移路径：哪些实体先加 organization/team ownership，哪些 authz/analytics/report surfaces 需要 compatibility readers。
- 为未来 SSO/CRM/org-sync/enterprise directory 预留 integration slots，但不把它们拉进当前实现范围。

## Inputs

- `T01 matrix`
- `future enterprise requirements`

## Expected Output

- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "migration path|organization|team|tenant|SSO|CRM|org sync|compatibility reader" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
