---
id: T02
parent: S01
milestone: M019
key_files:
  - backend/src/common/db/session.py
  - backend/src/common/db/legacy_schema_repair.py
  - backend/scripts/repair_legacy_schema.py
  - backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py
  - backend/tests/integration/test_startup_or_bootstrap_authority.py
  - backend/tests/unit/common/test_db_session_compatibility.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D211 — Restrict startup compatibility repairs to development/test bootstrap, and route production-like legacy persona/knowledge schema drift through explicit Alembic revision 20260413_1040_029 or scripts/repair_legacy_schema.py.
duration: 
verification_result: passed
completed_at: 2026-04-13T02:57:30.273Z
blocker_discovered: false
---

# T02: Restricted startup schema repair to development/test and moved legacy persona/knowledge fixes behind explicit repair-script and Alembic authority.

**Restricted startup schema repair to development/test and moved legacy persona/knowledge fixes behind explicit repair-script and Alembic authority.**

## What Happened

I moved the remaining startup-era schema repair responsibility off the production-like startup path and into explicit authority entrypoints. The core change was introducing `backend/src/common/db/legacy_schema_repair.py` as one shared sync repair seam for the two legacy compatibility surfaces that T01 identified: `personas.persona_policy` and `knowledge_documents` schema drift. `backend/src/common/db/session.py` now treats those repairs as development/test-only bootstrap compatibility; in non-development environments, startup inspects the live schema and raises an explicit `RuntimeError` that points operators at `alembic upgrade head` or `python scripts/repair_legacy_schema.py` instead of silently mutating schema during normal service startup. I then wired the same helper into `backend/scripts/repair_legacy_schema.py`, which now explicitly repairs both legacy surfaces rather than only the knowledge-documents path, and added idempotent Alembic revision `20260413_1040_029_explicit_legacy_startup_repairs.py` so the forward migration entrypoint also carries this repair authority. Finally, I added a focused integration proof in `backend/tests/integration/test_startup_or_bootstrap_authority.py` that locks the two key behaviors: production-like startup fails loudly on a legacy personas table, and the explicit repair script seam upgrades that same legacy schema successfully. I updated the existing unit authority-map proof and wrote back D211 plus a knowledge entry about `common.db.session` binding `DATABASE_URL`/engine at import time, which matters for future startup-authority tests.

## Verification

I reran the new focused proof plus the existing unit authority proof with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_startup_or_bootstrap_authority.py backend/tests/unit/common/test_db_session_compatibility.py -q`, and it finished 4/4 green. That proof confirms production-like startup now rejects a legacy `personas` table with an actionable migration/repair error and that the explicit repair-script seam upgrades the same legacy schema. I also reran the exact slice verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration -k "startup or bootstrap or migration" -x -q`, which passed with the new integration authority test selected by the gate. Fresh LSP diagnostics reported no issues on `backend/src/common/db/session.py`, `backend/src/common/db/legacy_schema_repair.py`, `backend/scripts/repair_legacy_schema.py`, `backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py`, `backend/tests/integration/test_startup_or_bootstrap_authority.py`, and `backend/tests/unit/common/test_db_session_compatibility.py`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_startup_or_bootstrap_authority.py backend/tests/unit/common/test_db_session_compatibility.py -q` | 0 | ✅ pass | 1803ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration -k "startup or bootstrap or migration" -x -q` | 0 | ✅ pass | 5513ms |

## Deviations

Beyond the plan’s minimum expected output, I introduced `backend/src/common/db/legacy_schema_repair.py` as a shared sync repair seam and added idempotent Alembic revision `20260413_1040_029` so startup, the explicit repair script, and `alembic upgrade head` all point at one executable authority instead of three drifting implementations.

## Known Issues

Focused pytest still emits pre-existing pytest-cov 'module src was never imported / no data was collected' warnings, and the focused SQLite proof still surfaces a teardown `ResourceWarning` for an unclosed sqlite connection. This task did not change that harness noise.

## Files Created/Modified

- `backend/src/common/db/session.py`
- `backend/src/common/db/legacy_schema_repair.py`
- `backend/scripts/repair_legacy_schema.py`
- `backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py`
- `backend/tests/integration/test_startup_or_bootstrap_authority.py`
- `backend/tests/unit/common/test_db_session_compatibility.py`
- `.gsd/KNOWLEDGE.md`
