---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: 为 admin security baseline 补 focused proof

Why: 权限矩阵和脱敏规则如果没有 focused proof，会在后续路由调整中很快漂移。

Do:
1. 补 focused tests/断言，锁定 admin 高风险接口的权限拒绝路径。
2. 为首批日志出口补脱敏行为 proof。
3. 形成最小 security baseline 说明，明确哪些已覆盖、哪些留待后续治理。

Done when: admin security baseline 既有 focused backend proof，也有清晰范围边界。

## Inputs

- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/unit/admin/test_admin_users_api_models.py`

## Expected Output

- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/unit/admin/test_admin_users_api_models.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q

## Observability Impact

admin 权限/脱敏回归可由 focused backend proof 直接发现。
