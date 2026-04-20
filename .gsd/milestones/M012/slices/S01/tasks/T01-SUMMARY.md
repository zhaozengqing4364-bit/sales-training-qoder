---
id: T01
parent: S01
milestone: M012
provides: []
requires: []
affects: []
key_files: ["backend/src/common/db/models.py", "backend/src/common/auth/api.py", "backend/src/common/auth/service.py", "backend/src/common/services/__init__.py", "backend/src/common/services/password_reset.py", "backend/alembic/versions/20260408_1718_026_password_reset_tokens.py", "backend/tests/integration/test_password_reset_api.py", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M012/slices/S01/tasks/T01-SUMMARY.md"]
key_decisions: ["Recorded D156: use pbkdf2_sha256 as the primary password-reset hashing scheme with bcrypt verify fallback in the shared CryptContext.", "Treat users.hashed_password as authoritative at login once a user has reset their password, instead of continuing to accept the shared env password for that account."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Focused verification passed with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` (5 tests covering token creation, non-enumeration, rate limiting, one-time use, and login with the reset password). Static diagnostics on the edited Python files reported no LSP issues. The exact planner command was also run and failed for an unrelated pre-existing import dependency in the websocket-status test collection path, not in the password-reset flow."
completed_at: 2026-04-08T09:29:23.879Z
blocker_discovered: false
---

# T01: Added a real forgot/reset-password backend flow with persisted reset tokens, user-specific password login, rate limiting, migration support, and contract tests.

> Added a real forgot/reset-password backend flow with persisted reset tokens, user-specific password login, rate limiting, migration support, and contract tests.

## What Happened
---
id: T01
parent: S01
milestone: M012
key_files:
  - backend/src/common/db/models.py
  - backend/src/common/auth/api.py
  - backend/src/common/auth/service.py
  - backend/src/common/services/__init__.py
  - backend/src/common/services/password_reset.py
  - backend/alembic/versions/20260408_1718_026_password_reset_tokens.py
  - backend/tests/integration/test_password_reset_api.py
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M012/slices/S01/tasks/T01-SUMMARY.md
key_decisions:
  - Recorded D156: use pbkdf2_sha256 as the primary password-reset hashing scheme with bcrypt verify fallback in the shared CryptContext.
  - Treat users.hashed_password as authoritative at login once a user has reset their password, instead of continuing to accept the shared env password for that account.
duration: ""
verification_result: mixed
completed_at: 2026-04-08T09:29:23.881Z
blocker_discovered: false
---

# T01: Added a real forgot/reset-password backend flow with persisted reset tokens, user-specific password login, rate limiting, migration support, and contract tests.

**Added a real forgot/reset-password backend flow with persisted reset tokens, user-specific password login, rate limiting, migration support, and contract tests.**

## What Happened

Replaced the inline password-reset prototype in common.auth.api with a service-backed implementation in common.services.password_reset. Added the PasswordResetToken ORM model plus a matching Alembic migration, added users.hashed_password so reset passwords persist durably, and made login treat that per-user password as authoritative once present. The service now hashes reset tokens with SHA-256 for exact lookup, expires them after 30 minutes, invalidates prior unused tokens, and emits structured logs with user_id/token_id only. Added an IP-scoped 1/minute rate limit to forgot-password and a redacted console email mock for local development. Wrote password-reset integration tests first, watched the old implementation fail, then implemented until the focused suite passed. During execution I also found the local passlib+bcrypt backend cannot mint new bcrypt hashes reliably, so I switched the shared CryptContext to pbkdf2_sha256 primary with bcrypt verify fallback and recorded that as D156 plus a knowledge note.

## Verification

Focused verification passed with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` (5 tests covering token creation, non-enumeration, rate limiting, one-time use, and login with the reset password). Static diagnostics on the edited Python files reported no LSP issues. The exact planner command was also run and failed for an unrelated pre-existing import dependency in the websocket-status test collection path, not in the password-reset flow.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` | 0 | ✅ pass | 4270ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q` | 1 | ❌ fail | 4220ms |


## Deviations

Added users.hashed_password to the schema and login flow even though the planner only named PasswordResetToken, because the existing auth path already depended on a per-user password field for reset passwords to be usable. Also changed the shared CryptContext to pbkdf2_sha256 primary with bcrypt verify fallback because the local passlib+bcrypt backend cannot mint fresh bcrypt hashes reliably.

## Known Issues

The exact slice/task verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q` still fails during unrelated test collection in `backend/tests/integration/test_websocket_status_contract.py` because the local environment is missing `multidict._multidict_py` through the `edge_tts` import chain. The dedicated password-reset suite passes.

## Files Created/Modified

- `backend/src/common/db/models.py`
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/services/__init__.py`
- `backend/src/common/services/password_reset.py`
- `backend/alembic/versions/20260408_1718_026_password_reset_tokens.py`
- `backend/tests/integration/test_password_reset_api.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M012/slices/S01/tasks/T01-SUMMARY.md`


## Deviations
Added users.hashed_password to the schema and login flow even though the planner only named PasswordResetToken, because the existing auth path already depended on a per-user password field for reset passwords to be usable. Also changed the shared CryptContext to pbkdf2_sha256 primary with bcrypt verify fallback because the local passlib+bcrypt backend cannot mint fresh bcrypt hashes reliably.

## Known Issues
The exact slice/task verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q` still fails during unrelated test collection in `backend/tests/integration/test_websocket_status_contract.py` because the local environment is missing `multidict._multidict_py` through the `edge_tts` import chain. The dedicated password-reset suite passes.
