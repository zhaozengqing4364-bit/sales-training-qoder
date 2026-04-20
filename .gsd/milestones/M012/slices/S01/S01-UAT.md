# S01: 认证与首页修复 — UAT

**Milestone:** M012
**Written:** 2026-04-09T02:55:56.411Z

# S01: 认证与首页修复 — UAT

**Milestone:** M012  
**UAT mode:** auth + dashboard first-login acceptance

## Why this UAT mode is sufficient

This slice is a launchability/user-trust slice, not a deep runtime workflow slice. Acceptance depends on whether a first-time learner can recover access without admin help, whether the login page truthfully marks unavailable auth options, and whether the dashboard stops looking like a hardcoded demo. The slice-close UAT therefore combines focused backend auth contracts with user-facing auth/dashboard checks.

## Preconditions

- Backend dependencies are installed in `backend/venv`.
- Frontend dependencies are installed in `web/node_modules`.
- Run commands from the repository root.
- Use an active user account that was created by an admin (self-service registration is still intentionally unsupported).
- For local/dev manual validation, the backend may use the console email mock; in that mode, capture the reset URL/token from backend stdout.

## Smoke Test

Run the four slice gates:

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q`
- `npm --prefix web test -- --run login`
- `npm --prefix web test -- --run dashboard`

**Expected:** all pass. Current slice-close proof: backend focused gate 6/6 passed, repo-root backend planner gate 6 selected tests passed, auth web gate 7/7 passed, dashboard web gate 14/14 passed.

## Test Cases

### 1. Login page exposes the real recovery path and clearly blocks WeCom

1. Open `/login`.
2. Inspect the secondary auth control.
3. **Expected:** the 企业微信登录 button is visibly disabled, lower-contrast, has a tooltip/title of `即将支持，敬请期待`, and is accompanied by explicit coming-soon copy.
4. Inspect the password area.
5. **Expected:** a `忘记密码？` link is visible below the password field and points to `/forgot-password`.

### 2. Known-email forgot-password request succeeds without friction

1. From `/login`, click `忘记密码？`.
2. Enter a valid active user email (for example the admin-created learner account).
3. Submit the form.
4. **Expected:** the page transitions to a success state with `邮件已发送` and generic copy stating that if the email is registered, a reset link will be sent.
5. In local/dev mode with console email transport, capture the reset URL/token from backend stdout.
6. **Expected:** stdout includes a one-time `/reset-password?token=...` link that can be used for the next step.

### 3. Unknown-email forgot-password request does not leak account existence

1. Repeat the forgot-password flow with an email that does not exist.
2. **Expected:** the UI returns the same generic success message as the known-email case.
3. **Expected backend contract:** no user-enumerating error is shown and no reset token row is created for the unknown email.

### 4. Reset-password form validates token and password before submit

1. Open `/reset-password` directly without a query token.
2. Try submitting with an empty token.
3. **Expected:** the page blocks submission and asks for the reset token.
4. Enter a token but use a password shorter than 8 characters.
5. **Expected:** the page shows `密码至少需要 8 个字符` and does not call the API.
6. Enter mismatched password/confirmation values.
7. **Expected:** the page shows `两次输入的密码不一致` and does not call the API.

### 5. Reset token can be consumed exactly once, and the new password becomes the login authority

1. Open the reset URL captured in the known-email flow, or navigate to `/reset-password?token=<token>`.
2. Enter a valid new password and matching confirmation.
3. Submit the form.
4. **Expected:** the page shows `密码已重置` and offers a `去登录` CTA.
5. Return to `/login`.
6. Attempt login with the old shared/original password.
7. **Expected:** login fails.
8. Attempt login with the newly reset password.
9. **Expected:** login succeeds and routes to `/`.
10. Reuse the same reset token.
11. **Expected:** backend rejects it as invalid/expired/consumed; the token is one-time only.

### 6. Dashboard header uses real identity and package version, not demo placeholders

1. Log in as a user with `display_name`/`name` populated.
2. Land on the dashboard home page (`/`).
3. **Expected:** the heading uses a time-based greeting (`早安` / `午安` / `晚安`) plus the real user name.
4. Inspect the version badge in the header.
5. **Expected:** it reads `v<package.json version>` instead of a hardcoded string/date.
6. Confirm the old hardcoded date (`2026年1月10日`) is absent.

### 7. Dashboard greeting falls back cleanly when no profile name is present

1. Log in as a user whose `display_name` and `name` are blank but whose email is populated.
2. Open the dashboard home page in the evening.
3. **Expected:** the greeting uses `晚安, <email prefix>` instead of a blank or hardcoded demo name.

## Edge Cases

- **Older unused reset tokens:** requesting a new reset should invalidate older unused tokens for the same user.
- **Rate limit:** repeated forgot-password requests from the same IP inside one minute should be rejected with a rate-limit response.
- **WeCom affordance:** the button must remain clearly unavailable until the real auth path ships; it should never look clickable by accident.
- **Local dev recovery:** if the console email transport is active, the printed link/token must remain visible enough to complete a manual reset flow.

## Failure Signals

- `/login` still looks like WeCom should work today.
- Forgot-password leaks whether an email exists.
- Reset-password accepts short or mismatched passwords.
- A used token can be replayed.
- Logging in still accepts the old shared/original password after a successful reset.
- The dashboard shows a hardcoded name, hardcoded date, or hardcoded version string.

## Requirements Proved By This UAT

- **R029** — self-service forgot/reset-password flow exists and works without admin intervention.
- **R030** — homepage/dashboard user-facing identity and version are dynamically sourced.
- **R031** — login page exposes a real forgot-password entry point and reset flow.

## Notes For The Next Slice

S02 should treat the dashboard header and auth entry surfaces as authoritative UI seams: do not reintroduce hardcoded user copy, and if more unavailable features must stay visible, follow the same explicit disabled-state pattern used for WeCom.
