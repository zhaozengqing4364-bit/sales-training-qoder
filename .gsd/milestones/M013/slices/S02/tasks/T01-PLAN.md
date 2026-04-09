---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T01: 盘点现有 focused verification commands

盘点现有 web/backend focused tests，把 auth/dashboard/history/profile/practice/lifecycle/websocket/admin 这几类验证面各自映射到一组真实命令。优先复用现有 focused tests，不引入大规模新测试。

## Inputs

- `web/src/**/*.test.tsx`
- `backend/tests/**/*`
- `.gsd/KNOWLEDGE.md`

## Expected Output

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`

## Verification

rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" docs/plans/2026-04-08-system-audit-remediation-plan.md

## Observability Impact

none
