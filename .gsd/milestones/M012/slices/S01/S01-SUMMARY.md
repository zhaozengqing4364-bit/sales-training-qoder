---
id: S01
parent: M012
milestone: M012
provides:
  - A real forgot/reset-password auth flow with persisted one-time tokens, reset-password login, and local-dev recovery visibility.
  - A trustworthy dashboard header that derives greeting/name/version from real user/package data instead of demo placeholders.
  - An explicit disabled-state pattern for not-yet-shipped auth affordances so users are not sent into dead-end entry points.
requires:
  []
affects:
  - S02
  - S03
key_files:
  - backend/src/common/db/models.py
  - backend/alembic/versions/20260408_1718_026_password_reset_tokens.py
  - backend/src/common/auth/api.py
  - backend/src/common/auth/service.py
  - backend/src/common/services/password_reset.py
  - backend/tests/integration/test_password_reset_api.py
  - backend/src/common/audio/tts_service.py
  - backend/tests/unit/test_tts_import_contract.py
  - web/src/app/(auth)/login/page.tsx
  - web/src/app/(auth)/forgot-password/page.tsx
  - web/src/app/(auth)/reset-password/page.tsx
  - web/src/lib/api/client.ts
  - web/src/app/(dashboard)/page.tsx
  - web/src/app/(auth)/login/page.test.tsx
  - web/src/app/(auth)/forgot-password/login-recovery.test.tsx
  - web/src/app/(auth)/reset-password/login-reset.test.tsx
  - web/src/app/(dashboard)/page.test.tsx
key_decisions:
  - Reuse a shared CryptContext with pbkdf2_sha256 as the primary hashing scheme and bcrypt verify fallback for password resets (D156).
  - Once a user has a stored `hashed_password`, login should treat that user-specific password as authoritative instead of continuing to accept the shared env password fallback.
  - Keep the login-page WeCom control visible but explicitly disabled with clear coming-soon copy, rather than leaving it as an ambiguous active-looking button.
  - Keep `common.audio.tts_service` on a lazy/guarded `edge_tts` import so unrelated backend suites can still collect and browser-TTS fallback remains available when the optional binary stack is broken (D160).
patterns_established:
  - Treat account recovery as a non-enumerating control-plane seam: persisted one-time token, explicit expiry, older-token invalidation, IP rate limit, and generic forgot-password success copy should travel together.
  - Any user-visible homepage identity chrome must source live truth (`useCurrentUser()`, `package.json`, or API data) with explicit fallback order instead of hardcoded demo copy.
  - Optional binary/runtime integrations such as `edge_tts` should be lazy-imported or guarded so unrelated repo-root verification is not blocked by environment-specific dependency breakage.
observability_surfaces:
  - Backend auth contract gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q`
  - Repo-root backend planner gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q`
  - Auth web gate: `npm --prefix web test -- --run login`
  - Dashboard web gate: `npm --prefix web test -- --run dashboard`
  - Static diagnostics gate: LSP reported no diagnostics on `backend/src/common/audio/tts_service.py`, `backend/src/common/services/password_reset.py`, `backend/tests/integration/test_password_reset_api.py`, `backend/tests/unit/test_tts_import_contract.py`, `web/src/app/(auth)/login/page.tsx`, `web/src/app/(auth)/forgot-password/page.tsx`, `web/src/app/(auth)/reset-password/page.tsx`, and `web/src/app/(dashboard)/page.tsx`.
  - Local-dev recovery surface: the console email mock now emits the reset URL/token so manual recovery can be traced without a real mail provider.
drill_down_paths:
  - .gsd/milestones/M012/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M012/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M012/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M012/slices/S01/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-09T02:55:56.411Z
blocker_discovered: false
---

# S01: 认证与首页修复

**S01 shipped self-service password reset, removed hardcoded dashboard identity/version copy, and made the unavailable WeCom login path explicitly non-actionable.**

## What Happened

S01 closed the first-login blockers that most visibly damaged trust for new learners. On the backend, the slice introduced a persisted `PasswordResetToken` model plus Alembic migration, then added a real forgot/reset-password service and routes that issue 30-minute one-time tokens, invalidate older unused tokens, enforce one request per minute per IP, avoid email enumeration, and switch login authority to the user’s stored password after reset. The auth stack also locked in pbkdf2_sha256 as the primary write scheme with bcrypt verify fallback so reset-password writes remain reliable in this repo’s current passlib environment. On the web side, the login page now exposes a visible `忘记密码？` entry point, the forgot-password page lets a user submit their email and see the generic success state, and the reset-password page accepts a reset token plus password/confirmation with minimum-length and mismatch validation before redirecting back to login. S01 also fixed the homepage trust issues: the dashboard greeting now reads `useCurrentUser()` for the real display name (falling back to `name`, then email prefix), changes copy by time of day, reads the visible version badge from `package.json`, and no longer shows the old hardcoded date. The WeCom login control was intentionally left visible but clearly disabled, with explicit “即将支持” copy so users are not misled into thinking it should already work. During slice-close verification, two non-obvious gaps surfaced and were closed: the local console email mock now prints the actual reset URL/token so local self-service recovery is runnable instead of being a dead-end, and `common.audio.tts_service` now guards the optional `edge_tts` import so the exact repo-root backend planner command can collect unrelated suites even when the local TTS binary stack is broken. Downstream slices can therefore assume the first-login auth path is self-service-capable, the dashboard header is sourced from real user/package data instead of hardcoded placeholders, and repo-root backend verification is no longer vulnerable to unrelated optional-TTS import crashes.

## Verification

Fresh slice-close verification reran every slice-plan gate after the final fixes and all passed. Backend focused auth contract: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` → 6 passed. Exact repo-root planner command: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q` → 6 selected tests passed, 1 skipped, 1494 deselected, confirming the prior unrelated `edge_tts` import crash is gone. Auth web gate: `npm --prefix web test -- --run login` → 7 passed across login, forgot-password, and reset-password suites. Dashboard web gate: `npm --prefix web test -- --run dashboard` → 14 passed, including the homepage dynamic greeting/version assertions. Additional regression verification passed `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_tts_import_contract.py -q` (1 passed) and `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_tts.py backend/tests/unit/test_tts_streaming.py -q` (10 passed, 1 skipped). LSP diagnostics reported no issues on the touched backend/frontend source files and new regression tests.

## Requirements Advanced

None.

## Requirements Validated

- R029 — Validated by fresh M012/S01 close-out verification: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q` passed 6 selected tests covering token creation, local recovery visibility, non-enumeration, rate limiting, one-time use, and reset-password login; `npm --prefix web test -- --run login` passed 7 auth web tests covering the forgot/reset UI flow.
- R030 — Validated by `npm --prefix web test -- --run dashboard` (14 passed), including assertions that the dashboard renders the real current-user name, falls back to the email prefix, shows `v${packageJson.version}`, and no longer shows the old hardcoded date.
- R031 — Validated by `npm --prefix web test -- --run login` (7 passed), which proves the login page exposes the forgot-password link and the forgot/reset pages complete the self-service recovery flow with frontend validation.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Slice-close verification uncovered two real gaps and closed them before completion: (1) the exact repo-root backend planner command initially failed during unrelated test collection because `common.audio.tts_service` hard-imported optional `edge_tts` and crashed on a broken local `aiohttp/multidict` stack, so the slice added a lazy/guarded import plus a regression test; (2) the local-development console email mock originally redacted the reset link even though the shipped reset page instructs local users to paste the token, so the slice added a focused regression and now prints the real local reset URL/token in the mock envelope. No roadmap-level scope change was required.

## Known Limitations

企业微信登录仍然只是明确标注的“即将支持”占位，不是可用认证路径。系统仍无自助注册流程（管理员创建账号仍是产品前提）。本地默认邮件传输仍是 console mock，而不是实际邮件服务；它现在可用于本地手工恢复验证，但生产环境仍需要真实邮件投递实现。

## Follow-ups

S02 should build on this slice by wiring history/sidebar/error-boundary polish without reintroducing hardcoded user-facing copy, and any future WeCom work should replace the disabled placeholder only when the real auth path exists end-to-end. If local/dev or CI environments continue to use the console email transport, keep the printed reset URL behavior so manual recovery remains testable.

## Files Created/Modified

- `backend/src/common/db/models.py` — Added the persisted `PasswordResetToken` model and user relationship used by the one-time reset flow.
- `backend/alembic/versions/20260408_1718_026_password_reset_tokens.py` — Added the schema migration for persisted password-reset tokens.
- `backend/src/common/auth/api.py` — Shipped forgot-password and reset-password endpoints with non-enumerating success copy, reset error mapping, and IP rate limiting.
- `backend/src/common/auth/service.py` — Kept password hashing on pbkdf2_sha256 primary with bcrypt verify fallback so reset-password writes remain reliable in this environment.
- `backend/src/common/services/password_reset.py` — Implemented token issuance/consumption, expiry/one-time-use rules, and a local console email mock that now prints the reset URL for dev recovery.
- `backend/tests/integration/test_password_reset_api.py` — Locked forgot/reset backend behavior, including non-enumeration, rate limiting, one-time token consumption, reset-password login, and local console-link output.
- `backend/src/common/audio/tts_service.py` — Guarded the optional `edge_tts` import so unrelated repo-root backend pytest collection no longer fails when the local TTS dependency chain is broken.
- `backend/tests/unit/test_tts_import_contract.py` — Added a regression proving `common.audio.tts_service` can be imported even when optional `edge_tts` binaries are unavailable.
- `web/src/app/(auth)/login/page.tsx` — Added the forgot-password entry point and converted the WeCom login control into an explicitly disabled coming-soon affordance.
- `web/src/app/(auth)/forgot-password/page.tsx` — Added the forgot-password request page with trimmed-email submission and success state.
- `web/src/app/(auth)/reset-password/page.tsx` — Added the reset-password page with token support, password confirmation, and minimum-length validation.
- `web/src/lib/api/client.ts` — Added typed `forgotPassword` and `resetPassword` client methods for the auth UI.
- `web/src/app/(dashboard)/page.tsx` — Removed hardcoded greeting/date/version values and now derive the visible name, greeting, and version badge dynamically.
- `web/src/app/(auth)/login/page.test.tsx` — Locked the login-page forgot-password link and disabled WeCom affordance.
- `web/src/app/(auth)/forgot-password/login-recovery.test.tsx` — Locked trimmed email submission and return-to-login behavior for the forgot-password page.
- `web/src/app/(auth)/reset-password/login-reset.test.tsx` — Locked reset-token submission and password validation behavior.
- `web/src/app/(dashboard)/page.test.tsx` — Locked dynamic user greeting, email-prefix fallback, package-version badge, and removal of the old hardcoded date.
- `.gsd/KNOWLEDGE.md` — Recorded the optional `edge_tts` import gotcha that can break unrelated repo-root backend verification.
- `.gsd/PROJECT.md` — Updated project state to reflect that M012/S01 is complete and that M012 is now focused on broader first-login usability polish.
