# S01: Auth transport hardening

**Goal:** 收口 cookie security、CSRF posture、websocket auth transport、shared-password 兼容退出路径。
**Demo:** After this: auth/cookie/websocket 的 transport policy 会落成真实代码与 focused tests，后续不再靠‘兼容默认值’猜测安全边界。

## Must-Haves

- 非开发环境 cookie secure 策略和 CSRF posture 有明确 authority，而不是隐藏默认值。
- websocket auth 不再依赖 query token 作为常态路径，兼容策略可审计。
- shared password 只作为显式兼容态存在，退出路径与验证命令清楚。

## Proof Level

- This slice proves: integration

## Integration Closure

S01 结束后，所有后续安全/运行时切片都以这一条 auth boundary 为准，不再继续在页面、hook、router 里各自发明登录态规则。

## Verification

- auth 失败、session 失效、ws 拒连原因和安全降级状态有明确日志/HTTP/close-code 信号。

## Tasks

- [x] **T01: 盘点 auth transport matrix 与兼容路径** `est:45m`
  - 盘点 `common.auth`、frontend auth hooks、sales/presentation websocket routers 当前支持的认证 transport：cookie、Authorization header、query token、shared password、per-user password。
- 写出当前真实 auth matrix，明确哪些是正式路径、哪些只是兼容路径。
- 锁定一组 focused auth/websocket tests，避免后续 hardening 改坏 learner/admin 主链。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/common/auth/service.py`, `backend/src/common/auth/api.py`, `backend/src/sales_bot/websocket/router.py`, `web/src/lib/auth-handler.ts`, `web/src/hooks/use-auth-protection.ts`
  - Verify: rg -n "AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS_JSON|session cookie|resolve_websocket_token|token: str = Query|Authorization" backend/src/common/auth backend/src/sales_bot/websocket backend/src/presentation_coach/websocket web/src/lib/auth-handler.ts web/src/hooks/use-auth-protection.ts

- [ ] **T02: 收口 cookie、CSRF 与 websocket auth authority** `est:2h`
  - 在 backend/frontend 收口非开发环境 cookie secure 和 CSRF posture；若当前采用 same-site/cookie-only 策略，也要把 authority 写清并让失败信号显式化。
- websocket router 与 client 改为 header/cookie 优先，query token 退为受控兼容路径或移除。
- 为 shared-password 兼容态加显式诊断/退场策略，避免长期成为默认主路径。
  - Files: `backend/src/common/auth/service.py`, `backend/src/common/auth/api.py`, `backend/src/main.py`, `backend/src/sales_bot/websocket/router.py`, `backend/src/presentation_coach/websocket`, `web/src/hooks/use-practice-websocket.ts`, `web/src/lib/api/client.ts`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_password_reset_api.py backend/tests/integration/test_websocket_status_contract.py -x -q

- [ ] **T03: 把 auth authority 写回 contract 与 runbook** `est:35m`
  - 更新 auth-local/setup/runbook/docs-api-contract，明确正式 transport、兼容 transport、关闭条件和 repo-root 验证命令。
- 确认前端对 session expired / unauthorized 的处理仍走统一 `authHandler`。
  - Files: `docs/setup/auth-local.md`, `docs/api-contract/websocket.md`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `web/src/lib/auth-handler.ts`
  - Verify: rg -n "Authorization|query token|cookie|CSRF|shared password|session expired" docs/setup/auth-local.md docs/api-contract/websocket.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/lib/auth-handler.ts

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/common/auth/service.py
- backend/src/common/auth/api.py
- backend/src/sales_bot/websocket/router.py
- web/src/lib/auth-handler.ts
- web/src/hooks/use-auth-protection.ts
- backend/src/main.py
- backend/src/presentation_coach/websocket
- web/src/hooks/use-practice-websocket.ts
- web/src/lib/api/client.ts
- docs/setup/auth-local.md
- docs/api-contract/websocket.md
