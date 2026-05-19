# 本地认证配置指南

本页记录当前仓库在 `M020/S01` 的 auth authority，目标是把“正式 transport / 兼容 transport / 关闭条件 / repo-root 验证命令”写成可执行 runbook，而不是散落在代码与测试里的隐含知识。

## 1) 当前 authority matrix

| Surface | 正式 authority | 兼容 authority | 当前说明 |
|---|---|---|---|
| HTTP API | `Authorization: Bearer <jwt>`、`HttpOnly session cookie` + `X-CSRF-Token`（unsafe cookie-backed requests） | 无 | `backend/src/common/auth/service.py::resolve_bearer_or_cookie_token()` 是当前唯一 HTTP auth resolver；浏览器主链通过 `web/src/lib/api/client.ts` 默认 `credentials: "include"`，并在带 session cookie 的 unsafe 请求上自动附带 `X-CSRF-Token`。非 development 环境会强制把 session / CSRF cookie 标记为 `Secure`。 |
| WebSocket | `Authorization` header、session cookie | `?token=` query token | sales / presentation websocket 都复用 `resolve_websocket_auth(...)` / `resolve_websocket_token(...)`；当前 shipped 顺序已收口为 `Authorization -> session cookie -> query token compatibility`，query token 仍是**活跃兼容路径**，但已明确降为 compatibility-only。 |
| 登录凭证 | `User.hashed_password` | `AUTH_USER_PASSWORDS_JSON`、`AUTH_SHARED_PASSWORD` | password reset 后的 `hashed_password` 是正式 authority；env password 只用于本地/兼容账号恢复，不是长期主路径。登录成功时会通过 `X-Auth-Authority` / `X-Auth-Compatibility-Mode` 暴露当前 authority。 |

## 2) WeCom SSO 配置

当环境已经配置真实企业微信 SSO 时，登录页会从 `GET /api/v1/auth/providers` 拉取状态，并把“企业微信登录 (WeCom)”按钮指向 `GET /api/v1/auth/wecom/start`。该起始端点会设置短时 OAuth state/return_to cookie，再由 `GET /api/v1/auth/wecom/callback` 完成 code 换取、用户映射和 session cookie 建立。

最小必填变量：

```env
WECHAT_CORP_ID=replace-with-corp-id
WECHAT_SECRET=replace-with-wechat-secret
WECHAT_AGENT_ID=replace-with-agent-id
AUTH_FRONTEND_BASE_URL=http://localhost:3445
```

说明：
- 也兼容 `WECOM_CORP_ID` / `WECOM_SECRET` / `WECOM_AGENT_ID` 这组三个别名；
- `AUTH_FRONTEND_BASE_URL` 决定 callback 成功/失败后浏览器回跳的前端地址；
- 非 development 环境若缺少上述 WeCom 变量，启动阶段会直接 fail closed，而不是把按钮伪装成可用。

## 3) 本地环境变量

在 `backend/.env`（或项目根 `.env`）中，至少保留一个兼容登录入口：

```env
AUTH_SHARED_PASSWORD=change-me
AUTH_USER_PASSWORDS_JSON={"admin@qoder.ai":"admin123","support@qoder.ai":"support123"}
```

规则：
- `AUTH_USER_PASSWORDS_JSON` 对命中邮箱优先；
- 未命中邮箱时回退到 `AUTH_SHARED_PASSWORD`；
- 两者都未配置时，`POST /api/v1/auth/login` 返回 `503 [AUTH_SERVICE_UNAVAILABLE]`；
- 一旦用户通过 reset-password 写入 `User.hashed_password`，该用户后续登录就应由 managed password authority 接管，而不是继续依赖 shared password。

## 4) 浏览器 / API / WebSocket 调用约定

### 浏览器 HTTP 主链
- 浏览器页面默认通过 `web/src/lib/api/client.ts` 发请求，并自动携带 `credentials: "include"`；
- 登录页会先读取 `GET /api/v1/auth/providers`，只在 provider 明确可用时暴露 WeCom CTA；
- 对带 session cookie 的 unsafe 请求（如 logout），client 会自动附带 `X-CSRF-Token`，并与 `app_csrf` cookie 做双提交校验；
- 401 由统一 transport seam 触发 `authHandler.sessionExpired()`，而不是页面各自弹错或各自跳转；
- login / logout / forgot-password / reset-password 这些 auth 自身接口显式设置 `skipSessionExpiredHandling: true`，避免把“登录失败”误当成“会话过期”。

### API / 脚本调用
- 非浏览器调用优先使用 `Authorization: Bearer <jwt>`；
- 若必须触发真实企业微信登录，请从浏览器打开 `/api/v1/auth/wecom/start`，不要在前端自行拼接第三方 OAuth URL；
- 不要依赖 localStorage token 约定，仓库当前前端主链已经是 cookie-session + centralized auth handler。

### WebSocket 调用
- 浏览器主链：优先复用 session cookie；前端 websocket hook 已不再默认把 `token=` 拼进 URL；
- 非浏览器 / 明确 bearer caller：使用 `Authorization: Bearer <jwt>`；
- `?token=` 仅允许作为 legacy compatibility transport；新调用方不要新增该依赖。

## 5) 兼容路径的关闭条件（off-ramp）

### shared password / user-password env 关闭条件
仅当以下条件同时满足时，才应移除 `AUTH_SHARED_PASSWORD` / `AUTH_USER_PASSWORDS_JSON`：
1. 目标账号都已通过 reset-password 写入 `User.hashed_password`；
2. `backend/tests/integration/test_auth_login_api.py` 中 managed password / forgot-password / reset-password 路径通过；
3. 运维 runbook 不再把 env shared password 当作日常登录入口，只保留 bootstrap/recovery 用途或彻底删除。

### websocket query token 关闭条件
仅当以下条件同时满足时，才应删除 websocket `?token=` 兼容：
1. web 主链与所有脚本调用都改为 `Authorization` header 或 session cookie；
2. `web/src/hooks/use-practice-websocket.ts` 不再生成 `token=`，且 focused tests 保持通过；
3. backend websocket contract proof 明确证明 query token 已降为兼容或已完全移除；
4. `docs/api-contract/websocket.md` 同步更新，不保留双重 authority。

## 9) Secret hygiene gate

Run this local/CI check before publishing release evidence:

```bash
bash scripts/secret-scan.sh
```

It scans tracked example/docs surfaces for obvious credential-shaped values and fails closed when a real-looking secret pattern is still present.

## 6) 初始化管理员账号

```bash
cd backend
python scripts/bootstrap_auth_admin.py --email admin@qoder.ai --name 管理员 --role admin
```

可选：

```bash
python scripts/bootstrap_auth_admin.py --email support@qoder.ai --name 支持工程师 --role support
```

说明：
- `bootstrap_auth_admin.py` 只负责账号引导，不拥有 schema authority；
- schema authority 仍在 Alembic / `init_db()` / `repair_legacy_schema.py` 这一条链上，不能把 auth bootstrap 误读为 DB 修复入口。

## 7) 启动后检查

后端启动日志会输出认证配置诊断（不含明文口令）：
- 是否配置 shared password；
- user override 条目数；
- override JSON 是否有效；
- login 能力是否 ready。

如果是非 development 环境，凭证缺失或 `AUTH_USER_PASSWORDS_JSON` 非法会直接阻断启动，而不是等到请求路径再隐式降级。

## 8) Repo-root 验证命令

在仓库根目录执行以下命令，验证 auth authority / compat / 前端 session-expired seam：

```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py -x -q
npm --prefix web test -- --run src/lib/api/client.auth.test.ts src/lib/auth-handler.test.ts
rg -n "Authorization|query token|cookie|CSRF|shared password|session expired" docs/setup/auth-local.md docs/api-contract/websocket.md web/src/lib/auth-handler.ts
```

如果这些 proof 与代码/文档描述不一致，应先修正文档 authority 或运行时，再继续后续安全切片。 
