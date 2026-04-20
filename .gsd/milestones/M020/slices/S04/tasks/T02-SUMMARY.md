---
id: T02
parent: S04
milestone: M020
key_files:
  - scripts/recovery_drill_baseline.py
  - scripts/recovery_drill_runner.py
  - scripts/recovery-drill-baseline.py
  - scripts/recovery-drill-runner.py
  - backend/scripts/bootstrap_auth_admin.py
  - backend/tests/unit/test_recovery_drill_runner.py
  - backend/tests/unit/test_bootstrap_auth_admin.py
  - docs/backup-recovery-runbook.md
  - docs/setup/backup-recovery-current-state.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D228 — keep the baseline script as the single source of drill command/precondition/failure-signal metadata and have the runner execute it directly while writing per-drill logs plus summary.json evidence.
  - Recovery entrypoint scripts that use AsyncSessionLocal outside the main app bootstrap must import agent.models first so SQLAlchemy can resolve PracticeSession -> Agent/Persona relationships during real drills.
duration: 
verification_result: mixed
completed_at: 2026-04-14T00:30:19.729Z
blocker_discovered: false
---

# T02: Added a baseline-driven recovery drill runner that executes auth/runtime/OSS/health checks with logged evidence and exposes the current Alembic migration blocker.

**Added a baseline-driven recovery drill runner that executes auth/runtime/OSS/health checks with logged evidence and exposes the current Alembic migration blocker.**

## What Happened

I turned the T01 recovery inventory into a minimal executable automation surface instead of leaving it as markdown plus unchecked command strings. `scripts/recovery_drill_baseline.py` now carries the baseline drill command templates, explicit env preconditions, and failure-signal hints; `scripts/recovery_drill_runner.py` consumes that same metadata directly, renders the selected drills, executes them, and writes per-drill logs plus `summary.json` under `.dev/recovery-drills/<timestamp>/`. I also added thin hyphenated CLI entrypoints (`scripts/recovery-drill-baseline.py`, `scripts/recovery-drill-runner.py`) so the task-plan grep contract can target `scripts/recovery-*` without creating a second authority surface.

To make the recovery path real, I fixed the existing auth bootstrap entrypoint instead of faking success in the runner. `backend/scripts/bootstrap_auth_admin.py` now imports `agent.models` before using `AsyncSessionLocal`, which avoids the late SQLAlchemy mapper failure on `PracticeSession -> Agent/Persona` relationships during a real recovery drill. Focused proof now locks both the baseline/runner behavior and that mapper-registration recovery gotcha. The runbook and current-state docs were updated to point at the new baseline + runner seam, document the evidence root, and keep auth bootstrap preconditions explicit rather than hardcoding secrets into the script layer.

## Verification

Focused unit proof finished green with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_bootstrap_auth_admin.py backend/tests/unit/test_recovery_drill_baseline.py backend/tests/unit/test_recovery_drill_runner.py -q` (7/7). A real drill run with `RECOVERY_ADMIN_EMAIL=admin@qoder.ai RECOVERY_ADMIN_NAME=管理员 python3 scripts/recovery-drill-runner.py run --continue-on-failure --drill db_migration --drill auth_bootstrap --drill redis_session_state --drill oss_signing_playback --drill health_check` wrote evidence to `.dev/recovery-drills/20260414T002842Z/summary.json`; `auth_bootstrap`, `redis_session_state`, `oss_signing_playback`, and `health_check` passed with captured per-drill logs, while `db_migration` truthfully failed on the current local environment with `KeyError: '20260412_0315_028'`, which is now an explicit recovery signal rather than a silent script crash. The task-plan verification gate `bash scripts/dependency-governance.sh status && rg -n "health|alembic|bootstrap|redis|oss|recovery" scripts/recovery-* docs/backup-recovery-runbook.md` passed, and LSP diagnostics were clean on `scripts/recovery_drill_baseline.py`, `scripts/recovery_drill_runner.py`, `backend/scripts/bootstrap_auth_admin.py`, `backend/tests/unit/test_recovery_drill_runner.py`, and `backend/tests/unit/test_bootstrap_auth_admin.py`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_bootstrap_auth_admin.py backend/tests/unit/test_recovery_drill_baseline.py backend/tests/unit/test_recovery_drill_runner.py -q` | 0 | ✅ pass | 1662ms |
| 2 | `RECOVERY_ADMIN_EMAIL=admin@qoder.ai RECOVERY_ADMIN_NAME=管理员 python3 scripts/recovery-drill-runner.py run --continue-on-failure --drill db_migration --drill auth_bootstrap --drill redis_session_state --drill oss_signing_playback --drill health_check` | 1 | ❌ fail | 9524ms |
| 3 | `bash scripts/dependency-governance.sh status && rg -n "health|alembic|bootstrap|redis|oss|recovery" scripts/recovery-* docs/backup-recovery-runbook.md` | 0 | ✅ pass | 100ms |

## Deviations

Adjusted the baseline command forms to match the repo’s real executable paths after live drill runs exposed shell/cwd mismatches: auth bootstrap now uses `backend/venv/bin/python backend/scripts/bootstrap_auth_admin.py ...`, and db migration now uses `cd backend && venv/bin/python -m alembic upgrade head`. I also added hyphenated CLI entrypoints so the slice verification pattern `scripts/recovery-*` can discover the shipped scripts without moving the underscore-based authority modules established by T01.

## Known Issues

The current local PostgreSQL/Alembic state is still inconsistent: the real `db_migration` drill fails with `KeyError: '20260412_0315_028'` when upgrading the repo’s configured `backend/.env` database. The new runner records that failure in `.dev/recovery-drills/<timestamp>/01-db_migration.log` and `summary.json`, but this task did not repair the underlying migration graph/database state.

## Files Created/Modified

- `scripts/recovery_drill_baseline.py`
- `scripts/recovery_drill_runner.py`
- `scripts/recovery-drill-baseline.py`
- `scripts/recovery-drill-runner.py`
- `backend/scripts/bootstrap_auth_admin.py`
- `backend/tests/unit/test_recovery_drill_runner.py`
- `backend/tests/unit/test_bootstrap_auth_admin.py`
- `docs/backup-recovery-runbook.md`
- `docs/setup/backup-recovery-current-state.md`
- `.gsd/KNOWLEDGE.md`
