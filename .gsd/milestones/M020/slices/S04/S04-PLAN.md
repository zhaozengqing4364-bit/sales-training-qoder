# S04: Recovery drill automation 与部署指导收口

**Goal:** 把手工 runbook 提升为最小可执行 recovery/drill automation，并校准部署指导。
**Demo:** After this: M018 的 backup/recovery baseline 会升级成可执行 drill/script，能针对 hardened auth/runtime/observability seams 做真实恢复验证。

## Must-Haves

- 至少一组 repo-local drill/script 能验证 auth/runtime/db/redis/oss 关键恢复路径。
- runbook 与脚本对同一 authority file/command 负责，不再分叉。
- 部署指导对单机与未来多实例边界有明确说明。

## Proof Level

- This slice proves: final-assembly

## Integration Closure

S04 是 M020 的 final assembly slice；完成后 M021/M022 的试验与交付可以建立在可恢复 runtime 之上。

## Verification

- 恢复动作会产出脚本输出、health check、trace/log evidence，而不是只剩 markdown 说明。

## Tasks

- [x] **T01: 把 recovery baseline 提炼成可执行 drills** `est:45m`
  - 基于 M018 baseline 与 S01-S03 hardened seams，选定最有价值的 recovery drills：auth/bootstrap、db migration、redis/session state、websocket reconnect、OSS signing/playback。
- 把手工 runbook 中可自动执行的步骤提炼成 repo-local scripts 或 checked commands。
- 明确哪些仍必须人工完成。
  - Files: `scripts`, `docs/backup-recovery-runbook.md`, `docs/setup/backup-recovery-current-state.md`
  - Verify: rg -n "backup|restore|recovery|drill|auth|redis|oss|websocket" scripts docs/backup-recovery-runbook.md docs/setup/backup-recovery-current-state.md

- [ ] **T02: 落地最小 recovery/drill scripts** `est:2h`
  - 实现并验证最小 drill scripts：检查环境、执行必要 migrate/bootstrap、跑 health/runtime/auth checks、记录失败信号。
- 确保这些脚本复用 runbook 中同一 authority commands，而不是发明另一套运维路径。
- 对需要 secrets 的步骤继续保持显式前置条件，不在脚本中硬编码。
  - Files: `scripts`, `docs/backup-recovery-runbook.md`, `backend/src/main.py`, `scripts/dev-up.sh`
  - Verify: bash scripts/dependency-governance.sh status && rg -n "health|alembic|bootstrap|redis|oss|recovery" scripts/recovery-* docs/backup-recovery-runbook.md

- [ ] **T03: 把 recovery drill 与部署边界写回运维文档** `est:35m`
  - 更新部署指导、architecture scan、support guidance，明确单机部署、未来多实例、以及 drill 适用范围。
- 把 drill outputs 纳入 release/recovery proof 说明，供后续 milestone 复用。
  - Files: `.sisyphus/deploy`, `.sisyphus/plans`, `docs/backup-recovery-runbook.md`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - Verify: rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md

## Files Likely Touched

- scripts
- docs/backup-recovery-runbook.md
- docs/setup/backup-recovery-current-state.md
- backend/src/main.py
- scripts/dev-up.sh
- .sisyphus/deploy
- .sisyphus/plans
- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
