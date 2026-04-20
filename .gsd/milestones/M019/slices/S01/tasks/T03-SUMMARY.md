---
id: T03
parent: S01
milestone: M019
key_files:
  - docs/backup-recovery-runbook.md
  - docs/setup/backup-recovery-current-state.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .github/workflows/nfr-performance-check.yml
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-13T03:10:02.761Z
blocker_discovered: false
---

# T03: Wrote the narrowed startup/migration/bootstrap authority line back into the runbook, setup baseline, architecture scan, and CI migration entrypoint.

**Wrote the narrowed startup/migration/bootstrap authority line back into the runbook, setup baseline, architecture scan, and CI migration entrypoint.**

## What Happened

I updated the long-lived operational and planning surfaces to match the post-T02 database authority split instead of leaving later work to infer it from code. In `docs/backup-recovery-runbook.md`, I added an explicit authority-line section that distinguishes Alembic migration authority, explicit legacy repair authority, auth bootstrap, and startup-only `init_db()` behavior; I also tightened the restore and verification steps so non-development startup drift now routes back to `alembic upgrade head` or `python scripts/repair_legacy_schema.py`, and I added reusable repo-root verification commands for later M019 slices. In `docs/setup/backup-recovery-current-state.md`, I rewrote the startup/repair facts so `init_db()` is documented as development/test bootstrap only, while `repair_legacy_schema.py` plus Alembic own explicit non-startup schema repair. In `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, I refreshed the M019/S01 authority inventory to reflect the T02 code reality: non-development startup no longer silently patches legacy personas/knowledge drift, the repair script now covers both repair surfaces, and the focused proof files are the repo-root authority check. Finally, I confirmed `.github/workflows/nfr-performance-check.yml` already aligns with the intended authority line and made that explicit by labeling the migration step as Alembic-owned rather than startup-owned; the workflow logic itself did not need structural changes.

## Verification

I reran the exact task-plan grep gate `rg -n "alembic upgrade head|bootstrap|init_db|migration" docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .github/workflows`, which passed and showed the updated authority wording across the runbook, architecture scan, and CI workflow. I also reran the focused proof `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_startup_or_bootstrap_authority.py backend/tests/unit/common/test_db_session_compatibility.py -q`, which finished 4/4 green and confirmed the documented startup/bootstrap authority still matches live behavior. The pytest run continued to emit the pre-existing pytest-cov no-data warnings and a SQLite teardown `ResourceWarning`, but there were no test failures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "alembic upgrade head|bootstrap|init_db|migration" docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .github/workflows` | 0 | ✅ pass | 23ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_startup_or_bootstrap_authority.py backend/tests/unit/common/test_db_session_compatibility.py -q` | 0 | ✅ pass | 1773ms |

## Deviations

The plan named runbook / architecture scan / workflow verification explicitly; I also updated `docs/setup/backup-recovery-current-state.md` because it still described pre-T02 startup repair behavior and would otherwise contradict the new authority line.

## Known Issues

Focused pytest still emits the pre-existing pytest-cov 'module src was never imported / no data was collected' warnings plus a SQLite teardown `ResourceWarning`; this task did not change that harness noise.

## Files Created/Modified

- `docs/backup-recovery-runbook.md`
- `docs/setup/backup-recovery-current-state.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.github/workflows/nfr-performance-check.yml`
