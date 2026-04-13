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
- outward domains：`auth`、`user`、`dashboard`、`analyticsOpen`、`supportRuntime`、`training`、`practice`、`sessions`、`scenarios`、`agents`、`analytics`、`admin`、`adminTools`、`presentations`、`adminPresentations`、`internal`
- high-fan-out consumers：learner auth/dashboard/profile/training/practice/report/replay 页面直接依赖 façade；admin analytics/users/personas/knowledge/settings/prompts 与 knowledge-answer debug panels 大量依赖 `api.admin*` / `api.adminTools`。

这意味着 S03 后续拆分不能把页面改成跨 domain 直连实现；正确方向是：
1. 保留 `api` 作为唯一 outward import surface；
2. 把 domain modules 收到 `web/src/lib/api/*` 内部，由 façade 回指；
3. 继续把 auth/error/trace 只留在 shared transport seam，而不是让页面或 domain module 自己处理 401、trace header、payload normalization。

`web/src/hooks/use-practice-websocket.ts` 当前也已经有清晰的 inward/outward 边界，而不是“整文件继续硬拆”：
- outward consumer 现在基本只剩 `web/src/app/(user)/practice/[sessionId]/page.tsx`（以及其测试/mock contract），所以 outward return shape 必须稳定。
- 已抽出的 inward helpers：`websocket/message-handlers.ts` 负责 inbound protocol -> state projection；`websocket/use-audio-playback.ts` 负责 legacy audio queue/unlock；`use-streaming-audio-player.ts` 负责 chunk playback；`use-voice-speed-preference.ts` 负责本地播放速率偏好。
- hook 自身仍是 transport orchestration authority：WS URL + trace 拼装、connect/disconnect、reconnect budget、pending outbound queue、binary negotiate、local backpressure buffer/flush abort、interrupt pre-cleanup。

**S03 downstream consumption rule**
- 如果改的是 auth/error/trace/request transport，优先扩展 API transport seam，而不是在 domain module 或页面里直接 `fetch(...)`。
- 如果改的是 learner/admin domain request surface，优先落在 `web/src/lib/api/*` 的 domain module，再由 `api` façade 暴露；不要让页面跨 domain 引别的实现细节。
- 如果改的是 realtime inbound state projection，优先扩展 `websocket/message-handlers.ts`。
- 如果改的是 websocket URL/auth/reconnect/backpressure/interrupt/outbound pacing，优先扩展 `use-practice-websocket.ts` 或其 transport helper；不要把这些逻辑下沉到 page-level effect。

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
- metrics / frontend error reporting / doc-contract 看似存在但未完全接通

落点：**M019**

### 7.2 Theme B — Security / runtime / recovery
对应问题：
- cookie secure / CSRF / shared-password 兼容风险
- websocket query token
- system log/admin 日志敏感信息暴露面
- SessionManager 多实例/重启语义不清
- recovery 仍偏 runbook 阶段

落点：**M020**

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