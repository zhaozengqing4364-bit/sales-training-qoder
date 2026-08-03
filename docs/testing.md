# 测试与质量门禁

> 状态：新人销售基础训练首发测试合同已实现（2026-07-18）。最终完整门禁证据为 `.sisyphus/evidence/task-9-quality-gate.txt`；不存在、未执行或失败的测试仍不得报告为通过。

## 分层门禁

| 层 | 必须证明 |
|---|---|
| Unit | 状态机、Gate、确定性评分、Presenter、错误与幂等纯规则 |
| Integration (PostgreSQL) | 事务/Outbox、唯一约束、Lease、并发 Attempt、revision 冻结、跨组织拒绝 |
| Contract | OpenAPI、事件 schema、AI/ASR Adapter、Fake Provider、错误信封、DTO/ViewModel |
| Migration | 空库 upgrade；旧开发库显式转换或写前拒绝；upgrade/downgrade/重建；无双写 |
| E2E | 分配 -> 五类活动 -> Dossier -> 人工决定；失败恢复、补练、申诉与权限 |
| Performance | 指定容量、固定数据集、预热/采样/百分位、查询数和资源指标 |
| Provider | Gold Set、shadow、canary、错误/成本/延迟与回滚阈值 |

## Slice 0 文档基线门禁

- `python3 .trellis/scripts/task.py validate <task-dir>`：Slice 0 与后续 8 个任务逐个通过。
- 所有新增 JSONL 每行可解析；YAML 可 `yaml.safe_load`；Markdown 相对链接存在。
- `python3 backend/scripts/architecture_dependency_guard.py --check`：仅验证当前 Guard 未回归；目标 detector 尚未接入的事实必须保留。
- `git diff --check`；搜索 Phase/Module、Realtime 首发、自动 Enrollment 迁移时，只允许出现在明确的 Legacy/Superseded 说明中。

## 每个实现切片最小门禁

```bash
cd backend
./.venv/bin/ruff check src/ tests/ scripts/
./.venv/bin/mypy src/
./.venv/bin/pytest <affected unit/contract/integration tests>
./.venv/bin/python scripts/generate_openapi_contract.py --check
./.venv/bin/python scripts/architecture_dependency_guard.py --check

cd ../web
npx tsc --noEmit
npx eslint . --quiet
npx vitest run <affected tests>
```

涉及数据库还要运行 Alembic empty/old-dev fixtures；涉及用户界面还要运行相关 Playwright、键盘、焦点、360px、200% zoom、长文本、慢网和权限状态；涉及 AI 还要运行 Fake Provider 与该能力 Gold Set。

### Slice 3 录音评测针对性门禁

开发中按当前修改选择最小子集；切片收口的标准针对性集合为：

```bash
cd backend
./.venv/bin/ruff check src/audio_assessment tests/unit/audio_assessment
./.venv/bin/python -m pytest \
  tests/unit/audio_assessment \
  tests/unit/newcomer_training/test_standard_pack.py \
  tests/unit/newcomer_training/test_route_contract.py \
  tests/unit/ai_platform/test_foundation_ai_composition.py \
  tests/migrations/test_audio_assessment_migration.py \
  --no-cov -q

cd ../web
./node_modules/.bin/eslint \
  src/components/newcomer-training/activity-runners \
  src/lib/auth/clear-client-auth-state.ts
./node_modules/.bin/vitest run \
  src/components/newcomer-training/activity-runners/audio-assessment-runner.test.tsx \
  src/components/newcomer-training/activity-runners/browser-audio-uploader.test.ts \
  src/components/newcomer-training/activity-runners/use-browser-audio-recorder.test.ts \
  src/components/newcomer-training/activity-shell.test.tsx \
  src/lib/api/audio-clean-cut.test.ts \
  src/lib/auth/clear-client-auth-state.test.ts
```

这组测试证明边界/分片恢复、完整性、Worker 故障分类、不可评分、版本追加、跨组织权限、旧写退役、浏览器分片草稿/续传和 UI 状态。真实 Provider Gold Set、完整浏览器 E2E、SLO 和发布回滚已在 Slice 8 受控环境验收；后续仍不得用开发机 Fake Provider 结果冒充真实 Provider 证据。

### Slice 5 能力证据与复核针对性门禁

最小集合必须覆盖七项标准能力、Outcome 幂等、Evidence supersede/失效、不可评分排除、增量与 rebuild 收敛、Snapshot stale、人工身份与 expected version、补练完成、申诉重评重开、AI 引用失败、学员安全投影、角色权限审计、API DTO/UI 和 migration upgrade/downgrade。全量浏览器 E2E、真实并发 PostgreSQL、性能和发布演练已由 Slice 8 完成；后续不得用 SQLite 顺序测试冒充生产并发证据。

### Slice 7 前端体验与开发性能门禁

最小门禁覆盖唯一学员入口、五类 Activity Shell、持久任务/通知恢复、音频草稿与 transcript、Coach 稳定视口、管理列表服务端分页、DTO/ViewModel、用户语言错误、隐私安全 UX 事件，以及学员/管理端实际渲染：

```bash
cd web
npx tsc --noEmit
npx eslint <本切片修改文件>
npx vitest run <本切片相关组件与 adapter 测试>
LD_LIBRARY_PATH="$PWD/../.dev/playwright-libs/root/usr/lib/x86_64-linux-gnu" \
  SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 \
  SMOKE_EVIDENCE_PREFIX=slice7-experience \
  npx playwright test \
    tests/e2e/newcomer-training-learner.spec.ts \
    tests/e2e/newcomer-training-admin.spec.ts
LD_LIBRARY_PATH="$PWD/../.dev/playwright-libs/root/usr/lib/x86_64-linux-gnu" \
  SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 \
  SMOKE_EVIDENCE_PREFIX=slice7-performance \
  npx playwright test tests/e2e/newcomer-training-performance.spec.ts
```

2026-07-18 开发机证据：Journey 主操作可见 8 次新浏览器上下文样本 `p75=834.8ms`；30 次预热后顺序读取的 Journey、Dossier、本人 Task 列表、管理学员列表 `p95` 分别为 `20.4ms`、`17.2ms`、`11.0ms`、`14.4ms`，错误率为 0。Journey 首屏每次 35 个网络响应，其中浏览器读取 API 为 0，仅有一个不阻塞的隐私安全埋点 POST；开发模式未压缩初始 JavaScript 为 32 个资源、5,987,344 bytes。学员列表以 1 行和 7 行 fixture 验证 SELECT 数保持不变。

这组数据只证明 Slice 7 没有明显前端读取瀑布、API 延迟回归或逐行查询；最终发布基线已经在 Slice 8 以生产构建、1,000 学员/100 在线/20 上传/20 AI Task 容量证据和受控真实 Provider staging 复测，分别保存在 `.sisyphus/evidence/foundation-capacity-baseline.json` 与 `.sisyphus/evidence/foundation-ai-real-provider-staging.json`。

### Slice 8 Foundation AI 质量门禁

确定性 Gold Set 是每次完整质量门禁的必跑项，也可独立执行：

```bash
cd backend
PYTHONPATH=src ./.venv/bin/python scripts/evaluate_foundation_ai_gold_set.py \
  --output ../.sisyphus/evidence/foundation-ai-gold-set.json
./.venv/bin/python -m pytest -c pyproject.toml \
  -o addopts='--import-mode=importlib' \
  tests/unit/ai_platform/test_foundation_ai_quality_gate.py -q
```

真实 Provider staging 默认关闭，且只允许显式执行；命令、冻结合同、证据边界和失败规则见 `docs/ai-governance.md`：

```bash
CRITICAL_GATE_MODE=foundation-ai-real-provider \
  LLM_API_KEY='通过环境或密钥系统注入' \
  LLM_BASE_URL='受安全策略允许的 HTTPS endpoint' \
  LLM_MODEL='已批准模型' \
  bash scripts/critical-quality-gate.sh
```

若完整门禁需要同时执行 staging，显式设置 `RUN_FOUNDATION_AI_REAL_PROVIDER_GATE=1`；正式发布环境还应设置 `FOUNDATION_AI_REAL_PROVIDER_REQUIRED=1`。只有非发布环境经负责人明确批准时，才可用 `FOUNDATION_AI_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1` 记录 `skipped`，该结果不能作为发布通过证据。门禁证据分别位于 `.sisyphus/evidence/foundation-ai-gold-set.json` 和 `.sisyphus/evidence/foundation-ai-real-provider-staging.json`。

### Slice 8 容量与并发基线

最终门禁固定运行隔离本机 PostgreSQL schema 的 Foundation 容量测试：1,000 学员、1,000 Enrollment、10,000 Attempt、每路径 100 活动、100 个并发 Journey 读取、20 个并发 Durable AI Task 入队和 20 个并发录音上传/处理。测试先预热管理列表，再记录样本、错误数和 p50/p75/p95/p99，并断言服务端分页/排序、页内 Attempt 查询、业务结果唯一和 Dossier 快照完整。

```bash
cd backend
set -a && source .env && set +a
PYTHONPATH=src ./.venv/bin/pytest \
  -o addopts='--import-mode=importlib' \
  tests/performance/test_foundation_capacity.py -q
```

证据写入 `.sisyphus/evidence/foundation-capacity-baseline.json`。录音全链路使用真实 PostgreSQL 写入、真实 Durable Task 持久化和确定性 Fake Media/ASR/LLM Adapter；真实 Provider 延迟仍由受控 staging 门禁单独证明，不能由该容量结果替代。

## 状态机与权限测试

- 每条允许转移至少一条正向测试；每条未允许边一条拒绝测试；终态不可变；相同命令幂等；同键异参冲突；expected_version 冲突不写数据；审计/Outbox 与业务写同成败。
- 权限矩阵每个角色覆盖正向、缺 capability、错误 Team、跨组织、对象不存在、只读/部分权限和批量范围。
- Realtime 必须在首发 Activity schema、seed、导航、权限与 E2E 中缺席。
- 发布新 PathRevision 后旧 Enrollment revision 保持不变；只有显式迁移命令写 `EnrollmentRevisionMigrated`。

## SLO 测量口径

测试基线：每组织 1,000 学员、100 并发在线、20 并发上传、20 并发 AI Task、每路径 100 活动、10,000 Attempt 管理列表。结果必须记录 commit、环境、CPU/内存、数据库规模、Provider 模式、样本数、预热、错误率和 p50/p75/p95/p99。

| 指标 | 起止点 | 目标 |
|---|---|---:|
| Journey 首屏 | navigation start -> 主任务/主操作可见 | p75 ≤ 2s |
| 普通 API | 服务端接收 -> 完整响应写出（排除长 AI） | p95 ≤ 500ms |
| AI Coach 可见反馈 | 提交已持久化 -> UI 收到真实 running/first event | ≤ 1.5s |
| AI Coach 完整响应 | 提交已持久化 -> validated result | 目标 ≤ 8s |
| Audio finalize | finalize request -> submission/task refs | ≤ 2s |
| Audio pipeline | finalize accepted -> Outcome/needs_review | p95 ≤ 90s |
| Dossier base | request -> 基础档案可见 | ≤ 2s |

性能测试同时断言 Journey/队列查询数不随返回行数线性增长、分页/筛选在服务端、无状态丢失、任务可重领且无重复业务结果。

## 最终门禁

运行 `bash scripts/critical-quality-gate.sh`、生产 Web build、核心 learner/admin/manager Playwright、Alembic、OpenAPI、目标 Architecture Guard failure probes、Provider staging、性能基准、reset/seed/verify、备份恢复与回滚演练。无法运行的项必须显式列为未验证和发布阻塞，不得用“当前能跑”替代。

reset/seed/verify 使用 `backend/scripts/rehearse_foundation_reset.py` 在随机本机 disposable database 连续执行两轮；必须显式设置 `FOUNDATION_RESET_REHEARSAL_CONFIRM=1`。演练器先把新建空库升级到唯一 Alembic head，再采集 reset 前快照并执行 reset/seed/verify，避免把“数据库尚无业务表”误判为清理失败。应用数据库角色没有 `CREATEDB` 时，另以 `FOUNDATION_RESET_REHEARSAL_ADMIN_DATABASE_URL` 提供同一台本机 PostgreSQL 的受控建库/删库连接。结果以 `.sisyphus/evidence/foundation-reset-rehearsal.json` 为准，权限不足、阶段失败或清理失败均是发布阻塞，不能标记为 skipped/passed。
