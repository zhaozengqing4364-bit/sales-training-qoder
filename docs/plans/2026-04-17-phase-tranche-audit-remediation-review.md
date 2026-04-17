# Phase-tranche audit remediation review — tranche 1

Date: 2026-04-17  
Worker: worker-3  
Scope source: `.omx/plans/ralplan-audit-remediation-roadmap.md`, PRD, and test spec (read-only)

## Scope reviewed

This review focuses on the first tranche item for cookie-session CSRF protection and records the verification state needed for leader integration. The related plan requirements are:

- unsafe methods (`POST`, `PATCH`, `DELETE`, etc.) skip CSRF for Bearer-token requests;
- cookie-backed unsafe requests require the `app_csrf` cookie to match `X-CSRF-Token`;
- safe methods (`GET`, `HEAD`, `OPTIONS`, `TRACE`) remain unaffected;
- auth bootstrap endpoints such as login/reset flows stay usable before a session exists.

## Changes made in this tranche

- Added a FastAPI HTTP middleware in `backend/src/main.py` that applies the existing `should_enforce_csrf()` and `validate_csrf_request()` helpers globally for cookie-backed unsafe requests.
- Kept auth bootstrap endpoints explicitly exempt: `/api/v1/auth/login`, `/api/v1/auth/dev-login`, `/api/v1/auth/forgot-password`, and `/api/v1/auth/reset-password`.
- Added integration coverage in `backend/tests/integration/test_auth_login_api.py` for:
  - missing CSRF header on a cookie-backed `PATCH /api/v1/users/me` returning `403` with `[CSRF_VALIDATION_FAILED]`;
  - mismatched CSRF header returning the same `403` envelope;
  - matching CSRF token allowing the write;
  - Bearer-token unsafe writes bypassing the cookie CSRF layer even when cookies are present.

## Verification evidence

| Check | Result | Notes |
| --- | --- | --- |
| `ruff check backend/src/main.py backend/tests/integration/test_auth_login_api.py` | PASS | Ruff reports only the pre-existing top-level config deprecation warning, then `All checks passed!`. |
| `python3 -m py_compile backend/src/main.py backend/tests/integration/test_auth_login_api.py` | PASS | Both modified files compile successfully. |
| `cd backend && pytest tests/integration/test_auth_login_api.py -q` | BLOCKED | Collection fails before tests run because the local environment lacks `jwt`/PyJWT: `ModuleNotFoundError: No module named 'jwt'`. |

## Review notes for leader integration

- The middleware preserves the existing logout route-level CSRF check; the global layer now rejects missing/mismatched cookie CSRF earlier for every unsafe cookie-backed endpoint.
- The response shape intentionally matches the existing CSRF detail envelope (`{"detail":{"error":"[CSRF_VALIDATION_FAILED]",...}}`) so current logout tests and clients keep the same failure contract.
- Remaining first-tranche lanes still need separate integration evidence: web Vitest project scoping, frontend lint/typecheck cleanup, and continuous audio uploader API-client unification.
