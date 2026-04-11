# S01: Password reset / auth backend 正式化

**Goal:** 把当前 password reset 和 auth 实现从“演示可用”升级为“正式 contract 可维护”。
**Demo:** forgot/reset 走正式 token 持久化与 lifecycle contract，现有登录兼容路径保持可证明。

## Must-Haves

- password reset token 有正式持久化模型、migration、一次性消费和过期处理。
- request-path DDL 或其他过渡 auth recovery 实现被移除。
- focused auth proof 能覆盖 forgot/reset 正向、过期、重复使用和兼容登录路径。

## Proof Level

- This slice proves: integration

## Integration Closure

S01 为 M016 后续错误契约与 admin 安全面收口提供稳定 auth seam，避免继续在请求路径和页面体验里维持过渡实现。

## Verification

- future agents 可通过 auth focused tests、migration 状态和 token 生命周期表面判断 forgot/reset 是否健康，而不是靠手动试页面。

## Tasks

- [x] **T01: 定位 password reset 正式化的最窄接入点** `est:30m`
  Why: 先定位当前 forgot/reset 正式化的最窄接入点，避免在 auth seam 上做不必要的扩散式重构。

Do:
1. 盘点 forgot/reset 路径中的 runtime DDL、token 生命周期、email 发送与 rate limit 现状。
2. 找出正式模型、migration 和 email seam 的最小落点。
3. 明确现有登录兼容路径必须保持不变的部分。

Done when: 后续正式化改动有明确接入点，不需要边做边重新判断 auth seam。
  - Files: `backend/src/common/auth/api.py`, `backend/src/common/auth/service.py`, `backend/src/common/db/models.py`
  - Verify: rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py

- [ ] **T02: 实现正式 PasswordResetToken contract 与 migration** `est:1.5h`
  Why: token 持久化、一次性消费、过期处理和 rate limit 是 auth recovery seam 的核心 contract，必须先变成正式实现。

Do:
1. 新增或完善 PasswordResetToken 正式模型与 migration。
2. 实现一次性消费、过期校验与 rate limit 策略。
3. 抽出 EmailService seam，但不强行引入外部邮件供应商依赖。
4. 保持现有登录兼容路径可证明通过。

Done when: forgot/reset 有正式持久化和 lifecycle contract，focused backend auth tests 通过。
  - Files: `backend/src/common/auth/api.py`, `backend/src/common/auth/service.py`, `backend/src/common/db/models.py`, `backend/alembic/versions/*`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

- [ ] **T03: 为 auth recovery contract 补 focused proof** `est:45m`
  Why: S01 只有在 focused proof 能锁定 forgot/reset 全链路行为时才算真正闭合。

Do:
1. 补 focused tests，覆盖 forgot/reset 成功、过期、重复使用、rate limit 等路径。
2. 增加对 request-path DDL 已移除的约束性 proof。
3. 保持 auth proof 仍围绕 repo-root focused gate，不引入新的大而全测试入口。

Done when: auth recovery contract 的关键正负路径都有 focused proof，且回归命令稳定通过。
  - Files: `backend/tests/integration/test_auth_login_api.py`, `backend/tests/**/*reset*.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

## Files Likely Touched

- backend/src/common/auth/api.py
- backend/src/common/auth/service.py
- backend/src/common/db/models.py
- backend/alembic/versions/*
- backend/tests/integration/test_auth_login_api.py
- backend/tests/**/*reset*.py
