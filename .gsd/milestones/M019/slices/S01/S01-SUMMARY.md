---
id: S01
parent: M019
milestone: M019
provides:
  - A stable database authority map for S02-S04 so they do not have to infer who owns schema evolution versus bootstrap.
  - Explicit repo-root verification commands for startup/migration/bootstrap failure localization.
  - One shared legacy schema repair seam (`common.db.legacy_schema_repair`) reusable by later authority and release-gate work.
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - backend/src/common/db/session.py
  - backend/src/common/db/legacy_schema_repair.py
  - backend/src/main.py
  - backend/scripts/repair_legacy_schema.py
  - backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py
  - backend/tests/integration/test_startup_or_bootstrap_authority.py
  - backend/tests/unit/common/test_db_session_compatibility.py
  - docs/backup-recovery-runbook.md
  - docs/setup/backup-recovery-current-state.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .github/workflows/nfr-performance-check.yml
key_decisions:
  - D210 — Keep Alembic as the schema evolution authority; keep init_db limited to startup bootstrap plus explicit compatibility guards; keep repair/bootstrap as one-off scripts.
  - D211 — Restrict startup compatibility repairs to development/test bootstrap, and route production-like legacy persona/knowledge schema drift through explicit Alembic revision 20260413_1040_029 or scripts/repair_legacy_schema.py.
patterns_established:
  - Authority maps should live in code-adjacent constants plus focused proof, not only in markdown.
  - Production-like startup should fail fast on schema drift and point to explicit migration/repair entrypoints.
  - Shared repair helpers should back startup compatibility, explicit scripts, and Alembic revisions to avoid divergent fixes.
  - Repo-root verification commands should be recorded in runbooks and reused by later slices.
observability_surfaces:
  - Structured startup logs for `Running startup database bootstrap` and `Database authority map resolved for startup`.
  - Explicit `RuntimeError` failure signals for non-development legacy personas/knowledge schema drift.
  - Runbook and CI migration wording that now surface Alembic as the schema authority rather than implicit startup repair.
drill_down_paths:
  - .gsd/milestones/M019/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M019/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M019/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-13T03:15:29.446Z
blocker_discovered: false
---

# S01: 启动期 schema authority 收口

**S01 made Alembic, explicit legacy repair, auth bootstrap, and startup bootstrap distinct database authority seams, with production startup now failing fast on legacy schema drift instead of silently repairing it.**

## What Happened

## What this slice delivered

S01 closed the startup-era schema ambiguity that had let `init_db()` behave like an implicit migration tool. The slice first inventoried the live authority surfaces across `backend/src/common/db/session.py`, `backend/src/main.py`, Alembic revisions, `scripts/dev-up.sh`, `backend/scripts/repair_legacy_schema.py`, and `backend/scripts/bootstrap_auth_admin.py`, then wrote that map into code, analysis, and operational docs so later M019 slices no longer have to guess which entrypoint owns which responsibility.

The shipped authority line is now explicit and executable:
- **Alembic** (`cd backend && alembic upgrade head`) is the forward schema-evolution authority.
- **`backend/scripts/repair_legacy_schema.py`** is the one-off legacy schema repair seam for historical `personas.persona_policy` / `knowledge_documents` drift.
- **`backend/scripts/bootstrap_auth_admin.py`** is auth/bootstrap only and does not own schema evolution.
- **`common.db.session.init_db()`** remains startup bootstrap only: it still runs `Base.metadata.create_all()`, but its compatibility guards are limited to `development` / `test` / `testing`.

The core behavior change is that non-development startup no longer silently patches legacy persona/knowledge schema drift. `backend/src/common/db/session.py` now inspects the live schema and raises an explicit `RuntimeError` pointing operators at Alembic or `python scripts/repair_legacy_schema.py` when production-like startup sees legacy drift. To keep repair logic from splitting again, the slice introduced `backend/src/common/db/legacy_schema_repair.py` as the shared repair seam used by startup compatibility guards, the explicit repair script, and new Alembic revision `20260413_1040_029_explicit_legacy_startup_repairs.py`.

S01 also wrote the result back into the long-lived operator and planning surfaces. `docs/backup-recovery-runbook.md`, `docs/setup/backup-recovery-current-state.md`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, and `.github/workflows/nfr-performance-check.yml` now all point at the same authority line instead of implying startup can carry schema evolution. That gives S02-S04 a stable base: backend application seams, frontend transport seams, and release gates can now assume database evolution has a named owner and explicit failure path.

## Patterns established

1. **Authority map in code, not just markdown** — `STARTUP_DB_AUTHORITY` in `backend/src/common/db/session.py` is the code-adjacent source of truth for startup/bootstrap/migration/repair/bootstrap entrypoints.
2. **Fail-fast over silent repair in production-like startup** — non-development startup must surface actionable migration/repair instructions instead of mutating schema during service boot.
3. **One repair seam reused everywhere** — `common.db.legacy_schema_repair` is shared by startup compatibility guards, the explicit repair script, and Alembic revision `029`, preventing drift between “temporary” repair paths.
4. **Repo-root focused verification** — later slices can reuse the same repo-root proof line instead of reconstructing environment-specific commands.

## Operational readiness (Q8)

- **Health signal:** startup logs now emit a structured database authority map (`Running startup database bootstrap`, `Database authority map resolved for startup`) and CI explicitly labels its DB step as `Run database migrations (schema authority: Alembic)`.
- **Failure signal:** in non-development environments, legacy `personas.persona_policy` or `knowledge_documents` drift now raises explicit startup `RuntimeError`s instructing operators to run Alembic revisions or `python scripts/repair_legacy_schema.py` instead of silently repairing schema.
- **Recovery procedure:** restore/update DB → run `cd backend && alembic upgrade head` → if startup still reports legacy drift, run `cd backend && python scripts/repair_legacy_schema.py --database-url <DATABASE_URL>` → run `python scripts/bootstrap_auth_admin.py ...` only if auth bootstrap is needed → restart service.
- **Monitoring gaps:** `scripts/dev-up.sh` still does not run Alembic automatically, `init_db()` still performs `Base.metadata.create_all()` plus dev/test compatibility guards, and the current proof stack still emits known pytest-cov/no-data and SQLite teardown warnings that are observable but not yet cleaned up.

## What downstream slices should know

- S02 can now pull lifecycle/report/runtime orchestration out of `practice.py` without also guessing whether startup owns schema repair.
- S03 can assume the frontend should never treat successful startup as proof that migrations already ran.
- S04 can build release truth lines around explicit migration/repair/bootstrap commands already named in code, docs, and CI.
- The remaining narrowing work is deliberately small and explicit: if M019 later wants to shrink `create_all()` or dev/test startup compatibility further, it should do so from this authority map instead of rediscovering the same startup drift.


## Verification

Fresh slice-close verification reran every slice-plan gate and all passed.

1. `rg -n "create_all|alembic|bootstrap|repair_legacy_schema|init_db" backend/src/common/db/session.py backend/src/main.py backend/alembic/versions scripts` — passed and showed the explicit authority map across startup code, scripts, and the new Alembic revision.
2. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration -k "startup or bootstrap or migration" -x -q` — passed (2 selected / 2 passed), proving production-like startup now fails loudly on legacy drift and the explicit repair seam remains green. Existing pytest-cov no-data warnings and a known SQLite teardown warning remained non-blocking harness noise.
3. `rg -n "alembic upgrade head|bootstrap|init_db|migration" docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .github/workflows` — passed and confirmed docs, analysis, and CI align to the same Alembic/repair/bootstrap authority line.
4. Fresh LSP diagnostics on `backend/src/common/db/session.py`, `backend/src/main.py`, `backend/src/common/db/legacy_schema_repair.py`, `backend/scripts/repair_legacy_schema.py`, `backend/tests/integration/test_startup_or_bootstrap_authority.py`, and `backend/tests/unit/common/test_db_session_compatibility.py` all returned `No diagnostics`.

This proves the slice goal at integration level: startup / migration / bootstrap failure is now localized to explicit authority entrypoints instead of being masked by implicit runtime schema repair.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

`init_db()` 仍执行 `Base.metadata.create_all()`，开发/测试环境仍保留最小 compatibility guard；`scripts/dev-up.sh` 仍不会自动执行 `alembic upgrade head`；focused pytest 仍有已知 pytest-cov/no-data 与 SQLite teardown warning 噪声。

## Follow-ups

S02-S04 should build on the new authority line instead of reopening startup schema repair. A later M019 slice may choose to narrow startup `create_all()` or dev/test compatibility further, but only from the now-explicit Alembic/repair/bootstrap boundary.

## Files Created/Modified

- `backend/src/common/db/session.py` — Introduced explicit startup/migration/bootstrap authority map and fail-fast startup behavior for non-development legacy drift.
- `backend/src/common/db/legacy_schema_repair.py` — Centralized persona/knowledge legacy repair logic for shared reuse by startup guards, scripts, and Alembic.
- `backend/src/main.py` — Logged the startup database authority map at application startup.
- `backend/scripts/repair_legacy_schema.py` — Expanded explicit repair authority to cover both persona-policy and knowledge-document legacy drift.
- `backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py` — Added idempotent Alembic revision carrying the explicit legacy startup repair authority.
- `backend/tests/integration/test_startup_or_bootstrap_authority.py` — Added focused production-startup and explicit-repair authority proofs.
- `backend/tests/unit/common/test_db_session_compatibility.py` — Locked the authority-map and compatibility behavior with focused unit proof.
- `docs/backup-recovery-runbook.md` — Documented the Alembic/repair/bootstrap authority line and reusable repo-root verification commands.
- `docs/setup/backup-recovery-current-state.md` — Updated current-state backup/recovery facts to match the new startup/bootstrap/migration split.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Persisted the M019/S01 database authority inventory and its follow-on implications.
- `.github/workflows/nfr-performance-check.yml` — Clarified CI migration wording so the workflow points at Alembic as schema authority.
