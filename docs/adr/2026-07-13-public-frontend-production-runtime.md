# ADR: 公网体验环境必须使用 Next.js 生产运行时

- 状态：Accepted
- 日期：2026-07-13

## 背景

公网 `3445` 曾由 `scripts/dev-up.sh` 以 `next dev` 启动。首次访问尚未编译的栏目时，
Turbopack 会即时编译路由并在页面左下角显示 `Rendering ...`。实测首次切换到训练、排行榜、
历史记录的 RSC 请求分别约为 2.15 秒、1.13 秒和 1.05 秒，其中 Next.js 开发运行时占
1.01–2.10 秒，应用代码只占 39–52 毫秒。

## 决策

- `scripts/dev-up.sh` 保持 `development` 默认值，用于本地热更新和 smoke。
- 新增 `scripts/app-up.sh` 作为共享体验和公网入口，固定 `FRONTEND_MODE=production`。
- 前端运行命令集中到 `scripts/frontend-runtime.sh`：生产模式先 `next build`，再 `next start`；
  开发模式继续 `next dev`。
- 公网运行不得通过隐藏开发指示器来掩盖即时编译，必须消除开发运行时本身。

## 结果

- 生产基线同一组栏目首轮内容稳定时间为 63–186 毫秒，P95 为 266 毫秒。
- `Rendering ...` 观测从开发模式的 3/10 次降为生产模式的 0/10 次。
- 后端认证、页面 API、权限边界和数据库模型均不变。
- 发布前需要完成 production build；构建失败时服务不会启动旧的新进程。

## 回滚

本地调试可继续执行 `bash scripts/dev-up.sh`。若生产构建临时阻塞共享环境，可显式使用
`FRONTEND_MODE=development bash scripts/dev-up.sh` 回退，但该模式不得视为正式公网运行状态。
