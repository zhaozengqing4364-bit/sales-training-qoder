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

## Smoke baseline：一键启动最小全栈验收环境

```bash
bash scripts/dev-smoke-up.sh
```

该入口建立在现有 `scripts/dev-up.sh` 之上，只补齐 smoke 需要的最小约定：
- 固定本地 smoke 管理员账号：`admin@qoder.ai`
- 固定本地 smoke 密码：`change-me`（可通过 `SMOKE_ADMIN_PASSWORD` 覆盖）
- 启动后自动执行 `backend/scripts/bootstrap_auth_admin.py`，确保 admin 路由可进入
- 记录 PostgreSQL / Redis 是否原本已在运行，供 teardown 时避免误停用户已有本地依赖
- `http://localhost:3444/health` 现在返回稳定的 machine-readable readiness payload（包含 `ready=true` 与 `readiness=ready`），供 smoke/轮询脚本直接消费

对应停止命令：

```bash
bash scripts/dev-smoke-stop.sh
```

## Playwright smoke：最小关键流

在仓库根目录或单独终端中运行：

```bash
cd web && npx playwright test
```

当前 smoke 现在覆盖 8 条关键流：
- login
- dashboard
- training entry
- practice session smoke
- report smoke
- replay smoke
- admin analytics smoke
- support/runtime smoke

Playwright 会通过 `web/playwright.config.ts` 的 global setup/teardown 自动调用 `scripts/dev-smoke-up.sh` / `scripts/dev-smoke-stop.sh`，因此无需额外手动拉起测试栈。

默认使用下列环境变量（必要时可覆盖）：
- `SMOKE_ADMIN_EMAIL`
- `SMOKE_ADMIN_PASSWORD`
- `SMOKE_WEB_BASE_URL`
- `SMOKE_BACKEND_BASE_URL`

HTML 报告默认输出到：
- `.sisyphus/evidence/task-9-playwright-report/`

## 一键质量门禁（本地 / CI 共用）

```bash
bash scripts/critical-quality-gate.sh
```

固定顺序：
1. secret / environment checks
2. backend ruff
3. web typecheck
4. web lint
5. vitest coverage gate
6. dev smoke stack + DB ready + `alembic upgrade head` + smoke bootstrap / seed
7. Playwright smoke matrix
8. Playwright newcomer closed-loop E2E
9. Playwright presentation / sales Phase 4 E2E
10. optional real-provider focused gates
11. backend newcomer coverage + mypy
12. backend targeted tests + smoke regression

说明：
- 这里的 Playwright 包含 smoke matrix、新人训练 closed-loop E2E 以及 presentation/sales Phase 4 E2E；真实 provider 仍由专项模式或显式开关验证。
- 默认门禁使用 deterministic local provider，不依赖外部 StepFun 或真实 LLM；真实 provider 由 release/nightly 专项模式验证。
- realtime 真实 provider 专项模式默认不会在缺凭证时通过；会输出 classified skip 证据并失败。只有人工明确设置 `NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1` 时，缺凭证才可作为可追踪跳过项通过；发布前仍可用 `NEWCOMER_REAL_PROVIDER_REQUIRED=1` 强制缺凭证失败。
- AI Coach 真实 provider 专项模式同样默认 fail-closed；缺 `LLM_API_KEY` / `OPENAI_API_KEY` 时会输出 classified skip 证据并失败，只有人工明确设置 `NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1` 才允许可追踪跳过。

真实 provider release/nightly 专项模式：

先运行不联网的 StepFun Realtime 预检；该脚本不会打印 `STEPFUN_API_KEY`：

```bash
python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env
```

若继续强制真实 provider gate：

```bash
CRITICAL_GATE_MODE=newcomer-real-provider \
NEWCOMER_REAL_PROVIDER_NAME=stepfun_realtime \
STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime \
STEPFUN_API_KEY=... \
bash scripts/critical-quality-gate.sh
```

人工允许缺凭证跳过时必须显式设置：

```bash
CRITICAL_GATE_MODE=newcomer-real-provider \
NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1 \
bash scripts/critical-quality-gate.sh
```

脚本会把完整输出保存到：
- `.sisyphus/evidence/task-9-newcomer-real-provider-gate.txt`
- `.sisyphus/evidence/newcomer-real-provider-gate.json`（仅真实 provider 专项模式或显式开启时生成）

AI Coach 真实 LLM provider release/nightly 专项模式：

```bash
CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider \
LLM_API_KEY=... \
LLM_PROVIDER=openai \
LLM_BASE_URL=https://api.openai.com/v1 \
LLM_MODEL=gpt-4o-mini \
bash scripts/critical-quality-gate.sh
```

人工允许缺凭证跳过时必须显式设置：

```bash
CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider \
NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1 \
bash scripts/critical-quality-gate.sh
```

脚本会把 AI Coach 真实 provider 证据保存到：
- `.sisyphus/evidence/task-9-newcomer-ai-coach-real-provider-gate.txt`
- `.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json`
- `.sisyphus/evidence/newcomer-ai-coach-real-provider-runtime-audit.json`

Playwright 报告会输出到：
- `.sisyphus/evidence/task-9-playwright-report/`
- `.sisyphus/evidence/task-9-playwright-report.html`

## Project governance checkpoint 证据流

```bash
bash scripts/project-governance-checkpoint.sh dry-checkpoint \
  .omo/evidence/project-governance-refactor/task-4-dry-checkpoint.txt
```

该脚本只负责保存治理重构每轮的轻量 checkpoint 输出，以及在 full gate 已运行后镜像 `.sisyphus/evidence/task-9-quality-gate.txt`：

```bash
bash scripts/project-governance-checkpoint.sh mirror-quality-gate
```

完整发布门禁仍然只有 `bash scripts/critical-quality-gate.sh`。配套证据命名和镜像规则见 `docs/architecture/project-governance-checkpoints.md`。

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

## 依赖治理 baseline

```bash
bash scripts/dependency-governance.sh status
```

配套文档见 `docs/setup/dependency-governance-baseline.md`。
当前脚本提供：
- `status`：输出当前依赖治理权威文件与前置条件阻塞项
- `web-audit`：执行 `npm audit --prefix web`
- `backend-audit`：在 `pip_audit` 已安装时对 `backend/requirements.txt` 执行扫描
- `license-plan`：输出当前批准使用的 license scan 命令与缺失前置条件

## 备份 / 恢复现状基线

当前仓库内可直接引用的 backup / recovery 现状清单见：

- `docs/setup/backup-recovery-current-state.md`

这份文档只记录当前真实可执行的入口、路径和缺口，用作后续 runbook 编写基线。

## 常用环境变量

- `BACKEND_PORT` / `FRONTEND_PORT`
- `POSTGRES_PORT` / `REDIS_PORT`
- `PORTS_TO_CLEAN`（逗号分隔）
- `AUTO_START_INFRA`（`1` 或 `0`）
- `DATABASE_URL` / `REDIS_URL`
- `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`
