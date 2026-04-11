---
id: T01
parent: S01
milestone: M016
key_files:
  - backend/src/common/auth/api.py
  - backend/src/common/auth/service.py
  - backend/src/common/db/models.py
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D188 — land M016 password-reset formalization on PasswordResetService + PasswordResetToken + Alembic 026/027, while preserving the hashed_password-first login compatibility fallback.
duration: 
verification_result: mixed
completed_at: 2026-04-11T19:09:16.417Z
blocker_discovered: false
---

# T01: Documented the password-reset authority seam and the hashed_password-first login compatibility boundary so downstream formalization can land on one explicit auth contract.

**Documented the password-reset authority seam and the hashed_password-first login compatibility boundary so downstream formalization can land on one explicit auth contract.**

## What Happened

I traced the live forgot/reset path through the real runtime seam and found the planner snapshot was slightly narrow: the actual password-reset behavior is already centralized in `common.services.password_reset.PasswordResetService`, while the durable lifecycle row lives in `common.db.models.PasswordResetToken` and the formal schema history is already carried by Alembic revisions `026_password_reset_tokens` and `027_password_reset_lifecycle_delivery`. The auth API handlers themselves only delegate into that service; they do not own request-path DDL. The remaining `Base.metadata.create_all()` usage sits in global startup/test bootstrap (`common.db.session.init_db` and fixtures), so I wrote the narrow landing-point back into the planned authority files instead of widening the change. Specifically, `backend/src/common/auth/api.py` now exposes the formalization surface and preserves the rule that `User.hashed_password` is authoritative once present, `backend/src/common/auth/service.py` now documents that password-reset work must not expand JWT/session helper scope or re-treat startup bootstrap as auth-local DDL, and `backend/src/common/db/models.py` now marks `PasswordResetToken` as the durable lifecycle contract where `used_at` means consumption and `invalidated_at` means superseded/expired-but-auditable. I also recorded the rule in `.gsd/KNOWLEDGE.md` and saved decision D188 so T02/T03 can land on one seam without re-researching auth boundaries.

## Verification

Ran the task-plan inventory command `rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py` and confirmed forgot/reset still resolves to the existing auth/model seam without any auth-local `CREATE TABLE` path. Then ran fresh LSP diagnostics on `backend/src/common/auth/api.py`, `backend/src/common/auth/service.py`, and `backend/src/common/db/models.py`; all three returned clean after the seam writeback. I also manually inspected `backend/alembic/versions/20260408_1718_026_password_reset_tokens.py` and `backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py` during execution to confirm migration authority already exists where T02 should land.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py` | 0 | ✅ pass | 17ms |
| 2 | `lsp diagnostics backend/src/common/auth/api.py — ✅ pass (no diagnostics)` | -1 | unknown (coerced from string) | 0ms |
| 3 | `lsp diagnostics backend/src/common/auth/service.py — ✅ pass (no diagnostics)` | -1 | unknown (coerced from string) | 0ms |
| 4 | `lsp diagnostics backend/src/common/db/models.py — ✅ pass (no diagnostics)` | -1 | unknown (coerced from string) | 0ms |

## Deviations

The planner inputs named only `backend/src/common/auth/api.py`, `backend/src/common/auth/service.py`, and `backend/src/common/db/models.py`, but the real runtime reset behavior lives in `backend/src/common/services/password_reset.py` and the live schema authority lives in Alembic revisions 026/027. I treated that as a local path correction, inspected those files, and wrote the seam back into the planned authority files instead of broadening the task into an implementation refactor.

## Known Issues

Password-reset delivery still defaults to `ConsoleEmailService`, so recovery delivery remains a development transport seam rather than a production provider integration. Login compatibility still depends on `AUTH_USER_PASSWORDS_JSON` / `AUTH_SHARED_PASSWORD` for users without `User.hashed_password`. Global startup/test bootstrap still uses `Base.metadata.create_all()` outside the request path, so T02 should continue collapsing auth recovery onto migrations/service boundaries without conflating that broader compatibility bootstrap with forgot/reset runtime DDL.

## Files Created/Modified

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
