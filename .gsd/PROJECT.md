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
- **M020 / S02**：sensitive log 与 admin observability redaction 已完成：logger、`/api/v1/admin/system-logs`、`/admin/logs` 现在共用一个 backend-owned allowlist-first diagnostics contract，admin/support 保留 `trace_id`/`error_code`/`phase`/`session_id`/`target_user_id` 等排障字段，但 raw `details`、精确 identifier/IP、provider/request/prompt/secret-adjacent payload 保持 backend-only。

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
- **M020/S02 admin/support observability authority 也已固定**：
  - `backend/src/common/monitoring/logger.py` 现在是 admin/support 日志可见性的 backend-owned authority seam；
  - `/api/v1/admin/system-logs` 通过 `policy.version`、`policy.diagnostic_fields`、masked identifiers、safe `details` summary、ordered `diagnostics[]` 暴露唯一可信的 admin/support diagnostics contract；
  - `/admin/logs` 只渲染 backend 返回的 diagnostics 列表，不再在前端本地重建 allowlist；
  - raw `details`、精确 `user_identifier` / `ip_address`、provider/request/response payload、prompt text、token/password/cookie/email、`base_url`、stack trace 与 secrets 保持 backend-only；
  - 未来 M021 quality/cost/failure events 若进入 admin/support 诊断面，必须复用这套 allowlist-first diagnostics contract，而不是发明第二套 support payload。

## Current Focus

当前项目处于 **M019 已完成、M020 进行中** 的状态：
- M019 已完成 milestone close-out：数据库 authority map、practice backend seam、frontend domain/transport seam、以及 assembled release truth line 都已经过 fresh milestone-level verification。
- M020 已完成前两片：
  1. **S01** auth transport、cookie/CSRF posture、websocket auth authority、shared-password compatibility diagnosis 已在代码、focused tests、runbook、API contract 与 architecture scan 上收口；
  2. **S02** sensitive log 与 admin observability redaction 已在 logger、system-log API、admin logs UI、focused tests、inventory 与 architecture scan 上收口。
- M020 后续切片仍待执行：
  1. **S03** multi-instance session state 与 reconnect authority 收口；
  2. **S04** recovery drill automation 与部署指导收口。

接下来的重点：
1. 保持 M019 authority truth 稳定，不要重开第二套 startup/migration/practice/frontend/release 入口。
2. 把 M020/S01 的 auth boundary 与 M020/S02 的 diagnostics redaction boundary 当成固定前提，再推进 S03-S04；不要让 session-state、reconnect、recovery drill 再次绕开这些 seam 发明隐式规则。
3. 后续安全/运行时工作优先落在现有 authority-bearing files、focused tests、workflow、runbook 与 contract docs 上，而不是写一套 markdown-only inventory。
4. M021 及以后的 quality/cost/failure/admin-support observability work 必须复用 S02 的 backend-owned diagnostics contract，而不是让 route/UI 各自决定哪些错误细节可以展示。

当前不应做的事：
- 不要把 `init_db()` 的 `create_all()` / compat guard 外推成生产迁移 authority。
- 不要因为 `scripts/dev-up.sh` 能启动，就跳过 `alembic upgrade head` 或显式 repair。
- 不要在 practice backend 后续切片里重新把 create/lifecycle/report/audio orchestration 塞回 `common/api/practice.py`。
- 不要让页面直接调用内部 domain builders 或本地拼 websocket transport；应继续沿 outward `api` façade 和 `usePracticeWebSocket()` 收口。
- 不要让后续 milestone 只凭 workflow 绿灯就宣称 release truth 完整；必须继续复用 web/backend/doc/metrics/error-reporting 的 assembled proof。
- 不要让后续 auth slices 回退到隐含默认值：cookie secure、CSRF、websocket query token、shared password 都已经在 M020/S01 被写成显式 authority / compatibility / off-ramp 规则。
- 不要让未来 admin/support observability slices 在 route 或 UI 层重新暴露 raw `details`、精确 identity/IP、provider/request payload 或 secret-adjacent config；这些已经在 M020/S02 被明确划回 backend-only。

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
- [ ] M020 — Security / multi-instance runtime / recovery hardening（S01-S02 complete; S03-S04 pending）
