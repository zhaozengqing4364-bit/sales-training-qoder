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

## Current Focus

当前项目处于 **M018 已完成、等待下一轮 focused delivery 选择** 的状态：
- M018 已把性能 / 依赖 / 恢复三类“像问题但未证实”的审计项，分别收口成可复跑、可引用、可继续演进的 baseline。
- 后续任何 performance/dependency/recovery 工作，都应直接从这些 baseline authority seam 起步，而不是重新做一轮 markdown-only audit。
- 当前更重要的是维护这些 baseline 的真实性：
  1. 性能项先拿真实 Postgres/runtime 证据，再决定是否进入实现；
  2. 依赖项继续保持 `npm audit` / `pip_audit` / license inventory / shared JWT seam 绿色；
  3. 恢复项只有在仓库真正补齐脚本、自动化、owner、演练记录后，才能把 Follow-up 内容提升进 executable baseline。

当前不应做的事：
- 不要在没有真实 Postgres/runtime 证据前，把 M018 的索引候选伪装成已确认优化。
- 不要把依赖治理退回成“文档承认 blocker 就算完成”；repo-local 命令现在已经可执行，后续要维护绿灯。
- 不要把 backup/recovery runbook 里的演练建议、RTO/RPO、owner gap 写成“当前已具备能力”；那仍然只是明确记录的后续工作。
- 不要绕开 code-adjacent / repo-local authority seam 另造并行 audit 文档；后续更新必须直接改动现有 baseline 文件与 proof。

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