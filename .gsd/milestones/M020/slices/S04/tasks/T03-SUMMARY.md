---
id: T03
parent: S04
milestone: M020
key_files:
  - .sisyphus/deploy/ai-backend.service
  - .sisyphus/deploy/ai-frontend.service
  - .sisyphus/deploy/ai-practice.nginx.conf
  - .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md
  - docs/backup-recovery-runbook.md
  - docs/api-contract/support-runtime.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D229 — treat the shipped systemd+nginx bundle as single-node authority only, and require release/recovery proof to pair node-local /health captures with repo-local recovery drill summary/log evidence.
duration: 
verification_result: passed
completed_at: 2026-04-14T00:48:27.951Z
blocker_discovered: false
---

# T03: Wrote the recovery-drill/deploy boundary into the ops docs so single-node deploy guidance, future multi-instance limits, and release/recovery proof now use the same evidence rules.

**Wrote the recovery-drill/deploy boundary into the ops docs so single-node deploy guidance, future multi-instance limits, and release/recovery proof now use the same evidence rules.**

## What Happened

I closed the last S04 documentation gap by writing the shipped deploy boundary back into the authority surfaces that operators and future slices will actually reuse. The `.sisyphus/deploy` systemd/nginx files now state that the current native bundle is single-node only, binds backend/frontend on loopback, treats `/health` as node-local proof, and does not imply cluster drain or cross-instance websocket authority. I then aligned the long-lived prose artifacts around that same contract: `docs/backup-recovery-runbook.md` now explains the deploy bundle scope, lists deploy-health plus drill-summary evidence locations, and cites the latest real drill output including the still-failing `db_migration` signal; `docs/api-contract/support-runtime.md` now tells support to pair release-health summaries with drill evidence instead of treating `/overview` as sufficient; `.sisyphus/plans/cloud-full-redeploy-115-191-36-90.md` now frames the cloud rollout as single-node today / multi-instance later and requires release/recovery proof to cite the latest recovery drill summary; and `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` now records the downstream rule so M021/M022 work can reuse it without rediscovering the boundary. I also recorded D229 plus a knowledge entry so downstream work keeps the same node-health-plus-drill-evidence rule.

## Verification

Ran the exact task-plan verification gate `rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, which passed and surfaced the expected wording across the deploy files, cloud redeploy plan, runbook, and architecture scan. Then ran a focused support/runtime grep gate `rg -n "release-health|recovery drill|summary.json|process-local|redis snapshot|healthy" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md`, which also passed and confirmed the support contract now explicitly pairs release-health summaries with recovery drill evidence and preserves the process-local vs Redis-snapshot runtime split.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` | 0 | ✅ pass | 32ms |
| 2 | `rg -n "release-health|recovery drill|summary.json|process-local|redis snapshot|healthy" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md` | 0 | ✅ pass | 12ms |

## Deviations

In addition to the task plan’s expected output surfaces, I updated `docs/api-contract/support-runtime.md` because the task explicitly called for support guidance and that file is the durable support-facing runtime contract. I also wrote the single-node/multi-instance boundary directly into `.sisyphus/deploy/*` comments so the deploy authority files themselves carry the rule instead of relying only on plan prose.

## Known Issues

The latest referenced drill evidence still records a real local migration blocker: `.dev/recovery-drills/20260414T002842Z/summary.json` shows `db_migration` failing with `KeyError: '20260412_0315_028'` while the other drills passed. This task intentionally documented that signal rather than masking it behind healthy node status.

## Files Created/Modified

- `.sisyphus/deploy/ai-backend.service`
- `.sisyphus/deploy/ai-frontend.service`
- `.sisyphus/deploy/ai-practice.nginx.conf`
- `.sisyphus/plans/cloud-full-redeploy-115-191-36-90.md`
- `docs/backup-recovery-runbook.md`
- `docs/api-contract/support-runtime.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
