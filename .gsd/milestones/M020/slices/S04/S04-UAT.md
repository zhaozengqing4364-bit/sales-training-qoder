# S04: Recovery drill automation 与部署指导收口 — UAT

**Milestone:** M020
**Written:** 2026-04-14T01:08:28.097Z

# S04 UAT — Recovery drills and deploy-boundary closure

## Preconditions
- Worktree is the current repository root.
- Local backend health endpoint is reachable at `http://127.0.0.1:3444/health` for node-level proof.
- `backend/venv` is present.
- Test admin bootstrap inputs are available for the drill run:
  - `RECOVERY_ADMIN_EMAIL=admin@qoder.ai`
  - `RECOVERY_ADMIN_NAME=管理员`
- Reviewer understands that `redis_service_restore`, `oss_bucket_export`, and `multi_instance_drain` are intentionally manual-only boundaries in this slice.

## Test Case 1 — Inventory authority is executable and complete
1. Run `python3 scripts/recovery-drill-baseline.py status`.
   - Expected: output lists exactly the shipped drill ids `db_migration`, `auth_bootstrap`, `redis_session_state`, `websocket_reconnect`, `oss_signing_playback`, `health_check`.
   - Expected: output also lists manual-only boundaries `redis_service_restore`, `oss_bucket_export`, and `multi_instance_drain`.
2. Run `python3 scripts/recovery-drill-baseline.py check`.
   - Expected: command exits 0.
   - Expected: output ends with `Repository validation: all referenced authority paths exist`.

## Test Case 2 — Runner reuses the same authority metadata instead of a second command list
1. Run `python3 scripts/recovery-drill-runner.py plan --drill db_migration --drill auth_bootstrap --drill health_check`.
   - Expected: plan output shows the same commands documented in the baseline/runbook.
   - Expected: `auth_bootstrap` displays required env vars `RECOVERY_ADMIN_EMAIL` and `RECOVERY_ADMIN_NAME`.
   - Expected: each selected drill shows a log path under `.dev/recovery-drills/<timestamp>/`.

## Test Case 3 — Minimal executable recovery drill bundle produces evidence and preserves blockers
1. Run:
   `RECOVERY_ADMIN_EMAIL=admin@qoder.ai RECOVERY_ADMIN_NAME=管理员 python3 scripts/recovery-drill-runner.py run --continue-on-failure --drill db_migration --drill auth_bootstrap --drill redis_session_state --drill oss_signing_playback --drill health_check`
2. Open the emitted `.dev/recovery-drills/<timestamp>/summary.json`.
   - Expected: `summary.json` exists and contains one entry per requested drill.
   - Expected: `auth_bootstrap`, `redis_session_state`, `oss_signing_playback`, and `health_check` are recorded with `status: "passed"`.
   - Expected: `health_check` captures a `/health` payload containing `status`, `timestamp`, and `version`.
   - Expected: `db_migration` is not silently ignored; if the environment is still broken, it is recorded as `status: "failed"` with a non-empty `failure_signal` (currently `KeyError: '20260412_0315_028'`).
3. Open the per-drill logs for `01-db_migration.log`, `02-auth_bootstrap.log`, and `05-health_check.log`.
   - Expected: each log contains the rendered command and exit code.
   - Expected: `02-auth_bootstrap.log` shows `[created]` or `[updated]` user output.
   - Expected: `01-db_migration.log` preserves the real Alembic traceback instead of a generic wrapper error.

## Test Case 4 — Support/runtime and deploy docs agree on the same boundary
1. Run `rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`.
   - Expected: matches appear in `.sisyphus/deploy/*`, the cloud redeploy plan, the runbook, and the architecture scan.
   - Expected: wording makes clear that the shipped native bundle is single-node only and `/health` is per-node proof only.
2. Run `rg -n "release-health|recovery drill|summary.json|process-local|redis snapshot|healthy" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md`.
   - Expected: support/runtime guidance explicitly pairs release-health summaries with recovery-drill evidence.
   - Expected: docs preserve the process-local live connection vs shared Redis snapshot split from S03.

## Edge Cases

### Edge Case A — Missing bootstrap inputs should fail as a precondition, not a crash
1. Run `python3 scripts/recovery-drill-runner.py run --drill auth_bootstrap` without exporting `RECOVERY_ADMIN_EMAIL` / `RECOVERY_ADMIN_NAME`.
   - Expected: the step is recorded as `precondition_failed` and writes a log explaining the missing env vars.
   - Expected: no fake success is emitted.

### Edge Case B — Healthy node status must not hide a migration blocker
1. Compare the latest `/health` output with the latest drill `summary.json`.
   - Expected: `/health` may still be `healthy` while `db_migration` remains failed.
   - Expected: release/recovery sign-off is blocked until the drill failure is either remediated or explicitly accepted as a known blocker with evidence.
