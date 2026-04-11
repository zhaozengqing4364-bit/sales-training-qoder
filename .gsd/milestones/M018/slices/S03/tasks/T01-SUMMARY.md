---
id: T01
parent: S03
milestone: M018
key_files:
  - docs/setup/backup-recovery-current-state.md
  - scripts/README.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Recorded the current backup/recovery baseline as a factual inventory document linked from the existing scripts index, instead of inventing unshipped backup automation or idealized ops flows.
duration: 
verification_result: passed
completed_at: 2026-04-11T23:57:55.617Z
blocker_discovered: false
---

# T01: Added a code-adjacent backup/recovery current-state baseline that maps the repo’s real startup, schema, storage, and missing-backup facts for the upcoming runbook.

**Added a code-adjacent backup/recovery current-state baseline that maps the repo’s real startup, schema, storage, and missing-backup facts for the upcoming runbook.**

## What Happened

I audited the repository’s real operational entrypoints and wrote `docs/setup/backup-recovery-current-state.md` as the authoritative current-state inventory for this slice. The new baseline records the actual local startup path (`scripts/dev-up.sh` / `scripts/dev-stop.sh`), the runtime database/session entrypoints (`backend/src/main.py`, `backend/src/common/db/session.py`), the Alembic migration surface, the one-time legacy schema repair script, the destructive reset script, the local admin bootstrap command, and the currently visible persistence surfaces across PostgreSQL, Redis session-state snapshots, local knowledge documents, local Chroma data, legacy PPT upload paths, and OSS-backed audio objects. I also linked that baseline from `scripts/README.md` so future agents can find it from the existing script index. During execution I documented one non-obvious but operationally important gotcha in `.gsd/KNOWLEDGE.md`: runtime config, shared config, and dev-up do not agree on a single implicit `DATABASE_URL` default, so any future restore/runbook work must record the actual environment value explicitly instead of assuming one universal default. I did not invent any backup automation; the document explicitly records the missing `pg_dump`/restore/Redis/archive/OSS backup gaps as current-state facts for T02.

## Verification

Fresh verification was run after writing the baseline. `find docs scripts -maxdepth 2 -type f | sort | head -n 20` succeeded from repo root, confirming the repository-level docs/scripts inventory command in the task plan still runs cleanly. A focused grep proof, `rg -n "DATABASE_URL|alembic upgrade head|repair_legacy_schema|bootstrap_auth_admin|pg_dump|OSS" docs/setup/backup-recovery-current-state.md scripts/README.md`, also succeeded and showed the new baseline contains the real recovery-side commands, the DATABASE_URL drift warning, the storage/OSS facts, and the explicit absence of repo-native backup automation.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `find docs scripts -maxdepth 2 -type f | sort | head -n 20` | 0 | ✅ pass | 6ms |
| 2 | `rg -n "DATABASE_URL|alembic upgrade head|repair_legacy_schema|bootstrap_auth_admin|pg_dump|OSS" docs/setup/backup-recovery-current-state.md scripts/README.md` | 0 | ✅ pass | 17ms |

## Deviations

None.

## Known Issues

The repository still has no repo-native backup or restore automation for PostgreSQL, Redis, local document/Chroma directories, legacy upload paths, or OSS audio objects; T01 only inventories these gaps and their real evidence paths.

## Files Created/Modified

- `docs/setup/backup-recovery-current-state.md`
- `scripts/README.md`
- `.gsd/KNOWLEDGE.md`
