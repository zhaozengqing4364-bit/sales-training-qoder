---
id: T02
parent: S01
milestone: M020
key_files:
  - backend/tests/integration/test_auth_login_api.py
  - backend/tests/integration/test_websocket_status_contract.py
  - web/src/lib/api/client.auth.test.ts
key_decisions:
  - Use focused red tests as the durable handoff artifact for T02 instead of attempting rushed partial runtime changes after the hard timeout warning.
duration: 
verification_result: mixed
completed_at: 2026-04-13T10:38:40.713Z
blocker_discovered: false
---

# T02: Added failing auth-hardening tests that capture the missing cookie-CSRF, websocket authority, and shared-password compatibility work for T02 handoff.

**Added failing auth-hardening tests that capture the missing cookie-CSRF, websocket authority, and shared-password compatibility work for T02 handoff.**

## What Happened

I resumed T02 by reading the slice/task plans, T01 carry-forward summary, the auth/websocket implementation files, and the focused verification suites. Based on that live code, I confirmed the remaining T02 work is still missing in three places: non-development cookie security and CSRF enforcement are not implemented in `common.auth`, websocket auth still resolves `Authorization -> query token -> cookie` instead of preferring header/cookie before the query-token compatibility path, and the frontend API client still does not send a CSRF header for cookie-backed unsafe requests. I then followed a red-first approach and updated the focused test surfaces to encode the intended target state: `backend/tests/integration/test_auth_login_api.py` now expects secure session+CSRF cookies in non-development, CSRF rejection for cookie-backed logout without the matching header, and explicit shared-password compatibility diagnostics; `backend/tests/integration/test_websocket_status_contract.py` now expects a new websocket auth-resolution helper that marks query-token as compatibility-only and prefers session cookies before query-token fallback; `web/src/lib/api/client.auth.test.ts` now expects the browser client to attach `X-CSRF-Token` for unsafe cookie-backed requests. I stopped at that point because of the hard timeout recovery path. No production implementation files were changed yet, so the task is not behaviorally complete even though the durable summary is now being written. The remaining execution path is straightforward: add the missing CSRF cookie/header constants and validation helpers in `backend/src/common/auth/service.py`, wire secure cookie + compatibility-diagnostic headers in `backend/src/common/auth/api.py`, reorder websocket auth resolution and downgrade logging in `backend/src/common/auth/service.py` / `backend/src/sales_bot/websocket/router.py` / `backend/src/main.py`, and teach `web/src/lib/api/client.ts` to attach the CSRF header on unsafe cookie-backed requests before rerunning the exact backend verification gate plus the focused frontend client test.

## Verification

Re-ran the minimal red tests that define the unfinished T02 target state. The backend auth integration subset failed during collection because `common.auth.service` does not yet export `AUTH_CSRF_COOKIE_NAME` or `AUTH_CSRF_HEADER_NAME`, proving the cookie/CSRF hardening seam is still unimplemented. The websocket contract subset failed during collection because `common.auth.service` does not yet export `resolve_websocket_auth`, proving the resolver-order/compatibility helper is still missing. The focused frontend client test ran and failed because `web/src/lib/api/client.ts` still does not attach `X-CSRF-Token` on cookie-backed unsafe requests. I did not run the full slice verification command because the red tests make the missing implementation explicit first; the exact task verification command would still fail until these runtime changes land.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -k "secure_session_and_csrf_cookies or logout_requires_matching_csrf_header or shared_password_fallback_exposes_compatibility_diagnostic_header" -q` | 2 | ❌ fail | 6031ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py -k "websocket_auth_prefers_session_cookie_before_query_token_compatibility or websocket_query_token_is_marked_as_compatibility_transport" -q` | 2 | ❌ fail | 3781ms |
| 3 | `npm --prefix web test -- --run src/lib/api/client.auth.test.ts -t "adds csrf header for cookie-backed unsafe requests when the csrf cookie is present"` | 1 | ❌ fail | 2814ms |

## Deviations

Timed out in the red-test / handoff phase. I intentionally did not start partial production edits after the timeout warning because that would have left a larger half-implemented surface. Instead I preserved the new target-state tests and recorded the exact remaining implementation steps.

## Known Issues

T02 remains incomplete. `backend/tests/integration/test_auth_login_api.py` currently fails to import the planned CSRF constants from `backend/src/common/auth/service.py`; `backend/tests/integration/test_websocket_status_contract.py` currently fails to import the planned websocket auth-resolution helper; and `web/src/lib/api/client.auth.test.ts` fails because the browser client does not yet add the CSRF header. Because no production auth/websocket/client code was updated yet, the slice verification gate has not been restored.

## Files Created/Modified

- `backend/tests/integration/test_auth_login_api.py`
- `backend/tests/integration/test_websocket_status_contract.py`
- `web/src/lib/api/client.auth.test.ts`
