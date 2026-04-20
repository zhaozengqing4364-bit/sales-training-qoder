---
id: T02
parent: S01
milestone: M016
key_files:
  - backend/src/common/db/models.py
  - backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py
  - backend/alembic/versions/20260412_0315_028_password_reset_single_active_token.py
  - backend/src/common/auth/api.py
  - backend/tests/integration/test_password_reset_api.py
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D189 — enforce the password-reset single-active-token invariant at the DB layer and keep password-reset Alembic revision ids within the version-table length limit.
duration: 
verification_result: passed
completed_at: 2026-04-11T19:18:54.933Z
blocker_discovered: false
---

# T02: Hardened password-reset persistence with a single-active-token schema contract and Alembic-safe revision ids.

**Hardened password-reset persistence with a single-active-token schema contract and Alembic-safe revision ids.**

## What Happened

I translated the missing formal contract into a failing focused test first by proving the database still allowed two active `password_reset_tokens` rows for the same user. To close that gap, I hardened `backend/src/common/db/models.py` with a partial unique index on `password_reset_tokens.user_id` for rows where `used_at` and `invalidated_at` are both null, then added Alembic revision `backend/alembic/versions/20260412_0315_028_password_reset_single_active_token.py` so the lifecycle invariant is part of schema history instead of only service behavior. While verifying migrations, I also found that the descriptive password-reset revision ids were longer than Alembic’s default `alembic_version.version_num` width, so I shortened the 027/028 revision identifiers to `027_reset_lifecycle_delivery` and `028_reset_single_active_token` and updated the formalization references in `backend/src/common/auth/api.py` and `backend/src/common/db/models.py`. The existing `EmailService` seam and hashed-password-first login compatibility boundary already matched the task contract, so I preserved them and only documented the new invariant instead of widening auth behavior. I also wrote the non-obvious Alembic-length/metadata-registration rule into `.gsd/KNOWLEDGE.md` and recorded decision D189 so future auth work knows the lifecycle invariant is a DB contract, not just a service convention.

## Verification

Ran the task-plan gate `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` and confirmed the focused auth/login compatibility suite stayed green after the schema hardening. Then ran `backend/tests/integration/test_password_reset_api.py -x -q`, which includes the new single-active-token regression and confirmed forgot/reset success, expiry, reuse rejection, and the new schema invariant all pass together. Finally, ran a repo-root Python contract check that verifies the password-reset Alembic revision ids are now all <=32 characters and that SQLite metadata creation emits the partial unique index SQL `WHERE used_at IS NULL AND invalidated_at IS NULL`, proving the lifecycle invariant is inspectable at the DB layer. I also attempted a fresh SQLite Alembic-from-zero upgrade; that exposed a pre-existing historical migration problem in `001_agent_platform_tables` (`practice_sessions` missing) outside this task’s scope, so I did not widen T02 into full legacy-chain repair.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` | 0 | ✅ pass | 3830ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` | 0 | ✅ pass | 3686ms |
| 3 | `backend/venv/bin/python - <<'PY' ... verify password-reset revision lengths <=32 and sqlite metadata emits uq_password_reset_tokens_single_active_user ... PY` | 0 | ✅ pass | 74ms |

## Deviations

The real reset authority seam lives in `common.services.password_reset` and the dedicated `backend/tests/integration/test_password_reset_api.py` suite, so I treated those as local path corrections alongside the planned auth/api/model/alembic files. I also had to shorten the 027/028 revision ids to stay within Alembic’s version-table width; the task plan did not call out migration-id hygiene explicitly, but the migration chain could not stay healthy without it.

## Known Issues

A fresh SQLite Alembic upgrade from the very start of the repository history still fails earlier in `001_agent_platform_tables` because that legacy chain assumes pre-existing `practice_sessions` tables. This task fixed the password-reset revision-id problem and formalized the reset schema invariant, but it did not widen into unrelated historical migration repair. Password-reset delivery still defaults to the existing console transport seam until a real email provider is configured.

## Files Created/Modified

- `backend/src/common/db/models.py`
- `backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py`
- `backend/alembic/versions/20260412_0315_028_password_reset_single_active_token.py`
- `backend/src/common/auth/api.py`
- `backend/tests/integration/test_password_reset_api.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
