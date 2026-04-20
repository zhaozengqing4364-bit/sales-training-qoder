---
id: T03
parent: S01
milestone: M020
key_files:
  - docs/setup/auth-local.md
  - docs/api-contract/websocket.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/DECISIONS.md
key_decisions:
  - D220 — document the live auth transport authority plus explicit compatibility off-ramp conditions and repo-root verification commands instead of documenting the desired hardening end state as if it already shipped.
duration: 
verification_result: mixed
completed_at: 2026-04-13T11:46:26.772Z
blocker_discovered: false
---

# T03: Documented the live auth transport authority, compatibility off-ramps, and repo-root verification commands across the local auth runbook, websocket contract, and architecture scan.

**Documented the live auth transport authority, compatibility off-ramps, and repo-root verification commands across the local auth runbook, websocket contract, and architecture scan.**

## What Happened

I updated `docs/setup/auth-local.md` to codify the current formal/compat auth matrix for HTTP, WebSocket, and login credentials, plus local env/bootstrap guidance, explicit off-ramp conditions for `AUTH_SHARED_PASSWORD` / `AUTH_USER_PASSWORDS_JSON` and websocket `?token=` compatibility, and repo-root verification commands. I updated `docs/api-contract/websocket.md` to record the current websocket auth transport contract, recommended vs compatibility connection forms, auth-related reject close codes, and the same repo-root proof commands. I also rewrote the `M020/S01` auth transport section in `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` so downstream work inherits the truthful runtime authority line: browser HTTP still defaults to cookie-session, the shipped websocket resolver order is still `Authorization -> query token -> session cookie`, and frontend 401/session-expired handling still funnels through the centralized `authHandler` seam via `apiFetch` / `apiUpload` plus `createAuthDomain(...).skipSessionExpiredHandling`. Finally, I recorded decision D220 so future slices keep documenting the live authority plus explicit retirement conditions instead of writing the desired hardening end state as if it had already shipped.

## Verification

The task-plan grep gate passed, proving the required `Authorization` / `query token` / `cookie` / `CSRF` / `shared password` / `session expired` surfaces are now explicitly written into the runbook, websocket contract, architecture scan, and auth handler seam. An isolated frontend proof (`src/lib/auth-handler.test.ts`) passed, confirming session-expired handling still routes through the centralized `authHandler` seam. Slice-level focused runtime proof remains red and was recorded rather than papered over: the combined frontend auth client/authHandler suite still fails the CSRF-header expectation, backend auth integration still fails collection because `AUTH_CSRF_COOKIE_NAME` / `AUTH_CSRF_HEADER_NAME` are not implemented in `common.auth.service`, and backend websocket contract integration still fails collection because `resolve_websocket_auth` is not implemented.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "Authorization|query token|cookie|CSRF|shared password|session expired" docs/setup/auth-local.md docs/api-contract/websocket.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/lib/auth-handler.ts` | 0 | ✅ pass | 23ms |
| 2 | `npm --prefix web test -- --run src/lib/auth-handler.test.ts` | 0 | ✅ pass | 1045ms |
| 3 | `npm --prefix web test -- --run src/lib/api/client.auth.test.ts src/lib/auth-handler.test.ts` | 1 | ❌ fail | 1756ms |
| 4 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_websocket_status_contract.py -x -q` | 1 | ❌ fail | 4027ms |
| 5 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py -q` | 2 | ❌ fail | 2402ms |

## Deviations

Because the carried-forward T02 hardening runtime is still red locally, I documented the live shipped authority and explicit off-ramp conditions instead of writing the desired CSRF/websocket target state as if it were already implemented.

## Known Issues

`web/src/lib/api/client.ts` still does not attach `X-CSRF-Token` for cookie-backed unsafe requests, so `web/src/lib/api/client.auth.test.ts` remains red on the CSRF case. `backend/src/common/auth/service.py` still does not export `AUTH_CSRF_COOKIE_NAME`, `AUTH_CSRF_HEADER_NAME`, or `resolve_websocket_auth`, so the focused backend auth/websocket integration suites fail during collection. As a result, this task closes the documentation authority, but the slice’s runtime hardening is not yet fully green.

## Files Created/Modified

- `docs/setup/auth-local.md`
- `docs/api-contract/websocket.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/DECISIONS.md`
