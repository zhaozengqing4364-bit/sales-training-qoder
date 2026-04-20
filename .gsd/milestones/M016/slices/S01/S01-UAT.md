# S01: Password reset / auth backend 正式化 — UAT

**Milestone:** M016
**Written:** 2026-04-11T19:30:02.253Z

# UAT — M016/S01 Password reset / auth backend 正式化

## Preconditions
- Backend test environment is available from repo root.
- Test database can be recreated or isolated for auth integration tests.
- Default password-reset email transport remains console-based unless an alternate `EmailService` transport is explicitly configured.
- A test user exists (or is created inside the test flow) with an email address and no previously managed `hashed_password`.

## Test Case 1 — Forgot-password issues one active token and returns a non-enumerating response
1. Create or select an active user account with email `reset-create@example.com`.
   - Expected: user exists and is active.
2. POST `/api/v1/auth/forgot-password` with that email and header `X-Forwarded-For: 203.0.113.10`.
   - Expected: HTTP 200 with generic success message `如果该邮箱已注册，重置链接将发送到您的邮箱`.
3. Inspect `password_reset_tokens` for that user.
   - Expected: exactly one row exists; `token_hash` is populated; `used_at` is null; `invalidated_at` is null; `expires_at` is roughly 30 minutes ahead.
4. Inspect the delivery outcome.
   - Expected: console/mock transport emits a `/reset-password?token=...` link; persisted row has delivery metadata populated through the lifecycle seam.

## Test Case 2 — Unknown email does not enumerate account state
1. POST `/api/v1/auth/forgot-password` with `missing-reset@example.com`.
   - Expected: HTTP 200 with the same generic success message as a known account.
2. Inspect `password_reset_tokens`.
   - Expected: no new row is created for the unknown email path.

## Test Case 3 — Same-IP forgot-password requests are rate limited
1. For an active test user, POST `/api/v1/auth/forgot-password` twice in quick succession with the same `X-Forwarded-For` header.
   - Expected: first request returns HTTP 200 generic success.
   - Expected: second request returns HTTP 429 with `[RATE_LIMIT_EXCEEDED]`.
2. Wait for the limiter window to clear or switch to a new IP before retrying.
   - Expected: a subsequent request from a different IP or after the limiter window can issue a new token normally.

## Test Case 4 — Issuing a second token supersedes the first token
1. Request forgot-password once for a user, capture token A.
   - Expected: token A is active in the lifecycle table.
2. Request forgot-password again for the same user from a different IP, capture token B.
   - Expected: second request returns HTTP 200.
3. Inspect `password_reset_tokens` for that user.
   - Expected: two rows exist; token A now has `invalidated_at` populated and `invalidation_reason = "superseded"`; token B is the only active row.
4. Try to reset with token A.
   - Expected: HTTP 400 `[INVALID_RESET_TOKEN]`.
5. Reset with token B.
   - Expected: HTTP 200 success.

## Test Case 5 — Successful reset promotes the account onto managed password login
1. Start with a user who can still log in through the env-backed compatibility password.
   - Expected: login with the original env-configured password succeeds before reset.
2. Complete `/api/v1/auth/reset-password` with a valid token and new password `NewPass123!`.
   - Expected: HTTP 200 success.
3. Attempt login with the old compatibility password.
   - Expected: HTTP 401 invalid credentials.
4. Attempt login with the new password.
   - Expected: HTTP 200 success and JWT/session issuance.
5. Inspect the lifecycle row.
   - Expected: `used_at` is populated for the consumed token.

## Test Case 6 — Reuse and expiry are rejected truthfully
1. Re-submit `/api/v1/auth/reset-password` with an already consumed token.
   - Expected: HTTP 400 `[INVALID_RESET_TOKEN]`.
2. Create a token and advance time past the 30-minute expiry window (or use the focused test harness to simulate expiry).
   - Expected: reset attempt fails with HTTP 400 `[INVALID_RESET_TOKEN]`.
3. Inspect the expired token row.
   - Expected: `invalidated_at` is populated and `invalidation_reason = "expired"`.

## Test Case 7 — Request-path auth recovery no longer owns runtime DDL
1. Run the focused auth proof: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q`.
   - Expected: suite passes, including the source-level constraint that forgot/reset handlers do not contain request-path DDL markers.
2. Optionally grep auth handlers for runtime DDL markers.
   - Expected: request handlers do not contain `CREATE TABLE IF NOT EXISTS` or equivalent auth-local table creation logic.

## Acceptance Result
- Slice is acceptable only if all seven cases pass: generic forgot response stays non-enumerating, the DB enforces one active token, superseded/expired/reused tokens are rejected, successful reset moves login onto `hashed_password`, same-IP rate limiting is enforced, and request-path auth recovery stays free of runtime DDL.
