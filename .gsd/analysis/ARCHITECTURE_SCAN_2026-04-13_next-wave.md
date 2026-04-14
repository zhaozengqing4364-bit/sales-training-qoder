# Architecture Scan — Post-M018 Next Wave（2026-04-13）

## 1. 结论先行

当前仓库的真实形态仍是**单仓库下的模块化单体**：
- `web/` 是 Next.js 16 + React 19 的 learner/admin 前端。
- `backend/` 是 FastAPI + SQLAlchemy Async + Alembic + Redis + Chroma/OSS/StepFun 的后端。
- 主业务链已跑通，但 authority 仍集中在少数超大编排文件：
  - `backend/src/common/api/practice.py`
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `web/src/lib/api/client.ts`
  - `web/src/hooks/use-practice-websocket.ts`

到 M018 为止，项目已经把 learner/report/replay/history/admin/security/performance/dependency/recovery 的 baseline 收口完毕；下一轮不该继续做“补洞式审计”，而应该进入**边界抽离 + control-plane 统一 + productization + org-ready 目标态**。

---

## 2. 仓库形态与现有规划状态

### 2.1 仓库形态
- 当前目录是仓库根目录：`/Users/zhaozengqing/github/销售训练qoder`
- 不是 pnpm workspace monorepo；而是 root + `web/` + `backend/` 双主应用结构。
- 根目录仅保留最小 Node 脚本入口：`package.json` 只有 `test`（`scripts/run-vitest-root.mjs`）。

### 2.2 现有规划痕迹
- `.gsd/` 已深度接管项目规划与执行。
- `M001` 到 `M018` 已全部完成，当前 `STATE.md` 显示无 active milestone。
- 已存在：
  - `.gsd/PROJECT.md`
  - `.gsd/REQUIREMENTS.md`
  - `.gsd/DECISIONS.md`
  - `.gsd/KNOWLEDGE.md`
  - `.gsd/milestones/M001..M018/*`
  - `.gsd/analysis/ARCHITECTURE_SCAN_SYSTEM_AUDIT_2026-04-08.md`
  - `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`
  - `.gsd/plans/GSD_PLAN_system-audit-repair.md`

### 2.3 当前规划结论
本轮不需要重建体系，而是要在现有 `.gsd/` 上追加下一波 milestone：
- **M019** — Authority seams 与 release gate 收口
- **M020** — Security / multi-instance runtime / recovery hardening
- **M021** — AI control plane / prompt / evaluation kernel 统一
- **M022** — Sales productization / manager truth / organization-ready roadmap

---

## 3. 技术栈与运行面

### 3.1 前端
- 框架：Next.js `^16.2.3`、React `19.2.3`、TypeScript `^5`
- UI：Tailwind CSS v4、Radix UI、Lucide、Framer Motion、Recharts
- 数据层：TanStack Query、Zustand
- 测试：Vitest + Testing Library + jsdom
- 关键文件：
  - `web/package.json`
  - `web/src/lib/api/client.ts`
  - `web/src/hooks/use-practice-websocket.ts`
  - `web/src/app/(dashboard)/**`
  - `web/src/app/(user)/practice/**`
  - `web/src/app/admin/**`

### 3.2 后端
- 框架：FastAPI
- ORM/迁移：SQLAlchemy 2 Async + Alembic
- 数据：PostgreSQL（运行）、SQLite（测试/兼容）、Redis、Chroma、OSS
- AI/runtime：StepFun realtime、PromptTemplateService、voice instruction compiler、knowledge-answer engine
- 监控/日志：structlog、Prometheus、OpenTelemetry
- 关键文件：
  - `backend/src/main.py`
  - `backend/src/common/api/practice.py`
  - `backend/src/common/db/session.py`
  - `backend/src/common/auth/*`
  - `backend/src/common/conversation/session_evidence.py`
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `backend/src/common/monitoring/*`

### 3.3 CI / 运维 / 脚本
- 当前仅有 `.github/workflows/nfr-performance-check.yml`
- 已有 repo-local 脚本：
  - `scripts/dev-up.sh`
  - `scripts/dev-stop.sh`
  - `scripts/dependency-governance.sh`
- 运维事实基线已在 M018 落成，但仍偏手工：
  - `docs/setup/backup-recovery-current-state.md`
  - `docs/backup-recovery-runbook.md`
  - `.sisyphus/deploy/*`

---

## 4. 当前真实 authority chain

### 4.1 训练主链
真实训练主链不是“evaluation/services/* 的离线评分”，而是：
1. 前端通过 `web/src/lib/api/client.ts` 创建/查询 practice session
2. 后端 `backend/src/common/api/practice.py` 冻结 `voice_policy_snapshot`、返回 runtime descriptor / report / audio audit 等读写面
3. 前端通过 `web/src/hooks/use-practice-websocket.ts` 连接 websocket
4. 后端 `backend/src/sales_bot/websocket/router.py` / `presentation_*handler.py` 接管 WS
5. Sales 在线主处理器是 `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
6. 结束后由 `SessionLifecycleService` + `SessionEvidenceService` 形成 report/replay/history/admin truth line

### 4.2 AI / prompt 主链
当前 live AI path 的核心是：
- `stepfun_realtime_handler.py`
- `voice_instruction_compiler.py`
- `persona_policy` / runtime guardrails
- `common/knowledge_engine/*`
- `SessionEvidenceService` / runtime diagnostics

当前 legacy / compat path 仍并存：
- `evaluation/services/staged_evaluation.py`
- `evaluation/services/comprehensive_report.py`
- `common/ai/llm_service.py`
- `prompt_templates/*`

这意味着：
- PromptTemplateService、legacy evaluation、realtime scoring、report/read-side 并未完全统一。
- 分数维度、prompt 来源、降级语义仍存在多轨并行。
- `backend/src/prompt_templates/taxonomy.py` + `backend/src/common/ai/llm_service.py::LEGACY_PROMPT_ENTRYPOINTS` 现在已经把当前 prompt source taxonomy 与 legacy 假接入点固化成代码拥有的 inventory，而不是只存在于一次性调研里。

### 4.3 M019/S02 practice application seam closure
`backend/src/common/api/practice.py` 仍是 practice route family 的 HTTP 入口，但当前 live split 已经不再要求后续工作回到 route 文件里拼装所有行为：
- route-facing compatibility bundle：`common.services.practice_service.build_practice_route_services`
- create / lifecycle / runtime descriptor / retry focus：`common.services.practice_session_service`
- report payload / audio audit / audio segment registration：`common.services.practice_report_service`
- completed-session canonical read model：`common.conversation.session_evidence.SessionEvidenceService`
- replay / history / admin route family 继续分别落在 `common.conversation.replay.ReplayService`、`common.analytics.history_service`、`admin/api/users.py`，但它们消费的仍是 `SessionEvidenceService` projection，而不是重新回 `common/api/practice.py` 组装 completed-session truth。

**S03 / M021 downstream consumption rule**
- 如果改动的是 session create、voice/runtime descriptor、retry focus、lifecycle orchestration，优先扩展 `practice_session_service`，再由 `practice_service` compatibility bundle 暴露给 route。
- 如果改动的是 practice report payload、audio audit、audio segment upload/register/failure surface，优先扩展 `practice_report_service`。
- 如果改动的是 replay / history / admin / manager intervention 的 completed-session truth，优先扩展 `SessionEvidenceService`、`ReplayService` 或 `history_service`，不要在 `practice.py` 里重新拼 projection/read model。
- 新的 backend consumer 应该从 `common.services.*` 或现有 read-model family import，而不是直接复用 `common/api/practice.py` 内部 helper。

### 4.4 M019/S01 数据库演进 / bootstrap authority inventory

| 责任类型 | 当前真实 authority | 真实入口 | 当前状态 / 风险 |
|---|---|---|---|
| 启动初始化 | `backend/src/main.py` 的 lifespan 调用 `common.db.session.init_db()` | `backend/src/main.py` → `await init_db()` | 仍带 startup schema side effect：`Base.metadata.create_all()` 会执行；失败会直接阻断服务启动。 |
| schema 演进 | Alembic revision 链 | `cd backend && alembic upgrade head` → `backend/alembic/env.py` + `backend/alembic/versions/*` | 这是唯一真实的 forward migration authority；`026/027/028` 已承载 password reset，`015/017/018` 已承载 persona / knowledge_documents 演进，`20260413_1040_029` 已把 legacy startup repair authority 收回显式迁移/repair seam。 |
| 开发 / 测试 bootstrap 兼容 guard | `common.db.session.init_db()` 内显式 compatibility guard | `_ensure_persona_policy_column_compatibility()`、`_ensure_knowledge_document_schema_compatibility()` | 现在只允许 `development` / `test` / `testing` 自动补齐本地 legacy fixture；非开发环境发现 drift 会 fail-fast 并指向 Alembic / `repair_legacy_schema.py`。 |
| 一次性 legacy repair | `backend/scripts/repair_legacy_schema.py` + `common.db.legacy_schema_repair` | `cd backend && python scripts/repair_legacy_schema.py [--stamp-revision ...]` | 不是启动自动流程；现在显式修补 `personas.persona_policy` 与 `knowledge_documents` drift，并可按需补 `alembic_version`。 |
| 一次性 auth/bootstrap | `backend/scripts/bootstrap_auth_admin.py` | `cd backend && python scripts/bootstrap_auth_admin.py --email ... --role ...` | 只负责账号重建/补齐，不拥有 schema authority。 |

补充事实：
- `scripts/dev-up.sh` 当前只是拉起 infra + `uvicorn src.main:app`，**不会先执行 `alembic upgrade head`**。
- 因此本地/轻运维环境今天仍可能依赖 startup bootstrap 才“看起来能跑起来”；但 production-like 环境已经不会再静默修补 legacy personas / knowledge drift。
- 当前未发现 request handler 内的隐式 schema repair；隐式 schema 修补集中在 **startup path**，不是 request path。
- `.github/workflows/nfr-performance-check.yml` 在性能验证前显式执行 `alembic upgrade head`，与这条 authority line 一致，而不是依赖 startup `init_db()`。
- `docs/backup-recovery-runbook.md` 与 `docs/setup/backup-recovery-current-state.md` 现在都把恢复顺序写成：`pg_restore` → `alembic upgrade head` → 必要时 `repair_legacy_schema.py` → `bootstrap_auth_admin.py`。
- repo-root focused proof 已固定为 `backend/tests/integration/test_startup_or_bootstrap_authority.py` + `backend/tests/unit/common/test_db_session_compatibility.py`。

这意味着 M019 当前的正确收口方向不是“再加一个修补入口”，而是：
1. 保持 `init_db()` 的 startup/bootstrap 责任显式可见；
2. 把 schema 演进 authority 固定回 Alembic；
3. 把 legacy repair 和 auth bootstrap 继续留在显式脚本入口；
4. 后续只在真正准备好外部 bootstrap/recovery authority 时，再考虑进一步收窄 startup path 的 `create_all()` / dev-test compat 行为。

### 4.5 M019/S03 frontend domain client / transport seam inventory
`web/src/lib/api/client.ts` 现在仍是前端统一 outward façade，但 repo-root inventory 已经能把它拆成明确 domain 面：
- cross-cutting seam：`apiFetch` / `apiUpload` / `fetchWithLoopbackRetry` + `createHeaders(buildTraceHeaders(...))` + `normalizeApiErrorPayload` / `ApiRequestError` + `authHandler.sessionExpired()`
- 已抽到 `web/src/lib/api/client-domains.ts` 的 page-proved builders：`createAuthDomain`、`createPracticeDomain`、`createSessionsDomain`、`createAgentsDomain`、`createPresentationsDomain`、`createAdminReportDomain`
- 仍留在 `client.ts` 内联的 façade domains：`user`、`dashboard`、`analyticsOpen`、`supportRuntime`、`training`、`scenarios`、`analytics`、`admin`、`adminTools`、`adminPresentations`、`internal`
- high-fan-out consumers：learner auth/dashboard/profile/training/practice/report/replay 页面直接依赖 façade；admin analytics/users/personas/knowledge/settings/prompts 与 knowledge-answer debug panels 大量依赖 `api.admin*` / `api.adminTools`

这意味着 S03 后续拆分不能把页面改成跨 domain 直连实现；正确方向是：
1. 保留 `api` 作为唯一 outward import surface；
2. 把 domain modules 收到 `web/src/lib/api/*` 内部，由 façade 回指；
3. 继续把 auth/error/trace 只留在 shared transport seam，而不是让页面或 domain module 自己处理 401、trace header、payload normalization。

`web/src/hooks/use-practice-websocket.ts` 当前也已经有清晰的 inward/outward 边界，而不是“整文件继续硬拆”：
- outward consumer 现在基本只剩 `web/src/app/(user)/practice/[sessionId]/page.tsx`（以及其测试/mock contract），所以 outward return shape 必须稳定。
- 已抽出的 inward helpers：`websocket/message-handlers.ts` 负责 inbound protocol -> state projection；`websocket/transport.ts` 负责 URL 组装、pending outbound queue、reconnect/backoff policy、close-reason mapping；`websocket/use-audio-playback.ts` 负责 legacy audio queue/unlock；`use-streaming-audio-player.ts` 负责 chunk playback；`use-voice-speed-preference.ts` 负责本地播放速率偏好。
- hook 自身仍是 transport orchestration authority：socket connect/disconnect、runtime lock inputs、binary negotiate、flush-session abort control、local backpressure buffer/flush、interrupt pre-cleanup（含 throttled interim transcript cleanup）以及 outward return contract。

**S03 downstream consumption rule**
- 如果改的是 auth/error/trace/request transport，优先扩展 API transport seam，而不是在 domain module 或页面里直接 `fetch(...)`。
- 如果改的是 learner/admin domain request surface，优先落在 `web/src/lib/api/*` 的 domain module，再由 `api` façade 暴露；不要让页面跨 domain 引别的实现细节。
- 如果改的是 realtime inbound state projection，优先扩展 `websocket/message-handlers.ts`。
- 如果改的是 websocket URL/auth/reconnect/backpressure/interrupt/outbound pacing，优先扩展 `use-practice-websocket.ts` 或 `websocket/transport.ts`；不要把这些逻辑下沉到 page-level effect。

### 4.6 M019/S04 assembled release gate 与 downstream reuse rule

S04/T02 之后，当前仓库已经有一条**可复用的 assembled release gate**，而不是只剩“文件存在”。按 repo-root 复核，当前真实接通状态如下：

| Surface | 当前 authority / 入口 | 真实接通状态 | 当前缺口 / 结论 |
|---|---|---|---|
| GitHub Actions assembled release gate | `.github/workflows/release-truth-gate.yml` | **已接通**：当前 release truth workflow 同时检查 `web/package-lock.json` + `backend/requirements.txt` install authority、web focused gate、backend auth/metrics/analytics gate、以及 docs/spec drift inventory。 | 这是 downstream milestone 默认复用的 release gate；新增 release truth surface 时，要同步更新 workflow、对应 focused proof 和本节 inventory。 |
| Backend NFR companion gate | `.github/workflows/nfr-performance-check.yml` | **已接通**：仍承担 backend NFR / load proof，但现在也已对齐 `backend/requirements.txt` authority。 | 这是 release gate 的补充 proof，不再单独代表整体 release truth line。 |
| Frontend error reporting / custom analytics beacons | `web/src/components/ErrorBoundary.tsx` + `web/src/lib/performance.ts` → `backend/src/common/api/analytics.py` | **已接通**：`/api/v1/analytics/error`、`/api/v1/analytics/performance`、`/api/v1/analytics/custom` 已有 live backend sink，`backend/tests/integration/test_observability_surfaces.py` 会证明 beacon 可被接收。 | 当前 truth line 只证明“被接收并计入 metrics”，还不等于已经有持久化告警、Sentry 聚合或产品级 triage 面。 |
| Backend Prometheus metrics | `backend/src/common/monitoring/metrics.py` + `backend/src/main.py` | **已接通**：`initialize_metrics(...)`、`MetricsMiddleware` 和 `/metrics` export 已挂到 live backend authority line。 | 现在的 release truth 是 raw Prometheus payload 可检查；更高阶 dashboard / SLO 仍属于后续 observability 工作，不应倒推成已实现。 |
| `docs/api-contract` doc contract authority | `docs/api-contract/*.md` | **部分纳入 release gate**：`sessions.md`、`release-verification.md`、`support-runtime.md` 这些与 live routes 对齐的 surface，已经通过 repo-root `rg` proof 成为当前 doc contract authority。 | 当前 gate 是 inventory-style drift proof，不是从 FastAPI 自动生成 OpenAPI；若未来升级为 machine-checked contract，必须替换整组 proof，而不是新增第二套 authority。 |
| Legacy checked-in OpenAPI | `specs/001-ai-practice-system/contracts/openapi.yaml` | **显式保留为 drift inventory**：它仍包含 `/auth/wechat` 等旧 surface，且缺少 `/api/v1/admin/release-verification`、`/api/v1/support/runtime`。 | 只有在它重新由 live router/openapi 生成或受 CI machine-check 约束时，才可重新晋升为 release authority；在此之前，它只是“负向 inventory proof”。 |
| Legacy API spec narrative | `api-spec.md` | **显式保留为 drift inventory**：仍写 `POST /api/v1/sessions` 等旧 practice flow，而 live authority 已经转到 `POST /api/v1/practice/sessions` family。 | 与 checked-in OpenAPI 一样，它现在是 drift surface，不是 release 合同。 |
| Admin 首页 truth surface | `web/src/app/admin/page.tsx` | **不得纳入 release gate**：页面顶部“训练效果核心看板（近7天）”会读 `api.internal.health()` 与 `api.analyticsOpen.getDashboard({ days: 7 })`，但同页其余运营卡片仍硬编码 `2,543`、`84`、`42%`、`68%`、`75%`、`450 GB` 以及静态日志/告警文案。 | 这些 demo stats / 假监控数字只能作为 **M022/S03 manager/admin truth surfaces** 的输入，不能被包装成当前 release surface。 |

**当前 assembled release gate 结论**
- 当前 release 是否可过线，应该看 **`.github/workflows/release-truth-gate.yml` + `.github/workflows/nfr-performance-check.yml` + live backend router/metrics/analytics sinks + `docs/api-contract` inventory proof** 的 assembled evidence，而不是只看单个 workflow 绿灯。
- 当前 repo-root release gate 默认复用命令为：
  1. `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"`
  2. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q`
  3. `rg -n "/api/v1/practice/sessions|/api/v1/admin/release-verification|/api/v1/support/runtime" docs/api-contract`
  4. `rg -n "/auth/wechat|POST /api/v1/sessions" api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml`
- 当前 repo-root **doc contract / drift inventory 补充 proof** 为：
  5. `rg -n "/practice/sessions|/admin/release-verification|/support/runtime" docs/api-contract backend/src/common/api/practice.py backend/src/admin/api/release_verification.py backend/src/support/api/runtime_status.py`
  6. `rg -n "api.internal.health|api.analyticsOpen.getDashboard|2,543|84|42%|68%|75%|450 GB" web/src/app/admin/page.tsx`
- **Downstream reuse rule（M020-M022 默认沿用）**：除非某个 slice 明确把新 surface 晋升为 authority，否则直接复用上述 repo-root commands、live surfaces、以及 doc-contract/live-route inventory proof；判断 `docs/api-contract` 是否仍是真实合同、判断 legacy spec 是否仍只是 drift surface、以及判断 admin home 是否还混有 demo stats，默认都先跑上面的 repo-root proof 再做结论。如果要晋升 legacy spec、增加新的 metrics/error-reporting sink、或把 admin/manager 面板提升为 release truth，必须同时更新 workflow、focused proof、architecture scan、以及对应计划文档，不能只改单个文件。

---

## 5. 代码热点与高耦合区

### 5.1 Mega files / orchestration hotspots
- `backend/src/common/api/practice.py`
  - 同时承载 session create、lifecycle、report、audio audit、retry focus、runtime descriptor
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - 同时承载 upstream connection、tool calls、grounding、persistence、diagnostics、reconnect snapshot
- `web/src/lib/api/client.ts`
  - 几乎全站 API client/错误归一化/trace/auth 都在单文件
- `web/src/hooks/use-practice-websocket.ts`
  - 虽已分拆 inbound handler/audio helpers，但 outward transport/reconnect/backpressure/interrupt 仍集中

### 5.2 不是当前瓶颈的区域
- stack 并不是问题；当前不是“换框架”阶段。
- learner/report/replay/history/admin/security/perf/recovery 的 baseline 已有，不该重做同类 audit。
- 现在最大的工程风险来自**边界不清**，不是“缺少更多页面”。

---

## 6. 现状成熟度判断

### 6.1 已成熟到可以复用的部分
- learner/report/replay/history/admin/security baseline 已由 M012-M018 证明
- report/replay/history/admin 大量 focused tests 已存在
- SessionEvidenceService 已经是跨 route 的事实线
- backup/dependency/performance baseline 已有可引用 artifact，不需从零盘点

### 6.2 已到复杂度拐点的部分
- practice backend route 编排
- realtime handler 编排
- front-end API/transport 编排
- 多轨 AI prompt / score / quality semantics

### 6.3 仍明显偏“平台底座”而非“成品销售 SaaS”的部分
- 方法论/rubric 仍偏规则和包装
- persona/scenario/customer-pressure/industry pack 已有 inspectable contract authority，但运营规则与 manager calibration handoff 仍需文档化收口
- manager/admin 决策面仍有 fake stats / weak truth surfaces
- organization/team/tenant 还不是一等公民模型

---

## 7. 本轮需求对应的四大规划主题

### 7.1 Theme A — Authority seams 与 release truth
对应问题：
- 隐式 schema 修补
- mega-file orchestration
- CI 与依赖 authority 漂移
- legacy spec / admin truth surfaces 容易被误判成 release authority，必须固定 repo-root assembled gate 与 drift inventory

落点：**M019**

### 7.2 Theme B — Security / runtime / recovery
对应问题：
- cookie secure / CSRF / shared-password 兼容风险
- websocket query token
- system log/admin 日志敏感信息暴露面
- SessionManager 多实例/重启语义不清
- recovery 仍偏 runbook 阶段

#### 7.2.1 M020/S01 当前 auth transport authority（真实现状 + runbook closure）
- **HTTP API 正式路径**：`common.auth.service.resolve_bearer_or_cookie_token(...)` 允许 `Authorization: Bearer <jwt>` 与 `HttpOnly session cookie` 两条正式 transport；`web/src/lib/api/client.ts` 默认 `credentials: "include"`，并在带 session cookie 的 unsafe 请求上自动附带 `X-CSRF-Token`，所以 learner/admin 浏览器主链现在是 cookie-session + CSRF 双提交校验，而不是 localStorage token。
- **登录凭证正式/兼容路径**：`User.hashed_password` 是正式密码 authority；尚未进入 managed password 的账号仍通过 `AUTH_USER_PASSWORDS_JSON`（per-user override）与 `AUTH_SHARED_PASSWORD`（shared password）兼容登录。这个兼容层目前仍在 `common.auth.api.login` 里真实生效，并会通过 `X-Auth-Authority` / `X-Auth-Compatibility-Mode` 诊断头显式暴露当前 authority，因此 runbook 必须把它写成“兼容入口 + 退出条件”，不能写成正式长期 authority。
- **WebSocket 正式/兼容路径**：sales router（`backend/src/sales_bot/websocket/router.py`）与 presentation router（`backend/src/main.py::_handle_presentation_websocket`）都复用 `resolve_websocket_auth(...)` / `resolve_websocket_token(...)`。当前 shipped 顺序已收口为 `Authorization header -> session cookie -> query token compatibility`；也就是说，`Authorization`/cookie 是正式 transport，而 `query token` 仍是**活跃兼容路径**，但现在已降为 cookie 之后的 compatibility-only fallback。这一事实现在需要同时写进 `docs/api-contract/websocket.md` 与 `docs/setup/auth-local.md`，避免只在代码注释里存在。
- **前端统一 session-expired seam 仍成立**：`web/src/lib/api/client.ts` 的 `apiFetch` / `apiUpload` 在 401 且未设置 `skipSessionExpiredHandling` 时统一调用 `authHandler.sessionExpired()`；`createAuthDomain(...)` 对 login / logout / forgot-password / reset-password 显式设置 `skipSessionExpiredHandling: true`，避免把 auth 自身失败误报成 session expired；`web/src/hooks/use-auth-protection.ts` 继续负责页面级 login/role guard。
- **兼容路径关闭条件（必须文档化）**：
  1. 只有当目标账号都已经写入 `User.hashed_password`，且 reset-password focused proof 通过时，才应移除 `AUTH_SHARED_PASSWORD` / `AUTH_USER_PASSWORDS_JSON`；
  2. 只有当 web 与脚本 caller 都迁移到 header/cookie，且 websocket focused proof 不再依赖 `query token` 时，才应删除 websocket `?token=`；
  3. 关闭 compat transport 时，`docs/setup/auth-local.md`、`docs/api-contract/websocket.md`、以及本节 inventory 必须一起更新，不能出现“代码已改、runbook 仍旧、analysis 仍写旧 authority”的三套说法。
- **Repo-root focused proof（T03 写回）**：
  1. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q`
  2. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py -x -q`
  3. `npm --prefix web test -- --run src/lib/api/client.auth.test.ts src/lib/auth-handler.test.ts`
  4. `rg -n "Authorization|query token|cookie|CSRF|shared password|session expired" docs/setup/auth-local.md docs/api-contract/websocket.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/lib/auth-handler.ts`

落点：**M020**

#### 7.2.2 M020/S02 admin/support 日志 redaction boundary（T03 inventory closure）
- **已收口的 authority seam**：`backend/src/common/monitoring/logger.py` 现在是 admin/support 日志可见性的 backend-owned authority。`SYSTEM_LOG_ADMIN_POLICY_VERSION=admin_support_redaction_v1`、`ADMIN_LOG_ALLOWED_DETAIL_KEYS`、`ADMIN_LOG_DIAGNOSTIC_FIELDS`、`ADMIN_LOG_REDACTION_SUMMARY` 一起定义了 system log route 与 admin logs page 可见的 diagnostics contract；`backend/src/admin/api/system_logs.py` 只序列化这套 contract，`web/src/app/admin/logs/page.tsx` 只渲染 backend 返回的 diagnostics 列表，不再在前端重建可见字段规则。
- **可安全展示给 admin/support 的字段（allowlist）**：`action`、`status`、`created_at`、masked `user_identifier`、coarse `ip_address`，以及 `trace_id` / `error_code` / `phase` / `session_id` / `target_user_id` 这组 diagnostics。它们的用途是让 support/admin 可以定位哪条链路失败、落在哪个阶段、关联哪个 session 或 trace，而不是获得原始错误 payload。
- **必须留在 backend 内部的字段（backend-only details）**：raw `details`、精确 `user_identifier` / `ip_address`、stack trace、request/response/provider payload、prompt text、token/password/cookie/email、`base_url`、secret，以及任何足以重放请求或暴露身份/配置的原文错误上下文。即使 logger sink 可以在 backend 受控环境里保留这些原始 details，admin/support route 和 UI 也不得原样转发。
- **support guidance / inspection rule**：未来排障时，把 `policy.diagnostic_fields` 与 `diagnostics[]` 当成唯一可信的 admin/support error-details surface；如果某个问题需要 raw details、provider body、prompt、secret-adjacent config 或 stack trace，就应该回到 backend-controlled logs / runtime diagnostics，而不是把 system log route 或 admin page 扩成第二条泄密面。
- **M021 quality-event 前置约束**：`M021/S04` 计划把 AI `quality/cost/failure events` 暴露到 support/runtime 与前端 proof，但这条事件线不能发明第二套 support payload。任何需要进入 admin/support 诊断面的 quality event 都必须复用同一 allowlist-first redaction boundary：显式标出 degraded / failure / compat 与 `trace_id` / `error_code` / `phase` / `session_id` 等安全 diagnostics，但不得把 provider rejected 原文、fallback request/response details、prompt text、`base_url`、token 或其他 secret 直接外露。这样 M021 强化的是“显式失败”，不是“显式泄密”。
- **Repo-root focused proof（T03 写回）**：
  1. `rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  2. `backend/venv/bin/python -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py`

#### 7.2.3 M020/S03 runtime state authority table（T01 baseline）

这轮 repo-root 复核后，websocket runtime state 的 authority 需要明确拆成 **process-local connection registry** 与 **cross-instance reconnect snapshot** 两层；当前真实代码入口是：
- `common.websocket.base_handler.ConnectionManager.active_connections` / `common.websocket.session_manager.SessionManager.sessions`
- `common.websocket.session_state_service.SessionStateService`
- `sales_bot.websocket.stepfun_realtime_handler.StepFunRealtimeHandler`
- `presentation_coach.websocket.presentation_handler.PresentationWebSocketHandler`

**场景 1：单实例运行（当前 happy path）**

| State / Signal | 当前 authority | Storage | 单实例语义 | 说明 |
|---|---|---|---|---|
| 当前 websocket 是否在线 / 连接数 | `ConnectionManager.active_connections` + `SessionManager.sessions` | 进程内内存 | 可直接回答 | 这是真实 live connection authority，但只对当前进程成立。 |
| session timeout / heartbeat 清理 | `SessionManager` | 进程内内存 + live websocket | 可直接执行 | timeout 关闭连接依赖当前进程持有 handler/websocket。 |
| reconnect 恢复所需 turn/page/status/runtime subset | `SessionStateService` snapshot | Redis TTL snapshot | 可恢复 | 这是断线后“应该恢复什么”的 authority，不是 live connection truth。 |
| StepFun 当前 request epoch（`current_request_id`） | `StepFunRealtimeHandler._create_state_snapshot()` → `runtime_state.current_request_id` | Redis snapshot | 可跨断线延续 | 当前已是 reconnect-safe；后续要继续围绕它收紧 request/drain 语义。 |
| StepFun action card UI 残影 | **不应持久化** | N/A | 不应跨断线重放 | 当前代码已故意不把 `latest_action_card` 写入 snapshot，避免 reconnect replay 旧卡片。 |
| Presentation 当前页 / required points | `PresentationWebSocketHandler` + DB page requirements | Snapshot + DB lookup | 可恢复 | 页码是 snapshot，页面上下文重新从 DB/coach service 补发。 |

**场景 2：多实例并发**

| State / Signal | authority | 结论 |
|---|---|---|
| 某个 session 在“整个集群”是否在线 | **当前没有 cluster-wide authority** | 只能回答“本进程看见的连接”；不能把 `active_connections` 当成全局 truth。 |
| reconnect snapshot / turn/page/status/runtime subset | `SessionStateService` | 只要 Redis 可用，就可以被其他实例读取；这是当前唯一跨实例 authority。 |
| timeout/drain 对 live websocket 的直接操作 | 持有连接的那个进程 | 其他实例即便读到 snapshot，也不能替代当前 owner 关闭 websocket。 |
| connection count / visibility 对 support 的解释 | 必须标注为 process-local | 后续 support/runtime surface 需要显式区分 local connections vs persisted reconnect snapshot。 |

**场景 3：进程重启**

| State / Signal | 重启后是否保留 | authority / 说明 |
|---|---|---|
| `active_connections` / `SessionManager.sessions` | 否 | 进程内 registry 全丢失；这是预期，不应伪装成 durable state。 |
| Redis reconnect snapshot | 是（直到 TTL 到期或 terminal delete） | `SessionStateService` 是 restart 后唯一还能解释 session runtime 的 authority。 |
| handler 内临时对象（pending response、action card、websocket refs） | 否 | 只能重新建立；不能依赖 restart 后还原这些瞬态对象。 |

**T01 baseline 决策**
- `SessionManager.get_stats()` 现在应该显式暴露它只拥有 **process-local connection registry authority**，而不是暗示 cluster-wide truth。
- `SessionStateService.get_stats()` 现在应该显式暴露它只拥有 **Redis reconnect snapshot authority**，并附带 save/get/delete/healthcheck metrics 与 `last_error`，方便后续 support/runtime surface 复用。
- focused reconnect proof 要锁住：`current_request_id` 作为当前 request epoch 可跨 reconnect 延续，而 `latest_action_card` 不能被 snapshot replay。

**T02/T03 write-back surfaces（当前 downstream 必须复用）**
- `docs/api-contract/support-runtime.md` 现在必须明确写成：`/api/v1/support/runtime/overview|faults` 是 release-health / fault summary contract，**不是** websocket cluster-state API；需要解释 live websocket runtime 时，要回到 `SessionManager.get_stats()`（process-local active connection authority）与 `SessionStateService.get_stats()`（shared Redis snapshot authority）这两条 companion inspection surfaces。
- `SessionManager.get_stats()` 当前 support-facing 关键字段是：`connection_visibility.scope=process_local`、`tracked_sessions[]`、以及 `tracked_sessions[].runtime_diagnostics.session_status|ai_state|current_request_id|reconnect_state`。这些字段只能回答“当前实例还持有哪些 live sockets / request epoch / disconnect reason”。
- `SessionStateService.get_stats()` 当前 support/runbook 关键字段是：`snapshot_visibility.scope=redis_snapshot`、`last_saved_snapshot`、`last_loaded_snapshot`、`request_epoch`、`connection_epoch`、`last_disconnect_reason`、`last_error`。这些字段是 restart 后仍可解释 reconnect state 的唯一共享 authority。
- `docs/backup-recovery-runbook.md` 现在必须明确写成：单机 / systemd restart 会丢失进程内 live registry；多实例 drain 需要仓库外的 LB / ingress 摘流能力；当前仓库**没有** repo-native drain endpoint、cluster-wide live connection authority 或跨实例 close orchestration。后续 runbook 不能再写成“只要重启服务就行”。
- restart / drain 解释规则：
  1. restart 前要分别记录目标实例的 `SessionManager.get_stats()` 与共享 Redis 的 `SessionStateService.get_stats()`；
  2. restart 后 local registry 归零是预期，不代表所有 session 正常结束；
  3. 只有 Redis snapshot 能解释 reconnect-safe state，pending response / websocket refs / latest action card 等瞬态对象不会跨重启保留；
  4. 单实例 restart 与未来多实例滚动升级都必须把“active connection”标成 instance-local，而不是 cluster truth。
- repo-root proof 继续以 docs grep 为准：
  `rg -n "reconnect|epoch|snapshot|active connection|drain|restart" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

#### 7.2.4 M020/S04 recovery drill + deploy boundary closure（T03 write-back）

- `scripts/recovery_drill_baseline.py` + `scripts/recovery_drill_runner.py` 现在已经把 recovery authority 从“手工 runbook 说明”提升成**最小可执行 drill bundle**：evidence 统一落到 `./.dev/recovery-drills/<timestamp>/summary.json` 与逐 drill `*.log`，而不是只剩 markdown 描述。
- 当前 deploy authority 也必须一起看：`.sisyphus/deploy/ai-backend.service`、`.sisyphus/deploy/ai-frontend.service`、`.sisyphus/deploy/ai-practice.nginx.conf` 共同定义的是 **single-node native deploy bundle**，即一个 loopback backend（`127.0.0.1:3444`）+ 一个 loopback frontend（`127.0.0.1:3445`）+ 一个 nginx proxy。`/health` 在这里是**单节点 release/recovery proof**，不是 cluster-wide health truth。
- 因此 drill 适用范围现在要写死成两层：
  1. **今天直接适用**：单机 restart/redeploy、恢复后验收、release 前后节点健康校验；
  2. **未来 multi-instance 仍可复用但不能越权**：db/auth/redis/oss/health drills 仍可作为每个目标节点的 cutover proof，但 cluster drain、流量摘除、stickiness、跨实例 failover orchestration 仍在 repo 外的 LB / ingress / orchestrator 里。
- 最新已知 proof（写本文档时的真实 runner 输出）是 `.dev/recovery-drills/20260414T002842Z/summary.json`：`auth_bootstrap`、`redis_session_state`、`oss_signing_playback`、`health_check` 已通过，而 `db_migration` 继续真实暴露 `KeyError: '20260412_0315_028'`。这意味着 downstream release/recovery 说明必须把 drill failure signal 与 `/health` 一起呈现，不能因为节点健康仍可返回 `healthy` 就把 migration blocker 隐去。
- downstream reuse rule 现在扩展为：云部署或 systemd/nginx 发布的证据包至少要同时包含 `.sisyphus/evidence/<deploy-run>/health-*.txt`（或等价 deploy health capture）以及最新 repo-local recovery drill summary/log bundle；单靠 `/health`、单靠 systemd active，或者单靠 markdown runbook，任何一个都不足以宣称“可恢复”。
- repo-root write-back proof：
  `rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

### 7.3 Theme C — AI control plane / evaluation kernel
对应问题：
- live path 与 legacy path 并存
- PromptTemplateService 假接入
- prompt 来源碎片化
- score dimensions 多轨漂移
- failure/cost/default fallback 掩盖真实状态

落点：**M021**

#### 7.3.1 M021/S01 live AI authority inventory（当前 shipped reality）

先把当前 AI 主链说死，后续 S02-S04 才不会把 legacy 文件名误当 live authority：
- `backend/.env.example` 当前默认 `DEFAULT_VOICE_MODE=stepfun_realtime`，但 `sales_bot/websocket/router.py` 仍正式接受 `legacy | stepfun_realtime` 两条 runtime mode，所以 classic voice path 不是死代码，而是 **compat runtime**。
- knowledge-answer rollout 的 authority 不在 handler 本地分支，而在 `common.knowledge_engine.compat.resolve_knowledge_answer_rollout_mode()`：默认返回 `legacy`；只有 `KNOWLEDGE_ANSWER_ENGINE_ENABLED=true` 才把 engine 升为 learner-visible live path，`KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN=true` 则保持 legacy payload 对外、engine 仅做 shadow audit。

| Path / seam | Entry / activation | Main callers | Output consumers | Current label | Why this label holds now |
|---|---|---|---|---|---|
| `backend/src/sales_bot/websocket/router.py` → `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | `/ws/sales` when persisted `PracticeSession.voice_mode == "stepfun_realtime"` | sales websocket router, `presentation_stepfun_realtime_handler.py` subclass reuse | learner live practice websocket, persisted StepFun messages/score snapshots, `knowledge-check` live diagnostics, terminal evidence sync | **live** | This is the shipped realtime sales runtime authority: it owns upstream StepFun audio/session lifecycle, tool calls, knowledge retrieval, claim-truth/runtime diagnostics, message persistence, and reconnect snapshot state. |
| `backend/src/sales_bot/services/voice_runtime_policy.py` + `backend/src/sales_bot/services/voice_instruction_compiler.py` | session creation, runtime policy resolution, StepFun handler `_load_effective_policy()`, knowledge-check tool preview | `PracticeSessionCreateService`, `common/api/practice.py`, `StepFunRealtimeHandler`, presentation StepFun adapter | frozen `voice_policy_snapshot`, compiled base instructions, `instruction_contract_hash`, StepFun tool list | **live** | This is the current prompt/runtime contract authority for StepFun sessions; live runtime instructions come from the compiled snapshot, not from `PromptTemplateService`. |
| `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py` | presentation websocket when persisted presentation session runs in StepFun mode | `main.py` presentation websocket entrypoint | learner presentation live runtime, page requirements feedback, role-aware interruption copy | **live** | Presentation realtime is not a separate AI stack; it is a live adapter on top of the same StepFun transport/runtime seam with sales-only capabilities disabled. |
| `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` + `backend/src/common/knowledge_engine/compat.py` | StepFun tool `search_internal_knowledge`; admin debug trigger also reuses the same compat helper | StepFun realtime handler tool path, `admin/api/knowledge_answer_config.py::debug_trigger_knowledge_answer` | websocket `_answerability` / `knowledge_answer_diagnostics`, transcript metadata, `KnowledgeAnswerRun` audit rows, debug payloads | **live rollout seam** | All shipped rollout modes (`legacy` / `enabled` / `dual_run`) pass through the compat seam. Learner-visible payload shape and rollout diagnostics are controlled here, not by direct engine callers. |
| `backend/src/common/knowledge_engine/engine.py` | only via `execute_knowledge_answer_engine(...)` | StepFun internal knowledge searcher, admin debug trigger | compat payloads/audit runs only through compat layer | **shadow by default; live only when enabled** | The engine is real code, but default repo behavior is still `legacy`; in `dual_run` it is shadow-only, and even in `enabled` mode it remains wrapped by the compat seam. |
| `backend/src/prompt_templates/service.py` + `backend/src/prompt_templates/api/routes.py` | `/api/v1/prompt-templates*`; scenario/template lookup from evaluation/report compilation and presentation interruption flows | prompt template admin routes, `evaluation/api.py`, evaluation/report services, presentation handlers | admin prompt governance UI/API, presentation interruption prompt fallback, compiled evaluation/report prompt contracts + diagnostics | **live governance + legacy compiled contract authority** | Prompt templates remain the admin control-plane surface and now also compile the concrete legacy evaluation/report prompt artifact that runtime consumers execute, but they are still not the live sales StepFun instruction authority. |
| `backend/src/evaluation/services/realtime_scoring.py` + `backend/src/evaluation/services/ai_scoring.py` + `backend/src/sales_bot/websocket/components/score_processor.py` | legacy sales websocket path (`voice_mode == "legacy"`) and scoring-context lookup during session finalization/report trigger | `ScoreProcessor`, `common/db/session_lifecycle.py`, `report_generation_trigger.py` | legacy `score_update` events, scoring context for compat report generation | **compat runtime** | These services are still reachable in the shipped classic voice path, so they are not dead. But StepFun sessions already write the canonical sales score/evidence line elsewhere, so this is no longer the primary truth surface. |
| `backend/src/evaluation/services/staged_evaluation.py` + `backend/src/evaluation/services/comprehensive_report.py` + `backend/src/evaluation/services/report_generation_trigger.py` + `backend/src/evaluation/api.py` | `/api/v1/evaluation/sessions/{id}/report`, `/api/v1/practice/sessions/{id}/comprehensive-report`, background report trigger on session end | `evaluation/api.py`, `common/api/practice.py`, `PracticeReportService._maybe_generate_comprehensive_sales_report()`, `EnhancedSalesHandler._handle_session_end()` | optional comprehensive-report fetches, `report_status` badges/diagnostics on history/support/admin, manual operator API usage | **compat enhancement / retire candidate** | This path is user-visible and still live enough that frontend/report-status surfaces consume it, but it is not the canonical completed-session truth line. Canonical learner/admin report/replay/history facts already sit on `/practice/sessions/{id}/report` + `SessionEvidenceService`; this layer is an enhancement/compat reader, not the source of truth. |
| `backend/src/common/ai/llm_service.py::evaluate/generate_report` | only through evaluation services | `StagedEvaluationService`, `ComprehensiveReportService` | legacy staged evaluation JSON and detailed comprehensive-report text | **compat backend adapter + compiled-contract consumer** | Its shipped role is still limited to the legacy evaluation/report stack, but these entrypoints now execute `CompiledPromptContract` when callers provide one and keep the raw-dict hardcoded prompt path only as compatibility fallback for untouched callers. |

**T02 compiled prompt authority map（当前代码拥有的 inventory）**
- **live compiled contract**：`voice_runtime_policy.py` 会把 `persona_policy`、`customer_pressure`、`tool_policy` 交给 `voice_instruction_compiler.py`，产出 `policy["instructions"]` 与 `instruction_contract_hash`；这条 compiled artifact 仍然是 StepFun live/presentation realtime 真正消费的 prompt contract。
- **live runtime guardrails**：`tool_policy`、`network_access_mode`、`require_kb_grounding`、`kb_lock_mode` 不只是配置字段，它们会同时影响 compiled instruction 文本和 StepFun tool surface，所以属于 prompt control plane 的 runtime authority。
- **live governance + compiled legacy contract authority**：`PromptTemplateService` 仍真实服务 admin prompt governance 与 presentation interruption fallback；对 legacy evaluation/report 来说，它现在会通过 `compile_runtime_prompt_contract(...)` 把 template 严格 render 成 `CompiledPromptContract(rendered_prompt + system_message + contract_hash)`，再交给运行时 consumer 执行。
- **explicit diagnostics / fail-closed boundary**：legacy evaluation/report 的 compiled contract 现在会显式暴露 missing var、empty render、provider/base_url policy 等诊断；典型 failure surface 是 `[PROMPT_CONTRACT_MISSING_VARIABLES:*]`、`[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]`、`[PROMPT_CONTRACT_BASE_URL_REQUIRED]`，不再 silent fail-open。
- **compat backend adapter**：`LLMService.evaluate(...)` / `generate_report(...)` 现在会消费 `CompiledPromptContract`，但 raw dict 输入仍保留 hardcoded prompt fallback，供未迁移 caller 继续运行。
- **admin routing rule**：改 `prompt-templates` / `scenario-prompts` 会影响下一次 legacy evaluation/report compiled prompt 与 presentation interruption helper；改 `personas` / `voice-runtime` 会影响下一次 StepFun 会话的 live instruction contract；改 `model-configs` 的 provider / `base_url` 决定 legacy compiled contract 能否执行。
- **S03 canonical evaluation kernel authority entry**：后续如果要继续收口 canonical evaluation kernel，入口应从 `prompt_templates.service.PromptTemplateService.compile_runtime_prompt_contract(...) -> CompiledPromptContract -> common.ai.llm_service.LLMService.evaluate/generate_report` 这条 seam 开始，而不是重新回到 lookup template 后各自重建 prompt 的旧路径。
- **code-owned proof surface**：后续如果有人要回答“哪个 prompt source 是 live、哪个只是 compat、哪个 surface 会影响哪个 runtime path”，先看 `prompt_templates/taxonomy.py::build_prompt_source_taxonomy()`、`prompt_templates.service.PromptTemplateService.compile_runtime_prompt_contract(...)` 与 `common.ai.llm_service.LEGACY_PROMPT_ENTRYPOINTS`，不要重新凭 grep 猜测。

**Current M021/S01 downstream rule**
- 如果改的是 live sales/presentation realtime behavior、prompt contract、knowledge diagnostics、claim truth、runtime guardrail，就先看 `stepfun_realtime_handler.py`、`voice_runtime_policy.py`、`voice_instruction_compiler.py`、`stepfun_internal_knowledge_searcher.py`、`common.knowledge_engine.compat`。
- 如果改的是 prompt governance UI / scenario template assignment，它现在会影响 compiled legacy evaluation/report contract 与 presentation interruption fallback，但不要把它误写成 live sales runtime prompt authority。
- 如果改的是 `score_update`、`report_status`、`/evaluation/*`、`/practice/*/comprehensive-report`，默认把它们当 **compat/enhancement** surface；除非后续 slice 明确晋升，否则不要倒推它们为 canonical report/evaluation kernel。
- 当前没有可以直接标成 **retire now** 的 AI 路径：legacy evaluation/classic scoring 仍有 shipped consumers。真正的 retire 判断要等 S02/S03 先把 compiled prompt contract 和 canonical evaluation kernel 收口后再做。

**T03 live/compat/retire input matrix（供 S02-S04 直接复用）**

| Bucket | Path / seam | Why it stays in this bucket now | Current consumer / blocker | Downstream input |
|---|---|---|---|---|
| **must keep** | `sales_bot/websocket/router.py` → `stepfun_realtime_handler.py` | 这是当前 learner live AI/runtime authority，本 milestone 不能绕开。 | learner websocket runtime、session snapshot、terminal evidence sync、live knowledge-check consumer | `S02` 只能把 compiled prompt contract 收口到这条 seam；`S03/S04` 默认围绕这条 authority 扩展 canonical evaluation 与 quality events。 |
| **must keep** | `voice_runtime_policy.py` + `voice_instruction_compiler.py` + `presentation_stepfun_realtime_handler.py` | StepFun session 的 frozen snapshot、instruction contract hash、presentation adapter 都来自这里。 | practice session create、sales/presentation StepFun runtime consumer | `S02` 必须把 prompt/runtime 统一建立在 compiled snapshot 上，而不是重新抬升 `PromptTemplateService` 为 live runtime authority。 |
| **must keep** | `stepfun_internal_knowledge_searcher.py` + `common.knowledge_engine.compat` | shipped knowledge rollout authority 已固定在 compat seam，而不是 engine direct call。 | learner `_answerability` / `knowledge_answer_diagnostics`、transcript metadata、admin debug consumer | `S04` 的 degraded/failure/cost/mode 事件必须沿同一 compat seam 暴露，不能旁路成第二条 knowledge truth line。 |
| **compat** | `prompt_templates/service.py` + `prompt_templates/api/routes.py` | 这是 live governance surface；对 legacy evaluation/report 已经是 compiled contract authority，但对 live StepFun runtime 仍不是主指令 authority。 | admin prompt governance UI、presentation interruption fallback、legacy evaluation/report prompt consumer | `S02` 可以继续收紧 taxonomy/compiled contract，但必须保住这些 consumer，直到 runtime-adjacent helper 完成迁移。 |
| **compat** | `evaluation/services/realtime_scoring.py` + `ai_scoring.py` + `score_processor.py` | classic voice mode 仍 shipped，legacy score path 不是死代码。 | `voice_mode == "legacy"` session、`score_update` consumer、report trigger scoring context | `S03` 可以把它降格为 compatibility readers，但不能在 classic mode 仍对外时直接删除。 |
| **retire candidate** | `evaluation/services/staged_evaluation.py` + `comprehensive_report.py` + `report_generation_trigger.py` + `evaluation/api.py` | 这是 enhancement/read-side surface，不是 canonical completed-session truth。 | history/support/admin `report_status` consumer、`/practice/*/comprehensive-report`、manual `/evaluation/*` operator consumer | `S03` 先把这些 consumer 迁回 canonical evidence/report line，再判断是否 retire；本 milestone 不能一刀切删除。 |
| **retire candidate** | `common/ai/llm_service.py::evaluate/generate_report` | 当前只服务 legacy evaluation/report stack，本身不直接挂在 live StepFun authority 上。 | `StagedEvaluationService`、`ComprehensiveReportService` consumer | 只有在 legacy evaluation/report consumer 迁完后才能退役；`S02-S04` 期间默认继续把它当 compat backend adapter。 |

**不能在本 milestone 里粗暴删除的 legacy consumers**
- persisted `voice_mode == "legacy"` 的 classic runtime / `score_update` consumer 仍然存在，所以 scoring compat path 不能在 `S03` 之前被删空。
- `history` / `support` / `admin` 侧的 `report_status`、`/practice/*/comprehensive-report`、manual `/evaluation/*` operator consumer 还在吃 legacy evaluation 输出，必须先迁到 canonical evidence line。
- `PromptTemplateService` 仍服务 admin prompt governance 与 presentation interruption fallback consumer；即使 `S02` 收口 compiled prompt contract，也不能把它当场拔掉。
- knowledge-answer rollout audit / admin debug consumer 仍通过 `common.knowledge_engine.compat` 观察 mode 与 diagnostics，所以 `S04` 不能直接跳过 compat seam 改成 engine-only truth。

**T02 proof/doc consumer sync**
- `docs/api-contract/sessions.md` 现在负责写清 live runtime/read-side consumers：session create + websocket mode selection 固化 snapshot authority，而 detail/report/knowledge-check/replay 都回读同一条 authority line。
- `docs/api-contract/prompt-templates.md` 现在负责写清 compiled legacy evaluation/report contract、显式 diagnostics，以及 prompt-templates / personas / voice-runtime / model-configs 之间的 admin 变更路由。
- `docs/api-contract/voice-runtime.md` 与 `docs/api-contract/personas.md` 现在共同写清 live StepFun compiled instruction authority：persona policy 是上游输入、runtime profile 是 guardrail/工具面 authority、会话 snapshot 仍是冻结边界。
- `docs/api-contract/model-configs.md` 现在承接 provider / `base_url` policy 的管理面修复入口，说明它决定的是 legacy compiled contract 能否执行，而不是 prompt source 选择。
- `docs/api-contract/support-runtime.md` 继续承接 support/read-side consumer 解释：`/support/runtime/*` 是 release-health / fault summary surface，不能替代 process-local live connection authority 或 shared Redis reconnect snapshot authority。

#### 7.3.2 M021/S03 canonical evaluation kernel baseline（T01 write-back）

T01 之后，canonical evaluation schema 与 compatibility reader map 不再只存在于计划文字里，而是已经固化到代码：
- `backend/src/common/effectiveness/canonical.py`
- `backend/src/common/conversation/session_evidence.py::describe_projection_kernel_contract(...)`

**统一 rollup contract（sales / presentation 共享）**
- canonical schema version：`evaluation_kernel_v1`
- shared rollup ids：`logic` / `accuracy` / `completeness`
- 这三个 rollup 继续兼容当前 DB / API 的 `logic_score`、`accuracy_score`、`completeness_score`，但维度层改为 scenario-aware catalog，而不是假设 sales / presentation 共享同一组 dimension label。

| Scenario | Canonical dimensions | Rollup mapping | 当前 compat 映射 |
|---|---|---|---|
| sales | `value_expression`、`customer_benefit_connection`、`evidence_usage`、`objection_handling`、`next_step_commitment` | `customer_benefit_connection` 同时参与 `logic` 与 `accuracy`；其余按当前 sales rollup 权重映射 | `practice_session_rollup_fields_v1`、`effectiveness_snapshot_v1`、`sales_realtime_score_snapshot_v1`、`comprehensive_sales_report_v1` |
| presentation | `fluency_coherence`、`factual_accuracy`、`professionalism`、`vividness`、`qa_handling`、`overall_presence` | `fluency_coherence -> logic`、`factual_accuracy -> accuracy`、其余四项平均进入 `completeness` | `practice_session_rollup_fields_v1`、`presentation_review_dimensions_v1` |

**surface cutover rule（当前 authoritative map）**
- `report` / `replay` / `history` / `admin`：`canonical_consumer`，primary reader 一律是 `session_evidence_projection_v1`
- `realtime`：仍是 canonical source，但 sales 读 `sales_realtime_score_snapshot_v1`，presentation 读 `presentation_review_dimensions_v1` 作为 terminal dimension source
- `comprehensive_report`：明确降格为 `compat_mirror`，不是 completed-session truth

**downstream execution rule（S03/T02-T03 直接复用）**
- 如果要判断某个 surface 现在是否已经切 canonical，先查 `get_surface_reader_plan(...)`，不要再从页面/接口字段名倒推。
- 如果要判断 projection 这条事实线对外暴露的 canonical schema/version/dimension ids，先查 `describe_projection_kernel_contract(...)`，不要再在 report/replay/history/admin 各自维护一份解释。
- S03 后续实现只能新增 canonical reader 或替换 compat reader 的调用点；不能再引入第三套 score dimension / rollup vocabulary。
- web/report、web/replay、web/history、web/admin 的读侧退役顺序也必须固定：先 **prefer `canonical_evaluation_kernel`**，缺失时再显式退回 `compatibility_readers`，只有在这两层都缺席时才读 legacy top-level rollup 字段。这样 compat reader 的退役条件才可被准确判断——当这些 web/admin consumers 全部不再命中 compat fallback，`practice_session_rollup_fields_v1` / `presentation_review_dimensions_v1` 等 reader 才进入真正的 retire 阶段，而不是边迁移边继续让页面偷偷依赖旧字段。

#### 7.3.3 M021/S04 quality / cost / failure inventory baseline（T01-T03 write-back）

T01 之后，S04 不再需要从 scattered fallback 文案里反推 AI runtime 发生了什么；当前 shipped hiding spots 已经被固定成三条 authority inventory：
- `backend/src/common/ai/llm_service.py::LLM_RUNTIME_EVENT_INVENTORY`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py::STEPFUN_RUNTIME_EVENT_INVENTORY`
- `backend/src/common/knowledge_engine/compat.py`（knowledge-answer rollout/mode 仍是 compat seam authority）

**当前 inventory 结论**
- **default score 不等于真实低分**：`LLMService.evaluate()` 在模型输出无法通过 `json.loads()` 时，会直接返回 60/60/60/60/60 + “完成了销售对话练习” 这组默认结果；这必须被视为 future `quality_degraded` 候选，而不是正常 evaluation success。
- **default report copy / fallback answer 不等于真实生成成功**：`LLMService.generate()` 在 `allow_fallback_response=True` 时会把 provider/config/runtime 失败翻成 filler 文案；`generate_report()` / `ComprehensiveReportService` 侧还会把多种失败压成 `[REPORT_GENERATION_FAILED]` 或空 `detailed_feedback`。这些都说明当前 report/enhancement path 仍会把 failure 翻译成“像成功一样的文本”。
- **cost tracking 目前只有 coarse in-memory total**：`cost_per_1k_tokens` + `session_costs[session_id]` 只记录成功 `agenerate()` 的粗粒度成本，没有 per-call/provider/contract/event 线，也没有把 degraded/failure 与 cost 关联起来。
- **StepFun runtime 已经有大量 implicit degraded signals，但还没统一成 event schema**：`KB lock warmup degraded`、`capability_pipeline_failed`、`browser_tts` fallback、`blocked_transcription_timeout`、以及 `coach_health` 的 `healthy/degraded/resumed` 切换都是真实运行信号，但今天仍分散在 log、payload flag、状态机字段里。
- **knowledge-answer path truth 仍必须沿 compat seam 读取**：live/dual_run/legacy 仍由 `resolve_knowledge_answer_rollout_mode()` 决定，`_diagnostics.knowledge_answer_rollout` + `_answerability` / `knowledge_answer_diagnostics` 才是今天唯一真实的 mode/evidence line；S04 后续不能旁路成另一套 engine-only truth。
- **claim-truth / knowledge diagnostics 已进入 live session payload，但 failure semantics 仍需要显式化**：`practice.py` 与 `stepfun_realtime_handler.py` 已能回读 `claim_truth`、`knowledge_answer_diagnostics`，这意味着 S04 不需要新造 evidence carrier；要做的是把 degraded/failure/cost/mode 事件并到同一 diagnostics 线上，而不是继续让 default 文案替代状态。

**S04/T02 downstream eventization rule（下一任务直接复用）**
- event schema 必须把 `mode` / `degraded` / `failure` / `compat` / `cost` 放在同一 inspection surface，而不是继续拆成 logger-only、payload-flag-only、status-only 三条线。
- event source 必须沿现有 authority seam收口：legacy evaluation/report 走 `LLMService` inventory，live sales runtime 走 `StepFunRealtimeHandler` inventory，knowledge-answer mode 走 `common.knowledge_engine.compat` inventory。
- support/admin 可见面只能暴露 allowlist-safe diagnostics（`trace_id`、`error_code`、`phase`、`session_id`、mode/degraded/failure/cost summary）；provider rejected 原文、prompt text、`base_url`、token、request/response body 仍保持 backend-only。
- knowledge-answer 的最终目标不是“只剩 enabled mode”，而是 **live + compat mode 可解释**：即便继续保留 compat/dual-run，也必须让 future readers 不用猜测当前回答到底来自 legacy、enabled 还是 shadow/live split。

**T02/T03 当前 shipped read-side / proof rule**
- unified inspection surface 已经收口到 `backend/src/common/knowledge_engine/runtime_events.py`：当前 event shape 固定为 `event_id / category / severity / status / source / summary / details / metrics / occurred_at`，其中 `category` 只使用 `quality | cost | failure | mode`，`severity` 只使用 `info | ok | degraded | failure`。
- support/read-side 现在不需要重新拼第二套 payload：`common.conversation.runtime_diagnostics.build_session_runtime_diagnostics()` 会把 knowledge-answer、kb-lock、claim-truth 的 runtime events 合并到同一 diagnostics 线上，`support.services.runtime_status_service` 再把这条线透传到 `/api/v1/support/runtime/faults.items[].diagnostics.runtime_events[]`。
- 读 support/runtime 时必须显式区分：`category = mode` / `status = live|compat` 回答的是**路径来源**，不是失败等级；真正的 degraded / failure 由 `severity` 负责表达，cost 事件则说明 token/session budget 观测，不自动等价于成功或失败。
- report / replay 前端 proof 不应该再把 compat 或 failure 翻译成“低质量成功”：score 读侧必须通过 `data-contract-source = canonical_kernel | compatibility_reader | legacy_rollup` 明确来源，evidence degradation / retrieval failure 文案则必须继续显式显示 degraded / failure 语义，而不是退回模糊低分解释。
- downstream 如果要验证这条 read-side 是否仍成立，先看 `docs/api-contract/support-runtime.md`、`web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`、`web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`，不要再从 fallback 文案、默认分数或 scattered logs 倒推当前 runtime truth。

### 7.4 Theme D — Sales productization / org-ready roadmap
对应问题：
- 更像内部训练平台，不像成熟销售产品
- 方法论、角色深度、行业包不足
- manager/admin truth surfaces 不够可信
- organization/team/tenant 目标态不明确

落点：**M022**

**M022/S01 methodology-aware rubric baseline（已落地 authority contract，T02 接线）**
- `backend/src/common/effectiveness/methodology.py::get_sales_methodology_contract()` 现在是首轮销售方法论 contract 的代码 authority，而不是让 realtime / report / history / admin 各自猜什么叫“好销售对话”。
- 首轮 rubric 固定为 `discovery_qualification`、`value_story`、`evidence_proof`、`objection_reframe`、`next_step_commitment` 五个维度；它们全部显式映射到现有 canonical dimension ids、`main_issue` / `next_goal` family、以及 realtime/report/read-side 的 shipped evidence path。
- 这条线 **是 additive contract，不是新 score schema**：`logic/accuracy/completeness`、`dimension_scores`、`effectiveness_snapshot.main_issue`、`effectiveness_snapshot.next_goal` 继续保留，方法论语义只是把这些现有 surface 串成一个统一 crosswalk。
- 当前 `sales_stage` 没有独立 `qualification` stage，所以第一轮 contract 明确把 qualification 并入 `opening + discovery`；后续若拆出独立 qualification，必须同步改 code contract、docs/api-contract/effectiveness.md、以及 focused proof，不能只在某个 surface 偷改解释。
- T02 downstream rule：直接复用这份 contract 接 realtime / report / session_evidence / manager read-side，不要再在各个 consumer 中复制 rubric 定义或另造 manager-only taxonomy。
- T03 write-back rule：learner-facing report copy 与 manager-facing 文档必须统一解释五个首轮 rubric 视角——`discovery / qualification`、`value`、`evidence`、`objection`、`next-step`——并明确 `main_issue` / `next_goal` 只是这套 rubric 在 canonical evidence 上的缺口与补强动作，不是额外的第二套评分器。
- T03 boundary rule：对外话术必须保持 boundary-honest。当前可以说“系统已能把 rubric 命中、缺口、校准写回报告 / history / admin 说明”，但不能说“已经覆盖完整销售方法论”或“已经有独立 qualification stage / rubric”。

**M022/S02 persona / scenario / industry-pack contract（T01 已定义 authority surface）**
- 当前 repo 里**没有独立 `industry_pack` 表或第二套内容平台**；首轮 industry pack 必须被视为一个 composed asset：`agent` 负责 runtime shell / capability defaults，`persona_policy` 负责角色设定 + `customer_pressure` + `knowledge_base_ids` / tool policy，`Scenario` 负责 session-facing 场景标签与 legacy `persona_prompt` 兼容面，knowledge 仍通过现有 `/api/v1/admin/knowledge/*` entrypoints 管理。
- 代码 authority 已落到 `backend/src/agent/services/industry_pack_contract.py`，并通过 `/api/v1/admin/agents/industry-pack-contract`、`/api/v1/admin/personas/industry-pack-contract`、`/api/v1/scenarios/sales/runtime-contract` 暴露 inspectable contract；未来 agent 不需要翻大文件才能判断字段归属。
- **字段归属规则（首轮固定）**：
  - persona-owned：`persona_policy.system_prompt`、`traits`、`behavior_config`、`tts_config`、`difficulty`
  - customer-pressure-owned：`persona_policy.customer_pressure.pressure_direction.*` + `follow_up_behavior.*`
  - knowledge-bundle-owned：`persona_policy.knowledge_base_ids` + `persona_policy.tool_policy.*`
  - scenario-owned：`scenarios.scenario_id / scenario_type / name / description`，以及 legacy-only `persona_prompt`
- **运行时映射规则（首轮固定）**：
  - persona / customer pressure / knowledge bundle 最终都要经过 `sales_bot.services.voice_runtime_policy.resolve_effective_policy()` 汇总，再冻结到 `practice_sessions.voice_policy_snapshot`
  - `customer_pressure` 还会被 `voice_instruction_compiler.compile_base_contract()` 编译进 `【销售追问焦点】` 指令段，说明它不是 metadata，而是 live prompt contract
  - knowledge bundle 会落到 `voice_policy_snapshot.knowledge_base_ids`，并进一步影响 StepFun tools、internal retrieval、以及 `runtime_diagnostics.build_retrieval_facts()` 的 read-side truth
  - scenario metadata 参与 session create / websocket scenario routing，但**不能**替代 persona-centered snapshot 成为 sales runtime truth
- `GET /api/v1/scenarios/sales/personas` 现在会给每个 persona 返回 `runtime_binding` 摘要，明确该角色当前 customer-pressure source、sales focus、objection axes、expected questions、knowledge_base_ids，以及它们会影响哪些 runtime surfaces；这条摘要是 T02 把 manager/admin truth 接上时的复用入口，而不是临时 debug 文案。
- **资产运营规则（T03 write-back）**：
  - `industry pack` 是 composed operating bundle，不是新表/新平台：运营上应通过现有 agent/persona/knowledge/scenario surfaces 组合发布，而不是另外维护一套 `industry_packs` 控制平面。
  - `customer pressure` 是 live runtime lever：它通过 `voice_instruction_compiler.compile_base_contract()` 进入实时指令，并在冻结后的 `voice_policy_snapshot_ref.runtime_binding` 中留下可审计摘要；如果运营改了 pressure axes / follow-up behavior，就应该预期 runtime 行为、report evidence、manager calibration summary 一起变化。
  - `knowledge bundle` 是 retrieval/evidence lever：运营上真正可维护的是 `knowledge_base_ids` + `tool_policy` 组合；report 与 manager/admin 读侧应通过冻结的 `runtime_binding` / retrieval facts 解释“本次训练为何出现这些行业事实与追问证据”，而不是单看 prompt 文案猜测。
  - `scenario package` 只是 session entry / routing / narrative lever：它可以承载行业故事、场景描述、legacy `persona_prompt` 兼容说明，但不能被包装成 sales runtime truth source；真正进入 runtime / report / calibration 的 authority 仍是 persona-centered snapshot + runtime binding。
  - manager calibration downstream rule：M022-S03 的 manager/admin truth surfaces 应直接复用 `voice_policy_snapshot_ref.runtime_binding` 与现有 contract endpoints 解释“这次校准基于哪个 industry pack / customer pressure / knowledge bundle”，不要再做一套 manager-only asset taxonomy。
  - **仍属手工内容运营项**：行业话术/角色设定仍主要来自 `persona_policy.system_prompt`、traits、behavior config 的人工策划；`customer pressure` 的 objection axes、expected questions、follow-up style 仍需人工编排；`knowledge bundle` 的文档挑选与更新节奏仍是人工运营；`scenario package` 的 narrative、brief、persona_prompt 兼容文案也仍是人工维护。系统现在提供的是可检查 contract 与 runtime evidence，不是自动生成整套行业包内容。
- downstream rule：如果未来要给某个行业再加“行业包”运营能力，优先把 metadata 写进 persona-centered contract（或其显式 extension key）并通过上述 contract surfaces / runtime snapshot 证明影响；不要新造 `industry_packs` 控制平面后再把现有 admin/persona/knowledge surfaces 晾在一边。

**M022/S03 manager/admin truth-surface inventory（T01 已盘点 fake stats 与漂移 summary）**
- `web/src/app/admin/page.tsx` 当前已经明确分成两类 truth surface：
  1. **真实 surface**：顶部“训练效果核心看板（近7天）”直接读取 `api.internal.health()` 与 `api.analyticsOpen.getDashboard({ days: 7 })`，只表达 backend online/offline 与四个 effectiveness pass-rate / retry-rate 指标；
  2. **inventory / 待接 surface**：总用户数、活跃会话、系统健康度资源指标、存储使用率，以及下半页的公告/快捷动作/系统动态/告警入口都还没有统一 authority，所以必须显式降级为 truth surface inventory，不能继续伪装成实时运营数字。
- `web/src/app/admin/analytics/page.tsx` 已经是当前 admin/manager 的 **P0 真实读侧**：`api.analytics.getOverview()`、`getTrends()`、`getOperatingPack()`、`getLeaderboard()`、`api.analyticsOpen.getDashboard()`、`api.supportRuntime.getFaults()` 共同组成 projection-backed 经营包、趋势、重复 blocker family、证据不足 / degraded breakdown、runtime fault linked-assets 等真实 summary。这里的 copy 已明确区分 evaluable vs not-evaluable / degraded，因此不应再在首页重新造一套“总览均分 + 运营故事”。
- `web/src/components/admin/manager-lite-panel.tsx` 是当前主管最小干预面的 **P0 真实 surface**：未达标名单、连续未练名单、达标上升名单都来自 `manager_lists`，并直接把主管带回统一报告与 `/admin/users/[id]` drill-in。它的统计边界已经固定为“只看已完成、可评估、可解释的训练证据”，后续不能再退回 manager-only 假名单或本地凑数。
- `web/src/app/admin/users/[id]/page.tsx` + `backend/src/admin/api/users.py` 是当前主管校准 / team coaching 的 **P0 真实 surface**：`get_user_stats()`、`get_user_sessions()`、`get_user_progress()`、`list_manager_interventions()` 和 `history_service.get_manager_intervention_results()` 都沿用 `SessionEvidenceService` / projection-backed history truth line。连续变化判断、主管重点、对应训练结果、runtime fault 关联资产都已经建立在 canonical evidence 上，而不是本地 summary 文案。
- **当前 manager calibration / team coaching 入口（写死为产品边界）**：
  1. `manager-lite-panel` = 主管日常分诊入口，负责 not passed / trend / 连续未练 / 达标回升名单；
  2. `/admin/users/[id]` = 单人 calibration / coaching 入口，负责 drill-in 到 session evidence、进步轨迹、manager interventions；
  3. `/admin/analytics` = 团队 coaching / 运营回顾入口，负责 team summary、degraded breakdown、repeat blocker family、runtime fault 关联资产。
- **当前可产品化边界（必须对外诚实）**：
  - 已可产品化：canonical evidence 驱动的 analytics、manager-lite、user detail / interventions。这些 surface 已能支持主管做“谁没过、为何没过、最近趋势、该跟进什么训练动作”的真实判断。
  - 仍属后续工作：admin 首页上的组织/资源/运维汇总卡、下半页快捷动作/系统动态/告警自动化、独立的 manager calibration workspace、脱离现有 user detail 的 team coaching cockpit。它们目前只能作为 inventory/roadmap surface，不能包装成已交付功能。
- **T02 优先级规则（固定）**：
  1. 先 truthify admin home 上最容易被误读为实时运营数字的四张卡（总用户、活跃会话、系统健康资源指标、存储）；
  2. 再复用 admin analytics / manager-lite / user detail 这三条现成真实线去承载主管决策面；
  3. 没有真实 authority 的 surface 必须继续保留为说明文案或跳转入口，不能在 manager/admin 面板上再发明 demo score、假趋势或 manager-only taxonomy。
- **T03 write-back rule**：产品与架构文档必须统一说清楚——当前 manager/admin 已产品化的是 canonical evidence 驱动的 analytics、manager-lite、user detail / interventions；仍未产品化的是 admin 首页上的组织/资源/运维汇总卡与下半页快捷动作/动态/告警自动化。对外不能把这些 inventory surface 说成“已接通的运营总览”，也不能把现有入口扩写成“完整 manager OS”。

**M022/S04 organization / team / tenant target-state matrix（T01 当前 contract baseline）**
- 当前代码里的 ownership/authz 仍是 **global user + global role + row-level user_id** 模型，而不是 org-aware 模型：
  - identity/auth：`users.user_id` 是唯一身份键，`users.role` 只表达全局 `user | support | admin`；`AUTH_TRANSPORT_MATRIX` 与 `get_current_admin_user()` 也只认全局角色，不认 organization/team membership。
  - learner runtime/report：`practice_sessions.user_id` 是训练、report、replay、history 的唯一业务 owner；`common.api.practice._can_read_session(...)` 只允许 `session.user_id == current_user.user_id` 或全局 admin 读取。
  - manager/admin surface：`manager_interventions.manager_user_id + user_id` 直接绑定两个全局 user；`admin/api/users.py`、`admin/api/analytics.py` 全都在 admin-only guard 之后做跨用户聚合，没有 team/org row filter。
  - content/control plane：`agents.created_by`、`personas.created_by`、`knowledge_config_versions.created_by/updated_by` 等只是审计字段；`knowledge_bases` 本身没有 owner/org 列，删除引用检查也只是全局扫描 agent/persona 对 KB 的引用。
  - runtime asset binding：sales runtime 真正继承的是 `agent_id + persona_id + voice_policy_snapshot.knowledge_base_ids/runtime_binding`，这些绑定会冻结进 session snapshot，但不会回指某个 organization/team。
- 这意味着当前仓库存在一组隐含的 **single-organization assumptions**：

| Surface | 当前 shipped owner / scope | 隐含假设 | 为什么会卡住下一阶段 |
|---|---|---|---|
| Identity / auth | `users.user_id` + global `role` | 一个用户只活在一个默认组织上下文里 | 无法表达同一身份在多个 org/team 的不同角色；SSO/group sync 也没有落点 |
| Practice session / report / replay / history | `practice_sessions.user_id` | learner 资产永远只按个人归属 | manager/team/org analytics 只能靠事后聚合，不能表达合法的组织可见范围 |
| Manager interventions | `manager_user_id -> user_id` | 主管和学员天然处于同一隐式组织 | 无法区分跨 team delegation、临时代理主管、或 org 内 team 迁移 |
| Admin analytics / admin users | admin-only route + 全局聚合 | 现有 admin 就是全租户超级管理员 | 未来 enterprise admin、org admin、team manager 无法共存 |
| Agent / persona / knowledge assets | global row + `created_by` audit | 内容资产默认全局共享 | 无法区分 org 私有包、共享模板库、和 team-level rollout bind |
| Runtime binding / report evidence | session snapshot 继承 `agent/persona/kb` | 只要 session 冻结了就足够解释上下文 | downstream 仍缺 org/team seam，无法说明这次训练属于哪条组织经营线 |

- T01 固定的 **target-state 概念边界** 不是“马上做多租户”，而是先把未来 enterprise boundary 说清楚：
  - **Organization** = 商业/account/authz 顶层边界。未来 SSO、CRM、directory sync、billing、org-level analytics 都挂在这里。
  - **Team** = organization 下的运营/管理 cohort。manager-lite、`/admin/users/[id]`、`/admin/analytics` 的默认主管视角最终都应先落到 team scope，再在需要时向上汇总到 org。
  - **Member** = `user` 在某个 organization 内的一条 membership，而不是新的身份表。用户身份可以全局存在，但权限、team assignment、manager chain 应通过 membership 决定。
  - **Tenant** = 更重的数据/部署隔离边界，不等于 organization。只有当未来出现真正的数据驻留、独立 infra、或客户要求物理隔离时，tenant 才值得从 org 之上/之外晋升为实现对象；本轮只保留 slot，不提前实现。
- T01 固定的 **role / access-scope target state**：

| 概念 | 目标职责 | 当前映射来源 | T01 结论 |
|---|---|---|---|
| Platform role | 平台级运维/支持/全局 admin（如 `support`、平台运维） | `users.role` | 继续保留为 global role，不拿它直接表示 org 内业务角色 |
| Org role | org owner / org admin / org analyst | 当前没有；只能由 global admin 代行 | 未来放到 membership 上，而不是继续塞进 `users.role` |
| Team role | team manager / coach / member | 当前隐含在 manager-lite、manager interventions、admin users drill-in | 未来应从 membership + team assignment 派生，不再靠页面入口默认推断 |
| Access scope | self / team / org / platform | 当前只有 `self` 与 `platform(admin)` 两档 | 后续 authz 应明确 scope，而不是继续写 `is_admin or user_id == owner` |

- T01 固定的 **entity / asset ownership target-state matrix**：

| Entity / asset | 当前 authority | Target-state owner seam | Authz / analytics implications |
|---|---|---|---|
| User identity | `users.user_id` | global identity + `organization_member` | 登录身份继续全局；组织权限从 membership 派生 |
| Practice session | `practice_sessions.user_id` | learner member owns session；同时挂 `team_id` / `organization_id` compatibility reader | report/replay/history 仍按 learner evidence 出真相，但 manager/org 统计可合法聚合 |
| Manager intervention | `manager_user_id` + `user_id` | manager member ↔ learner member，在同一 org 下解析 team chain | 支持 team manager 只看本 team，org admin 看全 org |
| Agent / persona templates | global rows + `created_by` audit | 先保留 global template library，再引入 org-scoped binding/publishing seam | 避免一上来复制所有内容资产；先区分“模板”与“org rollout binding” |
| Knowledge base / knowledge bundle | global KB rows + persona policy references | KB row 可继续全局，但 rollout binding 要支持 org visibility / org-private bundle | analytics/report 继续解释 `knowledge_base_ids`，但未来能回答“这个 org 能看到哪些 KB” |
| Admin analytics / manager-lite | admin-only global surfaces | team default scope + org aggregate scope + platform override | 后续页面不改成第二套产品，只给现有 surface 补 scope selector / scope-aware query |
| Prompt / runtime / knowledge-answer control plane | `created_by/updated_by` audit | org-governed config version / rollout binding，platform admin 保留 override | 让 enterprise config 可以挂 org，而不是只能由平台 admin 全局改 |

- **Authz downstream rule（固定）**：后续 enterprise work 不应继续新增 `require_role(["admin"])` 这种只看全局角色的分支判断，而应转向“platform role + org membership role + access scope”三层判定；在真正做 authz 重构前，文档和计划都要把当前 global-admin seam 视为 compatibility seam。
- **Analytics downstream rule（固定）**：`manager-lite-panel`、`/admin/users/[id]`、`/admin/analytics` 继续是当前真实 manager/admin evidence surface；未来只是在它们背后补 `self/team/org/platform` scope reader，而不是另做一套 org dashboard。
- **Asset downstream rule（固定）**：agent/persona/knowledge 先视为“global template + org rollout binding”两层，而不是直接把现有表全改成 org-owned。否则会在还没定义 membership/authz 前就把内容面硬分叉，反而破坏 M022/S02 已建立的 persona-centered runtime contract。
- **Integration slots（仅保留目标态落点，不提前实现）**：
  - SSO / enterprise directory → `organization_member` provisioning + team assignment source
  - CRM / account sync → organization-level account metadata / customer segmentation source
  - Org sync / HRIS → manager chain、team membership、deactivation/transfer source
- **T02 migration precondition（由 T01 锁定）**：后续迁移必须先加 org/team compatibility readers 到 session / analytics / manager read-side，再决定哪些实体值得真正落库 ownership；在那之前，不应把 `tenant`、SSO、CRM 直接写成当前 MVP 的已实现能力。

---

## 8. 与本轮规划最相关的模块清单

### 前端
- `web/src/lib/api/client.ts`
- `web/src/lib/auth-handler.ts`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/websocket/*`
- `web/src/app/(user)/practice/[sessionId]/*`
- `web/src/app/admin/page.tsx`
- `web/src/app/admin/logs/page.tsx`
- `web/src/components/admin/*`

### 后端
- `backend/src/main.py`
- `backend/src/common/db/session.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/auth/api.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/monitoring/logger.py`
- `backend/src/common/monitoring/metrics.py`
- `backend/src/common/websocket/session_manager.py`
- `backend/src/common/websocket/session_state_service.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/prompt_templates/*`
- `backend/src/evaluation/services/*`
- `backend/src/common/effectiveness/*`
- `backend/src/common/knowledge_engine/*`
- `backend/src/admin/api/*`

### 文档 / 运维 / 规划
- `docs/api-contract/*`
- `docs/setup/auth-local.md`
- `docs/backup-recovery-runbook.md`
- `.github/workflows/*`
- `.sisyphus/deploy/*`
- `.codex/roadmap/PROJECT_FUTURE.md`

---

## 9. 风险与不确定项

1. **不能把 M019-M022 做成“全面重写”**
   - 当前正确策略是：先抽 authority seam、再统一 control plane、最后 productize。
   - 不是先拆服务，也不是先改技术栈。

2. **一些目标必须以 compatibility reader / compat mode 过渡**
   - 尤其是 score schema、prompt path、auth transport。
   - 不能一次性删除 legacy consumers。

3. **组织/多租户目标态目前只能先做 plan，不应抢跑实现**
   - 当前仓库还未到直接上强组织边界的时机。
   - 但再不规划，后续每个功能都会继续把 user/session 当唯一 owner。

---

## 10. 直接输出

本次扫描后的直接 GSD 落地是：
- `.gsd/milestones/M019/*`
- `.gsd/milestones/M020/*`
- `.gsd/milestones/M021/*`
- `.gsd/milestones/M022/*`
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`

这四个 milestone 已按“边界 → 安全/runtime → AI 控制平面 → 产品化/组织化”顺序拆开，后续可直接执行。