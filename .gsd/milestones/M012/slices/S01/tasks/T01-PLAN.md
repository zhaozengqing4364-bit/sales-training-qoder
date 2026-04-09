---
estimated_steps: 8
estimated_files: 3
skills_used: []
---

# T01: 忘记密码后端 API

后端：新增 PasswordResetToken 模型、Alembic migration、forgot-password/reset-password 服务和路由。Token 有效期 30 分钟、一次性使用。邮件服务抽象为接口，本地开发用 console 打印 mock。Rate limit 1次/分钟/IP。

Steps:
1. 在 models.py 新增 PasswordResetToken 模型
2. 新增 Alembic migration
3. 在 services/ 下新增 password_reset.py 服务
4. 在 auth/api.py 新增 forgot-password 和 reset-password 路由
5. 新增 EmailService 抽象接口
6. 编写 pytest contract tests

## Inputs

- `backend/src/common/db/models.py`
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`

## Expected Output

- `backend/src/common/db/models.py`
- `backend/alembic/versions/*_password_reset_token.py`
- `backend/src/common/services/password_reset.py`
- `backend/src/common/auth/api.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q

## Observability Impact

Password reset token creation/use logged with user_id, no token value in logs
