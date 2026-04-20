---
id: T02
parent: S03
milestone: M018
key_files:
  - docs/backup-recovery-runbook.md
  - .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Separated the executable manual backup/recovery baseline from future drill/improvement guidance so the runbook only describes capabilities that are actually present in the repository today.
  - Documented owners as role-based placeholders and evidence paths rather than inventing named operators, because the repository still lacks an explicit on-call/owner roster.
duration: 
verification_result: passed
completed_at: 2026-04-12T00:05:19.118Z
blocker_discovered: false
---

# T02: Added a truthful manual backup/recovery runbook and analysis baseline that capture today’s backup cadence, restore order, verification steps, and explicit gaps.

**Added a truthful manual backup/recovery runbook and analysis baseline that capture today’s backup cadence, restore order, verification steps, and explicit gaps.**

## What Happened

I turned the current-state backup/recovery audit into two durable artifacts: `docs/backup-recovery-runbook.md` as the human-executable baseline runbook, and `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md` as the short analysis pointer that tells future agents where to start. The runbook stays strictly on today’s shipped surface: it uses the real repo entrypoints (`scripts/dev-up.sh`, `scripts/dev-stop.sh`, Alembic, `repair_legacy_schema.py`, `bootstrap_auth_admin.py`), records manual backup cadence for PostgreSQL / Redis / local directories, preserves the current OSS bulk-backup gap as an explicit uncovered risk, and separates quarterly drill guidance plus future improvements from the executable baseline so the document does not pretend unshipped automation exists. Because the repo still has no named on-call roster, I documented owner/evidence handling with truthful role placeholders rather than inventing people or SRE processes. I also appended two non-obvious recovery gotchas to `.gsd/KNOWLEDGE.md`: `pg_dump` / `pg_restore` must convert the app’s `postgresql+asyncpg://...` URL into `postgresql://...`, and Chroma persistence currently drifts between `CHROMA_PERSIST_DIRECTORY=./data/chroma` and `CHROMADB_PERSIST_DIR=./data/chromadb`, so future recovery work must verify the live path instead of trusting one default.

## Verification

Fresh verification was run on the final written version of the artifacts. `test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md` passed, proving the planned output files exist. A focused grep proof, `rg -n '当前最小备份频率|pg_dump|pg_restore|redis-cli|alembic upgrade head|bootstrap_auth_admin|/health|季度演练建议|未来改进' docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md`, passed and showed the runbook now contains the backup cadence, restore order, verification path, quarterly drill guidance, and explicit future-gap split. A second grep proof, `rg -n 'postgresql\+asyncpg|CHROMADB_PERSIST_DIR|CHROMA_PERSIST_DIRECTORY' docs/backup-recovery-runbook.md .gsd/KNOWLEDGE.md`, passed and confirmed the final artifact set records the asyncpg/libpq and Chroma-path drift gotchas that can derail later restore work.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md` | 0 | ✅ pass | 5ms |
| 2 | `rg -n '当前最小备份频率|pg_dump|pg_restore|redis-cli|alembic upgrade head|bootstrap_auth_admin|/health|季度演练建议|未来改进' docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md` | 0 | ✅ pass | 17ms |
| 3 | `rg -n 'postgresql\+asyncpg|CHROMADB_PERSIST_DIR|CHROMA_PERSIST_DIRECTORY' docs/backup-recovery-runbook.md .gsd/KNOWLEDGE.md` | 0 | ✅ pass | 8ms |

## Deviations

None.

## Known Issues

The repository still does not ship repo-native PostgreSQL scheduling, Redis restore automation, OSS bulk-export tooling, a single authoritative Chroma persistence path, or named RTO/RPO/on-call ownership; the new runbook records these as explicit gaps instead of pretending they are implemented.

## Files Created/Modified

- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`
- `.gsd/KNOWLEDGE.md`
