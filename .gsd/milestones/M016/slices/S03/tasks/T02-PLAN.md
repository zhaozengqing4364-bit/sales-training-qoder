---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T02: 收口 admin 权限与敏感日志高风险出口

Why: S03 需要先在最确定、最危险的出口上落权限和脱敏规则，才能把安全风险从 audit 语言变成真实收口。

Do:
1. 在高风险 admin APIs 上落实权限边界或拒绝路径。
2. 在高风险日志出口上增加 token/password/cookie/email 的脱敏规则。
3. 保持与现有 auth/error contract 一致，不做新的 page-local 或 route-local 特例体系。

Done when: 首批高风险 admin APIs 和日志出口的 focused backend proof 通过。

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

权限拒绝与日志脱敏变成可测试、可追踪的 backend baseline。
