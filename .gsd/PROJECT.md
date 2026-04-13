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
- **M016**：auth / API / admin security contract hardening 已完成——password reset 现在沿 `PasswordResetService` + `PasswordResetToken` + Alembic 026/027/028 的 durable seam 演进并由 DB enforce 单 active token；audited prompt-template / presentation / auth dependency surface 已统一到稳定错误契约并由 `ApiRequestError` 单 seam 消费；第一批高风险 admin router family 已在 module 级显式 `get_current_admin_user`，`StructuredLogger` 成为 token/password/cookie/email 的共享脱敏边界，security inventory / log-safety inventory 已把 fix-first 列表收敛到 0。
- **M017**：realtime contract 与 concurrency proof 收口已完成——session lifecycle stale-writer race 通过 `PracticeSession.status` optimistic compare-and-swap 固定，practice websocket reconnect/backpressure/interrupt contract 通过 fresh transport epoch + focused web proof 固定，presentation upload/replace/delete 风险通过 code-adjacent discovery artifact 收敛成清晰下一步边界（先处理 replace，再决定 delete policy，不抢跑 upload-wide lock）。
- **M018**：performance / dependency / recovery baselines 已完成——数据库性能疑点被收口为代码邻近、可执行的 discovery backlog；依赖安全/许可证/升级策略现在有 repo-local 可复跑的文档与脚本入口，并通过 web/backend audit + license inventory + shared `PyJWT` seam 回绿；备份 / 故障恢复 / 容灾现状被整理成 current-state inventory → manual runbook → analysis pointer 三层事实链，明确当前可执行恢复路径与仍未落地的运维缺口。
- **M019 / S01**：数据库 startup / migration / legacy repair / auth bootstrap 的 authority line 已从隐式 startup 修补收口到可验证入口：Alembic 是 forward migration authority，legacy schema drift 由显式 repair seam 与 Alembic revision `20260413_1040_029` 承担，非开发环境 startup 对 legacy personas/knowledge drift 改为 fail-fast，runbook / architecture scan / CI migration wording 已对齐这一事实线。
- **M019 / S02**：practice backend 已从 `common/api/practice.py` 的 mega-route 形态抽出明确应用层 seam：`practice_session_service` 负责 create/lifecycle/runtime-descriptor/retry-focus，`practice_report_service` 负责 report/audio-audit/audio-segment，`practice_service` 保留 route-facing compatibility bundle，而 replay/history/admin 的 completed-session truth 继续以 `SessionEvidenceService` 为 canonical read model。
- **M019 / S03**：frontend API client 与 practice websocket transport 现在也有明确 seam：`web/src/lib/api/client.ts` 保留 outward `api` façade 和 shared auth/error/trace/request authority，page-proved runtime domains 抽到 `web/src/lib/api/client-domains.ts`；`usePracticeWebSocket()` 保留 outward transport/orchestration contract，`web/src/hooks/websocket/transport.ts` 承接 URL/queue/backoff/close-reason helpers，并把 interrupt 的 throttled interim-transcript cleanup 固定在 transport seam 内。

## Current Product Truths

- 当前权威 learner surfaces 仍是现有 `/practice/{sessionId}`、`/practice/{sessionId}/report`、`/practice/{sessionId}/replay`、`/history`，不是新造第二套路由。
- 当前权威 admin surfaces 仍是现有 `/admin/*` 页面族，不应平行再造管理工作台。
- 训练事实权威线已经建立：会话生命周期、retrieval truth、audio audit、conclusion evidence、degradation taxonomy 都应复用现有 shared seam，而不是页面本地再推导。
- 前端 hygiene 边界现在已有三条明确约束：
  - raw `console.*` 只允许出现在 shared debug seam / instrumentation 例外。
  - native dialog / hard navigation 只允许出现在已文档化例外，其余业务流程必须走 shared dialog / toast / router / auth-handler seam。
  - learner shell fallback 只按 learner-core route families 闭合：sidebar learner routes + auth/practice flows；`/support/runtime` 和 admin route shells 不算 learner-shell 缺口。
- auth recovery 权威线现在也已明确：忘记密码/重置密码只能沿 `common.services.password_reset.PasswordResetService`、`common.db.models.PasswordResetToken` 与 Alembic 026/027/028 演进；`User.hashed_password` 一旦存在就是登录权威，`AUTH_USER_PASSWORDS_JSON` / `AUTH_SHARED_PASSWORD` 只保留给尚未托管密码的兼容用户。
- audited API error-contract 权威线现在同样明确：
  - route-local domain/not-found 4xx 需用 `JSONResponse(error_response(...))` 暴露顶层 `error/message/trace_id`；
  - dependency/auth/RBAC 失败需继续走 `_raise_auth_http_error(...)` 暴露结构化 `detail={error,message}`；
  - 前端统一从 `web/src/lib/api/client.ts` 的 `normalizeApiErrorPayload` / `ApiRequestError` 读取，不在页面里分叉解析。
- admin security baseline 权威线现已补齐第一批高风险 seam：
  - admin-only RBAC 必须直接声明在 router module 上，不能只依赖 `main.py` 的外层依赖包装；
  - token/password/cookie/email 的日志保护必须落在 `common.monitoring.logger.StructuredLogger` 共享 sink，而不是零散 call-site masking；
  - `backend/src/admin/api/security_inventory.py` 与 `backend/src/common/monitoring/log_safety_inventory.py` 是后续 admin security widening 的代码级事实源。
- lifecycle concurrency 权威线现在也已明确：
  - stale `pause` / `resume` writers 只能在写入时通过 status compare-and-swap 收敛，不能靠同一 `AsyncSession` 的“再读一次”假装并发安全；
  - sales 终态语义仍是 `end -> scoring`（后续 background finalization 才可能到 `completed`），presentation 终态语义仍是 `end -> completed`；
  - focused lifecycle proof 的长期入口仍是 `backend/tests/unit/test_session_lifecycle_service.py` + `backend/tests/integration/test_session_lifecycle_api.py`，不是额外的新并发 harness。
- websocket realtime 权威线现在也已明确：
  - `use-practice-websocket` 继续拥有 transport lifecycle、initial pending flush、binary negotiation、local backpressure buffering 与 interrupt pre-cleanup；
  - `web/src/hooks/websocket/message-handlers.ts` 继续拥有 `status` / `reconnected` / `interrupted` / `backpressure` 的 inbound state projection；
  - reconnect 是 fresh transport epoch，不应 replay stale dead-socket interrupt/control intent；
  - learner reconnect UX 需按 `connectionState` truth 区分 `reconnecting`（自动恢复中）与 `failed`（允许手动 `重新连接`）。
- presentation mutation discovery 权威线现在也已明确：
  - `backend/src/presentation_coach/api/presentations.py` 中的 `PRESENTATION_RESOURCE_RACE_INVENTORY`、`PRESENTATION_RESOURCE_RACE_FOCUS`、`PRESENTATION_RESOURCE_RACE_DISCOVERY_CONCLUSIONS` 是当前 upload/replace/delete 风险的 code-adjacent truth source；
  - in-place replace 是当前唯一已证实的 concurrent-writer race，应先做 per-`presentation_id` serialization/CAS，再决定是否需要 distributed lock；
  - delete 当前首先是 live-session policy/guard gap，而不是已经证明需要锁的路径；
  - upload-new 目前仍无 focused proof 证明存在有害并发冲突，不应抢跑到 idempotency-key 或 system-wide lock 方案。
- M018 database performance baseline 权威线现在也已明确：
  - 代码级 baseline 以 `ADMIN_ANALYTICS_DB_PERFORMANCE_BASELINE`、`HISTORY_QUERY_DB_PERFORMANCE_BASELINE`、`SESSION_EVIDENCE_DB_PERFORMANCE_BASELINE`、`TRAINING_RECORDS_DB_PERFORMANCE_BASELINE` 为准；
  - 可执行 follow-up backlog 以 `backend/tests/contract/test_analytics.py::QUERY_INDEX_DISCOVERY_CONCLUSIONS` 为准；
  - `focused_proof`、`code_path_confirmed`、`needs_real_postgres_evidence` 三层必须一起维护，不能把代码结构猜测直接当成索引 implementation mandate；
  - 没有真实 Postgres `EXPLAIN` / `pg_stat_statements` / runtime timing 前，不要把 scenario filter、message timestamp 扩展、search text index 这类候选直接当成已证实优化项。
- M018 dependency-governance 权威线现在也已明确：
  - 依赖治理事实源仍是 `web/package-lock.json` + `backend/requirements.txt`；
  - `scripts/dependency-governance.sh status` 是查看当前 prerequisites / authority files / CI drift 的首要入口；
  - repo-level backend proof 建议保留 requirements-scoped `pip_audit -r backend/requirements.txt`，但 exact gate `backend/venv/bin/python -m pip_audit` 也必须保持绿色；
  - 当本地 venv 出现重复 dist-info / metadata 污染时，truthful fix 不是“改文档解释过去”，而是 clean rebuild `backend/venv`；
  - backend JWT token handling 现在统一通过 `common.auth.service` 暴露 `JWTError` / `create_access_token` / `verify_token`，底层库改为 `PyJWT[crypto]`。
- M018 backup/recovery 权威线现在也已明确：
  - 运维事实链采用三层：`docs/setup/backup-recovery-current-state.md`（详细现状盘点）→ `docs/backup-recovery-runbook.md`（人类可执行 runbook）→ `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`（面向后续 agent 的短指针）；
  - runbook 只应引用已复核的 repo-local 路径与当前确实存在的标准工具/脚本，不应把理想化运维平台、值班人名册或自动化能力写成现实；
  - 恢复前必须先记录 live `DATABASE_URL` / Redis / 文件目录 / OSS 环境值，因为 `session.py`、`config.py`、`scripts/dev-up.sh`、Chroma 配置之间存在默认值漂移；
  - `pg_dump` / `pg_restore` 必须把应用的 `postgresql+asyncpg://...` URL 转成 libpq `postgresql://...` 才能直接使用；
  - `/health`、`alembic upgrade head`、`repair_legacy_schema.py` 与 `bootstrap_auth_admin.py` 是当前恢复后验证/补齐的真实 seam；
  - 灾备演练建议、owner gap、RTO/RPO、OSS bulk export 等未来工作必须留在 `Follow-up（非当前可执行基线）`，只有真正落地后才能提升进可执行基线。
- M019/S01 database authority 权威线现在也已明确：
  - `backend/src/common/db/session.py::STARTUP_DB_AUTHORITY` 是 startup / migration / legacy repair / auth bootstrap 的代码级 authority map；
  - `init_db()` 仍是 startup bootstrap seam，但开发/测试外不再承担 schema repair 责任；发现 `personas.persona_policy` 或 `knowledge_documents` drift 时必须显式走 Alembic 或 `python scripts/repair_legacy_schema.py`；
  - `backend/src/common/db/legacy_schema_repair.py` 是 startup compat guard、repair script、Alembic revision `20260413_1040_029_explicit_legacy_startup_repairs.py` 共享的 repair seam；
  - `scripts/dev-up.sh` 依旧不会先跑 `alembic upgrade head`，因此本地“能启动”不能再被误读为 schema 已完成迁移；
  - `docs/backup-recovery-runbook.md`、`docs/setup/backup-recovery-current-state.md`、`.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`、`.github/workflows/nfr-performance-check.yml` 已对齐为同一 authority line。
- M019/S02 practice backend authority 现在也已明确：
  - `backend/src/common/services/practice_service.py` 是 route-facing compatibility bundle，而不是新的第二套路由族；
  - `backend/src/common/services/practice_session_service.py` 负责 session create、retry focus、runtime descriptor、lifecycle orchestration；
  - `backend/src/common/services/practice_report_service.py` 负责 report payload、audio audit、audio-segment signing/register/failure flows；
  - completed-session truth 仍以 `common.conversation.session_evidence.SessionEvidenceService` 为准，replay/history/admin 不应回退到 `common/api/practice.py` 重新拼 projection；
  - lifecycle extraction 仍需保留 route-owned logger injection，否则既有 lifecycle observability proof 会失真。
- M019/S03 frontend authority 现在也已明确：
  - `web/src/lib/api/client.ts` 继续作为唯一 outward `api` façade 和 shared auth/error/trace/request seam；页面应继续从这里 import `api`，不要跨域直接拿内部 builder 或本地 `fetch(...)` 拼 transport；
  - `web/src/lib/api/client-domains.ts` 目前承接已证实的 runtime-facing domain builders（`auth`、`practice`、`sessions`、`agents`、`presentations`、admin report actions）；其余 façade domains 仍可继续留在 `client.ts`，但后续拆分应沿 domain module 扩展；
  - `usePracticeWebSocket()` 继续作为 live practice page 的唯一 outward transport/orchestration contract；
  - `web/src/hooks/websocket/transport.ts` 负责 URL 组装、pending queue 规则、reconnect/backoff、close-reason mapping，`websocket/message-handlers.ts` 负责 inbound state projection；
  - interrupt 的 throttled interim-transcript cleanup 必须留在 `usePracticeWebSocket()` transport seam 内，而不是回退到 page-level cleanup。

## Current Focus

当前项目处于 **M019 进行中，S01-S03 已完成，进入 S04 release gate / metrics / doc-contract truth line 收口** 的状态：
- S01 已把数据库 startup / migration / bootstrap authority 从“startup 隐式补洞”收口到显式、可验证的 entrypoint 和 fail-fast 信号。
- S02 已把 practice backend 从 mega-route 向明确 application seam 收口：后续 backend 改动应优先落在 `practice_session_service` / `practice_report_service` / `SessionEvidenceService` 的正确 authority 上，而不是继续堆回 `common/api/practice.py`。
- S03 已把前端 mega client 与 mega websocket hook 收口成清晰的 domain/transport seam：后续 frontend 改动应优先落在 `client-domains.ts`、`websocket/transport.ts`、`message-handlers.ts` 或 outward seam 头文件标明的 owning layer，而不是把 auth/request/reconnect/backpressure/interrupt 逻辑重新散回页面。
- 接下来的重点是完成：
  1. **S04**：release gate / metrics / doc-contract truth line，把 GitHub Actions、metrics、错误上报与 docs/spec 合到至少一条真实 release truth line。
- 当前更重要的是维持 M019 已建立的 authority truth：
  1. 不要重新把 non-development startup 当成 schema repair 常态入口；
  2. practice backend 的新增 write/report 逻辑不要再默认塞回 `practice.py`；
  3. replay/history/admin 的 completed-session truth 不要绕开 `SessionEvidenceService`；
  4. 前端页面不要绕开 outward `api` façade 或 `usePracticeWebSocket()` 自己重建 auth/error/trace/request transport 或 websocket lifecycle；
  5. 后续 slice 的 runbook / CI / docs / tests 必须继续引用同一 authority map，而不是各自发明新入口。

当前不应做的事：
- 不要把 `init_db()` 的 `create_all()` / compat guard 继续外推成生产迁移 authority。
- 不要因为 `scripts/dev-up.sh` 能启动，就跳过 `alembic upgrade head` 或显式 repair。
- 不要在 S03-S04 又各自发明一套启动/迁移/恢复说明；必须复用 S01 已写回的 authority map。
- 不要在 practice backend 后续切片里重新把 create/lifecycle/report/audio orchestration 塞回 `common/api/practice.py`。
- 不要绕开现有 code-adjacent seam 再写并行 markdown-only inventory；后续更新应直接修改现有 authority-bearing files/tests/docs。
- 不要让页面直接调用内部 domain builders 或本地拼 websocket transport；应继续沿 outward `api` façade 和 `usePracticeWebSocket()` 收口。

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
- [ ] M019 — Authority seams 与 release gate 收口（S01-S03 complete, S04 pending）
