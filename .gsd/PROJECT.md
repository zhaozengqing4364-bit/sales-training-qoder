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
- **M015**：frontend hygiene 与 learner shell 保护收口已完成并封板。
- **M016**：auth / API / admin security contract hardening 已完成。
- **M017**：realtime contract 与 concurrency proof 收口已完成。
- **M018**：performance / dependency / recovery baselines 已完成。
- **M019**：authority seams 与 release gate 收口已完成。
- **M020 / S01**：auth transport hardening 第一片已完成：非 development session/CSRF cookie 强制 `Secure`，cookie-backed unsafe request 走双提交 CSRF 校验，websocket auth authority 收口为 `Authorization -> session cookie -> query_token compatibility`，并把 shared-password compatibility 诊断、repo-root proof、runbook/doc contract 一起写回。
- **M020 / S02**：sensitive log 与 admin observability redaction 已完成：logger、`/api/v1/admin/system-logs`、`/admin/logs` 现在共用一个 backend-owned allowlist-first diagnostics contract，admin/support 保留 `trace_id`/`error_code`/`phase`/`session_id`/`target_user_id` 等排障字段，但 raw `details`、精确 identifier/IP、provider/request/prompt/config secrets 保持 backend-only。
- **M020 / S03**：multi-instance session state 与 reconnect authority 已收口：`SessionManager` 明确成为 instance-local live connection authority，`SessionStateService` 明确成为 shared Redis reconnect snapshot authority，StepFun reconnect snapshot 保留 `current_request_id` 与 `feedback_pacing_state` 但不重放 `latest_action_card`，support/runbook/architecture scan 也已写清 restart/drain 语义与缺失的 cluster drain control。
- **M020 / S04**：M018 的手工 recovery baseline 已升级为 repo-local drill bundle：`scripts/recovery_drill_baseline.py` 固定 db/auth/redis/websocket/oss/health authority，`scripts/recovery_drill_runner.py` 直接执行同一 metadata 并把证据落到 `.dev/recovery-drills/<timestamp>/summary.json` + `*.log`，runbook / support runtime / deploy bundle / cloud redeploy plan / architecture scan 也已统一写明单机部署边界与 release-health + drill-evidence 配对留证规则。
- **M020 milestone**：Security / multi-instance runtime / recovery hardening 已完成 milestone close-out；验收按 slice overview `After this` outcome 逐条核对，确认 auth transport、admin/support diagnostics、runtime authority split、以及 executable recovery drills 均已落到真实代码、focused proof 与长期文档/运行手册。里程碑同时保留了一个明确 follow-up：`.dev/recovery-drills/20260414T010316Z/summary.json` 真实暴露 `db_migration -> KeyError: '20260412_0315_028'`，后续必须修复并重跑 drill，而不能被 `/health` 掩盖。
- **M021 / S01**：live AI authority inventory 已完成：architecture scan、API contract、focused proof 文件、以及 post-M018 next-wave plan 现在都把 StepFun realtime + compiled voice snapshot 标成 live authority，把 `common.knowledge_engine.compat` 标成 shipped knowledge rollout seam，把 `PromptTemplateService` 标成 live governance + compat helper，把 classic scoring / legacy evaluation-report stack 标成 compat/enhancement 或 retire candidate。后续 M021 切片不应再把文件名看起来“像 prompt / evaluation 主链”的模块误判成真实 live authority。

## Current Product Truths

- 当前权威 learner surfaces 仍是现有 `/practice/{sessionId}`、`/practice/{sessionId}/report`、`/practice/{sessionId}/replay`、`/history`，不是新造第二套路由。
- 当前权威 admin surfaces 仍是现有 `/admin/*` 页面族，不应平行再造管理工作台。
- 训练事实权威线已经建立：会话生命周期、retrieval truth、audio audit、conclusion evidence、degradation taxonomy 都应复用现有 shared seam，而不是页面本地再推导。
- 前端 hygiene 边界已有明确约束：raw `console.*` 只允许出现在 shared debug seam / instrumentation 例外；native dialog / hard navigation 只允许出现在已文档化例外，其余业务流程必须走 shared dialog / toast / router / auth-handler seam；learner shell fallback 只按 learner-core route families 闭合。
- auth recovery 权威线已经明确：忘记密码/重置密码沿 `PasswordResetService`、`PasswordResetToken` 与 Alembic 026/027/028 演进；`User.hashed_password` 一旦存在就是登录 authority，兼容密码环境变量只留给未托管密码的历史用户。
- audited API error-contract 权威线同样明确：route-local 4xx 用 `JSONResponse(error_response(...))` 暴露顶层 `error/message/trace_id`；dependency/auth/RBAC 失败继续走结构化 `detail={error,message}`；前端统一从 `web/src/lib/api/client.ts` 的 `normalizeApiErrorPayload` / `ApiRequestError` 读取。
- admin security baseline 权威线已补齐第一批高风险 seam：admin-only RBAC 必须直接声明在 router module 上；token/password/cookie/email 的日志保护必须落在 `StructuredLogger` 共享 sink；`backend/src/admin/api/security_inventory.py` 与 `backend/src/common/monitoring/log_safety_inventory.py` 是后续 widening 的代码级事实源。
- lifecycle concurrency 权威线已经明确：stale `pause` / `resume` writers 只能在写入时通过 status compare-and-swap 收敛；sales 终态语义仍是 `end -> scoring`、presentation 终态语义仍是 `end -> completed`。
- websocket realtime 权威线已经明确：`usePracticeWebSocket()` 继续拥有 transport lifecycle、initial pending flush、binary negotiation、local backpressure buffering 与 interrupt pre-cleanup；`web/src/hooks/websocket/message-handlers.ts` 继续拥有 inbound state projection；reconnect 是 fresh transport epoch，不应 replay stale dead-socket interrupt/control intent。
- M019 database authority 现在已明确：`backend/src/common/db/session.py::STARTUP_DB_AUTHORITY` 是 startup / migration / legacy repair / auth bootstrap 的 code-level authority map；`init_db()` 仍是 startup bootstrap seam，但非 development/test 不再承担 schema repair 责任；显式 drift 需走 Alembic 或 `python scripts/repair_legacy_schema.py`。
- M019 frontend authority 也已明确：`web/src/lib/api/client.ts` 继续作为唯一 outward `api` façade；`usePracticeWebSocket()` 继续作为 live practice page 的唯一 outward transport/orchestration contract；页面不要绕开这些 seam 自己重建 auth/error/request transport 或 websocket lifecycle。
- M019 release truth authority 同样已明确：`.github/workflows/release-truth-gate.yml` + `.github/workflows/nfr-performance-check.yml`、live `/metrics` + `/api/v1/analytics/*`、以及 router-backed `docs/api-contract/*` 共同形成当前 assembled release truth line；legacy spec 与 admin home demo stats 仍只是 drift inventory，不得包装成 release authority。
- **M020/S01 auth transport authority 已固定**：
  - `backend/src/common/auth/service.py` 是 auth transport/cookie/CSRF 的共享 authority seam；
  - 非 development 环境下 `app_session` 与 `app_csrf` cookie 会被强制标记为 `Secure`；
  - cookie-backed unsafe HTTP request 必须通过 `app_csrf` ↔ `X-CSRF-Token` 双提交校验；
  - websocket auth authority 已收口为 `Authorization -> session cookie -> query token compatibility`，并通过 `resolve_websocket_auth(...)` / `resolve_websocket_token(...)` 统一；
  - `common.auth.api.login` 会通过 `X-Auth-Authority` / `X-Auth-Compatibility-Mode` 暴露 managed password / env compatibility authority，shared password 只作为显式 compatibility 模式存在。
- **M020/S02 admin/support observability authority 已固定**：
  - `backend/src/common/monitoring/logger.py` 现在是 admin/support 日志可见性的 backend-owned authority seam；
  - `/api/v1/admin/system-logs` 通过 `policy.version`、`policy.diagnostic_fields`、masked identifiers、safe `details` summary、ordered `diagnostics[]` 暴露唯一可信的 admin/support diagnostics contract；
  - `/admin/logs` 只渲染 backend 返回的 diagnostics 列表，不再在前端本地重建 allowlist；
  - raw `details`、精确 `user_identifier` / `ip_address`、provider/request/response payload、prompt text、token/password/cookie/email、`base_url`、stack trace 与 secrets 保持 backend-only；
  - 未来 M021 quality/cost/failure events 若进入 admin/support 诊断面，必须复用这套 allowlist-first diagnostics contract，而不是发明第二套 support payload。
- **M020/S03 websocket runtime authority 已固定**：
  - `SessionManager.get_stats()` 是 **instance-local live connection** inspection surface，只能回答“当前进程持有哪些 live sockets / runtime diagnostics”；
  - `SessionStateService.get_stats()` 是 **shared Redis reconnect snapshot** inspection surface，负责 `last_saved_snapshot`、`last_loaded_snapshot`、`request_epoch`、`connection_epoch`、`last_disconnect_reason`、`last_error` 等 restart-safe reconnect authority；
  - StepFun reconnect snapshot 现在保留 `current_request_id` 与 `feedback_pacing_state`，但仍故意不持久化 `latest_action_card`，避免断线后重放陈旧教练卡片；
  - `/api/v1/support/runtime` 明确保持 release-health / fault summary contract，不承担 cluster-wide websocket state API 职责；
  - restart / drain 语义必须显式区分 instance-local live sockets 与 shared Redis snapshot，当前仓库仍**没有** repo-native cluster drain endpoint、cross-instance live connection authority 或 ingress/LB orchestration。
- **M020/S04 recovery / deploy authority 已固定**：
  - `scripts/recovery_drill_baseline.py` 是 recovery drills 的唯一 repo-local authority inventory，固定 `db_migration`、`auth_bootstrap`、`redis_session_state`、`websocket_reconnect`、`oss_signing_playback`、`health_check` 的 checked commands / preconditions / failure signals / authority paths；
  - `scripts/recovery_drill_runner.py` 不维护第二套 runbook，它只执行 baseline metadata 并把逐 drill `*.log` 与 `summary.json` 落到 `.dev/recovery-drills/<timestamp>/`；
  - `.sisyphus/deploy/*` 当前只描述 **single-node native deploy bundle**，`/health` 与 `systemctl is-active` 只能证明单节点健康，不能外推出 multi-instance drain 或 cluster-wide runtime truth；
  - release/recovery proof 现在必须同时归档 deploy `/health` capture、`/api/v1/support/runtime/*` release-health/fault summary，以及最新 repo-local recovery drill bundle；单靠其中任何一层都不足以宣称“可恢复”；
  - manual-only 边界仍然是 `redis_service_restore`、`oss_bucket_export`、`multi_instance_drain`，后续工作不能把它们包装成已自动化能力。
- **M021/S01 AI authority inventory 已固定**：
  - `backend/src/sales_bot/websocket/router.py` → `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` 是当前 learner-facing sales live AI/runtime authority；presentation StepFun realtime 仍是同一 runtime seam 的 adapter，而不是第二套 AI 栈；
  - `backend/src/sales_bot/services/voice_runtime_policy.py` + `backend/src/sales_bot/services/voice_instruction_compiler.py` 是当前 compiled prompt/runtime contract authority；live StepFun 指令来自会话创建时固化的 `voice_policy_snapshot`，不是 `PromptTemplateService`；
  - `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` + `backend/src/common/knowledge_engine/compat.py` 是当前 shipped knowledge rollout authority seam；`common.knowledge_engine.engine.py` 默认仍是 shadow-by-default / enabled-only live path；
  - `backend/src/prompt_templates/service.py` + routes 是 live governance surface，也是 runtime-adjacent compat helper，但**不是** live sales StepFun prompt authority；
  - `backend/src/evaluation/services/realtime_scoring.py`、`ai_scoring.py`、`score_processor.py` 仍是 classic `voice_mode == "legacy"` 的 compat runtime；`staged_evaluation.py`、`comprehensive_report.py`、`report_generation_trigger.py`、`evaluation/api.py`、`common/ai/llm_service.py::evaluate/generate_report` 仍有 shipped readers/consumers，所以目前只能视为 compat/enhancement 或 retire candidate，不能粗暴删除；
  - 对外 consumer-facing authority docs 现在以 `docs/api-contract/sessions.md` 与 `docs/api-contract/prompt-templates.md` 为主，`docs/api-contract/support-runtime.md` 保持 support/read-side authority explainer，不承担 live AI control-plane spec 角色。

## Current Focus

当前项目处于 **M020 已完成里程碑收口、M021/S01 已完成 AI authority inventory、M021 后续切片准备执行** 的状态：
- **M019** 已完成 milestone close-out：数据库 authority map、practice backend seam、frontend domain/transport seam、以及 assembled release truth line 都已经过 fresh milestone-level verification。
- **M020** 已完成 milestone close-out，四个切片都已被 milestone-level assembled evidence 吸收：
  1. **S01** auth transport、cookie/CSRF posture、websocket auth authority、shared-password compatibility diagnosis 已在代码、focused tests、runbook、API contract 与 architecture scan 上收口；
  2. **S02** sensitive log 与 admin observability redaction 已在 logger、system-log API、admin logs UI、focused tests、inventory 与 architecture scan 上收口；
  3. **S03** runtime connection visibility、session snapshot、reconnect epoch、restart/drain semantics 已在 runtime surfaces、focused reconnect proofs、support/runtime docs 与 recovery runbook 上收口；
  4. **S04** recovery drill automation 与部署指导已完成：repo-local drill inventory/runner、runbook/current-state/support-runtime/deploy/cloud plan/architecture scan、以及 `.dev/recovery-drills/<timestamp>/summary.json` evidence bundle 已收口到同一 authority line。
- **M021/S01** 已完成 slice close-out准备：
  1. AI/runtime/prompt/score/report 主链已被明确标成 live / compat / shadow / retire candidate；
  2. `docs/api-contract/sessions.md`、`docs/api-contract/prompt-templates.md`、`docs/api-contract/support-runtime.md` 与 focused proof 文件已写明 authority boundary；
  3. `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` 与 `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` 已包含 S02-S04 直接可用的 must-keep / compat / retire-candidate matrix；
  4. 最终 `M021-CONTEXT.md` 仍受 depth verification gate 限制，当前应以 `M021-CONTEXT-DRAFT.md` + architecture scan §7.3.1 作为 downstream 研究输入。
- 当前最新 close-out evidence 确认：
  - M020 的 roadmap `After this` outcomes 已全部逐条满足；
  - `.dev/recovery-drills/20260414T010316Z/summary.json` 中 `auth_bootstrap`、`redis_session_state`、`oss_signing_playback`、`health_check` 通过；
  - `db_migration` 仍真实暴露 `KeyError: '20260412_0315_028'`，这已经被收口为 recovery evidence 的一部分，而不是被节点健康状态掩盖；
  - M021/S01 的 fresh slice verification 已重新确认 AI inventory grep gate、focused backend proof bundle、authority wording grep gate、以及 keep/compat/retire matrix grep gate全部通过。

接下来的重点：
1. 修复 `20260412_0315_028` 对应的 Alembic revision / migration-graph drift，然后重跑同一套 recovery drills，直到 `db_migration` 也转绿。
2. 按 M021/S01 的 must-keep / compat / retire-candidate matrix 执行 M021/S02-S04，不要再把 `PromptTemplateService`、classic scoring、legacy evaluation/report 文件名误判成 live AI authority。
3. 保持 M019 assembled release truth 与 M020 的四条 authority seam 稳定，不要重开第二套 startup/migration/practice/frontend/release/auth/observability/runtime/recovery 入口。
4. 继续把 AI control-plane / evaluation / quality-event work 落在 authority-bearing code、focused tests、workflow、runbook 与 contract docs 上，而不是退回 markdown-only inventory。

当前不应做的事：
- 不要把 `init_db()` 的 `create_all()` / compat guard 外推成生产迁移 authority。
- 不要因为 `scripts/dev-up.sh` 能启动，就跳过 `alembic upgrade head` 或显式 repair。
- 不要在 practice backend 后续切片里重新把 create/lifecycle/report/audio orchestration 塞回 `common/api/practice.py`。
- 不要让页面直接调用内部 domain builders 或本地拼 websocket transport；应继续沿 outward `api` façade 和 `usePracticeWebSocket()` 收口。
- 不要让后续 milestone 只凭 workflow 绿灯就宣称 release truth 完整；必须继续复用 web/backend/doc/metrics/error-reporting 的 assembled proof。
- 不要让后续 auth slices 回退到隐含默认值：cookie secure、CSRF、websocket query token、shared password 都已经在 M020/S01 被写成显式 authority / compatibility / off-ramp 规则。
- 不要让未来 admin/support observability slices 在 route 或 UI 层重新暴露 raw `details`、精确 identity/IP、provider/request payload 或 secret-adjacent config；这些已经在 M020/S02 被明确划回 backend-only。
- 不要把单实例 `SessionManager.total_sessions=0` 误写成“集群已 drain 完毕”；S03 已明确这只是 instance-local 视角，真正 restart-safe 的 shared authority 只有 Redis reconnect snapshot。
- 不要把 `/health`、systemd active、或一份 runbook 文档单独当成“recovery 已验证”；S04 已明确必须配对最新 `.dev/recovery-drills/<timestamp>/summary.json` + 逐 drill log，并把失败 drill 如实写进 release/recovery 记录。
- 不要发明第二套 recovery command list；后续 drill / deploy / support guidance 必须直接复用 `scripts/recovery_drill_baseline.py` 的 metadata，而不是在 plan/doc/script 里各自维护一套。
- 不要在 M021 后续切片里把 `PromptTemplateService` 倒推成 live StepFun prompt authority，也不要在 classic `voice_mode == "legacy"`、`report_status` / comprehensive-report readers、manual `/evaluation/*` operator flow、PromptTemplateService admin/runtime helper、或 knowledge compat debug/audit consumer 仍存在时粗暴删除 legacy AI surfaces。

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
- [x] M020 — Security / multi-instance runtime / recovery hardening
- [ ] M021 — AI control plane / prompt / evaluation kernel 统一
