---
estimated_steps: 3
estimated_files: 3
skills_used: []
---

# T01: 把 recovery baseline 提炼成可执行 drills

- 基于 M018 baseline 与 S01-S03 hardened seams，选定最有价值的 recovery drills：auth/bootstrap、db migration、redis/session state、websocket reconnect、OSS signing/playback。
- 把手工 runbook 中可自动执行的步骤提炼成 repo-local scripts 或 checked commands。
- 明确哪些仍必须人工完成。

## Inputs

- `M018 baseline`
- `M020 S01-S03 outputs`

## Expected Output

- `scripts/*recovery* or scripts/*drill*`
- `docs/backup-recovery-runbook.md`

## Verification

rg -n "backup|restore|recovery|drill|auth|redis|oss|websocket" scripts docs/backup-recovery-runbook.md docs/setup/backup-recovery-current-state.md
