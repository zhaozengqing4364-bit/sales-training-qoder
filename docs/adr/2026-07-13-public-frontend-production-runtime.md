# ADR: 公网体验环境必须使用 Next.js 生产运行时

- 状态：Accepted
- 日期：2026-07-13

## 背景

公网 `3445` 曾由 `scripts/dev-up.sh` 以 `next dev` 启动。首次访问尚未编译的栏目时，
Turbopack 会即时编译路由并在页面左下角显示 `Rendering ...`。实测首次切换到训练、排行榜、
历史记录的 RSC 请求分别约为 2.15 秒、1.13 秒和 1.05 秒，其中 Next.js 开发运行时占
1.01–2.10 秒，应用代码只占 39–52 毫秒。

远程浏览器若直接请求后端 `3444`，还会依赖额外端口暴露，并使 host-only session cookie
与前端 SSR 路由守卫分属不同主机边界。实际观测中浏览器能连接公网前端 `3445`，但登录
请求无法建立到 `3444` 的连接，最终被前端 8 秒超时中止。

## 决策

- `scripts/dev-up.sh` 保持 `development` 默认值，用于本地热更新和 smoke。
- 新增 `scripts/app-up.sh` 作为共享体验和公网入口，固定 `FRONTEND_MODE=production`。
- 前端运行命令集中到 `scripts/frontend-runtime.sh`：生产模式先 `next build`，再 `next start`；
  开发模式继续 `next dev`。
- 公网运行不得通过隐藏开发指示器来掩盖即时编译，必须消除开发运行时本身。
- 浏览器 HTTP 与 WebSocket 统一使用前端同源 `3445`：`/api/v1/*` 和 `/health` 由 Next.js
  rewrite 转发到 `SERVER_API_URL` 指向的内部后端；WebSocket upgrade 沿 `/ws/*`
  路径转发。浏览器不再需要直接访问 `3444`。
- `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` 只描述浏览器同源入口；Next.js 服务端认证和
  rewrite 使用 `SERVER_API_URL`，默认 `http://127.0.0.1:3444/api/v1`。

## 结果

- 生产基线同一组栏目首轮内容稳定时间为 63–186 毫秒，P95 为 266 毫秒。
- `Rendering ...` 观测从开发模式的 3/10 次降为生产模式的 0/10 次。
- 后端认证、页面 API、权限边界和数据库模型均不变。
- session / CSRF cookie 与前端页面保持同一主机；刷新后的 SSR 路由守卫可继续解析会话。
- 发布前需要完成 production build；构建失败时服务不会启动旧的新进程。

## 回滚

本地调试可继续执行 `bash scripts/dev-up.sh`。若生产构建临时阻塞共享环境，可显式使用
`FRONTEND_MODE=development bash scripts/dev-up.sh` 回退，但该模式不得视为正式公网运行状态。
