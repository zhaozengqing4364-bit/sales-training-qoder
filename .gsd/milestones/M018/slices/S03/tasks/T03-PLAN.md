---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: 校正 runbook 为真实可执行现状

Why: runbook 如果不和真实命令、真实路径对齐，很快就会变成误导性文档。

Do:
1. 人工走查 runbook 引用的命令与路径。
2. 去掉空泛理想架构描述，只保留当前可执行现状。
3. 把未来演练建议单列为 follow-up，而不混进当前基线。

Done when: runbook 里的路径/命令都能在当前仓库语境下成立，grep proof 通过。

## Inputs

- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`

## Expected Output

- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`

## Verification

grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md

## Observability Impact

runbook 是否仍反映当前现实，可由文件存在和内容 grep 直接检查。
