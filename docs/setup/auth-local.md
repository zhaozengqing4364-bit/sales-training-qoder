# 本地认证配置指南

本页记录当前仓库在 `M020/S01` 的 auth authority，目标是把“正式 transport / 兼容 transport / 关闭条件 / repo-root 验证命令”写成可执行 runbook，而不是散落在代码与测试里的隐含知识。

## 1) 当前 authority matrix

| Surface | 正式 authority | 兼容 authority | 当前说明 |
|---|---|---|---|
| HTTP API | `Authorization: Bearer <jwt>`、`HttpOnly session cookie` + `X-CSRF-Token`（unsafe cookie-backed requests） | 无 | `backend/src/common/auth/service.py::resolve_bearer_or_cookie_token()` 是当前唯一 HTTP auth resolver；浏览器主链通过 `web/src/lib/api/client.ts` 默认 `credentials: "include"`，并在带 session cookie 的 unsafe 请求上自动附带 `X-CSRF-Token`。非 development 环境会强制把 session / CSRF cookie 标记为 `Secure`。 |
| WebSocket | `Authorization` header、session cookie | `?token=` query token | sales / presentation websocket 都复用 `resolve_websocket_auth(...)` / `resolve_websocket_token(...)`；当前 shipped 顺序已收口为 `Authorization -> session cookie -> query token compatibility`，query token 仍是**活跃兼容路径**，但已明确降为 compatibility-only。 |
| 登录凭证 | `User.hashed_password` | 无 | 密码登录只接受受管用户哈希；临时密码只获得 password-change scope。已有 env shared password 值保留但不会被读取。 |

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

## 3) 本地受管密码

本地账号也必须拥有自己的受管密码。可通过 bootstrap 参数或环境变量提供：

```bash
cd backend
BOOTSTRAP_ADMIN_PASSWORD='<至少 8 个字符的本地密码>' \
  python scripts/bootstrap_auth_admin.py --email admin@qoder.ai --name 管理员
```

规则：

- 不提供密码时会生成一次性临时密码，只在终端输出一次，并要求首次修改；
- 明确提供密码时创建 active 本地凭证；
- 无 `hashed_password` 的账号统一按无效凭证处理，不回退到环境共享密码；
- `AUTH_SHARED_PASSWORD` / `AUTH_USER_PASSWORDS_JSON` 可以暂时保留在既有 Secret 中，但不会影响登录结果。

## 4) 浏览器 / API / WebSocket 调用约定

### 浏览器 HTTP 主链
- 浏览器页面默认通过 `web/src/lib/api/client.ts` 发请求，并自动携带 `credentials: "include"`；
- 远程开发环境中，浏览器必须请求前端同源的 `http://<当前页面主机>:3445/api/v1`。`web/next.config.ts` 将 `/api/v1/*` 转发到 `SERVER_API_URL`（本机默认 `http://127.0.0.1:3444/api/v1`），并将 `/health` 转发到同一后端；不要再要求远程浏览器直接开放或访问 `3444`；
- 推荐开发配置为 `NEXT_PUBLIC_API_URL=http://localhost:3445/api/v1` 与 `SERVER_API_URL=http://127.0.0.1:3444/api/v1`。前者会按浏览器当前主机解析，后者只供 Next.js 服务端和 rewrite 使用；这样 session cookie 与 SSR 路由守卫始终处于同一主机边界；
- 登录页会先读取 `GET /api/v1/auth/providers`，只在 provider 明确可用时暴露 WeCom CTA；
- 对带 session cookie 的 unsafe 请求（如 logout），client 会自动附带 `X-CSRF-Token`，并与 `app_csrf` cookie 做双提交校验；
- 401 由统一 transport seam 触发 `authHandler.sessionExpired()`，而不是页面各自弹错或各自跳转；
- login / logout / forgot-password / reset-password 这些 auth 自身接口显式设置 `skipSessionExpiredHandling: true`，避免把“登录失败”误当成“会话过期”。

### API / 脚本调用
- 非浏览器调用优先使用 `Authorization: Bearer <jwt>`；
- 若必须触发真实企业微信登录，请从浏览器打开 `/api/v1/auth/wecom/start`，不要在前端自行拼接第三方 OAuth URL；
- 不要依赖 localStorage token 约定，仓库当前前端主链已经是 cookie-session + centralized auth handler。

### WebSocket 调用
- 远程浏览器默认连接当前前端同源的 `ws(s)://<当前页面主机>/ws/*`，由 Next.js 转发到内部后端；`NEXT_PUBLIC_WS_URL` 推荐配置为 `ws://localhost:3445`，运行时会按当前页面主机、端口和 HTTP/HTTPS 协议解析；
- 浏览器主链：优先复用 session cookie；前端 websocket hook 已不再默认把 `token=` 拼进 URL；
- 非浏览器 / 明确 bearer caller：使用 `Authorization: Bearer <jwt>`；
- `?token=` 仅允许作为 legacy compatibility transport；新调用方不要新增该依赖。

## 5) 兼容路径状态

### shared password / user-password env

运行时兼容路径已退役。配置值是否从 Secret 管理系统移除是独立的运维清理动作，不得通过 reset 自动删除；无论值是否存在，都不再具有认证意义。

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
- schema authority 只有 Alembic；应用启动只读校验 head，旧库统一从首发 baseline 重建。

## 7) 启动后检查

后端启动日志只输出受管凭证 authority 和 WeCom provider 是否 configured，不输出明文口令、共享密码值、用户密码映射或 API key。

## 8) Repo-root 验证命令

在仓库根目录执行以下命令，验证 auth authority / compat / 前端 session-expired seam：

```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py -x -q
npm --prefix web test -- --run src/lib/api/client.auth.test.ts src/lib/auth-handler.test.ts
rg -n "Authorization|query token|cookie|CSRF|managed password|session expired" docs/setup/auth-local.md docs/api-contract/websocket.md web/src/lib/auth-handler.ts
```

如果这些 proof 与代码/文档描述不一致，应先修正文档 authority 或运行时，再继续后续安全切片。 
