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
- **M001-M010**：首发训练闭环、知识与角色真实性、report/replay/history learner loop、主管趋势、retrieval truth、audio audit、conclusion evidence / degradation taxonomy 已全部验证。
- **M011-M018**：KnowledgeAnswerEngine control plane、首登可用性与 learner 入口修复、frontend hygiene、auth/API/admin security contract、realtime/concurrency proof、performance / dependency / recovery baselines 已完成并封板。
- **M019**：database / frontend / practice / release truth authority seams 已完成 assembled close-out。
- **M020**：security / multi-instance runtime / recovery hardening 已完成 milestone close-out；auth transport、admin/support allowlist diagnostics、instance-local vs Redis reconnect authority、repo-local recovery drill bundle 已统一到真实代码、focused proof、长期文档与运行手册。
- **M021 / S01**：AI/runtime/prompt/score/report 主链已盘点为 live / compat / shadow / retire candidate，后续切片不应再基于“文件名像主链”做误判。
- **M021 / S02**：PromptTemplateService 已真正驱动 legacy evaluation/report compiled prompt contract；missing vars / empty render / base_url / generation failure 已进入 explicit diagnostics / fail-closed contract。
- **M021 / S03**：canonical evaluation kernel 已完成 shared-kernel 收口：realtime、report、replay、history、admin 现在共享同一套 scenario-aware `canonical_evaluation_kernel` 与 `compatibility_readers`；legacy top-level rollups 只作为过渡镜像保留，web report/replay/history 已明确按 canonical -> compatibility -> legacy 的同一读侧顺序消费分数事实。

## Current Product Truths

- 当前权威 learner surfaces 仍是现有 `/practice/{sessionId}`、`/practice/{sessionId}/report`、`/practice/{sessionId}/replay`、`/history`，不是新造第二套路由。
- 当前权威 admin surfaces 仍是现有 `/admin/*` 页面族，不应平行再造管理工作台。
- 训练事实权威线已经建立：会话生命周期、retrieval truth、audio audit、conclusion evidence、degradation taxonomy 都应复用现有 shared seam，而不是页面本地再推导。
- 前端 hygiene 边界已有明确约束：raw `console.*` 只允许出现在 shared debug seam / instrumentation 例外；native dialog / hard navigation 只允许出现在已文档化例外，其余业务流程必须走 shared dialog / toast / router / auth-handler seam；learner shell fallback 只按 learner-core route families 闭合。
- auth recovery 权威线已经明确：忘记密码/重置密码沿 `PasswordResetService`、`PasswordResetToken` 与 Alembic 026/027/028 演进；`User.hashed_password` 一旦存在就是登录 authority，兼容密码环境变量只留给未托管密码的历史用户。
- audited API error-contract 权威线同样明确：route-local 4xx 用 `JSONResponse(error_response(...))` 暴露顶层 `error/message/trace_id`；dependency/auth/RBAC 失败继续走结构化 `detail={error,message}`；前端统一从 `web/src/lib/api/client.ts` 的 `normalizeApiErrorPayload` / `ApiRequestError` 读取。
- admin security baseline 权威线已补齐第一批高风险 seam：admin-only RBAC 必须直接声明在 router module 上；token/password/cookie/email 的日志保护必须落在 `StructuredLogger` 共享 sink；`backend/src/admin/api/security_inventory.py` 与 `backend/src/common/monitoring/log_safety_inventory.py` 是后续 widening 的代码级事实源。
- lifecycle concurrency 权威线已经明确：stale `pause` / `resume` writers 只能在写入时通过 status compare-and-swap 收敛；sales 终态语义仍是 `end -> scoring`、presentation 终态语义仍是 `end -> completed`。
- websocket realtime 权威线已经明确：`usePracticeWebSocket()` 继续拥有 transport lifecycle、initial pending flush、binary negotiation、local backpressure buffering 与 interrupt pre-cleanup；`web/src/hooks/websocket/message-handlers.ts` 继续拥有 inbound state projection；reconnect 是 fresh transport epoch，不应 replay stale dead-socket intent。
- **M020/S01 auth transport authority 已固定**：`backend/src/common/auth/service.py` 是 cookie/CSRF/websocket auth 的共享 authority seam；非 development 下 session/CSRF cookie 强制 `Secure`；cookie-backed unsafe request 走双提交 CSRF 校验；websocket auth authority 为 `Authorization -> session cookie -> query token compatibility`。
- **M020/S02 admin/support observability authority 已固定**：`backend/src/common/monitoring/logger.py` 是 allowlist-first diagnostics authority seam；`/api/v1/admin/system-logs` 与 `/admin/logs` 只暴露 masked identifiers、safe diagnostics、policy metadata；raw details / precise IP / provider payload / secrets 保持 backend-only。
- **M020/S03 runtime authority 已固定**：`SessionManager.get_stats()` 只回答 instance-local live connection，`SessionStateService.get_stats()` 才是 shared Redis reconnect snapshot authority；support/runtime 仍是 release-health summary，不是 cluster-wide websocket state API。
- **M020/S04 recovery / deploy authority 已固定**：`scripts/recovery_drill_baseline.py` 是 repo-local recovery drill inventory authority，`scripts/recovery_drill_runner.py` 只执行同一 metadata 并把证据落到 `.dev/recovery-drills/<timestamp>/`；release/recovery proof 必须配对 deploy health、support runtime、以及最新 drill bundle。
- **M021/S01 AI authority inventory 已固定**：live sales/presentation realtime authority 仍在 `sales_bot/websocket/stepfun_realtime_handler.py` 与 voice runtime policy/compiler；`PromptTemplateService` 是 governance + legacy compiled-contract seam，不是 live StepFun prompt authority；classic scoring、legacy evaluation/report、manual `/evaluation/*` 仍是 compat/enhancement surfaces。
- **M021/S02 compiled prompt authority 已固定**：`PromptTemplateService.compile_runtime_prompt_contract(...)` 是 legacy evaluation/report compiled prompt handoff seam；compiled path 会显式记录并 fail-close 到 `[PROMPT_CONTRACT_MISSING_VARIABLES:*]`、`[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]`、`[PROMPT_CONTRACT_BASE_URL_REQUIRED]`、`[LLM_GENERATION_ERROR:*]`。
- **M021/S03 canonical evaluation authority 已固定**：
  - `backend/src/common/effectiveness/canonical.py` 是 scenario-aware canonical dimension catalog、shared rollup contract、surface reader plan 的 code-owned authority；
  - `SessionEvidenceService` 是 report/replay/history/admin 的 canonical projection authority，并把 canonical kernel 与 compatibility readers 一起暴露给下游；
  - realtime score snapshot persistence 必须同步扩展 `sales_bot/websocket/components/stepfun_message_helpers.normalize_score_snapshot()`，否则新 kernel 字段会只在内存存在、落库时丢失；
  - web read-side 必须复用 `web/src/lib/session-evidence.ts::readSessionEvaluationRollups(...)`，统一执行 `canonical_evaluation_kernel -> compatibility_readers -> legacy rollups`，不得再让页面各自重算或偷读旧字段。

## Current Focus

当前项目处于 **M020 已完成里程碑收口、M021/S01-S03 已完成 AI authority inventory + prompt control plane + canonical evaluation kernel unified seam、M021/S04 待执行** 的状态：
- **M019** 已完成 milestone close-out：数据库 authority map、practice backend seam、frontend domain/transport seam、assembled release truth line 已经过 fresh milestone-level verification。
- **M020** 已完成 milestone close-out，auth transport、sensitive log/admin observability redaction、instance-local vs shared reconnect authority、以及 executable recovery drills 均已落到真实代码、focused proof 与长期文档/手册。
- **M021/S01** 已完成 AI authority inventory：live / compat / shadow / retire-candidate matrix 已写回 architecture scan、API contract 与 downstream plan。
- **M021/S02** 已完成 prompt control plane 收口：PromptTemplateService 现在真正驱动 legacy evaluation/report compiled prompt runtime，并显式暴露 fail-closed diagnostics。
- **M021/S03** 已完成 canonical evaluation kernel 收口：
  1. `common.effectiveness.canonical` 已定义并构建 one shared scenario-aware kernel；
  2. realtime scoring / StepFun snapshot normalization / session evidence projection / report / replay / history / admin 现在共享同一 canonical kernel 与 compatibility readers；
  3. report / replay / history 前端已经显式改成 shared resolver 读取 canonical -> compat -> legacy，而不是页面各自猜测分数来源；
  4. 旧 top-level rollup 字段仍保留为 compatibility mirrors，方便后续 S04 与后续 retire work 在现有 surfaces 上平滑过渡。
- 当前最新 close-out evidence 还确认：
  - M020 的 roadmap `After this` outcomes 已全部逐条满足；
  - `.dev/recovery-drills/20260414T010316Z/summary.json` 中 `auth_bootstrap`、`redis_session_state`、`oss_signing_playback`、`health_check` 通过；
  - `db_migration` 仍真实暴露 `KeyError: '20260412_0315_028'`，这已被纳入 recovery evidence，而不是被 `/health` 掩盖；
  - M021/S03 fresh verification 已重新确认：backend canonical-evidence/admin/history bundle 49/49 通过，web report/replay/history bundle 44/44 通过，canonical -> compat -> legacy retirement-order 文档 grep gate 通过。

接下来的重点：
1. 修复 `20260412_0315_028` 对应的 Alembic revision / migration-graph drift，然后重跑同一套 recovery drills，直到 `db_migration` 也转绿。
2. 在 **M021/S04** 把 compiled prompt diagnostics 与 AI quality/cost/failure signals 收口成显式事件面，并继续复用 M020/S02 的 allowlist-first observability contract。
3. 继续沿 M021/S03 已建立的 canonical evaluation kernel seam 推进 compatibility reader retire 条件检查，而不是回到页面/route 各自重算 rollup 的旧模式。
4. 保持 M019 assembled release truth 与 M020/M021 已封板 authority seams 稳定，不要重开第二套 startup/migration/practice/frontend/release/auth/observability/runtime/evaluation 入口。
5. 继续把 AI control-plane / evaluation / quality-event work 落在 authority-bearing code、focused tests、workflow、runbook 与 contract docs 上，而不是退回 markdown-only inventory。

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
- 不要在 M021 后续切片里把 `PromptTemplateService` 倒推成 live StepFun prompt authority，也不要在 classic `voice_mode == "legacy"`、legacy report/evaluation readers、PromptTemplateService governance/helper surfaces、或 knowledge compat debug/audit consumers 仍存在时粗暴删除 legacy AI surfaces。
- 不要让 compiled prompt failures重新回到 silent fail-open：缺变量、空渲染、provider/base_url 缺失、generation error 已经在 M021/S02 被定义成 explicit diagnostics / fail-closed contract；后续切片应沿这条 seam 扩展，而不是重新引入 filler copy 掩盖失败。
- 不要让 report / replay / history / future admin pages 绕开 shared frontend score resolver 重新解释 fallback 顺序；一旦某个 surface 私自重算，就会让 compatibility fallback 无法被准确退休。

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
