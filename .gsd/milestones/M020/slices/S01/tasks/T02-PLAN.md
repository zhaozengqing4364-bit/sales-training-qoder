---
estimated_steps: 3
estimated_files: 7
skills_used: []
---

# T02: 收口 cookie、CSRF 与 websocket auth authority

- 在 backend/frontend 收口非开发环境 cookie secure 和 CSRF posture；若当前采用 same-site/cookie-only 策略，也要把 authority 写清并让失败信号显式化。
- websocket router 与 client 改为 header/cookie 优先，query token 退为受控兼容路径或移除。
- 为 shared-password 兼容态加显式诊断/退场策略，避免长期成为默认主路径。

## Inputs

- `T01 matrix`
- `current auth tests`

## Expected Output

- `backend/src/common/auth/service.py`
- `backend/src/common/auth/api.py`
- `backend/src/sales_bot/websocket/router.py`
- `web/src/hooks/use-practice-websocket.ts`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_password_reset_api.py backend/tests/integration/test_websocket_status_contract.py -x -q
