# S03: RBAC、敏感日志与 admin 安全面 audit

**Goal:** 为 admin routes 的权限粒度与日志脱敏建立明确的风险图谱，并先修高确定性问题。
**Demo:** admin 高风险接口有权限证明，日志敏感字段脱敏规则落到高风险出口。

## Must-Haves

- admin 高风险接口有明确的角色边界与 focused 权限 proof。
- token/password/cookie/email 等敏感字段在首批高风险日志出口上有脱敏规则。
- security baseline 只覆盖高风险 surface，不扩成一次性全仓审计。

## Proof Level

- This slice proves: integration

## Integration Closure

S03 把 M016 前两块 auth/error contract 工作推进到 admin 高风险 route family 与日志出口，形成后续治理可直接复用的 security baseline。

## Verification

- future agents 可通过 admin 权限矩阵、敏感日志出口清单和 focused backend proof 快速判断问题出在权限边界还是日志策略。

## Tasks

- [ ] **T01: 建立 admin 权限矩阵与敏感日志出口清单** `est:40m`
  Why: 先建立权限矩阵和敏感日志出口清单，才能避免 S03 变成盲扫 backend 的长期审计工程。

Do:
1. 建立 admin route permission matrix，列出接口、角色、拒绝路径和当前证据。
2. 扫描 logger/middleware/helper 中可能输出 token/password/cookie/email 的高风险点。
3. 标记最先处理的一组高风险 surface。

Done when: 后续修复有明确高风险目标，不需要继续扩大扫描范围。
  - Files: `backend/src/admin/api/*`, `backend/src/common/monitoring/*`, `backend/src/common/auth/*`
  - Verify: rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth

- [ ] **T02: 收口 admin 权限与敏感日志高风险出口** `est:1h`
  Why: S03 需要先在最确定、最危险的出口上落权限和脱敏规则，才能把安全风险从 audit 语言变成真实收口。

Do:
1. 在高风险 admin APIs 上落实权限边界或拒绝路径。
2. 在高风险日志出口上增加 token/password/cookie/email 的脱敏规则。
3. 保持与现有 auth/error contract 一致，不做新的 page-local 或 route-local 特例体系。

Done when: 首批高风险 admin APIs 和日志出口的 focused backend proof 通过。
  - Files: `backend/src/admin/api/*`, `backend/src/common/monitoring/*`, `backend/src/common/auth/*`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q

- [ ] **T03: 为 admin security baseline 补 focused proof** `est:40m`
  Why: 权限矩阵和脱敏规则如果没有 focused proof，会在后续路由调整中很快漂移。

Do:
1. 补 focused tests/断言，锁定 admin 高风险接口的权限拒绝路径。
2. 为首批日志出口补脱敏行为 proof。
3. 形成最小 security baseline 说明，明确哪些已覆盖、哪些留待后续治理。

Done when: admin security baseline 既有 focused backend proof，也有清晰范围边界。
  - Files: `backend/tests/integration/test_admin_users_api.py`, `backend/tests/unit/admin/test_admin_users_api_models.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q

## Files Likely Touched

- backend/src/admin/api/*
- backend/src/common/monitoring/*
- backend/src/common/auth/*
- backend/tests/integration/test_admin_users_api.py
- backend/tests/unit/admin/test_admin_users_api_models.py
