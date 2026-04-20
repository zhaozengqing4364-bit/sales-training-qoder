---
id: S04
parent: M020
milestone: M020
provides:
  - A repo-local recovery drill bundle that downstream slices and release work can execute or extend without inventing a second ops surface.
  - A truthful single-node deploy boundary for `.sisyphus/deploy/*` and cloud redeploy guidance.
  - A fresh evidence bundle showing both passing recovery checks and the currently-open Alembic migration blocker.
requires:
  - slice: S01
    provides: The hardened auth transport and bootstrap authority that S04 reuses for `auth_bootstrap` drill commands and recovery documentation.
  - slice: S02
    provides: The allowlist-first admin/support diagnostics contract that S04 reuses when pairing support runtime summaries with drill evidence.
  - slice: S03
    provides: The process-local SessionManager vs shared Redis SessionStateService runtime split that S04 reuses for redis/websocket recovery interpretation.
affects:
  []
key_files:
  - scripts/recovery_drill_baseline.py
  - scripts/recovery_drill_runner.py
  - scripts/recovery-drill-baseline.py
  - scripts/recovery-drill-runner.py
  - backend/scripts/bootstrap_auth_admin.py
  - docs/backup-recovery-runbook.md
  - docs/setup/backup-recovery-current-state.md
  - docs/api-contract/support-runtime.md
  - .sisyphus/deploy/ai-backend.service
  - .sisyphus/deploy/ai-frontend.service
  - .sisyphus/deploy/ai-practice.nginx.conf
  - .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/PROJECT.md
key_decisions:
  - D227 — represent recovery drill authority as a non-destructive repo-local inventory first, then make later automation consume that same metadata.
  - D228 — keep the baseline script as the single source of drill command/precondition/failure-signal metadata and have the runner emit per-drill logs plus summary.json evidence.
  - D229 — treat the shipped systemd+nginx bundle as single-node authority only, and require release/recovery proof to pair node-local /health captures with repo-local drill summary/log evidence.
patterns_established:
  - Recovery automation should reuse one code-owned metadata seam (`scripts/recovery_drill_baseline.py`) across scripts, docs, and tests.
  - Release/recovery sign-off must pair node-local deploy health with repo-local drill evidence instead of trusting `/health` alone.
  - Manual-only boundaries (`redis_service_restore`, `oss_bucket_export`, `multi_instance_drain`) must stay explicit until real automation lands.
  - Failure signals such as migration drift belong in the proof artifact, not behind optimistic summary prose.
observability_surfaces:
  - `.dev/recovery-drills/<timestamp>/summary.json` and per-drill `*.log` files
  - `/api/v1/support/runtime/overview` and `/api/v1/support/runtime/faults` as release-health / fault-summary surfaces
  - `/health` as per-node native deploy proof only
drill_down_paths:
  - .gsd/milestones/M020/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M020/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M020/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T01:08:28.096Z
blocker_discovered: false
---

# S04: Recovery drill automation 与部署指导收口

**Promoted the M018 manual recovery baseline into one repo-local drill bundle plus aligned deploy/support docs, with fresh evidence showing auth/redis/OSS/health recovery checks pass from a shared authority surface while db_migration now fails loudly and traceably instead of hiding behind healthy node status.**

## What Happened

## Delivered
- Added one repo-local recovery authority seam instead of keeping recovery guidance split across markdown:
  - `scripts/recovery_drill_baseline.py` is now the single inventory for drill ids, checked commands, preconditions, authority paths, and failure signals.
  - `scripts/recovery_drill_runner.py` executes that same metadata directly and writes `summary.json` plus per-drill `*.log` evidence under `.dev/recovery-drills/<timestamp>/`.
  - `scripts/recovery-drill-baseline.py` and `scripts/recovery-drill-runner.py` exist only as CLI entrypoints so operators and grep-based verification hit the same underlying authority module.
- Upgraded the recovery baseline from “manual runbook only” to “minimal executable drill bundle” across the long-lived ops surfaces:
  - `docs/backup-recovery-runbook.md`
  - `docs/setup/backup-recovery-current-state.md`
  - `docs/api-contract/support-runtime.md`
  - `.sisyphus/deploy/*`
  - `.sisyphus/plans/cloud-full-redeploy-115-191-36-90.md`
  - `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- Wrote the deploy boundary back into the authority files themselves: the shipped systemd + nginx bundle is single-node only, `/health` is per-node proof only, and future multi-instance drain/stickiness/failover remains external-orchestrator territory.

## What this slice actually proved
- The repo now has a truthful executable recovery inventory for the hardened seams from S01-S03: `db_migration`, `auth_bootstrap`, `redis_session_state`, `websocket_reconnect`, `oss_signing_playback`, and `health_check`.
- The runner can execute a real drill set and produce machine-readable evidence instead of only prose. Fresh close-out evidence is at `.dev/recovery-drills/20260414T010316Z/summary.json`.
- On that fresh run, `auth_bootstrap`, `redis_session_state`, `oss_signing_playback`, and `health_check` all passed and wrote logs. `db_migration` failed with `KeyError: '20260412_0315_028'`, which is now preserved as an explicit failure signal in `summary.json` and `01-db_migration.log` instead of being masked by otherwise healthy service status.
- Manual-only boundaries are now explicit and shared across scripts/docs instead of being implied: `redis_service_restore`, `oss_bucket_export`, and `multi_instance_drain` are still outside repo-native automation.

## Patterns established for downstream slices
1. **One metadata source, many consumers** — future drill automation, runbooks, tests, and deploy docs must reuse `scripts/recovery_drill_baseline.py` instead of inventing parallel command lists.
2. **Health is necessary but not sufficient** — release/recovery proof now requires node-local `/health`, support runtime release-health/fault summaries, and the latest drill `summary.json` + per-drill logs together.
3. **Single-node truth before multi-instance ambition** — `.sisyphus/deploy/*` comments, the cloud redeploy plan, and the runbook now all say the same thing: the shipped bundle is node-local today and does not imply cluster drain authority.
4. **Failure signals are first-class evidence** — a failing drill is still a successful proof artifact if it records the blocker truthfully and keeps the recovery surface from pretending everything is green.

## Operational Readiness (Q8)
- **Health signal:** `curl -fsS http://127.0.0.1:3444/health` returns `{"status":"healthy",...}` for node-local proof; `/api/v1/support/runtime/*` remains the release-health / fault-summary surface; `.dev/recovery-drills/<timestamp>/summary.json` is the recovery-drill outcome surface.
- **Failure signal:** non-zero drill exits plus `summary.json.steps[*].failure_signal`, especially the currently reproducible `db_migration -> KeyError: '20260412_0315_028'` signal, are the authoritative recovery blockers.
- **Recovery procedure:** run `python3 scripts/recovery-drill-baseline.py check`, then `python3 scripts/recovery-drill-runner.py run --continue-on-failure ...`, inspect `summary.json` + per-drill logs, remediate blockers (for example Alembic revision drift), rerun the same drills, and only then pair the drill bundle with deploy `/health` captures for release/recovery sign-off.
- **Monitoring gaps:** the repo still lacks repo-native Redis restore automation, OSS bucket export/backup tooling, and cluster drain orchestration; `/api/v1/support/runtime` is intentionally not a cluster-state API and cannot fill those gaps by itself.

## Verification

Fresh slice-close verification reran the assembled S04 proof stack from repo root.

1. `python3 scripts/recovery-drill-baseline.py check` — passed and confirmed all referenced authority paths exist.
2. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_bootstrap_auth_admin.py backend/tests/unit/test_recovery_drill_baseline.py backend/tests/unit/test_recovery_drill_runner.py -q` — passed (7/7).
3. `RECOVERY_ADMIN_EMAIL=admin@qoder.ai RECOVERY_ADMIN_NAME=管理员 python3 scripts/recovery-drill-runner.py run --continue-on-failure --drill db_migration --drill auth_bootstrap --drill redis_session_state --drill oss_signing_playback --drill health_check` — executed a real drill bundle and wrote fresh evidence to `.dev/recovery-drills/20260414T010316Z/summary.json`; `auth_bootstrap`, `redis_session_state`, `oss_signing_playback`, and `health_check` passed, while `db_migration` failed truthfully with `KeyError: '20260412_0315_028'`.
4. `rg -n "backup|restore|recovery|drill|auth|redis|oss|websocket" scripts docs/backup-recovery-runbook.md docs/setup/backup-recovery-current-state.md` — passed.
5. `bash scripts/dependency-governance.sh status && rg -n "health|alembic|bootstrap|redis|oss|recovery" scripts/recovery-* docs/backup-recovery-runbook.md` — passed.
6. `rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — passed.
7. `rg -n "release-health|recovery drill|summary.json|process-local|redis snapshot|healthy" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md` — passed.
8. LSP diagnostics on `scripts/recovery_drill_baseline.py`, `scripts/recovery_drill_runner.py`, `backend/scripts/bootstrap_auth_admin.py`, `backend/tests/unit/test_recovery_drill_runner.py`, and `backend/tests/unit/test_bootstrap_auth_admin.py` all returned no diagnostics.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None. Slice close-out reran the planned verification stack and produced a newer evidence bundle at `.dev/recovery-drills/20260414T010316Z/`; the slice still keeps the manual-only boundaries explicit instead of pretending they became automated.

## Known Limitations

The current local `db_migration` drill still fails with `KeyError: '20260412_0315_028'`, so the recovery bundle proves the blocker truthfully but does not repair the underlying Alembic revision/database state. Repo-native Redis service restore, OSS bucket export/backup, and multi-instance drain orchestration are still not shipped and remain manual-only boundaries.

## Follow-ups

1. Repair the missing Alembic revision / migration graph state behind `20260412_0315_028`, then rerun the same drill bundle until `db_migration` passes.
2. If future work introduces multi-instance rollout, keep S04's per-node drill evidence and move drain/stickiness/failover orchestration into external LB/ingress controls rather than extending `/api/v1/support/runtime` into a fake cluster-control surface.
3. If repo-native Redis restore or OSS export tooling is later added, add it through `scripts/recovery_drill_baseline.py` first so the runner/docs/tests stay on one authority line.

## Files Created/Modified

- `scripts/recovery_drill_baseline.py` — Defines the canonical drill ids, commands, preconditions, failure signals, authority paths, and manual-only boundaries.
- `scripts/recovery_drill_runner.py` — Executes the baseline metadata directly and writes machine-readable drill evidence under `.dev/recovery-drills/<timestamp>/`.
- `backend/scripts/bootstrap_auth_admin.py` — Imports the missing model registration path so auth bootstrap drills can use AsyncSessionLocal without late mapper failures.
- `docs/backup-recovery-runbook.md` — Now points to the executable drill bundle, records the single-node deploy boundary, and pairs health evidence with drill summary/log evidence.
- `docs/setup/backup-recovery-current-state.md` — Documents the current recovery surfaces, drill entrypoints, and explicit manual-only boundaries.
- `docs/api-contract/support-runtime.md` — Pins `/api/v1/support/runtime` as a release-health / fault-summary surface that must be read together with drill evidence.
- `.sisyphus/deploy/ai-backend.service` — Documents the backend systemd unit as single-node only and requires drill evidence alongside `/health`.
- `.sisyphus/deploy/ai-frontend.service` — Documents the frontend systemd unit as node-local only rather than implying multi-instance orchestration.
- `.sisyphus/deploy/ai-practice.nginx.conf` — Documents `/health` and websocket proxying as per-node proof, not cluster-wide truth.
- `.sisyphus/plans/cloud-full-redeploy-115-191-36-90.md` — Requires the release/recovery evidence package to pair deploy health captures with the latest recovery drill bundle.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Records the downstream reuse rule for S04's drill bundle and deploy boundary.
- `.gsd/PROJECT.md` — Refreshes current project state to reflect all four M020 slices being implemented and S04 close-out evidence now existing.
