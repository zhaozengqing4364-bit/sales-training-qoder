---
estimated_steps: 2
estimated_files: 4
skills_used: []
---

# T03: 把 recovery drill 与部署边界写回运维文档

- 更新部署指导、architecture scan、support guidance，明确单机部署、未来多实例、以及 drill 适用范围。
- 把 drill outputs 纳入 release/recovery proof 说明，供后续 milestone 复用。

## Inputs

- `T02 script outputs`
- `current deploy configs`

## Expected Output

- `.sisyphus/deploy/*`
- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
