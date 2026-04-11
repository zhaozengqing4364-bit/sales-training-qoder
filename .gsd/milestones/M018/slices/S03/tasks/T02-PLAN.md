---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T02: 输出 backup/recovery baseline runbook

Why: S03 的核心交付是把“缺失”变成一份最小可执行 runbook，而不是继续停留在 audit 描述。

Do:
1. 编写最小 runbook：备份频率、恢复步骤、验证步骤、负责人/证据位置、季度演练建议。
2. 只写当前真实现状，不写未落地的理想化运维平台。
3. 保留未来改进建议，但与当前可执行内容分开。

Done when: 仓库中出现一份可直接被人类执行的 backup/recovery baseline runbook。

## Inputs

- `docs/*`
- `scripts/*`

## Expected Output

- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`

## Verification

test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md

## Observability Impact

backup/recovery 基线从 audit 描述变成可检查的仓库 artifact。
