---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T02: 落地最小 recovery/drill scripts

- 实现并验证最小 drill scripts：检查环境、执行必要 migrate/bootstrap、跑 health/runtime/auth checks、记录失败信号。
- 确保这些脚本复用 runbook 中同一 authority commands，而不是发明另一套运维路径。
- 对需要 secrets 的步骤继续保持显式前置条件，不在脚本中硬编码。

## Inputs

- `T01 drill selection`
- `existing health/auth/runtime commands`

## Expected Output

- `scripts/recovery-*.sh or .py`
- `docs/backup-recovery-runbook.md`

## Verification

bash scripts/dependency-governance.sh status && rg -n "health|alembic|bootstrap|redis|oss|recovery" scripts/recovery-* docs/backup-recovery-runbook.md
