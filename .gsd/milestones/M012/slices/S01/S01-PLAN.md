# S01: 认证与首页修复

**Goal:** 修复认证层缺失功能和首页硬编码问题，让用户能自助重置密码，登录后首页显示真实个人信息。
**Demo:** After this: 用户可自助登录、重置密码，首页显示真实用户名和动态版本号，企业微信按钮已标注即将支持

## Tasks
- [x] **T01: Added a real forgot/reset-password backend flow with persisted reset tokens, user-specific password login, rate limiting, migration support, and contract tests.** — 后端：新增 PasswordResetToken 模型、Alembic migration、forgot-password/reset-password 服务和路由。Token 有效期 30 分钟、一次性使用。邮件服务抽象为接口，本地开发用 console 打印 mock。Rate limit 1次/分钟/IP。

Steps:
1. 在 models.py 新增 PasswordResetToken 模型
2. 新增 Alembic migration
3. 在 services/ 下新增 password_reset.py 服务
4. 在 auth/api.py 新增 forgot-password 和 reset-password 路由
5. 新增 EmailService 抽象接口
6. 编写 pytest contract tests
  - Estimate: 2h
  - Files: backend/src/common/db/models.py, backend/src/common/services/password_reset.py, backend/src/common/auth/api.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q
- [ ] **T02: 忘记密码前端流程** — 前端：在登录页添加'忘记密码？'链接，新建 forgot-password 和 reset-password 页面，表单校验完整。

Steps:
1. 登录页 email+password 表单下方添加'忘记密码？'链接
2. 新建 forgot-password 页面：email 输入 → 调用 API → 成功提示
3. 新建 reset-password 页面：token + 新密码 + 确认密码 → 调用 API → 跳转登录
4. 在 api client 添加对应方法
5. 表单校验：密码最小长度 8 位、两次输入一致
  - Estimate: 1.5h
  - Files: web/src/app/(auth)/login/page.tsx, web/src/app/(auth)/forgot-password/page.tsx, web/src/app/(auth)/reset-password/page.tsx, web/src/lib/api/client.ts
  - Verify: npm --prefix web test -- --run login
- [ ] **T03: 首页硬编码用户名和版本号修复** — 首页修复：将'早安，亚历山大'改为读 currentUser 真实姓名，问候语根据时段动态切换，版本号从 package.json 动态读取，移除硬编码日期。

Steps:
1. 首页从 useCurrentUser hook 读取真实用户名
2. 根据时段切换早安/午安/晚安
3. 无姓名 fallback 到 email 前缀
4. 版本号从 package.json version 读取
5. 移除硬编码的 2026年1月10日
  - Estimate: 1h
  - Files: web/src/app/(dashboard)/page.tsx
  - Verify: npm --prefix web test -- --run dashboard
- [ ] **T04: 企业微信按钮处理** — 将企业微信登录按钮改为 disabled 状态并添加提示，或完全移除。确保视觉上明确标识为不可用。

Steps:
1. 将企业微信按钮改为 disabled
2. 添加 title='即将支持，敬请期待' 提示
3. 视觉上降低对比度表示不可用
  - Estimate: 30m
  - Files: web/src/app/(auth)/login/page.tsx
  - Verify: npm --prefix web test -- --run login
