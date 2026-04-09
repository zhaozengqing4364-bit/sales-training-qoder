---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: 把 forgot/reset 升级为正式 auth seam

正式化 password reset token 存储、过期/一次性使用、email abstraction 与 rate limit；补 migration，并保持现有登录路径兼容。

## Inputs

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`
- `backend/tests/integration/test_auth_login_api.py`

## Expected Output

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`
- `backend/alembic/versions/*`
- `backend/tests/integration/test_auth_login_api.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

## Observability Impact

token 生命周期、过期、一次性使用、rate limit 事件
