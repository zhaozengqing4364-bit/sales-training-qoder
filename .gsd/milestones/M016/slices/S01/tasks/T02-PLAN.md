---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T02: 实现正式 PasswordResetToken contract 与 migration

Why: token 持久化、一次性消费、过期处理和 rate limit 是 auth recovery seam 的核心 contract，必须先变成正式实现。

Do:
1. 新增或完善 PasswordResetToken 正式模型与 migration。
2. 实现一次性消费、过期校验与 rate limit 策略。
3. 抽出 EmailService seam，但不强行引入外部邮件供应商依赖。
4. 保持现有登录兼容路径可证明通过。

Done when: forgot/reset 有正式持久化和 lifecycle contract，focused backend auth tests 通过。

## Inputs

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`
- `backend/alembic/versions/*`

## Expected Output

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`
- `backend/alembic/versions/*`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

## Observability Impact

password reset token 生命周期和拒绝路径可通过数据库与 focused tests 共同回查。
