---
estimated_steps: 2
estimated_files: 3
skills_used: []
---

# T03: 把 runtime state authority 写回 support/runbook surfaces

- 为 support/runtime、architecture scan、runbook 补充新的 state inspection surfaces 和 restart/drain guidance。
- 把单机/systemd 与未来多实例边界说清，不让 downstream milestones 再假设 ‘只要重启服务就行’。

## Inputs

- `T02 结果`
- `support runtime surfaces`

## Expected Output

- `docs/api-contract/support-runtime.md`
- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "reconnect|epoch|snapshot|active connection|drain|restart" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
