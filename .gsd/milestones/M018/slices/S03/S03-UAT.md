# S03: 备份 / 故障恢复 / 容灾 runbook 基线 — UAT

**Milestone:** M018
**Written:** 2026-04-12T00:13:54.611Z

# S03 UAT — Backup / Recovery baseline runbook

## Preconditions
- Repository is checked out at the current branch root.
- Shell has `find`, `grep`, and standard POSIX test utilities available.
- Tester can read repository docs but does **not** need a running app stack for this UAT; this slice ships documentation and verified command paths, not new runtime automation.

## Test Case 1 — Runbook artifacts are present in the repository
1. From repo root, run: `find docs scripts -maxdepth 2 -type f | sort | head -n 20`
2. Confirm the output includes `docs/backup-recovery-runbook.md`.
3. Run: `test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md`

**Expected outcome**
- The inventory command exits 0.
- `docs/backup-recovery-runbook.md` is visible in the repository inventory.
- The file-presence gate exits 0, proving the shipped runbook/baseline artifacts exist.

## Test Case 2 — Executable backup/recovery content is discoverable by grep proof
1. Run: `grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md`
2. Review the matched lines.

**Expected outcome**
- Command exits 0.
- Matches show explicit sections for backup frequency, recovery order, post-recovery verification, and drill/follow-up guidance.
- The docs are discoverable by future agents using the exact proof gate defined in the slice plan.

## Test Case 3 — Runbook only documents today’s real recovery path
1. Open `docs/backup-recovery-runbook.md`.
2. Verify Section 2 requires recording real environment values for `DATABASE_URL`, `REDIS_URL`, `SESSION_STATE_REDIS_URL`, document/vector/upload paths, and OSS config.
3. Verify Section 4 includes manual backup steps for PostgreSQL (`pg_dump`/`pg_restore` URL conversion), optional Redis RDB, and local file archives.
4. Verify Section 5 defines the current recovery order: stop services → restore PostgreSQL → align Alembic / repair legacy schema if needed → restore local files → optionally recover Redis → rebuild admin/support users if needed → restart services.
5. Verify Section 6 uses `/health` plus `alembic upgrade head` and admin bootstrap as the post-recovery validation seam.

**Expected outcome**
- The runbook reflects only the repository’s current shipped surfaces (`scripts/dev-up.sh`, `scripts/dev-stop.sh`, Alembic, `repair_legacy_schema.py`, `bootstrap_auth_admin.py`, `/health`).
- No fictional platform, scheduler, or orchestration layer is required to follow the baseline.

## Test Case 4 — Explicit gaps remain gaps instead of being disguised as shipped capability
1. In `docs/backup-recovery-runbook.md`, inspect Sections 7 and 8.
2. Confirm the doc explicitly states that the repository does **not** currently ship:
   - automated PostgreSQL backup scheduling,
   - Redis restore automation,
   - OSS bulk export tooling,
   - fixed RTO/RPO documentation,
   - named on-call roster.
3. Confirm disaster-recovery drill suggestions and future improvements are grouped under `Follow-up（非当前可执行基线）`.

**Expected outcome**
- Current gaps are called out as absent capabilities, not implied features.
- Advice and future work are clearly separated from executable baseline steps.

## Test Case 5 — Authority seams are explicit enough for future maintainers
1. Review the intro of `docs/backup-recovery-runbook.md` and the `本次已复核的 repo-local 引用` section in `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`.
2. Confirm both documents name concrete repository seams such as `scripts/dev-up.sh`, `scripts/dev-stop.sh`, `backend/src/main.py`, `backend/scripts/repair_legacy_schema.py`, `backend/scripts/bootstrap_auth_admin.py`, and `docs/setup/auth-local.md`.
3. Open `docs/setup/backup-recovery-current-state.md` and confirm it remains the detailed factual inventory backing the runbook.

**Expected outcome**
- Future operators/agents can start from the runbook and immediately know which repo files anchor each operational claim.
- The analysis pointer and current-state inventory agree on the same authority seams.

## Edge Cases

### Edge Case A — Ownership is truthful when no roster exists
1. In `docs/backup-recovery-runbook.md`, inspect Section 1 (`当前责任边界与证据位置`).
2. Confirm the doc uses role-based placeholders (`执行人`, `审批人`) and evidence locations, rather than inventing specific people.

**Expected outcome**
- The runbook stays truthful to the current repository/deployment reality even though no named on-call rota is stored in the repo.

### Edge Case B — Environment drift is surfaced before recovery starts
1. In `docs/backup-recovery-runbook.md`, inspect Section 2.2.
2. Confirm it explicitly documents the drift between `scripts/dev-up.sh`, `backend/src/common/db/session.py`, `backend/src/common/config.py`, `backend/src/common/storage/document.py`, and `backend/src/common/knowledge/vector_store.py`.

**Expected outcome**
- The runbook forces the operator to record live environment values first, preventing restore work from assuming one universal default database or Chroma path.

