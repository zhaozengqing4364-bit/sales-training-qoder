---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 收口 admin 权限与敏感日志高风险出口

在高风险 admin APIs 和日志出口上落实权限/脱敏规则，优先处理 token、password、cookie、email 全量输出风险。

## Inputs

- `backend/src/admin/api/*`
- `backend/src/common/monitoring/*`
- `backend/src/common/auth/*`

## Expected Output

- `backend/src/admin/api/*`
- `backend/src/common/monitoring/*`
- `backend/src/common/auth/*`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q

## Observability Impact

sensitive-field redaction active
