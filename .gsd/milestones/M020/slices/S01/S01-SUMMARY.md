---
id: S01
parent: M020
milestone: M020
provides:
  - A concrete auth transport authority seam for all later M020 security/runtime slices.
  - Focused backend/frontend proof that cookie security, CSRF posture, websocket auth precedence, and shared-password compatibility remain truthful.
  - Runbook and API-contract language that now matches the shipped runtime instead of an inferred or stale security posture.
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - backend/src/common/auth/service.py
  - backend/src/common/auth/api.py
  - backend/src/sales_bot/websocket/router.py
  - web/src/lib/api/client.ts
  - backend/tests/integration/test_auth_login_api.py
  - backend/tests/integration/test_websocket_status_contract.py
  - web/src/lib/api/client.auth.test.ts
  - docs/setup/auth-local.md
  - docs/api-contract/websocket.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/PROJECT.md
key_decisions:
  - D219 — codify the current auth authority baseline as bearer-or-cookie for HTTP, query-token compatibility for websocket, and hashed-password formalization with env password fallbacks.
  - D220 — document the live auth transport authority plus explicit compatibility off-ramp conditions and repo-root verification commands instead of documenting the desired hardening end state as if it already shipped.
patterns_established:
  - Keep auth transport policy in one shared backend authority seam (`common.auth.service`) and make compatibility paths explicit, diagnosable, and test-backed.
  - Treat browser cookie auth as a pair: session cookie plus CSRF cookie/header double-submit enforcement on unsafe requests.
  - Write runbook/API-contract language to the shipped behavior first, then list off-ramp conditions for compatibility paths rather than documenting the aspirational target state as if it already exists.
observability_surfaces:
  - Login response headers `X-Auth-Authority` and `X-Auth-Compatibility-Mode`.
  - `403 [CSRF_VALIDATION_FAILED]` for cookie-backed unsafe requests without a matching CSRF token.
  - Warning-level signal when websocket auth falls back to compatibility transport.
drill_down_paths:
  - .gsd/milestones/M020/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M020/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M020/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-13T12:10:46.983Z
blocker_discovered: false
---

# S01: Auth transport hardening

**Hardened the auth transport boundary by enforcing secure cookie+CSRF posture for cookie-backed HTTP auth, reordering websocket auth to header/cookie first with query-token compatibility fallback, and writing the resulting authority line into focused tests and docs.**

## What Happened

S01 started from a truthful inventory of the shipped auth surface instead of assuming the desired hardening state was already present. T01 locked the live baseline in code and tests: HTTP formal auth was bearer-or-cookie, websocket formal auth was bearer-or-cookie with query token still active as compatibility, and login authority was managed `User.hashed_password` with env password fallbacks. T02 then converted the red handoff into real runtime behavior. `backend/src/common/auth/service.py` now owns the transport authority seam: non-development always forces `Secure` on both session and CSRF cookies; cookie-backed unsafe requests must satisfy an `app_csrf` ↔ `X-CSRF-Token` double-submit check; and websocket auth now resolves in the order `Authorization -> session cookie -> query token compatibility` through `resolve_websocket_auth(...)`. `backend/src/common/auth/api.py` now emits explicit compatibility diagnostics (`X-Auth-Authority`, `X-Auth-Compatibility-Mode`) when login still falls back to env-managed passwords, so shared-password mode is observable instead of hidden. On the frontend, `web/src/lib/api/client.ts` remains the single outward request seam and now automatically attaches `X-CSRF-Token` for cookie-backed unsafe requests, preserving the centralized `authHandler` session-expired flow. T03 then rewrote the runbook and websocket contract to match the shipped code instead of the old baseline, so downstream slices inherit one real auth boundary rather than scattered assumptions.

This slice establishes three reusable patterns for the rest of M020. First, auth/security behavior now has a code-owned authority seam (`common.auth.service`) rather than route-local hidden defaults. Second, compatibility paths remain allowed only when they are explicit, diagnosable, and documented with off-ramp conditions; query-token websocket auth and shared-password login are no longer silent defaults. Third, repo-root focused proof is now part of the boundary itself: backend auth/websocket suites and frontend API/authHandler suites are the durable verification surface for future slices that touch logging, multi-instance reconnect semantics, or recovery drills.

Operational Readiness
- Health signal: login in non-development sets both session and CSRF cookies as `Secure`; cookie-backed logout succeeds only with a matching `X-CSRF-Token`; websocket auth prefers bearer/session-cookie before query-token compatibility; login responses expose `X-Auth-Authority` and `X-Auth-Compatibility-Mode` when compatibility auth is used.
- Failure signal: missing or mismatched CSRF token returns `403 [CSRF_VALIDATION_FAILED]`; invalid websocket auth still rejects with the existing close-code boundary; compatibility websocket use is logged as a warning so it is auditable instead of invisible.
- Recovery procedure: if a browser-auth flow fails after deployment, first verify the session/CSRF cookie pair and client `X-CSRF-Token` attachment, then rerun the repo-root auth/websocket proof bundle. If a websocket caller breaks, migrate it to bearer header or session-cookie transport; query-token should only remain as a controlled compatibility fallback.
- Monitoring gaps: S01 made compatibility and CSRF failures explicit, but sensitive log redaction and admin/runtime observability tightening are still follow-on work in S02; multi-instance reconnect/session-state correctness is still follow-on work in S03.

## Verification

Fresh slice-close verification reran the required focused gates and passed. Backend runtime gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_password_reset_api.py backend/tests/integration/test_websocket_status_contract.py -x -q` ✅ pass (35 passed). Frontend auth transport gate: `npm --prefix web test -- --run src/lib/api/client.auth.test.ts src/lib/auth-handler.test.ts` ✅ pass (16 passed). Task-plan inventory gate: `rg -n "AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS_JSON|session cookie|resolve_websocket_token|resolve_websocket_auth|token: str = Query|Authorization" backend/src/common/auth backend/src/sales_bot/websocket backend/src/presentation_coach/websocket web/src/lib/auth-handler.ts web/src/hooks/use-auth-protection.ts` ✅ pass. Task-plan doc-contract gate: `rg -n "Authorization|query token|cookie|CSRF|shared password|session expired" docs/setup/auth-local.md docs/api-contract/websocket.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/lib/auth-handler.ts` ✅ pass. LSP diagnostics on `backend/src/common/auth/service.py`, `backend/src/common/auth/api.py`, `backend/src/sales_bot/websocket/router.py`, and `web/src/lib/api/client.ts` were clean.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 and T03 task summaries recorded an intermediate red-test handoff state before implementation landed. Slice close-out completed that work rather than preserving the blocker: runtime auth behavior, client transport behavior, and docs now all match the hardened authority line.

## Known Limitations

Sensitive log redaction and admin/runtime observability tightening are still pending in M020/S02, so compatibility-use warnings and auth diagnostics are now explicit but not yet fully redacted/audited across every sink. Query-token websocket auth still exists as a compatibility fallback and therefore remains an allowed, but explicitly temporary, transport path.

## Follow-ups

M020/S02 should use the new explicit auth/compatibility signals to finish sensitive-log and admin-observability redaction without re-opening transport ambiguity. M020/S03 should treat `resolve_websocket_auth(...)` plus the cookie/CSRF seam as the fixed auth boundary while it hardens multi-instance reconnect and session-state authority. M020/S04 should reuse the repo-root auth proof bundle as part of recovery-drill validation.

## Files Created/Modified

None.
