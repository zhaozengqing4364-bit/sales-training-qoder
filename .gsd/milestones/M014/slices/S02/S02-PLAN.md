# S02: 认证与个人中心体验补齐

**Goal:** 把 learner 侧“能登录”提升到“能维护账号”：forgot/reset 正式化、profile 修改密码体验闭合、语速偏好持久化补齐。
**Demo:** 用户可从 profile 走到正式修改密码路径，语速偏好刷新后保留，forgot/reset 体验完整

## Must-Haves

- 用户可从 profile 走到正式修改密码路径，不再依赖生硬跳转或假入口。
- forgot/reset 的前后端行为、token 生命周期与兼容登录路径都有 focused proof。
- 语速偏好刷新后保持稳定，若某项设置无法真实落地，则被诚实隐藏或移除。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 把 auth/profile 的体验闭环与 backend auth seam 接到一起，为 M014/S04 的 practice preflight 与中断 UX 提供稳定登录/偏好前提。

## Verification

- future agents 可通过 auth focused tests、profile 页面行为和语速偏好持久化表面判断登录恢复与 profile 体验是否健康，而不是只看页面文案。

## Tasks

- [x] **T01: 盘点现有 forgot/reset、profile 修改密码与语速偏好现状** `est:30m`
  Why: 先把 forgot/reset、profile 修改密码入口与语速偏好的当前真实表面盘清，避免把已存在能力和过渡实现混为一谈。

Do:
1. 梳理前端 auth 路由、profile 页面和 backend auth API/service 的现状。
2. 标出 forgot/reset 哪些已是正式能力、哪些仍是过渡实现。
3. 定位 profile 中修改密码入口和语速偏好的真实存储/恢复路径。
4. 记录仍在用 `window.location` 或静默容错的点。

Done when: 后续两项任务可以直接按现状差距动手，不需要再次做 auth/profile 范围摸底。
  - Files: `web/src/app/(auth)/*`, `web/src/app/(dashboard)/profile/page.tsx`, `backend/src/common/auth/api.py`, `backend/src/common/auth/service.py`
  - Verify: rg -n "forgot|reset|password|speech|rate|window.location" web/src/app/\(auth\) web/src/app/\(dashboard\)/profile backend/src/common/auth

- [ ] **T02: 把 forgot/reset 升级为正式 auth seam** `est:1.5h`
  Why: backend auth seam 必须先正式化，前端 profile/forgot/reset 才有稳定依赖面。

Do:
1. 正式化 password reset token 存储、过期处理和一次性消费逻辑。
2. 抽出 email delivery seam 和 rate limit 策略，但不强接外部邮件平台。
3. 加 migration，移除 request-path DDL 或其他过渡实现。
4. 保持现有登录兼容路径和 focused auth tests 可继续证明。

Done when: forgot/reset 有正式持久化与 lifecycle contract，且 focused backend auth proof 通过。
  - Files: `backend/src/common/auth/api.py`, `backend/src/common/auth/service.py`, `backend/src/common/db/models.py`, `backend/alembic/versions/*`, `backend/tests/integration/test_auth_login_api.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

- [ ] **T03: 闭合 profile 修改密码与语速偏好体验** `est:1h`
  Why: profile 修改密码与语速偏好必须落到真实可持续的前端体验，否则 S02 只会留下“后端更正式，但用户还在走假入口”。

Do:
1. 把 profile 中的修改密码动作接到正式路径，移除生硬的 `window.location` 跳转。
2. 把语速偏好接到真实存储/恢复路径；若某项设置无法真实落地，则隐藏或删除。
3. 补 focused tests，覆盖 login/profile 关键路径和偏好保留行为。
4. 保持 learner 文案诚实，不虚构未实现的账号设置能力。

Done when: profile 密码入口与语速偏好形成真实闭环，focused web proof 通过。
  - Files: `web/src/app/(auth)/*`, `web/src/app/(dashboard)/profile/page.tsx`, `web/src/app/(auth)/login/page.test.tsx`
  - Verify: npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"

## Files Likely Touched

- web/src/app/(auth)/*
- web/src/app/(dashboard)/profile/page.tsx
- backend/src/common/auth/api.py
- backend/src/common/auth/service.py
- backend/src/common/db/models.py
- backend/alembic/versions/*
- backend/tests/integration/test_auth_login_api.py
- web/src/app/(auth)/login/page.test.tsx
