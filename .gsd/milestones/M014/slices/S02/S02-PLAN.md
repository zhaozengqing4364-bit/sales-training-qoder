# S02: 认证与个人中心体验补齐

**Goal:** 把 learner 侧“能登录”提升到“能维护账号”：forgot/reset 正式化、profile 修改密码体验闭合、语速偏好持久化补齐
**Demo:** After this: 用户可从 profile 走到正式修改密码路径，语速偏好刷新后保留，forgot/reset 体验完整

## Tasks
- [ ] **T01: 盘点现有 forgot/reset、profile 修改密码与语速偏好现状** — 梳理现有 forgot/reset 前后端路径、profile 修改密码入口和语速偏好存储现状，确认哪些是过渡实现，哪些可以沿用。
  - Estimate: 30m
  - Files: web/src/app/(auth)/*, web/src/app/(dashboard)/profile/page.tsx, backend/src/common/auth/api.py, backend/src/common/auth/service.py
  - Verify: rg -n "forgot|reset|password|speech|rate|window.location" web/src/app/\(auth\) web/src/app/\(dashboard\)/profile backend/src/common/auth
- [ ] **T02: 把 forgot/reset 升级为正式 auth seam** — 正式化 password reset token 存储、过期/一次性使用、email abstraction 与 rate limit；补 migration，并保持现有登录路径兼容。
  - Estimate: 1.5h
  - Files: backend/src/common/auth/api.py, backend/src/common/auth/service.py, backend/src/common/db/models.py, backend/alembic/versions/*, backend/tests/integration/test_auth_login_api.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
- [ ] **T03: 闭合 profile 修改密码与语速偏好体验** — 收口前端 auth/profile 体验：profile 内改为正式修改密码路径，去掉 window.location 跳转；语速偏好接到真实存储或明确隐藏/移除；补 focused tests。
  - Estimate: 1h
  - Files: web/src/app/(auth)/*, web/src/app/(dashboard)/profile/page.tsx, web/src/app/(auth)/login/page.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"
