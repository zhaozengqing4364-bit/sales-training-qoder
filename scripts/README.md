# Development Scripts

## 一键启动开发环境（无 Docker）

```bash
bash scripts/dev-up.sh
```

默认行为：
- 自动读取 `backend/.env` 与 `web/.env.local`
- 默认清理 API/前端端口 `3444,3445`；显式启用 Worker/Dispatcher 时再清理 `3446/3447`。当
  `DATABASE_URL/REDIS_URL` 指向本机时，脚本还会管理 `5432,6379`
- 自动拉起 PostgreSQL / Redis（`brew services`）
- 启动 Backend（`uvicorn`）和 Frontend（`next dev`）；显式设置
  `TASK_WORKER_ENABLED=1` 时另起 Durable Task Worker，显式设置
  `OUTBOX_DISPATCHER_ENABLED=1` 时另起 Outbox Dispatcher
- Worker probe：`http://127.0.0.1:3446/live`、`/ready`、`/status`
- Dispatcher probe：`http://127.0.0.1:3447/live`、`/ready`、`/status`

Worker 默认并行数为 4，可用 `TASK_WORKER_MAX_PARALLELISM` 调整；用
`TASK_WORKER_TASK_TYPES=a.b,c.d` 限定本进程可领取的显式注册任务类型。临时只启动
API/前端时保持默认 `TASK_WORKER_ENABLED=0`。Slice 1 尚未接入业务 Handler，空 registry 会
fail closed；后续切片注册至少一个 Handler 后，可用
`TASK_WORKER_ENABLED=1 bash scripts/dev-up.sh` 一键同时启动。Worker 只在数据库 schema 已到 Alembic head、
任务类型配置有效且最近一次数据库维护/领取成功后返回 ready。

Outbox Dispatcher 默认同样关闭。生产进程必须由组合根显式配置真实 `EventTransport`，否则
fail closed。只做本地确定性联调时可显式使用不会外发事件的 fake：

```bash
ENVIRONMENT=development \
OUTBOX_DISPATCHER_ENABLED=1 \
OUTBOX_DISPATCHER_ALLOW_DEV_FAKE=1 \
bash scripts/dev-up.sh
```

fake 在 production 环境即使误开也会拒绝启动。`bash scripts/dev-stop.sh` 会先给 Worker 和
Dispatcher 发送 `SIGTERM`，等待在途任务/批次 drain，再清理进程和 probe 端口。

该入口只用于本地开发和自动化 smoke。`next dev` 会在首次访问路由时即时编译，并显示
Next.js 的 `Rendering ...` 开发指示器，不应作为公网运行方式。

## 一键启动公网体验环境（生产前端）

```bash
bash scripts/app-up.sh
```

该入口复用同一套后端、数据库和停止脚本，但前端会先执行 `next build`，再以 `next start`
启动。它不会显示开发指示器，也不会在用户首次点击栏目时临时编译路由。

- 公网或共享体验环境：使用 `bash scripts/app-up.sh`
- 需要前端热更新的本地开发：使用 `bash scripts/dev-up.sh`
- 两种模式统一使用 `bash scripts/dev-stop.sh` 停止
- 底层也可通过 `FRONTEND_MODE=production bash scripts/dev-up.sh` 显式选择生产前端

## Smoke baseline：一键启动最小全栈验收环境

```bash
bash scripts/dev-smoke-up.sh
```

该入口建立在现有 `scripts/dev-up.sh` 之上，只补齐 smoke 需要的最小约定：
- 固定本地 smoke 管理员账号：`admin@qoder.ai`
- 固定本地 smoke 密码：`change-me`（可通过 `SMOKE_ADMIN_PASSWORD` 覆盖）
- 启动后自动执行 `backend/scripts/bootstrap_auth_admin.py`，写入该账号自己的受管密码哈希；登录不依赖共享密码 fallback
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

Playwright 会通过 `web/playwright.config.ts` 的 global setup/teardown 自动调用 `scripts/dev-smoke-up.sh` / `scripts/dev-smoke-stop.sh`，因此无需额外手动拉起测试栈。Smoke 前端使用独立的 `web/.next-smoke` 构建目录，避免与 `app-up.sh` 的生产构建缓存交叉污染。

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
1. secret / environment checks 与 policy selector manifest；
2. backend ruff、architecture guard、OpenAPI parity、全量 `mypy src`；
3. backend `tests/unit tests/contract` 自动发现并启动 branch coverage；
4. web typecheck、lint、全量 Vitest coverage 自动发现；
5. dev smoke stack + DB ready + `alembic upgrade head` + smoke bootstrap / seed；
6. selector 选择的 Playwright：四条关键 spec 保留各自 provider 环境，其余 spec 使用通用 runner；
7. optional AI Coach real-provider focused gate；
8. selector 选择的 backend integration/E2E 以 `--cov-append --cov-branch` 合并覆盖率；
9. changed-line 80% 与关键状态机 branch baseline guard。

说明：
- 这里的 Playwright 包含 smoke matrix、新人训练 closed-loop E2E 以及 presentation/sales Phase 4 E2E；新人首发不包含 Realtime 对练。
- 默认门禁使用 deterministic local provider，不依赖外部 StepFun 或真实 LLM；新人 AI Coach 的真实 provider 由 release/nightly 专项模式验证。
- AI Coach 真实 provider 专项模式同样默认 fail-closed；缺 `LLM_API_KEY` / `OPENAI_API_KEY` 时会输出 classified skip 证据并失败，只有人工明确设置 `NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1` 才允许可追踪跳过。

### 影响测试选择与覆盖率

本地默认收集 committed diff、staged、unstaged 和 untracked 变更：

```bash
bash scripts/critical-quality-gate.sh
```

CI 必须显式传稳定的事件语义：PR 使用 base SHA 到实际 checkout SHA（GitHub 默认是 synthetic
merge commit）的 triple-dot，确保 coverage 行号与被测试工作树一致；push 使用 double-dot；定时和
手工完整门禁使用 full fallback。

```bash
QUALITY_GATE_SELECTION_MODE=pr \
QUALITY_GATE_BASE_SHA=<pull-request-base-sha> \
QUALITY_GATE_HEAD_SHA=<checked-out-merge-sha> \
bash scripts/critical-quality-gate.sh
```

选择权威在 `docs/architecture/quality-test-selection-policy.yaml`。critical baseline、直接改动、
path policy 构成稳定底座；健康 CodeGraph 结果只允许增加测试。CI 缺 CodeGraph 时记录 degraded
原因但保留 policy 选择；版本错误、malformed/empty 结果、不可信 base、未知生产路径、删除/重命名
和全局横切改动会 fail closed 到 family/full fallback。runner 只消费 selector 校验后、相对各自
工作目录的数组，原 repo path 和 reason 始终保留在 manifest。

覆盖率权威在 `docs/architecture/changed-coverage-policy.yaml`。backend unit+contract 的 coverage
data 会与 selected integration/E2E 追加合并后才生成最终 JSON；frontend `coverage.include`
覆盖全部生产 `src`。guard 仅计算报告确认的 executable changed lines，同时执行关键 branch
不回退检查。两份 policy 的临时 adoption anchor 必须完全一致，过期或漂移直接失败。

门禁证据：

- `.sisyphus/evidence/quality-test-selection.json`
- `.sisyphus/evidence/backend-coverage.json`
- `.sisyphus/evidence/changed-coverage-report.json`
- `web/coverage/coverage-final.json`
- `web/coverage/coverage-summary.json`

selector 或报告为空、schema 非法、coverage 不足、suite 超过 1200 秒都会非零退出。排障时先看
manifest 的 `selection_mode`、`fallback_reasons`、`degraded_reasons` 和每条测试的 `reasons`，
再看 changed coverage report 的 `violations`，不要手工缩小 runner 清单。

### OpenAPI 合同

```bash
cd backend
.venv/bin/python scripts/generate_openapi_contract.py
.venv/bin/python scripts/generate_openapi_contract.py --check
```

生成命令以 FastAPI runtime schema 为权威更新 committed contract；`--check` 只读并在
语义漂移时返回非零退出码。

独立 Presentation/Sales Realtime 产品在自己的发布流程中可运行以下不联网预检；该脚本不会打印 `STEPFUN_API_KEY`，也不属于新人基础训练首发门禁：

```bash
python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env
```

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

当前仓库内可直接引用的 backup / recovery 与首发重置说明见：

- `docs/backup-recovery-runbook.md`
- `docs/launch-reset-runbook.md`

首发 reset 是破坏性流程，只允许按后者的 inspect → dry-run → apply → verify 步骤执行。

## 常用环境变量

- `BACKEND_PORT` / `FRONTEND_PORT`
- `POSTGRES_PORT` / `REDIS_PORT`
- `PORTS_TO_CLEAN`（逗号分隔）
- `AUTO_START_INFRA`（`1` 或 `0`）
- `DATABASE_URL` / `REDIS_URL`
- `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`
