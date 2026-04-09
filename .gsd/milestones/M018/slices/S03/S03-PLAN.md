# S03: 备份 / 故障恢复 / 容灾 runbook 基线

**Goal:** 把备份频率、恢复流程、灾难恢复演练从“缺失”转成最小可执行 runbook
**Demo:** After this: 有一份按当前部署现状可执行的 backup/recovery runbook

## Tasks
- [ ] **T01: 盘点当前 backup/recovery 现状** — 梳理当前部署方式、脚本、数据库连接方式与已有备份事实，确认 runbook 能引用的真实命令/路径/证据位置。
  - Estimate: 30m
  - Files: docs/*, scripts/*
  - Verify: find docs scripts -maxdepth 2 -type f | sort | head -n 20
- [ ] **T02: 输出 backup/recovery baseline runbook** — 编写最小可执行 backup/recovery runbook：备份频率、恢复步骤、验证步骤、负责人/证据位置、季度演练建议。只写当前真实现状。
  - Estimate: 40m
  - Files: docs/*, analysis artifact
  - Verify: test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
- [ ] **T03: 校正 runbook 为真实可执行现状** — 人工走查 runbook 引用的命令与路径，去掉空泛理想架构描述，保留未来演练建议作为 follow-up。
  - Estimate: 20m
  - Files: docs/*, analysis artifact
  - Verify: grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
