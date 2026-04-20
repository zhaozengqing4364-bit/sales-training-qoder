---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: 收口 repo-root verification contract

把 repo-root 可直接执行的 backend pytest 命令与必须串行的约束写进 remediation plan，避免 auto-mode 把 `cd backend && pytest` 拆散后误报失败。

## Inputs

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- `.gsd/KNOWLEDGE.md`

## Expected Output

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- `.gsd/plans/GSD_PLAN_system-audit-repair.md`

## Verification

rg -n "串行|coverage|backend/venv/bin/python -m pytest -c backend/pyproject.toml" docs/plans/2026-04-08-system-audit-remediation-plan.md .gsd/plans/GSD_PLAN_system-audit-repair.md

## Observability Impact

none
