# GSD Plan: post-M018-next-wave

## 1. 需求重述与工作假设

### 1.1 用户目标
- 基于当前仓库真实结构，把你刚给出的系统、AI、产品、交付审查结论拆成**可直接执行的 M/S/T**。
- 结果必须落到 `.gsd/milestones/`，不是停留在口头建议。
- 不能遗漏：architecture、runtime、security、CI/observability、AI control plane、sales productization、organization-ready 目标态都要进计划。

### 1.2 当前阶段目标
- 在 `M001-M018` 已完成的前提下，规划下一波 4 个 milestone：M019-M022。
- 让后续执行模型可以直接从 milestone/slice/task plan 开工，而不需要重新做全仓扫描。
- 保持当前 modular monolith，不抢跑 service split，不换技术栈。

### 1.3 关键约束
- 保留现有 stack：Next.js + FastAPI + SQLAlchemy Async + Alembic + Redis + Chroma + OSS + StepFun。
- 不把“想法型问题”伪装成“已经证实的 defect”；需要 discovery 的继续保持 discovery slice。
- 不把移动端/i18n/PWA/CRM/SSO/多租户实现硬塞进当前执行波次。
- 不绕开现有 authority seams：`SessionEvidenceService`、practice route family、admin surfaces、learner routes、shared auth/debug/logger seams。

### 1.4 工作假设
- 用户这一轮要的是**规划与落盘**，不是立刻实现 M019-M022 代码。
- 下一轮执行应按 milestone 顺序推进：先边界与底座，再 AI 统一，再产品化。
- 旧 milestone 的已验证 baseline 继续成立；新 milestone 只处理新的高杠杆问题。

---

## 2. 范围定义（In / Out）

### In Scope
- 新增 M019-M022 roadmap / slice plan / task plan。
- 为 post-M018 next wave 生成架构扫描与总计划文档。
- 覆盖以下四类问题：
  - Authority seams / release truth
  - Security / multi-instance runtime / recovery hardening
  - AI control plane / prompt / evaluation kernel 统一
  - Sales productization / manager truth / organization-ready roadmap

### Out of Scope
- 本轮不直接修改产品代码。
- 不直接改 `REQUIREMENTS.md` 状态，也不强行新增 requirement ID。
- 不直接上线多租户、SSO、CRM、移动端、i18n、导出报告。
- 不把 M019-M022 写成“全面重写计划”或“拆服务计划”。

---

## 3. 工程分层分析

| 层级 | 当前项目现状 | 本轮是否纳入 | 说明 |
|---|---|---:|---|
| 产品/业务层 | 企业内部 AI 训练平台已成型，但销售产品化不足 | 是 | M022 负责 productization / manager truth / org-ready |
| 前端层 | `client.ts` / `use-practice-websocket.ts` 是高扇出编排 seam | 是 | M019 先抽边界，M020/M021/M022 复用 |
| 后端层 | `practice.py` / realtime handlers / auth / logger 是集中热点 | 是 | M019-M021-M020 均涉及 |
| 数据层 | Alembic + models + projection-backed read model 已存在 | 是 | M019 先收 authority，M022 做 org-ready plan |
| 集成/接口层 | REST + WS + docs/api-contract 已有，但有 drift 风险 | 是 | M019 S04 / M020 S01 / M021 S02-S04 |
| 测试层 | web/backend focused gates 丰富 | 是 | 所有 slices 都写 repo-root verification |
| 部署/运维层 | M018 已有 baseline，但仍偏手工 runbook | 是 | M020 S04 升级为 drills |
| 文档/可观测性层 | `.gsd/` 完整，metrics/error/reporting/doc-contract 有假接通风险 | 是 | M019 S04 / M020 S02 / M021 S04 |

---

## 4. 里程碑总览

### M019. Authority seams 与 release gate 收口
- 目标：把 schema authority、practice backend、frontend client/ws、CI/metrics/doc-contract 先收口成可执行边界。
- 为什么先做：后续所有 hardening/productization 都依赖这条 truth line；不先收口，任何新改动都会继续堆进 mega files。
- 完成后得到：数据库/应用层/前端 transport/CI release gate 都有明确 authority。
- 依赖：无（接在 M018 之后直接开始）。
- 风险：容易滑向大重构；必须保持“抽 seam、不重写产品”。

### M020. Security / multi-instance runtime / recovery hardening
- 目标：把 auth transport、日志 redaction、session state authority、recovery drill 从 baseline 升成真实 hardening。
- 为什么先做：这些问题会放大后续所有 runtime 与 AI 工作的风险。
- 完成后得到：cookie/ws/auth/logs/session-state/recovery 有可信生产边界。
- 依赖：M019。
- 风险：auth 与 runtime 都是高 blast radius 区域，需要 strong model 牵头。

### M021. AI control plane / prompt / evaluation kernel 统一
- 目标：把 live AI path、prompt contract、evaluation kernel、quality/cost/failure events 收口到同一 truth line。
- 为什么先做：当前 live path 和 legacy path 混在一起，PromptTemplateService 和多套分数维度会继续制造 drift。
- 完成后得到：prompt/evidence/score/quality 具备统一 authority。
- 依赖：M019；M020 的安全/运行时底座最好先到位。
- 风险：高扇出 contract 变更，必须依赖 compatibility readers/compat mode。

### M022. Sales productization / manager truth / organization-ready roadmap
- 目标：把产品从“训练平台底座”往更专业的销售训练产品推进，同时定义 org/team/tenant 目标态。
- 为什么先做：这是你审查里最明显的“产品可信度与商业化阻力”来源。
- 完成后得到：方法论-aware rubric、行业包/压力模型、manager truth surfaces、组织边界迁移路线。
- 依赖：M021。
- 风险：如果跳过前面的 kernel/control-plane 统一，会只剩包装没有底层真相。

---

## 5. 详细切片清单

> 说明：每个切片的完整任务已写入对应 milestone 目录下的 `S##-PLAN.md` 与 `tasks/T##-PLAN.md`。这里保留执行前必须看的 slice 摘要。

### [M019-S01] 启动期 schema authority 收口
- Goal：把 `init_db` / startup compatibility patch / bootstrap / Alembic 的职责画清并收口。
- Why：不先收口数据库 authority，后面任何抽层都会继续踩 runtime DDL 漂移。
- In Scope：startup/migration/bootstrap inventory、隐式 schema 修补迁移、runbook/update。
- Out of Scope：重写整个迁移体系；改变 SQLite/Postgres 兼容策略。
- Inputs / Preconditions：`backend/src/common/db/session.py`、`backend/src/main.py`、Alembic、scripts、M018 recovery baseline。
- Target Files / Modules：`backend/src/common/db/session.py`、`backend/src/main.py`、`backend/alembic/versions/*`、`docs/backup-recovery-runbook.md`。
- Implementation Notes：显式迁移或 bootstrap，禁止继续把 request/startup path 当常态 schema repair。
- Done When：prod/dev 启动与迁移职责明确，focused proof 可复跑。
- Verification：`rg -n "create_all|alembic|bootstrap|repair_legacy_schema|init_db" ...`
- Deliverable：migration-only / bootstrap-only authority map。
- Risk Level：High
- Recommended Executor：Strong model

### [M019-S02] Practice backend application seam 抽离
- Goal：从 `backend/src/common/api/practice.py` 抽出 create/lifecycle/report/audio/runtime-descriptor 应用服务。
- Why：这是当前最大的 backend 编排热点之一。
- In Scope：service seam 设计、应用层提取、focused proof 更新。
- Out of Scope：改 route contract；新造第二套路由。
- Inputs / Preconditions：M019-S01 authority 结果、practice/report/session evidence 现有 tests。
- Target Files / Modules：`backend/src/common/api/practice.py`、`backend/src/common/services/*`、`backend/src/common/conversation/session_evidence.py`。
- Implementation Notes：route 仅留 auth、request parsing、response composition。
- Done When：route 不再承载主要业务编排，focused backend tests 继续通过。
- Verification：repo-root pytest：practice evidence / lifecycle / practice flow focused suites。
- Deliverable：practice application services。
- Risk Level：High
- Recommended Executor：Strong model

### [M019-S03] Frontend domain client 与 transport seam 抽离
- Goal：把 `client.ts` 拆成 domain modules，把 `use-practice-websocket.ts` 固定为 outward transport seam。
- Why：当前前端请求与 realtime orchestration 仍过度集中。
- In Scope：domain split、transport helper split、focused web proof。
- Out of Scope：页面本地直连 API/WS；重写所有 hooks。
- Inputs / Preconditions：M019-S02 backend seam、现有 web tests。
- Target Files / Modules：`web/src/lib/api/*`、`web/src/hooks/use-practice-websocket.ts`、`web/src/hooks/websocket/*`。
- Implementation Notes：保留 shared auth/error/trace seam，不分叉到页面里。
- Done When：domain client 与 transport boundary 清楚，focused web tests 继续覆盖。
- Verification：`npm --prefix web test -- --run ...`
- Deliverable：domain client + stable transport boundary。
- Risk Level：High
- Recommended Executor：Strong model

### [M019-S04] Release gate / metrics / doc-contract truth line 收口
- Goal：让 workflow、metrics、frontend error reporting、doc/spec contract 成为真实 release surface。
- Why：当前 CI/观测/契约有明显“文件存在但未必接通”的风险。
- In Scope：workflow 对齐、metrics/error surface 收口、doc-contract drift check。
- Out of Scope：完整平台级观测重建。
- Inputs / Preconditions：M019 S01-S03 outputs、当前 `.github/workflows`、ErrorBoundary、metrics helpers、api docs。
- Target Files / Modules：`.github/workflows/*`、`backend/src/main.py`/`common/api/*`、`web/src/components/ErrorBoundary.tsx`、`docs/api-contract/*`。
- Implementation Notes：所有命令以 repo-root 为准；默认 authority 以 `.github/workflows/release-truth-gate.yml` 为 assembled release gate，以 `.github/workflows/nfr-performance-check.yml` 为 backend NFR companion gate。M020-M022 默认复用同一组 repo-root verification bundle 与 doc-contract/live-route inventory proof；如果要把新的 route/spec/metrics/admin surface 升级为 authority，必须同步更新 workflow、focused proof、architecture scan 和计划文档。`web/src/app/admin/page.tsx` 的 demo stats 仅作为 M022-S03 输入，不能并入 release gate。
- Done When：release gate 能检查 web/backend/doc/metrics/error-reporting 关键 truth line，并把 legacy `api-spec.md` / checked-in `openapi.yaml` 明确留在 drift inventory，而不是继续伪装成 release authority；admin home demo stats 继续显式留在 M022-S03 truth-surface 收口输入里。
- Verification：默认复用以下 repo-root bundle：`npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"`；`backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q`；`rg -n "/api/v1/practice/sessions|/api/v1/admin/release-verification|/api/v1/support/runtime" docs/api-contract`；`rg -n "/auth/wechat|POST /api/v1/sessions" api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml`；`rg -n "/practice/sessions|/admin/release-verification|/support/runtime" docs/api-contract backend/src/common/api/practice.py backend/src/admin/api/release_verification.py backend/src/support/api/runtime_status.py`。
- Deliverable：assembled release gate + downstream reuse rule。
- Risk Level：Medium
- Recommended Executor：Strong model

### [M020-S01] Auth transport hardening
- Goal：收口 cookie security、CSRF posture、websocket auth transport、shared-password 兼容退出路径。
- Why：当前 auth transport 仍有多条兼容路径并存。
- In Scope：auth matrix、cookie/ws policy、compat exit。
- Out of Scope：SSO 实现；完全移除所有兼容路径。
- Inputs / Preconditions：M019 release truth line、current auth/websocket tests。
- Target Files / Modules：`backend/src/common/auth/*`、`backend/src/sales_bot/websocket/router.py`、`web/src/hooks/use-practice-websocket.ts`。
- Implementation Notes：query token 不能继续作为常态路径。
- Done When：正式 transport 与兼容 transport 明确，focused tests 通过。
- Verification：repo-root auth/websocket pytest suites。
- Deliverable：auth transport authority。
- Risk Level：High
- Recommended Executor：Strong model

### [M020-S02] Sensitive log 与 admin observability redaction 收口
- Goal：统一 logger sink、system log API、admin logs UI 的 redaction policy。
- Why：只修 logger 不修 API/UI，敏感信息仍会从另一层漏出。
- In Scope：allowlist/denylist、三层统一 policy、focused tests。
- Out of Scope：完全禁掉 support/admin 的诊断信息。
- Inputs / Preconditions：M020-S01 auth boundary、现有 security inventories。
- Target Files / Modules：`backend/src/common/monitoring/logger.py`、`backend/src/admin/api/system_logs.py`、`web/src/app/admin/logs/page.tsx`。
- Implementation Notes：保留 trace_id、error code、phase 等必要诊断字段。
- Done When：三层暴露规则一致，focused tests 锁定。
- Verification：backend admin users/log tests + web admin logs tests。
- Deliverable：安全可见的 observability surface。
- Risk Level：Medium
- Recommended Executor：Fast model（需谨慎）

### [M020-S03] Multi-instance session state 与 reconnect authority 收口
- Goal：让 SessionManager/SessionStateService 的 state authority 在多实例/重启场景下可解释。
- Why：当前单进程 happy path 容易掩盖扩容/重启问题。
- In Scope：state authority table、snapshot/reconnect/drian hardening、support/runtime docs 更新。
- Out of Scope：直接上容器编排或集群化重构。
- Inputs / Preconditions：M020-S01/S02、安全边界和 logs 已收口。
- Target Files / Modules：`backend/src/common/websocket/session_manager.py`、`session_state_service.py`、sales/presentation handlers。
- Implementation Notes：不要把所有 state 都塞进 Redis，只提升真正需要跨实例可见的部分。
- Done When：single-node / restart / multi-instance 的 authority 边界与 focused proof 清楚。
- Verification：websocket reconnect/status backend suites。
- Deliverable：runtime state authority table + hardened snapshot semantics。
- Risk Level：High
- Recommended Executor：Strong model

### [M020-S04] Recovery drill automation 与部署指导收口
- Goal：把 M018 recovery baseline 升成最小可执行 drill/script。
- Why：仅有 runbook 还不够，后续 runtime/AI/product milestone 需要可复跑恢复能力。
- In Scope：drill selection、repo-local scripts、运维文档对齐。
- Out of Scope：全自动灾备平台。
- Inputs / Preconditions：M018 baseline、M020 S01-S03 outputs。
- Target Files / Modules：`scripts/*`、`docs/backup-recovery-runbook.md`、`.sisyphus/deploy/*`。
- Implementation Notes：仍需 secrets 的步骤保持显式前置条件，不硬编码。
- Done When：至少一组 repo-local recovery drill 可执行。
- Verification：脚本 grep/check + repo-root commands。
- Deliverable：可执行 recovery drill baseline。
- Risk Level：Medium
- Recommended Executor：Fast model

### [M021-S01] Live AI authority inventory
- Goal：给 AI/runtime/prompt/score/report 路径打上 live/compat/shadow/retire 标签。
- Why：不先分清 live 与 compat，统一工作会打错地方。
- In Scope：inventory、docs/proof annotations、keep/compat/retire matrix。
- Out of Scope：立刻删除 legacy path。
- Inputs / Preconditions：M019 extracted seams、current AI modules。
- Target Files / Modules：`stepfun_realtime_handler.py`、`evaluation/services/*`、`prompt_templates/*`、`knowledge_engine/*`。
- Implementation Notes：必须回答“现在真正在线的 AI 主链是什么”。
- Done When：inventory 可直接驱动 S02-S04。
- Verification：`rg -n "PromptTemplateService|generate_report|evaluate\(|stepfun|knowledge_answer|voice_instruction" ...`
- Deliverable：live/compat/shadow inventory。
- Risk Level：High
- Recommended Executor：Strong model

**M021 S02-S04 input matrix（from S01 inventory）**
- **must keep**：`stepfun_realtime_handler.py`、`voice_runtime_policy.py`、`voice_instruction_compiler.py`、`presentation_stepfun_realtime_handler.py`、`stepfun_internal_knowledge_searcher.py`、`common.knowledge_engine.compat`。这些是 live runtime / compiled snapshot / shipped knowledge rollout authority，后续 slices 只能围绕它们收口，不能另起第二条主链。
- **compat**：`prompt_templates/service.py` + routes、`evaluation/services/realtime_scoring.py`、`ai_scoring.py`、`score_processor.py`。这些仍有 shipped consumer（admin prompt governance、presentation interruption fallback、classic `voice_mode == "legacy"` score_update / report trigger），只能降格治理，不能在 M021 中直接拔掉。
- **retire candidate**：`staged_evaluation.py`、`comprehensive_report.py`、`report_generation_trigger.py`、`evaluation/api.py`、`common/ai/llm_service.py::evaluate/generate_report`。它们不是 canonical truth，但还有 history/support/admin `report_status` consumer、`/practice/*/comprehensive-report`、manual `/evaluation/*` operator consumer 在依赖，所以只可在 consumer 迁走后退役。
- **legacy consumer guardrail**：M021 期间禁止一次性粗暴删除 classic `voice_mode == "legacy"` runtime、`report_status` / comprehensive-report read-side、manual `/evaluation/*` operator flow、PromptTemplateService 的 admin/runtime helper surface、以及 knowledge compat debug/audit consumer。
- **Slice handoff**：`S02` 必须把 compiled prompt contract 建在 must keep seam 上，并保留 compat consumer；`S03` 先迁 `report_status` / report readers 再判 retire candidate；`S04` 继续沿 `common.knowledge_engine.compat` 暴露 quality/cost/failure/mode 事件，不能旁路成 engine-only truth。

### [M021-S02] Prompt control plane 统一
- Goal：让 PromptTemplateService、voice instruction、persona policy、runtime guardrail 形成真实 compiled prompt contract。
- Why：当前存在 template 假接入、prompt 来源碎片化、missing vars fail-open。
- In Scope：taxonomy、compiled contract、guardrails/diagnostics、docs。
- Out of Scope：一次性重写所有 prompt。
- Inputs / Preconditions：M021-S01 inventory。
- Target Files / Modules：`backend/src/prompt_templates/*`、`common/ai/llm_service.py`、`voice_instruction_compiler.py`。
- Implementation Notes：base_url/missing vars/fail-open policy 需要显式化。
- Done When：模板真正影响 live/compat path，diagnostics 可检查。
- Verification：repo-root pytest `-k "prompt or knowledge_answer or report"`
- Deliverable：compiled prompt contract。
- Risk Level：High
- Recommended Executor：Strong model

### [M021-S03] Canonical evaluation kernel 收口
- Goal：统一 realtime、report、history、admin、replay 的 canonical dimension schema 与 rollup contract。
- Why：当前存在双轨/三轨分数事实，不可校准。
- In Scope：schema 定义、compatibility readers、backend/web read-side 调整。
- Out of Scope：一次性删除所有旧字段。
- Inputs / Preconditions：M021-S02 compiled prompt contract、current evidence/read-side surfaces。
- Target Files / Modules：`backend/src/common/effectiveness/*`、`session_evidence.py`、`common/analytics/*`、`web/src/lib/api/types.ts`。
- Implementation Notes：sales/presentation 用 scenario-aware schema，不再各自飘。
- Done When：canonical 与 compat path 都清晰可测。
- Verification：parity + analytics/history backend suites；report/replay/history web suites。
- Deliverable：canonical evaluation kernel。
- Risk Level：High
- Recommended Executor：Strong model

### [M021-S04] AI quality/cost/failure events 与 knowledge path 收口
- Goal：显式记录 AI 失败、降级、成本和 knowledge-answer mode，不再让默认分数/默认文案掩盖失败。
- Why：这是当前 AI runtime 真相线最薄弱的一层。
- In Scope：event schema、runtime/read-side/event surfaces、support docs、front-end degraded assertions。
- Out of Scope：完整成本计费系统。
- Inputs / Preconditions：M021 S01-S03 outputs。
- Target Files / Modules：`common/ai/llm_service.py`、`knowledge_engine/*`、`stepfun_*` components、`support/api/runtime_status.py`。
- Implementation Notes：不得泄露敏感配置/secret/base_url/token。
- Done When：quality/cost/failure events 可检查，knowledge path mode 清晰。
- Verification：knowledge/websocket/report/replay focused suites。
- Deliverable：explicit AI quality event line。
- Risk Level：Medium
- Recommended Executor：Strong model

### [M022-S01] Methodology-aware sales rubric 收口
- Goal：把销售训练提升到方法论 aware 的 rubric contract。
- Why：这是销售专业度不足的第一性问题。
- In Scope：方法论/证据映射、shared effectiveness 接入、用户/管理面说明。
- Out of Scope：一次覆盖所有销售方法论。
- Inputs / Preconditions：M021 canonical kernel。
- Target Files / Modules：`common/effectiveness/*`、`realtime_scoring.py`、`sales_stage.py`、report surfaces。
- Implementation Notes：首轮只需一套可配置 rubric contract，不追求完全教材化。
- Done When：realtime/report/manager coaching 至少共享一套方法论语义。
- Verification：backend sales-focused suites。
- Deliverable：methodology-aware rubric contract。
- Risk Level：High
- Recommended Executor：Strong model

### [M022-S02] Persona / scenario / industry pack 运营化
- Goal：让 persona/customer-pressure/scenario/knowledge 能组成可维护行业包，不再只靠单条 prompt。
- Why：角色与场景深度是当前产品可信度短板。
- In Scope：industry pack contract、现有 admin entrypoints 接入、运营规则文档化。
- Out of Scope：新造内容管理平台。
- Inputs / Preconditions：M022-S01 rubric contract。
- Target Files / Modules：`backend/src/agent/api/*`、`sales_bot/api/scenarios.py`、admin personas/agents/knowledge pages。
- Implementation Notes：继续复用现有 admin surfaces；把 `industry pack` 明确定义成 composed asset：agent 负责 runtime shell，persona policy + `customer pressure` 负责角色与追问压力，`knowledge bundle` 负责 retrieval/evidence，`scenario package` 负责入口 narrative/routing 而不是 runtime truth。
- Operating Rules：运营改 `customer pressure` 时，预期 live runtime instruction、report evidence、future manager calibration 一起变化；运营改 `knowledge bundle` 时，必须能从 frozen `runtime_binding` / retrieval facts 解释证据来源；运营改 `scenario package` 时，只能宣称影响 session 入口与叙事，不可包装成独立 runtime authority。
- Manual Ops Boundary：行业话术、persona system prompt、pressure axes / expected questions、knowledge bundle 选编、scenario package narrative 仍是手工内容运营项；系统提供的是 inspectable contract、runtime evidence、admin read surfaces，而不是自动生成行业包内容。
- Done When：资产合同明确，runtime/report/manager calibration 都能指出用了哪种 industry pack / customer pressure / knowledge bundle，且边界说明不把 `scenario package` 冒充成 runtime truth。
- Verification：persona/knowledge/scenario backend suites + admin personas web suite；文档 grep 需能直接找到 `industry pack` / `customer pressure` / `scenario package` / `knowledge bundle` 运营规则。
- Deliverable：industry pack operating contract + write-back rules in architecture scan / product plan.
- Risk Level：Medium
- Recommended Executor：Strong model

### [M022-S03] Manager calibration 与 admin truth surfaces 收口
- Goal：把 manager/admin 的决策面建立在真实 evidence 与真实 stats 上。
- Why：fake stats/dummy cards 会直接损害产品可信度。
- In Scope：fake stats inventory、真实 surface 替换、manager truth 文档化。
- Out of Scope：完整管理系统重建。
- Inputs / Preconditions：M022-S01/S02；另外直接继承 M019/S04 的已知输入：`web/src/app/admin/page.tsx` 当前只有顶部“训练效果核心看板（近7天）”读取真实 API，其余卡片仍硬编码 `2,543`、`84`、`42%`、`68%`、`75%`、`450 GB` 以及静态日志/告警文案。
- Target Files / Modules：`web/src/app/admin/page.tsx`、`web/src/components/admin/*`、`backend/src/common/analytics/*`。
- Implementation Notes：没有真实数据的卡片要降级或移除，不再硬造运行中数字；M019/S04 已明确这些 admin home demo stats 不是 release truth，也不能被营销/运营文案包装成 live monitoring。产品边界按现有入口写死：`manager-lite-panel` 是主管分诊入口，`/admin/users/[id]` 是单人 calibration / team coaching drill-in 入口，`/admin/analytics` 是 team summary / degraded breakdown / runtime fault 回顾入口。
- Product Boundary：
  - 已可产品化：canonical evidence 驱动的 manager-lite、admin analytics、user detail / manager interventions。它们已经能支持主管做 not passed、trend、calibration、team coaching 的真实判断。
  - 仍属后续工作：admin 首页组织/资源/运维汇总卡、快捷动作/系统动态/告警自动化、独立 manager calibration workspace、独立 team coaching cockpit。它们仍只是 inventory / roadmap surface，不能在对外文案里写成已交付能力。
- Messaging Guardrail：任何计划/销售话术都必须把这些 surface 说成 “truth surface” 或 inventory boundary，而不是把 placeholder card、fake stats、静态动作入口包装成实时运营中枢。
- Done When：关键 admin/manager 决策面只显示真实数字和真实 summary，且产品计划明确区分“已产品化 truth surface”与“仍是后续工作的 inventory / placeholder surface”。
- Verification：admin home / manager-lite web tests + admin analytics backend tests。
- Deliverable：manager/admin truth surfaces。
- Risk Level：Medium
- Recommended Executor：Fast model（有产品判断）

### [M022-S04] Organization / team / tenant target-state plan
- Goal：定义 organization/team/tenant 目标态、authz 影响和 modular-monolith 迁移路径。
- Why：再不规划，后续每个功能都会继续绑定到 `user/session/global-admin`，enterprise 需求一进来就只能继续堆兼容分支。
- In Scope：ownership/authz matrix、migration path、future integration slots。
- Out of Scope：本轮实现多租户/SSO/CRM/org sync。
- Inputs / Preconditions：M022-S03、M020 hardened auth boundary。
- Target Files / Modules：analysis/plan docs、`backend/src/common/db/models.py`、`common/auth/*`、`admin/*`。
- Implementation Notes：这是 contract/roadmap slice，不是实现 slice。T01 先锁当前 shipped ownership matrix 与 target-state 概念边界；T02 再决定 modular monolith 下哪些实体先补 compatibility readers；T03 最后把 out-of-scope 与 future milestone 入口写回 roadmap。
- Current-state assumptions to retire：
  - `users.role` 目前只表达 global `user/support/admin`，还不能表示 org/team 内角色。
  - `practice_sessions.user_id`、`manager_interventions.manager_user_id/user_id`、`admin/api/users.py`、`admin/api/analytics.py` 都默认全局单组织上下文。
  - `agents/personas/knowledge_bases` 目前最多只有 `created_by/updated_by` 审计字段，不是 org-owned 资产。
- Target-state matrix（固定 contract）：
  - `organization` = account / authz / analytics 顶层边界，未来 SSO/CRM/org-sync 都挂这里。
  - `team` = organization 下的 manager/coaching cohort，manager-lite、user drill-in、admin analytics 默认先按 team scope 出真相。
  - `member` = global `user` 在某个 organization 内的一条 membership；org/team role 应挂在 membership，而不是继续塞进 `users.role`。
  - `tenant` = 更重的数据/部署隔离边界，不等于 organization；本轮只留 slot，不提前实现。
  - asset ownership 先走 `global template + org rollout binding` 两层：agent/persona/knowledge 不立即按 org 复制，先给 rollout/authz 留 seam。
- Authz rule：后续 enterprise work 应从 `platform role + org membership role + access scope(self/team/org/platform)` 推导权限；当前 `global admin` 只能视为 compatibility seam。
- Analytics rule：未来 organization/team 视角要复用现有 `manager-lite-panel`、`/admin/users/[id]`、`/admin/analytics` 真实 surface，加 scope-aware reader，而不是另做一套 org dashboard。
- Integration slots：
  - SSO / directory sync → membership provisioning + team assignment source
  - CRM / account sync → organization account metadata / segmentation source
  - org sync / HRIS → manager chain、team transfer、deactivation source
- T02 migration path（固定 contract）：
  1. **Phase 1 — reader-first within the modular monolith**：先不拆服务，也不重写主表；优先给 `practice_sessions`、`manager_interventions`、`SessionEvidenceService` projection、`/admin/users/[id]`、`/admin/analytics`、manager-lite 补 `organization_id` / `team_id` compatibility reader，让 report/replay/history/admin surfaces 能按 `self/team/org/platform` scope 解释既有 evidence。
  2. **Phase 2 — authz seam before asset cloning**：引入 `organization_member` / team assignment 作为 membership seam，把 org/team role 与 access scope 从 `users.role` 中拆开；`get_current_admin_user()`、`_can_read_session(...)`、manager/admin queries 先走 platform-role + membership-role + scope reader 的 compatibility path，`global admin` 继续保留 override 语义。
  3. **Phase 3 — rollout binding for content/control plane**：agent / persona / knowledge / prompt / voice-runtime / knowledge-config 继续保留 global template row，不直接改成 org-owned；先增加 org rollout binding / visibility seam，让 runtime snapshot、`voice_policy_snapshot_ref.runtime_binding`、report evidence 还能解释“模板来源 + org 发布范围”。
  4. **Phase 4 — integration adapters stay outside runtime truth**：SSO、CRM、org sync 只写 organization/member/team/account metadata seam，不直接接管 session runtime、manager analytics、prompt runtime 或 knowledge truth；这些 integration source 只是 provisioning / metadata adapter，不是新的业务 authority。
  5. **Phase 5 — service split only after monolith pressure is real**：只有当 organization-scoped write path、membership sync、或 org-level analytics 因吞吐/隔离/合规要求出现独立扩缩容与发布节奏时，才考虑拆 service；在那之前继续留在 modular monolith，用模块边界 + compatibility readers 演进。
- Migration ordering rule：session/read-side scope 先于 authz write path，authz write path 先于 asset ownership，asset ownership 先于外部 integration automation；禁止跳过 compatibility reader 直接把现有 global row 改成 org-owned。
- Compatibility-reader surfaces（必须先补）:
  - session/report/replay/history：`practice_sessions.user_id` 周边 read model、`SessionEvidenceService`、`voice_policy_snapshot_ref.runtime_binding`
  - manager/admin：`manager_interventions`、`/admin/users/[id]`、`/admin/analytics`、manager-lite
  - authz：`get_current_admin_user()`、`require_role(...)`、`common.api.practice._can_read_session(...)`
- Roadmap handoff（下一轮 enterprise roadmap 固定入口）:
  - **继续留在 modular monolith 的默认条件**：新需求如果只是把现有 learner / manager / admin truth surface 补成 `self/team/org/platform` scope-aware reader、membership authz、org rollout binding、organization metadata seam，默认继续在 modular monolith 内推进，不额外创建 org service、team service 或 tenant service。
  - **下一轮应该优先排入的 enterprise 输入**：`organization_member` / team assignment seam、session/report/replay/history/admin scope-aware reader、`global template + org rollout binding` 可见性、organization account metadata inventory、以及 SSO/CRM/org sync 的 provisioning adapter contract。
  - **service split 触发器（缺一不可）**：只有当 `organization` 范围写路径或 membership sync 需要独立扩缩容/失败隔离、org-level analytics/export/compliance 需要独立发布与数据保留策略、并且这些压力已经不能靠 modular monolith 模块边界 + compatibility readers 消化时，才值得进入 service split roadmap。
  - **out-of-scope（本轮与下一轮入口都不抢跑）**：当前不做多租户 runtime/tenant implementation，不接 SSO/CRM 的生产集成，不改外部集成 authority，不新造 org dashboard，也不把现有 global row 直接改写成 org-owned row。
- Done When：组织边界与迁移路线可直接作为下一轮企业化 milestone 输入，并且后续 agent 可以据此判断新需求应挂在 self/team/org/platform 哪个 seam。
- Verification：grep plan/analysis/future roadmap。
- Deliverable：org/team/tenant target-state roadmap。
- Risk Level：High
- Recommended Executor：Strong model

---

## 6. 依赖关系图（文字版）

- `M019-S01 → M019-S02 → M019-S03 → M019-S04`
- `M019` 完成后，`M020` 与 `M021` 可以开始，但建议先做 `M020-S01` 再推进 `M021-S02/S03/S04`
- `M020-S01 → M020-S02 → M020-S03 → M020-S04`
- `M021-S01 → M021-S02 → M021-S03 → M021-S04`
- `M022` 依赖 `M021`，因为 productization 需要 canonical evaluation/prompt truth line
- `M022-S01 → M022-S02 → M022-S03 → M022-S04`

---

## 7. 执行模型分流建议

### 适合 Fast model 的切片
- `M019-S04` 的 workflow/doc drift check 子任务
- `M020-S02` 的 logger/API/UI redaction 落地
- `M020-S04` 的 recovery drill 脚本化
- `M022-S03` 的 fake stats inventory 和 truth-surface 替换

### 必须 Strong model 处理的切片
- `M019-S01`、`M019-S02`、`M019-S03`
- `M020-S01`、`M020-S03`
- `M021-S01` 到 `M021-S04` 全部
- `M022-S01`、`M022-S02`、`M022-S04`

### 分流原则
- 涉及 auth、runtime、schema authority、compiled prompt、canonical evaluation kernel、organization target-state 的都归 Strong model。
- 边界清晰的 UI/doc/workflow/redaction/drill 子任务可交给 Fast model。
- 若执行中发现 slice 需要重新定义 authority seam，立即升级为 Strong model 并触发 replan。

---

## 8. 重规划触发条件

- 连续两次 focused verification 在同一 authority seam 失败。
- 实际代码结构与本次 architecture scan 记录不一致。
- 发现新的 live path，推翻 `live/compat/shadow` inventory。
- 提示词/评分/日志/auth 任一 slice 需要跨两个以上 milestone 的边界才能完成。
- 发现关键环境/依赖缺失，导致 planned verification command 无法如期作为 authority。
- manager/admin/product 化工作试图绕过 canonical evidence 或 fake stats 替换原则。
- organization/team/tenant 目标态被新需求提前拉成“本轮直接实现”。

---

## 9. 对当前项目的 GSD / GSD auto 落地建议

### 目录建议
- 规划入口继续放在：`.gsd/milestones/M019..M022/`
- 总文档继续放在：
  - `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`

### 命名建议
- 继续用 milestone bare ID：`M019`, `M020`, `M021`, `M022`
- slice 继续用 `S01..S04`
- task 继续用 `T01..T03`

### 执行顺序建议
1. `M019`
2. `M020-S01`
3. `M021-S01`
4. `M020` remainder
5. `M021` remainder
6. `M022`

### 风险控制建议
- 每个 slice 开工前先读对应 `M0xx-ROADMAP.md`、`S0x-PLAN.md`、`T0x-PLAN.md`。
- 后端 repo-root pytest 命令串行执行，避免 `.coverage` 竞争。
- 对 `practice.py` / `client.ts` / `use-practice-websocket.ts` 的工作，一律先跑 focused proof 再动手。
- 对 `auth/service`、`logger`、`session_manager`、`stepfun_realtime_handler` 的工作，默认加 diagnostics review。

---

## 10. 可直接给执行模型的任务单模板（3 个实例）

### Task Card 1
- Task ID: `M019-S02-T02`
- Title: 抽出 session create/lifecycle/report 应用服务
- Goal: 从 `practice.py` 中抽出应用层 service，同时保持现有 route contract。
- In Scope: create/lifecycle/report/audio/runtime-descriptor service seam
- Out of Scope: 改 API 路径；重写 report/replay/history
- Preconditions: M019-S01 已明确 schema/startup authority；focused practice tests 可跑
- Files/Modules to Inspect:
  - `backend/src/common/api/practice.py`
  - `backend/src/common/conversation/session_evidence.py`
  - `backend/src/common/db/session_lifecycle.py`
- Constraints:
  - route 仅留 auth/request/response
  - 不引入新 route family
- Done When: `practice.py` 的主要编排逻辑移到命名清晰的 service seam，focused backend tests 继续通过
- Verification Steps:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q`
- Expected Output:
  - `backend/src/common/services/practice_session_service.py`
  - `backend/src/common/services/practice_report_service.py`
- Recommended Executor: Strong model

### Task Card 2
- Task ID: `M020-S01-T02`
- Title: 收口 cookie、CSRF 与 websocket auth authority
- Goal: 明确正式 auth transport，并让 query token/shared password 只剩受控兼容语义。
- In Scope: backend auth、ws router、frontend websocket auth transport、cookie secure posture
- Out of Scope: SSO；完全移除所有兼容路径
- Preconditions: M019 release truth line 已有；auth/websocket focused tests 可跑
- Files/Modules to Inspect:
  - `backend/src/common/auth/service.py`
  - `backend/src/common/auth/api.py`
  - `backend/src/sales_bot/websocket/router.py`
  - `web/src/hooks/use-practice-websocket.ts`
- Constraints:
  - 不打断现有 learner/admin 登录链
  - 所有失败信号必须显式可见
- Done When: auth transport matrix 中的正式路径与兼容路径清楚，focused tests 通过
- Verification Steps:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_password_reset_api.py backend/tests/integration/test_websocket_status_contract.py -x -q`
- Expected Output:
  - auth transport policy 落地到代码与文档
- Recommended Executor: Strong model

### Task Card 3
- Task ID: `M021-S03-T02`
- Title: 实现 canonical evaluation kernel 与 compatibility readers
- Goal: 统一 realtime/report/history/admin/replay 的评分事实线。
- In Scope: canonical schema、rollup、compat readers、backend read-side
- Out of Scope: 一次性删除所有旧字段
- Preconditions: M021-S01 inventory、M021-S02 compiled prompt contract 已明确
- Files/Modules to Inspect:
  - `backend/src/common/effectiveness/*`
  - `backend/src/common/conversation/session_evidence.py`
  - `backend/src/common/analytics/*`
  - `backend/src/agent/capabilities/realtime_scoring.py`
- Constraints:
  - compatibility readers 必须显式存在
  - 不允许再次让各 read-side 自己算分
- Done When: canonical kernel 生效，focused parity/analytics/history tests 通过
- Verification Steps:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q`
- Expected Output:
  - canonical evaluation kernel + compatibility readers
- Recommended Executor: Strong model

---

## 11. 直接执行入口

已经落盘的执行入口：
- `.gsd/milestones/M019/M019-ROADMAP.md`
- `.gsd/milestones/M020/M020-ROADMAP.md`
- `.gsd/milestones/M021/M021-ROADMAP.md`
- `.gsd/milestones/M022/M022-ROADMAP.md`
- 各 slice 的 `S##-PLAN.md`
- 各 task 的 `tasks/T##-PLAN.md`

下一步如果直接执行，建议从 **M019/S01/T01** 开始。