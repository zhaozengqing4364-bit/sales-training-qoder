---
id: T01
parent: S01
milestone: M020
key_files:
  - backend/src/common/auth/service.py
  - backend/src/sales_bot/websocket/router.py
  - backend/tests/unit/common/test_auth_transport_matrix.py
  - backend/tests/unit/test_sales_websocket_router.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D219 — codify the current auth authority baseline as bearer-or-cookie for HTTP, query-token compatibility for websocket, and hashed-password formalization with env password fallbacks
duration: 
verification_result: passed
completed_at: 2026-04-13T10:05:23.757Z
blocker_discovered: false
---

# T01: Codified the live auth transport matrix and locked it with focused backend/frontend auth-websocket proofs.

**Codified the live auth transport matrix and locked it with focused backend/frontend auth-websocket proofs.**

## What Happened

I executed T01 as an inventory-and-proof task rather than a behavior change. I first read the slice/task plans plus the repository loop state, then inspected the live auth and websocket entrypoints to confirm the real transport rules. The key finding was that browser HTTP flows already default to cookie-session auth on the frontend, login credentials already distinguish managed `User.hashed_password` from env-based compatibility passwords, and both sales/presentation websocket entrypoints still accept query-token auth as an active compatibility path. I then used a red-green cycle to make that matrix explicit in code: a new backend unit test failed because `AUTH_TRANSPORT_MATRIX` did not exist, so I added a code-owned matrix plus resolver-order documentation in `backend/src/common/auth/service.py`; a second red test failed because the sales websocket router did not publish its own policy, so I added `SALES_WS_AUTH_POLICY` in `backend/src/sales_bot/websocket/router.py`. After that I wrote the same reality back into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, recorded decision D219 for the auth authority baseline, and added a knowledge entry warning that frontend websocket URLs no longer emit `token=` while backend websocket entrypoints still resolve query token before cookie. The end result is that M020/S01 now starts from one truthful matrix instead of scattered assumptions, and T02 can harden from an explicit baseline rather than rediscovering transports.

## Verification

Ran the task-plan grep gate to prove the intended auth surfaces are present, then ran focused backend and frontend proofs. Backend proof: `backend/tests/unit/common/test_auth_transport_matrix.py`, `backend/tests/unit/test_sales_websocket_router.py`, `backend/tests/unit/test_main_presentation_ws_runtime.py`, and `backend/tests/integration/test_auth_login_api.py` all passed together (30 tests). Frontend proof: `src/hooks/use-practice-websocket.test.ts`, `src/hooks/websocket/transport.test.ts`, `src/lib/auth-handler.test.ts`, and `src/app/(auth)/login/page.test.tsx` all passed together (32 tests), confirming no websocket `token=` query params on the live hook and no regression in centralized auth/session-expired handling. LSP diagnostics were clean on the touched Python files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS_JSON|session cookie|resolve_websocket_token|token: str = Query|Authorization" backend/src/common/auth backend/src/sales_bot/websocket backend/src/presentation_coach/websocket web/src/lib/auth-handler.ts web/src/hooks/use-auth-protection.ts` | 0 | ✅ pass | 36ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_auth_transport_matrix.py backend/tests/unit/test_sales_websocket_router.py backend/tests/unit/test_main_presentation_ws_runtime.py backend/tests/integration/test_auth_login_api.py -q` | 0 | ✅ pass | 5130ms |
| 3 | `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/websocket/transport.test.ts" "src/lib/auth-handler.test.ts" "src/app/(auth)/login/page.test.tsx"` | 0 | ✅ pass | 2560ms |

## Deviations

None.

## Known Issues

The backend websocket entrypoints still resolve `Authorization header -> query token -> session cookie`; query-token compatibility remains an active runtime path and is intentionally only documented, not removed, in T01. Backend pytest also still emits the pre-existing pytest-cov no-data warning plus unrelated third-party deprecation warnings during focused runs.

## Files Created/Modified

- `backend/src/common/auth/service.py`
- `backend/src/sales_bot/websocket/router.py`
- `backend/tests/unit/common/test_auth_transport_matrix.py`
- `backend/tests/unit/test_sales_websocket_router.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
