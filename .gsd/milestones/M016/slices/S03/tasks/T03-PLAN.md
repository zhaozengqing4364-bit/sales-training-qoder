---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: 为 admin security baseline 补 focused proof

补 focused tests / assertions，锁定 admin 高风险接口的权限拒绝与日志脱敏行为，并形成最小审计日志策略说明。

## Inputs

- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/unit/admin/test_admin_users_api_models.py`

## Expected Output

- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/unit/admin/test_admin_users_api_models.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q

## Observability Impact

permission / redaction proof
