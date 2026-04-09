# S01: Password reset / auth backend 正式化

**Goal:** 把当前 password reset 和 auth 实现从“演示可用”升级为“正式 contract 可维护”
**Demo:** After this: forgot/reset 走正式 token 持久化与 lifecycle contract，现有登录兼容路径保持可证明

## Tasks
- [ ] **T01: 定位 password reset 正式化的最窄接入点** — 盘点当前 forgot/reset 路径中的 runtime DDL、token 生命周期、email 发送与 rate limit 现状，确认正式模型和 migration 的最窄接入点。
  - Estimate: 30m
  - Files: backend/src/common/auth/api.py, backend/src/common/auth/service.py, backend/src/common/db/models.py
  - Verify: rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py
- [ ] **T02: 实现正式 PasswordResetToken contract 与 migration** — 新增/完善 PasswordResetToken 正式模型、migration、一次性消费与过期校验逻辑，抽出 EmailService seam 和 rate limit 策略。保持现有登录兼容。
  - Estimate: 1.5h
  - Files: backend/src/common/auth/api.py, backend/src/common/auth/service.py, backend/src/common/db/models.py, backend/alembic/versions/*
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
- [ ] **T03: 为 auth recovery contract 补 focused proof** — 补 focused tests 覆盖 forgot/reset 成功、过期、重复使用、rate limit 等路径，确认 request-path DDL 已移除。
  - Estimate: 45m
  - Files: backend/tests/integration/test_auth_login_api.py, backend/tests/**/*reset*.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
