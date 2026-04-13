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
- persona/scenario/customer-pressure/industry pack 还没形成强运营 contract
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

### 7.3 Theme C — AI control plane / evaluation kernel
对应问题：
- live path 与 legacy path 并存
- PromptTemplateService 假接入
- prompt 来源碎片化
- score dimensions 多轨漂移
- failure/cost/default fallback 掩盖真实状态

落点：**M021**

### 7.4 Theme D — Sales productization / org-ready roadmap
对应问题：
- 更像内部训练平台，不像成熟销售产品
- 方法论、角色深度、行业包不足
- manager/admin truth surfaces 不够可信
- organization/team/tenant 目标态不明确

落点：**M022**

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