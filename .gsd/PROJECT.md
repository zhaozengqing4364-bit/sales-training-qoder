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
- **M017/S01**：session lifecycle 并发 proof 已收口——`pause`/`resume` 对抗 `end` 的 stale-writer race 现在通过 `PracticeSession.status` 的 optimistic compare-and-swap 收敛为 terminal no-op，不再把 sales `scoring` 或 presentation `completed` 重新打开；并发 contract 与 terminal split 已固定在 focused lifecycle tests 与 `practice_session_lifecycle_concurrency_conflict` 日志 seam 上。
- **M017/S02**：practice websocket reconnect/backpressure/interrupt contract 已收口——`use-practice-websocket` 明确保持 transport/outbound orchestrator 角色，`websocket/message-handlers` 保持 inbound authority seam；reconnect 现在被视为 fresh transport epoch，只允许初次 `connecting` 握手 replay queued outbound，interrupt 会清空 pending outbound + local backpressure/slow state，presentation stale interrupt 与 learner reconnect guidance 也都被 focused proof 锁定。

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

## Current Focus

M017 仍处于并发与 realtime contract 收口阶段，当前状态如下：
- **S01 已完成**：SessionLifecycleService 的 stale-writer race 已被证明并收敛，pause/resume/end 的 terminal 语义边界已固定。
- **S02 已完成**：practice websocket 的 reconnect / backpressure / interrupt seam 已收口，transport epoch contract 与 learner reconnect guidance 已通过 focused proof 固定。
- **接下来优先 S03**：围绕 presentation upload / replace 等资源竞争点做 discovery，但必须沿 M017 已锁定的“先做可证伪 proof，再决定是否加锁/重试/幂等”路径推进。

当前不应做的事：
- 不要把 lifecycle 并发问题重新包装成前端防抖或 route guard 修补。
- 不要引入新的 report/replay 终态分支去绕过 backend lifecycle contract。
- 不要在 upload / websocket slice 里重复发明第二套 terminal-state 或 transport-epoch 语义。

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
- [ ] M017 — Realtime contract 与 concurrency proof 收口（S01-S02 complete; S03 pending）
