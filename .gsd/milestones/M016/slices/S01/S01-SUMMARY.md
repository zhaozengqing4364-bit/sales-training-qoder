---
id: S01
parent: M016
milestone: M016
provides:
  - A stable forgot/reset backend contract for S02 error-shape unification.
  - An auditable password-reset lifecycle surface for S03 admin security and log-redaction review.
  - A proven hashed_password-first compatibility path that later auth work can extend without guessing fallback behavior.
requires:
  []
affects:
  - S02
  - S03
key_files:
  - backend/src/common/services/password_reset.py
  - backend/src/common/db/models.py
  - backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py
  - backend/alembic/versions/20260412_0315_028_password_reset_single_active_token.py
  - backend/src/common/auth/api.py
  - backend/tests/integration/test_auth_login_api.py
  - backend/tests/integration/test_password_reset_api.py
  - .gsd/PROJECT.md
key_decisions:
  - D188 — Treat PasswordResetService + PasswordResetToken + Alembic 026/027 as the auth-recovery authority seam while preserving hashed_password-first login compatibility.
  - D189 — Enforce the single-active password-reset token invariant at the DB layer and keep password-reset Alembic revision IDs within the version-table length limit.
  - D190 — Keep proof split between the repo-root auth gate and the dedicated reset lifecycle suite instead of creating a new umbrella auth suite.
patterns_established:
  - Auth recovery changes must land on the service/model/migration seam, not on request handlers or global bootstrap code.
  - Use DB-layer partial unique indexes for security lifecycle invariants that must always hold.
  - Preserve backward-compatible login fallbacks explicitly while making `User.hashed_password` the durable authority once present.
  - Keep auth proof narrow by separating compatibility-gate tests from lifecycle-detail tests.
observability_surfaces:
  - Structured auth logs for password reset token issued/delivered/consumed/rejected events.
  - Password reset lifecycle table fields: `delivery_status`, `delivery_attempted_at`, `delivery_error`, `used_at`, `invalidated_at`, `invalidation_reason`.
  - Focused acceptance gates: `backend/tests/integration/test_auth_login_api.py` and `backend/tests/integration/test_password_reset_api.py`.
drill_down_paths:
  - .gsd/milestones/M016/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M016/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M016/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T19:30:02.253Z
blocker_discovered: false
---

# S01: Password reset / auth backend 正式化

**Formalized the forgot/reset backend contract so password-reset tokens are durable, single-active, auditable, and still preserve hashed_password-first login compatibility.**

## What Happened

## What this slice actually delivered

S01 closed the gap between an already-working forgot/reset flow and a formal auth-recovery contract that later slices can safely build on. The backend authority seam is now explicit: `common.services.password_reset.PasswordResetService` owns issuance/consume/delivery/rate limiting, `common.db.models.PasswordResetToken` owns the durable lifecycle row, and Alembic revisions `026_password_reset_tokens`, `027_reset_lifecycle_delivery`, and `028_reset_single_active_token` own schema history. This slice did **not** widen into JWT/session helper refactors or new frontend auth flows; it kept the change narrow and strengthened the existing seam.

## Delivered behavior and contracts

- Added/confirmed durable password-reset lifecycle fields for `used_at`, `invalidated_at`, `invalidation_reason`, `delivery_status`, `delivery_attempted_at`, and `delivery_error`, so token state is auditable instead of implicit.
- Enforced the **single-active-token** invariant at the DB layer with a partial unique index on `password_reset_tokens.user_id` where `used_at IS NULL AND invalidated_at IS NULL`, so supersession is a schema contract, not only a service convention.
- Preserved the existing login compatibility rule: once `User.hashed_password` exists it becomes the login authority, while `AUTH_USER_PASSWORDS_JSON` / `AUTH_SHARED_PASSWORD` remain fallback only for users who have not yet moved onto managed hashes.
- Kept the default email seam intentionally lightweight: password-reset delivery still goes through `EmailService`, with `ConsoleEmailService` remaining the default dev transport rather than forcing a provider integration into this hardening slice.
- Expanded focused proof on the existing auth seams instead of adding a new umbrella suite: `test_auth_login_api.py` now proves success, expiry/reuse rejection, same-IP rate limiting, hashed-password-first login, and request-path DDL absence; `test_password_reset_api.py` proves lifecycle details like superseded-token rejection and DB invariant enforcement.

## Patterns established for downstream slices

1. **Auth recovery changes must land on the service/model/migration seam, not request handlers.** Future slices should treat `PasswordResetService + PasswordResetToken + Alembic` as the only valid authority path.
2. **Schema invariants matter for security seams.** If a lifecycle rule must always hold, prefer a DB constraint/index plus tests rather than a soft service-only convention.
3. **Compatibility fallbacks stay explicit and bounded.** `hashed_password` is now the durable credential path; env-backed passwords are a temporary compatibility edge, not a co-equal authority.
4. **Focused proof should stay split by responsibility.** The repo-root auth gate proves compatibility behavior; the dedicated reset suite proves row-level lifecycle behavior.

## What downstream slices should know

- S02 can now standardize auth/API error shapes on top of a stable forgot/reset seam instead of guessing whether reset failures are transport issues, invalid token issues, or legacy DDL artifacts.
- S03 can rely on an auditable password-reset table surface (`delivery_status`, invalidation metadata, consumption timestamps) when reviewing admin/security posture and log-redaction boundaries.
- The remaining `Base.metadata.create_all()` usage is still global startup/test bootstrap, **not** request-path auth DDL. Do not reopen S01 by conflating those bootstrap compatibility calls with forgot/reset runtime behavior.

## Operational Readiness (Q8)

- **Health signal:** focused auth gates stay green (`test_auth_login_api.py`, `test_password_reset_api.py`), forgot/reset issues `PasswordResetToken` rows with observable `delivery_status`, and structured logs emit token issued/delivered/consumed/rejected events.
- **Failure signal:** 429 `[RATE_LIMIT_EXCEEDED]`, 400 `[INVALID_RESET_TOKEN]`, failed delivery rows with `delivery_status="failed"` plus `delivery_error`, and token rows marked `invalidated_at`/`invalidation_reason` when superseded or expired.
- **Recovery procedure:** inspect the latest `password_reset_tokens` row for the user, verify whether the active token was superseded/expired/used, re-request forgot-password from a new window once the per-IP limiter clears, and keep provider rollouts behind the existing `EmailService` seam instead of bypassing the lifecycle table.
- **Monitoring gaps:** delivery remains console-backed by default, so there is still no production mail-provider success/failure telemetry beyond the persisted lifecycle fields; the repository’s historical Alembic-from-zero chain still has an older unrelated `001_agent_platform_tables` issue outside this slice.


## Verification

Fresh close-out verification reran the slice gate `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` and it passed 17/17 in 2.98s, proving reset success, expiry/reuse rejection, same-IP rate limiting, hashed-password-first login compatibility, and request-path DDL absence. Fresh lifecycle verification reran `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` and it passed 8/8 in 2.52s, proving forgot/reset success, single-active-token enforcement, superseded-token rejection, and lifecycle-row observability. Fresh LSP diagnostics for `backend/tests/integration/test_auth_login_api.py` and `backend/tests/integration/test_password_reset_api.py` were both clean. Focused pytest-cov warnings (`Module src was never imported` / `No data was collected`) remain non-blocking noise for these narrow commands; both suites exited 0.

## Requirements Advanced

- R029 — hardened the already-validated self-service password reset capability into a durable, auditable backend contract with DB-enforced token lifecycle invariants and fresh focused auth proof.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None beyond the task-level path correction already captured in task summaries: the real auth-recovery authority seam lives in `common.services.password_reset`, `PasswordResetToken`, and Alembic 026/027/028 rather than in request handlers themselves.

## Known Limitations

Default password-reset delivery is still `ConsoleEmailService`, so production-grade provider telemetry is not part of this slice. A fresh Alembic upgrade from the very start of repository history still hits an older unrelated `001_agent_platform_tables` issue outside the password-reset chain. Focused pytest runs still emit pytest-cov no-data warnings that are noisy but non-blocking.

## Follow-ups

S02 should align auth/reset failures with the upcoming unified API error contract so frontend consumers no longer infer token/delivery/compatibility failures page-locally. S03 should review whether password-reset delivery/error fields and auth logs need additional redaction or RBAC-protected admin visibility.

## Files Created/Modified

- `backend/src/common/services/password_reset.py` — Continues to own issuance, supersession, delivery metadata persistence, token consumption, and rate-limited forgot/reset runtime behavior.
- `backend/src/common/db/models.py` — Defines the durable `PasswordResetToken` lifecycle contract and the partial unique index that enforces one active token per user.
- `backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py` — Carries lifecycle delivery fields such as invalidation and delivery metadata into formal schema history.
- `backend/alembic/versions/20260412_0315_028_password_reset_single_active_token.py` — Adds the DB-level single-active-token invariant to the migration chain.
- `backend/src/common/auth/api.py` — Preserves hashed_password-first login compatibility and points forgot/reset behavior at the formalized auth seam.
- `backend/tests/integration/test_auth_login_api.py` — Acts as the repo-root auth gate proving reset compatibility behavior, rate limiting, DDL absence, and managed-password login promotion.
- `backend/tests/integration/test_password_reset_api.py` — Acts as the dedicated lifecycle suite proving supersession, expiry, reuse rejection, and single-active-token enforcement.
