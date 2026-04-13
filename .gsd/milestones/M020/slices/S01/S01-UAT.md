# S01: Auth transport hardening — UAT

**Milestone:** M020
**Written:** 2026-04-13T12:10:46.983Z

# S01 UAT — Auth transport hardening

## Preconditions
- Backend is running with the current M020/S01 code.
- Repo-root verification bundle is available.
- One test account exists that can still log in via `AUTH_SHARED_PASSWORD` or `AUTH_USER_PASSWORDS_JSON`.
- For browser tests, the app is opened through the same loopback host as the backend auth cookie scope.

## Test Case 1 — Non-development login sets secure session + CSRF cookies
1. Set `ENVIRONMENT=production` (or another non-development value) and keep a valid compatibility password configured.
2. Call `POST /api/v1/auth/login` with valid credentials.
3. Inspect all `Set-Cookie` headers.

### Expected
- Response is `200`.
- A session cookie is set for `app_session` (or configured session cookie name).
- A CSRF cookie is set for `app_csrf` (or configured CSRF cookie name).
- Both cookies include `Secure`.
- Session cookie remains `HttpOnly`.
- Login response includes `X-Auth-Authority`.
- If compatibility auth was used, `X-Auth-Compatibility-Mode` is present and truthful.

## Test Case 2 — Cookie-backed unsafe request is rejected without matching CSRF header
1. Log in through `/api/v1/auth/login` and keep the returned session+CSRF cookies.
2. Send `POST /api/v1/auth/logout` using the cookie-backed session but without `X-CSRF-Token`.
3. Repeat the same request with `X-CSRF-Token` equal to the CSRF cookie value.

### Expected
- First logout attempt returns `403` with `[CSRF_VALIDATION_FAILED]`.
- Second logout attempt returns `200`.
- Logout clears the session cookie.
- A follow-up `GET /api/v1/users/me` returns `401` after successful logout.

## Test Case 3 — Shared-password compatibility is explicit and auditable
1. Use an account without `User.hashed_password` and log in via `AUTH_SHARED_PASSWORD`.
2. Inspect response headers and logs.

### Expected
- Login still succeeds for compatibility users.
- Response header `X-Auth-Authority` is `compatibility_env_password`.
- Response header `X-Auth-Compatibility-Mode` identifies the compatibility mode (`shared_password` or `user_password_override`).
- Compatibility login is no longer silent or indistinguishable from managed-password auth.

## Test Case 4 — WebSocket auth prefers session cookie before query token fallback
1. Open a websocket connection with a valid session cookie and a stale/legacy `?token=` omitted.
2. Confirm the connection succeeds.
3. Open a second websocket connection with no bearer header and no session cookie, but with a valid `?token=`.

### Expected
- Cookie-backed connection succeeds as a formal transport.
- Query-token connection still succeeds only as a compatibility fallback.
- Compatibility use is auditable (warning-level signal / compatibility mode), not the preferred path.
- Invalid websocket auth still fails with the existing reject surface rather than silently connecting.

## Test Case 5 — Frontend API client automatically carries CSRF on cookie-backed unsafe requests
1. In the web app, log in through the normal auth flow so the browser stores session + CSRF cookies.
2. Trigger a cookie-backed unsafe auth action that goes through `web/src/lib/api/client.ts` (for example logout).
3. Inspect the outgoing request.

### Expected
- Request still uses `credentials: include`.
- `X-CSRF-Token` is automatically attached and matches the CSRF cookie.
- Auth-owning endpoints still use the centralized `authHandler` behavior (`skipSessionExpiredHandling` for login/logout/forgot/reset remains intact).

## Edge Cases
- A bearer-authenticated unsafe request should not require the browser CSRF cookie path.
- Setting `AUTH_SESSION_COOKIE_SECURE=false` must not disable `Secure` cookies outside development.
- A stale compatibility caller that still uses websocket `?token=` should work only as a documented compatibility path, not outrank session-cookie auth.
- After a password reset writes `User.hashed_password`, the same user should stop depending on shared-password authority for subsequent logins.
