# Project

## What This Is

这是一个企业内部 AI 销售训练平台，围绕真实销售与 PPT 演练闭环建设：管理员配置 Persona / 知识库 / PPT，学员发起训练，会话经过实时语音与评分链路，训练结束后在统一 report / replay / history 路由上复盘，并让主管据此进行线下辅导。

它不是一个“看起来有 AI 感”的演示站。当前工作的主方向是把已有能力收口成稳定、可信、可审计、可持续运营的产品能力。

## Core Value

把“训练 → 反馈 → 复盘 → 再训练”做成真实可用闭环：
- 训练过程尽量稳定，不因生命周期、重连、路由或前端异常轻易断链。
- 训练事实可审计，报告结论能回到 transcript / retrieval / audio evidence。
- 管理员能维护长期运营资产，主管能用统一报告和趋势视角带人。
- learner/admin 前端表层行为要统一、可信，不再依赖 demo 风格的弹窗、硬跳转或硬编码文案。

## Current Product State

### Core shipped baseline
- 已有双训练模式：sales 与 presentation。
- 已有前端骨架：Next.js 用户侧与管理侧、统一 practice / report / replay / history 路由族。
- 已有后端骨架：FastAPI API、WebSocket runtime、PracticeSession 生命周期、报告与回放读侧。
- 已有资产治理：Agent、Persona、知识库、PPT、语音 runtime policy 与对应 admin 页面。

### Already-validated milestone capabilities
- **M001**：桌面端销售训练、PPT 会后复盘、知识生效链、单次报告与主管连续变化闭环已验证。
- **M003**：Persona / knowledge 已能真实影响 objection-heavy 销售训练，而不是只停留在 prompt 文案层。
- **M004**：report / replay / history / retry learner loop 已完成 explanation-rich 收口。
- **M005-M006**：admin analytics / intervention / governance / weekly operating pack 与共享 seam 已完成并封板。
- **M007**：实时教练闭环与 same-session report/replay unlock 已正式封板，R009 已验证。
- **M008-M010**：retrieval truth、raw audio audit、report conclusion evidence / degradation taxonomy 已全部打通并验证。
- **M011**：KnowledgeAnswerEngine、control plane、audit、debug API、compat rollout 已接入现有 runtime。
- **M012**：首登与 learner 基础体验已补齐（forgot-password、可信 dashboard/profile、shared help、practice route fallback 等）。
- **M013**：system audit findings 已归一化成可信 repair backlog 与 focused verification baseline。
- **M014**：learner 入口与体验闭环补齐（dashboard CTA、profile→forgot/reset、shared help、practice preflight/interruption guidance）。
- **M015**：frontend hygiene 与 learner shell 保护收口已完成并封板——raw console 已统一到 shared debug seam，原生 dialog/hard navigation 已收口到 auth-handler/router/dialog/toast seam，learner dashboard/auth/practice 入口已具备明确的 route-level loading/error fallback，并把剩余 responsive/timezone 风险锁成 focused baseline proof。
- **M016**：auth / API / admin security contract hardening 已完成——password reset 沿 `PasswordResetService` + `PasswordResetToken` + Alembic 026/027/028 的 durable seam 演进；audited prompt-template / presentation / auth dependency surface 已统一到稳定错误契约并由 `ApiRequestError` 单 seam 消费；第一批高风险 admin router family 已在 module 级显式 `get_current_admin_user`，`StructuredLogger` 成为 token/password/cookie/email 的共享脱敏边界。
- **M017**：realtime contract 与 concurrency proof 收口已完成——session lifecycle stale-writer race 通过 optimistic compare-and-swap 固定，practice websocket reconnect/backpressure/interrupt contract 通过 fresh transport epoch + focused web proof 固定，presentation upload/replace/delete 风险通过 code-adjacent discovery artifact 收敛成清晰下一步边界。
- **M018**：performance / dependency / recovery baselines 已完成——数据库性能疑点、依赖治理、备份恢复现状都已落到可执行且可复跑的 repo-local baseline。
- **M019**：authority seams 与 release gate 收口已完成——数据库 startup/migration/repair/bootstrap authority line 已显式化并在非开发环境 fail-fast；practice backend 与 frontend 的 mega-file orchestration 已抽成明确 service/domain/transport seam；`.github/workflows/release-truth-gate.yml` + `.github/workflows/nfr-performance-check.yml`、live `/metrics` + `/api/v1/analytics/*`、以及 router-backed `docs/api-contract/*` 共同形成可复用的 assembled release truth line。

## Current Product Truths

- 当前权威 learner surfaces 仍是现有 `/practice/{sessionId}`、`/practice/{sessionId}/report`、`/practice/{sessionId}/replay`、`/history`，不是新造第二套路由。
- 当前权威 admin surfaces 仍是现有 `/admin/*` 页面族，不应平行再造管理工作台。
- 训练事实权威线已经建立：会话生命周期、retrieval truth、audio audit、conclusion evidence、degradation taxonomy 都应复用现有 shared seam，而不是页面本地再推导。
- 前端 hygiene 边界现在已有三条明确约束：
  - raw `console.*` 只允许出现在 shared debug seam / instrumentation 例外；
  - native dialog / hard navigation 只允许出现在已文档化例外，其余业务流程必须走 shared dialog / toast / router / auth-handler seam；
  - learner shell fallback 只按 learner-core route families 闭合；`/support/runtime` 和 admin route shells 不算 learner-shell 缺口。
- auth recovery 权威线已经明确：忘记密码/重置密码只能沿 `common.services.password_reset.PasswordResetService`、`common.db.models.PasswordResetToken` 与 Alembic 026/027/028 演进；`User.hashed_password` 一旦存在就是登录权威，兼容密码环境变量只留给未托管密码的历史用户。
- audited API error-contract 权威线同样明确：
  - route-local domain/not-found 4xx 需用 `JSONResponse(error_response(...))` 暴露顶层 `error/message/trace_id`；
  - dependency/auth/RBAC 失败继续走 `_raise_auth_http_error(...)` 暴露结构化 `detail={error,message}`；
  - 前端统一从 `web/src/lib/api/client.ts` 的 `normalizeApiErrorPayload` / `ApiRequestError` 读取，不在页面里分叉解析。
- admin security baseline 权威线已补齐第一批高风险 seam：admin-only RBAC 必须直接声明在 router module 上；token/password/cookie/email 的日志保护必须落在 `StructuredLogger` 共享 sink；`backend/src/admin/api/security_inventory.py` 与 `backend/src/common/monitoring/log_safety_inventory.py` 是后续 widening 的代码级事实源。
- lifecycle concurrency 权威线已经明确：stale `pause` / `resume` writers 只能在写入时通过 status compare-and-swap 收敛；sales 终态语义仍是 `end -> scoring`、presentation 终态语义仍是 `end -> completed`；长期 focused proof 入口仍是 `backend/tests/unit/test_session_lifecycle_service.py` + `backend/tests/integration/test_session_lifecycle_api.py`。
- websocket realtime 权威线已经明确：
  - `use-practice-websocket` 继续拥有 transport lifecycle、initial pending flush、binary negotiation、local backpressure buffering 与 interrupt pre-cleanup；
  - `web/src/hooks/websocket/message-handlers.ts` 继续拥有 `status` / `reconnected` / `interrupted` / `backpressure` 的 inbound state projection；
  - reconnect 是 fresh transport epoch，不应 replay stale dead-socket interrupt/control intent；
  - learner reconnect UX 需按 `connectionState` truth 区分 `reconnecting` 与 `failed`。
- presentation mutation discovery 权威线已经明确：`backend/src/presentation_coach/api/presentations.py` 中的 discovery 常量是当前 upload/replace/delete 风险的 code-adjacent truth source；in-place replace 是当前唯一已证实的 concurrent-writer race，应先做 per-`presentation_id` serialization/CAS，再决定是否需要 distributed lock。
- M018 database performance baseline 权威线已经明确：`*_DB_PERFORMANCE_BASELINE` 常量与 `QUERY_INDEX_DISCOVERY_CONCLUSIONS` 是 follow-up 起点；没有真实 Postgres `EXPLAIN` / `pg_stat_statements` / runtime timing 前，不要把候选索引直接当成已证实优化项。
- M018 dependency-governance 权威线已经明确：`web/package-lock.json` + `backend/requirements.txt` 是事实源，`scripts/dependency-governance.sh status` 是首要入口；backend JWT seam 统一通过 `common.auth.service` 暴露 `JWTError` / `create_access_token` / `verify_token`。
- M018 backup/recovery 权威线已经明确：运维事实链采用三层——`docs/setup/backup-recovery-current-state.md` → `docs/backup-recovery-runbook.md` → `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`；恢复验证需要显式走 `/health`、`alembic upgrade head`、`repair_legacy_schema.py`、`bootstrap_auth_admin.py` 等真实 seam。
- M019/S01 database authority 现在也已明确：
  - `backend/src/common/db/session.py::STARTUP_DB_AUTHORITY` 是 startup / migration / legacy repair / auth bootstrap 的代码级 authority map；
  - `init_db()` 仍是 startup bootstrap seam，但开发/测试外不再承担 schema repair 责任；发现 `personas.persona_policy` 或 `knowledge_documents` drift 时必须显式走 Alembic 或 `python scripts/repair_legacy_schema.py`；
  - `backend/src/common/db/legacy_schema_repair.py` 是 startup compat guard、repair script、Alembic revision `20260413_1040_029_explicit_legacy_startup_repairs.py` 共享的 repair seam。
- M019/S02 practice backend authority 现在也已明确：
  - `backend/src/common/services/practice_service.py` 是 route-facing compatibility bundle，而不是新的第二套路由族；
  - `practice_session_service.py` 负责 session create、retry focus、runtime descriptor、lifecycle orchestration；
  - `practice_report_service.py` 负责 report payload、audio audit、audio-segment signing/register/failure flows；
  - completed-session truth 仍以 `SessionEvidenceService` 为准，replay/history/admin 不应回退到 `common/api/practice.py` 重新拼 projection。
- M019/S03 frontend authority 现在也已明确：
  - `web/src/lib/api/client.ts` 继续作为唯一 outward `api` façade 和 shared auth/error/trace/request seam；页面应继续从这里 import `api`；
  - `web/src/lib/api/client-domains.ts` 承接已证实的 runtime-facing domain builders；
  - `usePracticeWebSocket()` 继续作为 live practice page 的唯一 outward transport/orchestration contract；
  - `web/src/hooks/websocket/transport.ts` 负责 URL 组装、pending queue、reconnect/backoff、close-reason mapping，interrupt 的 throttled interim-transcript cleanup 必须留在 transport seam 内。
- M019/S04 release truth authority 现在也已明确：
  - `.github/workflows/release-truth-gate.yml` + `.github/workflows/nfr-performance-check.yml` 是默认 assembled release gate；新增 release surface 时必须同步更新 workflow、focused proof、architecture scan 和计划文档；
  - backend install authority 以 `backend/requirements.txt` 为准，web install authority 以 `web/package-lock.json` 为准；CI 命令漂移本身就是 release-truth drift；
  - `/metrics` 与 `/api/v1/analytics/error|performance|custom` 是当前 live observability truth line，但这只证明“可接受、可导出、可通过 focused gate 复核”，不等于已经有完整告警平台；
  - `docs/api-contract/sessions.md`、`release-verification.md`、`support-runtime.md` 是当前 contract authority，但仍靠 router-backed repo-root inventory proof，而不是 machine-generated OpenAPI；
  - `api-spec.md`、`specs/001-ai-practice-system/contracts/openapi.yaml` 与 `web/src/app/admin/page.tsx` 的 demo stats 继续是 explicit drift inventory / negative proof，不得被包装成 release authority；
  - 判断 release 是否可过线，默认先跑 M019/S04 固定下来的 repo-root verification bundle，而不是只看单个 workflow 是否绿灯。

## Current Focus

当前项目处于 **M019 已完成、进入 post-M019 稳态与 M020 准备阶段** 的状态：
- M019 已完成 milestone close-out：数据库 authority map、practice backend seam、frontend domain/transport seam、以及 assembled release truth line 都已经过 fresh milestone-level verification。
- 接下来优先级应转向 **M020**，但前提是继续复用 M019 已固定的 authority / release surfaces，而不是重开第二套入口或证明方式。

接下来的重点：
1. **保持 M019 authority truth 稳定**：
   - 不要重新把 non-development startup 当成 schema repair 常态入口；
   - practice backend 的新增 write/report 逻辑不要再默认塞回 `common/api/practice.py`；
   - replay/history/admin 的 completed-session truth 不要绕开 `SessionEvidenceService`；
   - 前端页面不要绕开 outward `api` façade 或 `usePracticeWebSocket()` 自己重建 auth/error/request transport 或 websocket lifecycle；
   - 后续 slice 的 runbook / CI / docs / tests 必须继续引用同一 authority map；
   - 不要把 legacy spec、stale comments、或 admin home demo stats 偷偷升级成 release authority。
2. **准备 M020**：在不破坏 M019 assembled release bundle 的前提下推进 auth transport hardening 与后续工作。
3. **继续沿 authority-bearing files 演进**：后续更新优先修改现有 code-adjacent seam、测试、workflow、runbook、contract docs，而不是再写一套 markdown-only inventory。

当前不应做的事：
- 不要把 `init_db()` 的 `create_all()` / compat guard 继续外推成生产迁移 authority。
- 不要因为 `scripts/dev-up.sh` 能启动，就跳过 `alembic upgrade head` 或显式 repair。
- 不要在后续切片里又各自发明一套启动/迁移/恢复说明；必须复用 S01 已写回的 authority map。
- 不要在 practice backend 后续切片里重新把 create/lifecycle/report/audio orchestration 塞回 `common/api/practice.py`。
- 不要让页面直接调用内部 domain builders 或本地拼 websocket transport；应继续沿 outward `api` façade 和 `usePracticeWebSocket()` 收口。
- 不要让后续 milestone 只凭 workflow 绿灯就宣称 release truth 完整；必须继续复用 web/backend/doc/metrics/error-reporting 的 assembled proof。

## Capability Contract

显式 requirement 状态与验证证据以 `.gsd/REQUIREMENTS.md` 为准。

## Milestone Snapshot

- [x] M001 — 首发训练闭环可用化
- [ ] M002 — historical failed-closeout foundation only（不再继续执行）
- [x] M003 — 知识与角色真实性
- [x] M004 — 复盘与学习闭环增强
- [x] M005 — 后台治理与规模化运营
- [x] M006 — 后台共享 seam 收口
- [x] M007 — 实时教练闭环正式封板
- [x] M008 — 检索事实链收口
- [x] M009 — 录音审计链收口
- [x] M010 — 报告证据链收口
- [x] M011 — 知识问答链落地
- [x] M012 — 首登可用性与体验修复
- [x] M013 — system audit 归一化与修复基线
- [x] M014 — learner 入口与体验闭环补齐
- [x] M015 — Frontend hygiene 与 learner shell 保护收口
- [x] M016 — Auth / API / admin security contract hardening
- [x] M017 — Realtime contract 与 concurrency proof 收口
- [x] M018 — Performance / dependency / recovery baselines
- [x] M019 — Authority seams 与 release gate 收口
