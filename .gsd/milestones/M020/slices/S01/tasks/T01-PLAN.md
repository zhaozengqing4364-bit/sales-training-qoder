---
estimated_steps: 3
estimated_files: 6
skills_used: []
---

# T01: 盘点 auth transport matrix 与兼容路径

- 盘点 `common.auth`、frontend auth hooks、sales/presentation websocket routers 当前支持的认证 transport：cookie、Authorization header、query token、shared password、per-user password。
- 写出当前真实 auth matrix，明确哪些是正式路径、哪些只是兼容路径。
- 锁定一组 focused auth/websocket tests，避免后续 hardening 改坏 learner/admin 主链。

## Inputs

- `backend/src/common/auth/service.py`
- `backend/src/common/auth/api.py`
- `backend/src/sales_bot/websocket/router.py`
- `web/src/lib/auth-handler.ts`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/common/auth/service.py`
- `backend/src/sales_bot/websocket/router.py`

## Verification

rg -n "AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS_JSON|session cookie|resolve_websocket_token|token: str = Query|Authorization" backend/src/common/auth backend/src/sales_bot/websocket backend/src/presentation_coach/websocket web/src/lib/auth-handler.ts web/src/hooks/use-auth-protection.ts
