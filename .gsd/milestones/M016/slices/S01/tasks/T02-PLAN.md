---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: 实现正式 PasswordResetToken contract 与 migration

新增/完善 PasswordResetToken 正式模型、migration、一次性消费与过期校验逻辑，抽出 EmailService seam 和 rate limit 策略。保持现有登录兼容。

## Inputs

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`

## Expected Output

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`
- `backend/alembic/versions/*`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

## Observability Impact

token lifecycle / rate limit signals
