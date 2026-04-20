# S02: 认证与个人中心体验补齐 — UAT

**Milestone:** M014
**Written:** 2026-04-11T15:20:37.570Z

# S02: 认证与个人中心体验补齐 — UAT

**Milestone:** M014
**Written:** 2026-04-11T23:11:00+08:00

# S02 UAT — 认证与个人中心体验补齐

## Preconditions
- Start the current branch with the backend migrated to Alembic head, including `027_password_reset_lifecycle_delivery`.
- Use a learner account that already exists (for example `learner@example.com`) and can sign in to the dashboard/profile surface.
- In local/dev, have access to backend console output or logs so you can copy the reset link/token emitted by the console email transport. If a real email provider is configured, use the delivered email instead.
- Clear or inspect the browser `localStorage` key `voice_speed_preference` before the voice-speed tests.

## Test Case 1 — Login page hands the learner into forgot-password with the typed email intact
1. Open `/login` and type a learner email with leading/trailing spaces, for example `  learner@example.com  `.
   - Expected: the email field accepts the value and the rest of the login page remains usable.
2. Click `忘记密码？`.
   - Expected: navigation goes to `/forgot-password?email=learner%40example.com` rather than a blank route, `#`, or no-op button.
3. Inspect the forgot-password email field.
   - Expected: it is prefilled with `learner@example.com` (trimmed) and the page shows copy explaining the email was carried over from login/profile.

## Test Case 2 — Forgot-password request stays truthful and leads to a usable reset token
1. From `/forgot-password`, submit the prefilled learner email.
   - Expected: the page transitions to the generic success state `邮件已发送` without revealing whether the account exists beyond the standard anti-enumeration copy.
2. Retrieve the reset token from the real email or from the local console/log output.
   - Expected: the emitted link targets `/reset-password?token=...` and contains a fresh token value.
3. Immediately submit a second forgot-password request for the same account.
   - Expected: the user-facing surface remains the same generic success flow; the newest token is now the only valid one, and the older token should no longer work.

## Test Case 3 — Reset-password works via both deep-linked token and manual token entry
1. Open the reset link from email/console directly.
   - Expected: `/reset-password` loads with the token already filled from the query string and tells the learner it was auto-filled from the link.
2. Enter a new password of at least 8 characters twice and submit.
   - Expected: the page shows `密码已重置` and offers `去登录`.
3. Return to `/login` and sign in with the new password.
   - Expected: login succeeds with the new password.
4. Trigger another forgot-password email, copy the new token, open `/reset-password` without query params, paste the token manually, and reset again.
   - Expected: the manual-token path succeeds too, proving the local/dev console-delivery fallback remains usable.

## Test Case 4 — Superseded or reused tokens are rejected instead of silently working
1. Request token A for the learner account.
2. Before using token A, request token B for the same account.
   - Expected: token B becomes the active token.
3. Attempt to reset the password with token A.
   - Expected: the page/API rejects it with the existing invalid-or-expired-token error; token A must not still work after being superseded.
4. Use token B successfully once, then try to reuse token B.
   - Expected: the second attempt is rejected as invalid/expired/used, proving one-time consumption still holds.

## Test Case 5 — Profile page keeps password changes truthful and voice speed refresh-safe
1. Sign in as the learner and open `/profile`.
   - Expected: the settings card shows `语音播放速度` with copy explicitly saying the setting is only stored in the current browser, and `修改密码` is presented as `通过邮箱重置密码`.
2. Inspect the password button target.
   - Expected: it links to `/forgot-password?email=<current user email>` when the profile has an email, or `/forgot-password` when profile loading degraded.
3. Change the voice-speed selector from the default to `1.5x`.
   - Expected: the selector updates immediately and the browser `localStorage` key `voice_speed_preference` becomes `1.5`.
4. Refresh `/profile`.
   - Expected: the selector still shows `1.5x`, proving refresh persistence works.
5. (Optional devtools check) Watch the network panel while changing only the voice-speed selector.
   - Expected: no fake `PATCH /users/me` request is sent just to persist voice speed.

## Edge Cases
- If `voice_speed_preference` is manually corrupted in `localStorage` (for example set to `fast`), reloading `/profile` should normalize the selector back to `1.0x` instead of leaving a broken or blank state.
- If profile bootstrap fails and the page shows the existing inline error, the password CTA should still degrade truthfully to `/forgot-password` instead of disappearing or becoming dead.
- In local/dev console-email mode, the slice is still acceptable as long as the reset token can be copied from console output and the manual-token reset flow works end to end.
