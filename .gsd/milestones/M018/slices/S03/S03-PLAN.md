# S03: 备份 / 故障恢复 / 容灾 runbook 基线

**Goal:** 把备份频率、恢复流程、灾难恢复演练从“缺失”转成最小可执行 runbook。
**Demo:** 有一份按当前部署现状可执行的 backup/recovery runbook。

## Must-Haves

- 仓库里有一份按当前部署现状可执行的 backup/recovery runbook。
- runbook 只描述当前真实路径、命令、验证步骤和责任边界，不写理想化未来架构。
- 文件存在与内容 grep proof 可稳定证明该基线仍然在仓库里。

## Proof Level

- This slice proves: operational

## Integration Closure

S03 把当前部署/脚本/负责人/验证路径沉淀成 runbook，为未来运维自动化或恢复演练 slice 提供事实起点。

## Verification

- future agents 可直接检查 runbook 文件和引用路径，判断当前备份/恢复现状，而不是重新从部署脚本和 workflow 猜。

## Tasks

- [x] **T01: 盘点当前 backup/recovery 现状** `est:30m`
  Why: 先盘清当前已有文档、脚本和数据库连接方式，runbook 才不会写成脱离仓库现实的空文档。

Do:
1. 梳理当前部署方式、脚本、数据库连接方式与已知备份事实。
2. 找出 runbook 可以引用的真实命令、路径和证据位置。
3. 记录缺失项，但不在本任务里臆造自动化能力。

Done when: 已有一份 backup/recovery 现状清单，可直接支撑 runbook 编写。
  - Files: `docs/*`, `scripts/*`
  - Verify: find docs scripts -maxdepth 2 -type f | sort | head -n 20

- [ ] **T02: 输出 backup/recovery baseline runbook** `est:40m`
  Why: S03 的核心交付是把“缺失”变成一份最小可执行 runbook，而不是继续停留在 audit 描述。

Do:
1. 编写最小 runbook：备份频率、恢复步骤、验证步骤、负责人/证据位置、季度演练建议。
2. 只写当前真实现状，不写未落地的理想化运维平台。
3. 保留未来改进建议，但与当前可执行内容分开。

Done when: 仓库中出现一份可直接被人类执行的 backup/recovery baseline runbook。
  - Files: `docs/backup-recovery-runbook.md`, `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`
  - Verify: test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md

- [ ] **T03: 校正 runbook 为真实可执行现状** `est:20m`
  Why: runbook 如果不和真实命令、真实路径对齐，很快就会变成误导性文档。

Do:
1. 人工走查 runbook 引用的命令与路径。
2. 去掉空泛理想架构描述，只保留当前可执行现状。
3. 把未来演练建议单列为 follow-up，而不混进当前基线。

Done when: runbook 里的路径/命令都能在当前仓库语境下成立，grep proof 通过。
  - Files: `docs/backup-recovery-runbook.md`, `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`
  - Verify: grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md

## Files Likely Touched

- docs/*
- scripts/*
- docs/backup-recovery-runbook.md
- .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
