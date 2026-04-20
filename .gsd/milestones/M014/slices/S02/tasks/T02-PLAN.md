---
estimated_steps: 7
estimated_files: 5
skills_used: []
---

# T02: 把 forgot/reset 升级为正式 auth seam

Why: backend auth seam 必须先正式化，前端 profile/forgot/reset 才有稳定依赖面。

Do:
1. 正式化 password reset token 存储、过期处理和一次性消费逻辑。
2. 抽出 email delivery seam 和 rate limit 策略，但不强接外部邮件平台。
3. 加 migration，移除 request-path DDL 或其他过渡实现。
4. 保持现有登录兼容路径和 focused auth tests 可继续证明。

Done when: forgot/reset 有正式持久化与 lifecycle contract，且 focused backend auth proof 通过。

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

password reset token 生命周期与拒绝路径可被 focused auth tests 和持久化表面回查。
