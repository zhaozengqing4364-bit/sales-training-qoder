---
id: S02
parent: M014
milestone: M014
provides:
  - A formal backend password-reset lifecycle/delivery seam that downstream auth and practice work can rely on without re-investigating token invalidation semantics.
  - A truthful learner profile entrypoint into forgot/reset recovery, including current-email handoff and manual-token fallback for local/dev console delivery.
  - Focused regression proof that spans backend auth lifecycle plus learner login/forgot/reset/profile/voice-speed surfaces, making future drift detectable.
requires:
  []
affects:
  - S03
  - S04
key_files:
  - backend/src/common/services/password_reset.py
  - backend/src/common/rate_limit/api_limiter.py
  - backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py
  - backend/tests/integration/test_auth_login_api.py
  - backend/tests/integration/test_password_reset_api.py
  - web/src/app/(dashboard)/profile/page.tsx
  - web/src/app/(dashboard)/profile/page.test.tsx
  - web/src/app/(auth)/forgot-password/page.tsx
  - web/src/app/(auth)/reset-password/page.tsx
  - web/src/hooks/use-voice-speed-preference.ts
  - web/src/hooks/use-voice-speed-preference.test.ts
key_decisions:
  - D176 — password reset tokens now distinguish consumed vs invalidated states and persist delivery outcome metadata while keeping console email as the default transport seam.
  - Reuse the existing truthful `/forgot-password` handoff from learner profile instead of inventing an authenticated change-password API before product and backend support exist.
  - Keep voice-speed persistence on the shared `useVoiceSpeedPreference()` browser-local seam and explicitly avoid fake `PATCH /users/me` storage until a real backend preference contract exists.
patterns_established:
  - Treat password-reset authority as one lifecycle seam: issued token rows persist delivery outcome, invalidation reason, and eventual consumption instead of hiding those states in API behavior alone.
  - Keep learner profile password changes on a truthful forgot/reset handoff until a real authenticated change-password contract exists; do not resurrect `window.location` jumps or fake in-profile password APIs.
  - Keep voice-speed preference on one shared frontend seam (`useVoiceSpeedPreference()`) and make the browser-local scope explicit instead of pretending it is stored on the user profile.
observability_surfaces:
  - `PasswordResetToken` lifecycle columns: `invalidated_at`, `invalidation_reason`, `delivery_status`, `delivery_attempted_at`, `delivery_error`.
  - Forgot-password HTTP diagnostics now include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers on success responses as well as rate-limit errors.
  - Learner voice-speed state is visibly scoped to the browser via the shared `useVoiceSpeedPreference()` seam and can be inspected through the `voice_speed_preference` localStorage key.
drill_down_paths:
  - .gsd/milestones/M014/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T15:20:37.569Z
blocker_discovered: false
---

# S02: 认证与个人中心体验补齐

**Formalized the forgot/reset backend lifecycle and closed the learner profile/account-maintenance loop, so password changes route through the real recovery path and voice-speed preference survives refresh truthfully.**

## What Happened

S02 closed the learner account-maintenance loop without inventing fake settings surfaces. On the backend, the existing password-reset authority seam was formalized instead of rebuilt: `PasswordResetToken` now records explicit invalidation state (`invalidated_at`, `invalidation_reason`) alongside delivery lifecycle fields (`delivery_status`, `delivery_attempted_at`, `delivery_error`), superseded requests retire prior unused tokens instead of masquerading as consumed ones, expired tokens persist their invalidation reason before rejection, and forgot-password keeps its anti-enumeration success surface even when the delivery transport fails. The rate-limit decorator was also fixed so `JSONResponse` paths like forgot-password now expose the same `X-RateLimit-*` headers that enforcement already honored, making focused auth proof and live diagnostics line up.

On the learner-facing side, profile/password behavior stayed honest. The profile page keeps the “修改密码” action as a real Next `Link` to `/forgot-password`, pre-filling the current email when available and explaining that password updates happen through the email-reset flow. The forgot-password page hydrates that handoff email and trims it before submission, while the reset-password page supports both emailed query tokens and manually pasted tokens so the local console-delivery path remains usable. In parallel, voice-speed preference remains on one shared frontend authority seam: `useVoiceSpeedPreference()` normalizes supported values, persists them to `localStorage`, rehydrates them after refresh, and the profile page makes that browser-local scope explicit instead of pretending the choice is stored via `PATCH /users/me`.

The slice therefore delivers the intended user outcome from the roadmap: a learner can move from profile to the formal password-reset path, recover the account through forgot/reset with a stable backend lifecycle contract, and keep the voice-speed preference after refresh without fake persistence claims. Just as importantly for downstream slices, S02 establishes the pattern that learner account surfaces must either connect to a real seam or stay visibly local/truthful — no imperative `window.location` jumps, no dead password buttons, and no silent backend-preference theater.

## Operational Readiness

- **Health signal:** new `password_reset_tokens` rows move through explicit lifecycle states (`pending` → `sent`/`failed`, or `invalidated`/`used_at`), forgot-password responses expose `X-RateLimit-*` headers, and the profile voice-speed selector rehydrates the last supported value from `localStorage` after refresh.
- **Failure signal:** password-reset delivery issues now show up as `delivery_status='failed'` plus `delivery_error`/`delivery_attempted_at`, invalid or superseded tokens return the existing `[INVALID_RESET_TOKEN]` user-facing error, and malformed browser storage snaps the voice-speed selector back to `1.0` instead of silently drifting.
- **Recovery procedure:** if delivery fails, inspect the latest `PasswordResetToken` row/logs, fix or temporarily fall back to the console transport, then ask the learner to request a fresh reset email so any previous token is superseded. If voice-speed looks wrong locally, clear the malformed `voice_speed_preference` key or re-select a supported option and refresh.
- **Monitoring gaps:** there is still no external email-provider integration or alerting pipeline for repeated `delivery_status='failed'` events, and voice-speed preference has no server-side telemetry or cross-device visibility because the shipped seam is intentionally browser-local.

## Verification

Fresh slice-close verification reran both slice-plan gates and the focused auth/profile proofs that actually demonstrate the shipped learner account-maintenance loop.

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` ✅ pass (14/14)
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` ✅ pass (6/6)
- `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"` ✅ pass (3/3)
- `npm --prefix web test -- --run "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts"` ✅ pass (14/14)
- LSP diagnostics on `web/src/app/(dashboard)/profile/page.tsx` and `backend/src/common/services/password_reset.py` ✅ clean

That gives this slice one trustworthy proof bundle: backend reset lifecycle + delivery resilience, login → forgot handoff, forgot/reset page closure, truthful profile password routing, and refresh-safe voice-speed persistence.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The slice plan named `backend/tests/integration/test_auth_login_api.py` and `src/app/(auth)/login/page.test.tsx` as the minimum proof gates, but the real authority surfaces for the shipped work also include the dedicated password-reset backend suite plus the forgot-password/reset-password/profile/voice-speed web suites. Slice close-out kept the planned commands, added those focused proofs, and replaced the auto-mode placeholder `T03-SUMMARY.md` with a truthful task summary so downstream agents inherit the actual learner-facing closure instead of a blocker stub.

## Known Limitations

Password reset delivery still defaults to the console transport until a real provider is configured, so local/dev recovery continues to rely on log or console access. The profile password action is intentionally a forgot-password handoff rather than an authenticated in-profile change-password form. Voice-speed preference is intentionally browser-local only; there is still no backend user-preference field or cross-device sync for it.

## Follow-ups

S03 can attach learner help/feedback to a profile/auth shell that no longer contains fake account-maintenance affordances. S04 can assume forgot/reset recovery and browser-local voice-speed persistence are stable while it designs practice preflight and interruption recovery. If product later needs cross-device preference sync or a true authenticated change-password flow, that should be a new slice with an explicit backend user-settings contract rather than retroactively pretending this slice already shipped it.

## Files Created/Modified

- `web/src/app/(dashboard)/profile/page.tsx` — Profile page now keeps password changes on a truthful `/forgot-password` handoff, carries current-email query params, and surfaces the browser-local voice-speed preference seam with honest copy.
- `web/src/app/(dashboard)/profile/page.test.tsx` — Focused profile regressions lock the password CTA handoff, browser-local voice-speed persistence, malformed localStorage normalization, and no-fake-PATCH boundary.
- `web/src/app/(auth)/forgot-password/page.tsx` — Forgot-password page hydrates email handoff, trims values before submission, and preserves a truthful success surface for console or real email delivery.
- `web/src/app/(auth)/reset-password/page.tsx` — Reset-password page supports query-token and manual-token paths so both emailed links and local console-delivery recovery stay usable.
- `web/src/hooks/use-voice-speed-preference.ts` — Shared voice-speed hook remains the single frontend authority seam for normalization plus localStorage persistence across refreshes.
- `backend/src/common/services/password_reset.py` — Password reset backend now records explicit invalidation and delivery lifecycle state on `PasswordResetToken`, keeping forgot-password resilient when transport delivery fails.
- `backend/src/common/rate_limit/api_limiter.py` — Rate-limit decorator now attaches `X-RateLimit-*` headers to response objects like `JSONResponse`, making forgot-password diagnostics match enforcement.
- `backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py` — Alembic revision formalizes password-reset invalidation/delivery columns, constraints, and indexes for the backend authority seam.
- `.gsd/milestones/M014/slices/S02/tasks/T03-SUMMARY.md` — Recovered the missing T03 task artifact with a truthful summary of the shipped profile/auth closure and focused verification evidence.
