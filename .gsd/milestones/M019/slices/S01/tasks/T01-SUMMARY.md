---
id: T01
parent: S01
milestone: M019
key_files:
  - backend/src/common/db/session.py
  - backend/src/main.py
  - backend/tests/unit/common/test_db_session_compatibility.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D210 — Keep Alembic as schema evolution authority, keep init_db as startup bootstrap plus explicit compatibility guards, and keep repair/bootstrap as one-off scripts.
duration: 
verification_result: passed
completed_at: 2026-04-13T02:40:32.822Z
blocker_discovered: false
---

# T01: Made startup/migration/bootstrap authority explicit across db startup code, analysis, and focused proof.

**Made startup/migration/bootstrap authority explicit across db startup code, analysis, and focused proof.**

## What Happened

I audited the live startup and schema surfaces across `backend/src/common/db/session.py`, `backend/src/main.py`, `backend/alembic/env.py`, the relevant Alembic revisions (`015`, `017`, `018`, `026`, `027`, `028`), `backend/scripts/repair_legacy_schema.py`, `backend/scripts/bootstrap_auth_admin.py`, `scripts/dev-up.sh`, and `docs/backup-recovery-runbook.md`. The key finding was that the real implicit repair surface is concentrated in the startup path, not request handlers: `lifespan -> init_db()` still runs `Base.metadata.create_all()` plus the `persona_policy` and `knowledge_documents` compatibility guards, while `scripts/dev-up.sh` starts `uvicorn src.main:app` directly and does not run `alembic upgrade head` first. I made that split explicit by introducing `STARTUP_DB_AUTHORITY` in `backend/src/common/db/session.py`, logging the authority map during startup in both `session.py` and `main.py`, adding a focused unit test that locks the named migration/repair/bootstrap entrypoints, and extending `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` with a concrete M019/S01 authority inventory table. I also captured the non-obvious `dev-up` / startup-patch drift in `.gsd/KNOWLEDGE.md` and saved decision D210 so downstream M019 work can tighten the remaining startup-path schema repair against one shared baseline instead of rediscovering it.

## Verification

I reran the slice-plan grep gate and it now exposes the explicit startup/migration/bootstrap authority surface in `backend/src/common/db/session.py` and `backend/src/main.py`. I also grepped the architecture scan and knowledge log to prove the new inventory persisted to the expected long-lived artifacts. The focused backend proof `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_db_session_compatibility.py -q` passed 2/2 after adding the authority-map assertion alongside the existing knowledge-documents compatibility test. Finally, fresh LSP diagnostics reported no issues on `backend/src/common/db/session.py`, `backend/src/main.py`, and `backend/tests/unit/common/test_db_session_compatibility.py`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "create_all|alembic|bootstrap|repair_legacy_schema|init_db" backend/src/common/db/session.py backend/src/main.py backend/alembic/versions scripts` | 0 | ✅ pass | 22ms |
| 2 | `rg -n "M019/S01 数据库演进 / bootstrap authority inventory|scripts/dev-up.sh 当前只是拉起 infra|M019/S01/T01 database authority inventory exposed" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/KNOWLEDGE.md` | 0 | ✅ pass | 22ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_db_session_compatibility.py -q` | 0 | ✅ pass | 1699ms |

## Deviations

Expanded beyond the minimum expected-output list by adding a focused unit proof, a knowledge-log entry, decision D210, and safe-grow continuity updates so the authority split is executable, discoverable, and resumable rather than markdown-only.

## Known Issues

Focused pytest still emits pre-existing pytest-cov 'module src was never imported / no data was collected' warnings plus a SQLite ResourceWarning on suite teardown; this task did not change that harness noise.

## Files Created/Modified

- `backend/src/common/db/session.py`
- `backend/src/main.py`
- `backend/tests/unit/common/test_db_session_compatibility.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
