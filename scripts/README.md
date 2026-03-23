# Development Scripts

## 一键启动开发环境（无 Docker）

```bash
bash scripts/dev-up.sh
```

默认行为：
- 自动读取 `backend/.env` 与 `web/.env.local`
- 默认清理 `3444,3445`，并在 `DATABASE_URL/REDIS_URL` 指向本机时额外清理 `5432,6379`
- 自动拉起 PostgreSQL / Redis（`brew services`）
- 启动 Backend（`uvicorn`）和 Frontend（`next dev`）

## 一键停止开发环境

```bash
bash scripts/dev-stop.sh
```

可选停止基础服务：

```bash
STOP_INFRA=1 bash scripts/dev-stop.sh
```

## 安装仓库级 Git hooks

```bash
bash scripts/setup-git-hooks.sh
```

当前会安装 repo 内置 `.githooks/pre-commit`，用于：
- 把 `.gsd/completed-units.json` 规范化成低冲突的多行 JSON
- 阻止在默认分支（例如 `001-ai-practice-system` / `main`）直接提交 `.gsd/milestones/*/slices/Sxx/**` slice 文件

## 常用环境变量

- `BACKEND_PORT` / `FRONTEND_PORT`
- `POSTGRES_PORT` / `REDIS_PORT`
- `PORTS_TO_CLEAN`（逗号分隔）
- `AUTO_START_INFRA`（`1` 或 `0`）
- `DATABASE_URL` / `REDIS_URL`
- `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`
