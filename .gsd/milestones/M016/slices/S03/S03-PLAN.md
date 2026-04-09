# S03: RBAC、敏感日志与 admin 安全面 audit

**Goal:** 为 admin routes 的权限粒度与日志脱敏建立明确的风险图谱，并先修高确定性问题
**Demo:** After this: admin 高风险接口有权限证明，日志敏感字段脱敏规则落到高风险出口

## Tasks
- [ ] **T01: 建立 admin 权限矩阵与敏感日志出口清单** — 建立 admin route permission matrix，按接口列出访问角色、拒绝路径和当前证据；同时扫描 logger/middleware/helper 中可能输出 token/password/cookie/email 的高风险点。
  - Estimate: 40m
  - Files: backend/src/admin/api/*, backend/src/common/monitoring/*
  - Verify: rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth
- [ ] **T02: 收口 admin 权限与敏感日志高风险出口** — 在高风险 admin APIs 和日志出口上落实权限/脱敏规则，优先处理 token、password、cookie、email 全量输出风险。
  - Estimate: 1h
  - Files: backend/src/admin/api/*, backend/src/common/monitoring/*, backend/src/common/auth/*
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q
- [ ] **T03: 为 admin security baseline 补 focused proof** — 补 focused tests / assertions，锁定 admin 高风险接口的权限拒绝与日志脱敏行为，并形成最小审计日志策略说明。
  - Estimate: 40m
  - Files: backend/tests/integration/test_admin_users_api.py, backend/tests/unit/admin/test_admin_users_api_models.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q
