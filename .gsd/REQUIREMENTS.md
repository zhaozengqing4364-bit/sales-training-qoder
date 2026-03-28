# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R009 — 客户演练在训练过程中应逐步提供可用的实时评分、阶段反馈或下一轮建议，帮助用户边练边调整，而不是只能事后看分。
- Class: differentiator
- Status: active
- Description: 客户演练在训练过程中应逐步提供可用的实时评分、阶段反馈或下一轮建议，帮助用户边练边调整，而不是只能事后看分。
- Why it matters: 这是系统从“训练记录工具”升级为“教练系统”的关键能力。
- Source: user
- Primary owning slice: M007/S01
- Supporting slices: M007/S02, M007/S03, M007/S04
- Validation: mapped
- Notes: M007 正式吸收此前已开始的 M002 remediation 事实线与未封板收尾工作。S01 负责训练中 coach degraded / resumed 的真实可见性与恢复语义；S02 负责同一条真实 session 从 realtime coaching 到 /practice/{sessionId}/report 与 /practice/{sessionId}/replay 的结论同源 proof；S03 负责把旧 M002 remediation artifacts、requirement/roadmap/validation/summary/state 的 authority 正式归并到 M007；S04 负责最终 integrated validation 与封板。只有产品真相 proof 与工件对账同轮通过后，R009 才能从 active 升到 validated。

## Validated

### R001 — 桌面端销售客户演练必须能稳定完成多轮来回，不能在第二轮录音、第二轮响应、会话结束或重连时频繁失效。
- Class: primary-user-loop
- Status: validated
- Description: 桌面端销售客户演练必须能稳定完成多轮来回，不能在第二轮录音、第二轮响应、会话结束或重连时频繁失效。
- Why it matters: 多轮稳定性是训练系统成立的前提，不稳定的主链路会直接摧毁首练完成率和后续复练意愿。
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: M001/S08
- Validation: validated
- Notes: 这是 M001 的 P0；若此项未达标，其它增强能力即使存在也不构成可上线训练系统。

### R002 — 当 ASR、LLM、TTS、WebSocket、会话状态或知识检索出现失败时，系统必须提供恢复、降级或可诊断路径，而不是直接终止训练或依赖人工猜测问题。
- Class: failure-visibility
- Status: validated
- Description: 当 ASR、LLM、TTS、WebSocket、会话状态或知识检索出现失败时，系统必须提供恢复、降级或可诊断路径，而不是直接终止训练或依赖人工猜测问题。
- Why it matters: 训练场景对心流和连续性极度敏感；失败模式不可见或不可恢复，会让系统只适合演示而不适合真实使用。
- Source: research
- Primary owning slice: M001/S01
- Supporting slices: M001/S08
- Validation: validated
- Notes: 需覆盖真实桌面端训练生命周期，不接受只在单元测试层面“看起来可恢复”。

### R003 — 销售训练需要让学员把公司产品价值点翻译成客户收益，支持真实销售表达，而不是只背公司 PPT 或泛泛陪聊。
- Class: core-capability
- Status: validated
- Description: 销售训练需要让学员把公司产品价值点翻译成客户收益，支持真实销售表达，而不是只背公司 PPT 或泛泛陪聊。
- Why it matters: 用户明确要求训练目标是“讲清价值并处理异议”，不是娱乐性对话；缺少真实价值表达，系统就无法改善销售表现。
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: M001/S04, M001/S07
- Validation: Validated by S05 slice verification: backend sales baseline/persona/compiler/contract/integration suites passed, web ScorePanel + websocket handler + report focused tests passed, live StepFun sales runtime showed value/price/competitor/evidence prompts driving sales-specific score_update dimensions and knowledge-check queries, and the canonical /practice/{sessionId}/report surfaced sales-specific main_issue, next_goal, pass_flags labels, and value/evidence/objection rollups from the unified evidence contract.
- Notes: 已证明客户演练会围绕产品价值翻译、客户收益、价格/竞品/证据异议运转；仍依赖 S06/S08 把这套分类继续拉到跨会话趋势与最终发布验收。

### R004 — 培训负责人或管理员必须能在系统里自己上传、更新、替换公司标准 PPT 与产品资料，且这些材料在下一次新建训练时生效。
- Class: admin/support
- Status: validated
- Description: 培训负责人或管理员必须能在系统里自己上传、更新、替换公司标准 PPT 与产品资料，且这些材料在下一次新建训练时生效。
- Why it matters: 训练材料会随着业务变化而更新；如果训练内容无法由业务侧维护，系统很快失真。
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S07
- Validation: Validated by S04 slice verification: backend knowledge/presentation integration suites passed, web admin knowledge/admin presentation/agent entry focused tests passed, live runtime/browser checks showed admin knowledge search diagnostics + knowledge-check snapshot fields, and standard PPT replacement exposed stable presentation_id + version/status with explicit 409 active-session blocking while user entry displayed the current deck version/status.
- Notes: M001 第一批硬要求材料是公司标准 PPT 与产品资料 / 功能说明；后续可扩展到更多知识类型。

### R005 — 每次训练结束后，学员都能获得结构清晰、建议具体且基于真实训练事实的单次报告，而不是抽象分数或模糊总结。
- Class: launchability
- Status: validated
- Description: 每次训练结束后，学员都能获得结构清晰、建议具体且基于真实训练事实的单次报告，而不是抽象分数或模糊总结。
- Why it matters: 如果报告不可读或不可信，学员无法把训练结果转化为下一次行动，首练后就会失去复练动力。
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: M001/S02, M001/S08
- Validation: Validated by S03 slice verification: backend contract/admin integration tests passed, web focused report/admin tests passed, and live runtime report UAT (after alembic head) proved the first screen leads with result, main issue, next goal, and unified evidence without placeholder/export affordances.
- Notes: S02 已验证 report / replay / history / trends 共享统一事实基线；S03 继续负责把这套事实翻译成真正可读、可执行的单次报告，而不是只做漂亮展示。

### R006 — 单次报告必须支持主管快速判断这次练得好不好、卡在哪个环节、哪些话说错或说虚、哪些异议没接住，以及下一次该重点练什么。
- Class: admin/support
- Status: validated
- Description: 单次报告必须支持主管快速判断这次练得好不好、卡在哪个环节、哪些话说错或说虚、哪些异议没接住，以及下一次该重点练什么。
- Why it matters: 主管是第一版的重要使用者；如果主管看完报告仍不知道怎么带人，管理侧价值就无法成立。
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: M001/S05, M001/S07
- Validation: Validated by S03 slice verification: admin sessions integration contract passed, admin detail + manager-lite focused tests passed, and live runtime admin APIs exposed projection-backed supervisor preview fields and canonical /practice/{sessionId}/report drill-in targets for the same completed sessions.
- Notes: 第一版主管动作先在线下发生，系统先负责提供可执行判断依据。

### R007 — 系统必须让主管看到某人在最近几次训练中的变化趋势，而不是只能看到单次表现。
- Class: operability
- Status: validated
- Description: 系统必须让主管看到某人在最近几次训练中的变化趋势，而不是只能看到单次表现。
- Why it matters: 用户明确要求主管判断“有没有进步、总卡在哪类问题、该不该换训练重点”；没有连续变化视图，就无法形成管理判断。
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S03
- Validation: Validated by S06 slice verification: backend HistoryService/admin-user projection suites passed, focused /progress and /stats integration assertions stayed aligned with projection-backed /sessions previews, web admin user-detail tests passed, Alembic was upgraded to head, and live browser review on /admin/users/{id} proved the supervisor-readable continuous-change panel answers whether the learner is improving, what keeps repeating, whether focus should change, and how inline empty/error states behave when progress data is unavailable.
- Notes: S06 now proves the first supervisor trend view on top of the same evidence projection used by single-session reports and completed-session previews; system-internal task assignment remains deferred.

### R008 — PPT 对练第一版必须允许用户完整讲完一轮，并在结束后获得围绕真实 PPT 价值点的统一复盘、评分与建议。
- Class: primary-user-loop
- Status: validated
- Description: PPT 对练第一版必须允许用户完整讲完一轮，并在结束后获得围绕真实 PPT 价值点的统一复盘、评分与建议。
- Why it matters: 用户明确把 PPT 对练列为并行训练模式；即使实时纠偏后置，会后完整复盘也必须可用。
- Source: user
- Primary owning slice: M001/S07
- Supporting slices: M001/S04
- Validation: Validated by S07 slice verification: backend presentation unit/degraded-path/contract/integration suites passed, live report API checks proved both complete and degraded presentation sessions keep `scenario_type="presentation"` plus canonical `presentation_review` without falling back to sales `main_issue`/`next_goal`, a fresh local audio-driven page-turn session (`8531c7f6-50da-4934-9fd4-63784c791edf`) completed through the real StepFun presentation websocket and produced page-aware summaries/coverage on `/api/v1/practice/sessions/{id}/report`, and the shared `/practice/{sessionId}/report` page rendered the PPT branch with sales-only sections absent while retry continuity preserved `presentation_id`.
- Notes: S07 proves the first PPT postmortem is now canonical from the shared report entrypoint; realtime interruption coaching remains deferred.

### R010 — AI 客户必须能在现有 admin Persona/knowledge 配置 → practice 会话创建 → runtime retrieval → knowledge-check/report/replay 业务链路上，基于知识库和 Persona 配置，对价格、竞品、证据等真实销售问题进行持续追问，而不是给出泛泛回答。
- Class: integration
- Status: validated
- Description: AI 客户必须能在现有 admin Persona/knowledge 配置 → practice 会话创建 → runtime retrieval → knowledge-check/report/replay 业务链路上，基于知识库和 Persona 配置，对价格、竞品、证据等真实销售问题进行持续追问，而不是给出泛泛回答。
- Why it matters: 用户要训练的重点之一就是在真实追问下不乱，缺少知识和角色真实性会让训练回到娱乐模式。
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: M003/S02, M003/S03, M003/S04, M003/S05, M003/S06
- Validation: Validated by M003/S06 completion. Combined evidence: S05 already proved the live admin Persona/knowledge -> practice -> knowledge-check -> canonical report same-session chain on current routes, and S06 added fresh focused regressions plus a fresh localhost same-session proof that preserved the immediate sales `status="scoring"` lifecycle-end contract, promoted the persisted session to `completed` during background finalization even when optional enhanced-report generation failed, and then loaded `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, `GET /api/v1/sessions/{id}/highlights`, `/practice/{sessionId}/report`, and `/practice/{sessionId}/replay` truthfully on that same session while truly unfinished sessions still returned `[SESSION_NOT_COMPLETED]`.
- Notes: S06 retired the remaining acceptance blocker recorded in S05: same-session replay/highlights are no longer trapped behind persisted `status="scoring"` once canonical evidence is readable. Optional enhanced-report failures remain secondary/localized and no longer block canonical replay availability.

### R011 — 训练会话的逐轮内容、阶段、评分、高光与关键问题需要沉淀为可检索、可回放、可解释的数据资产，支撑后续复盘与学习。
- Class: continuity
- Status: validated
- Description: 训练会话的逐轮内容、阶段、评分、高光与关键问题需要沉淀为可检索、可回放、可解释的数据资产，支撑后续复盘与学习。
- Why it matters: 训练价值来自“做完后知道为什么好/差、下次怎么改”，没有复盘证据链，系统很难形成长期学习闭环。
- Source: user
- Primary owning slice: M004/S01
- Supporting slices: M001/S02, M001/S06, M001/S07, M001/S08, M004/S02
- Validation: Validated by M004. Evidence chain: S01 delivered explanation-rich `learning_evidence` + shared issue/goal vocabulary across replay/highlight/report/history; S02 delivered canonical `replay_anchor` deep links with resolved/degraded/missing diagnostics; S03 delivered canonical `retry_entry.focus_intent` carried into new session `voice_policy_snapshot` and surfaced via `runtime_descriptor.focus_intent`; S04 delivered PPT page-level `presentation_review.page_summaries[*].issue_clusters` and replay/report evidence on existing routes; S05 completed live sales and PPT learner-loop proof with degraded states still understandable, backed by `.artifacts/m004-s05-t02/` and `.artifacts/m004-s05-t03/` and milestone validation in `.gsd/milestones/M004/M004-VALIDATION.md`.
- Notes: M001 established the unified session-evidence baseline across report/replay/history/trends, supervisor summaries, PPT review, and runtime diagnostics. M004 completed the learner-loop upgrade on top of that baseline: current sales and PPT report/replay/history/practice entrypoints now expose explanation-rich evidence, report→replay anchors, targeted retry focus carry-forward, and readable degraded states without introducing a second learning page or evaluator.

### R012 — 知识库、PPT、Persona、报告视角和管理使用方式都需要按长期运营来设计，而不是一次配置后固定不变。
- Class: operability
- Status: validated
- Description: 知识库、PPT、Persona、报告视角和管理使用方式都需要按长期运营来设计，而不是一次配置后固定不变。
- Why it matters: 该项目目标是“真正切实可用、可闭环”的训练系统；缺少治理和运营视角，系统会很快过时。
- Source: research
- Primary owning slice: M005 (provisional)
- Supporting slices: none
- Validation: Validated by M005 close-out: S01 aligned current admin analytics/user drill-in to the projection-backed evidence line; S02 added persistent supervisor focus/reminder/result workflow; S03 added runtime-backed asset governance and linked-asset anomaly context on current pages; S04 added the fixed 7-day operating pack with context-preserving drill-ins; S05 proved the integrated shipped admin workflow. Milestone validation verdict: pass. Fresh close-out verification reran backend admin governance suites (49/49) and web admin governance suites (19/19).
- Notes: M001 只做首发必要治理，M005 再补系统内管理动作、扩展集成和规模化能力。

### R013 — 现有仓库已经存在销售与 PPT 双训练模式入口、训练页、会话创建与基础生命周期骨架。
- Class: primary-user-loop
- Status: validated
- Description: 现有仓库已经存在销售与 PPT 双训练模式入口、训练页、会话创建与基础生命周期骨架。
- Why it matters: 这说明项目不是从零开始规划，而是在既有平台上做能力收敛与闭环增强。
- Source: execution
- Primary owning slice: baseline
- Supporting slices: none
- Validation: validated
- Notes: 证据来自 `web/src/app/(user)/practice/[sessionId]/page.tsx`、`backend/src/common/api/practice.py`、`backend/src/main.py` 等现有实现检查。

### R014 — 现有仓库已存在知识库模型、服务、管理页面和相关 API，可作为管理员维护训练材料的起点。
- Class: admin/support
- Status: validated
- Description: 现有仓库已存在知识库模型、服务、管理页面和相关 API，可作为管理员维护训练材料的起点。
- Why it matters: 这减少了从零构建后台治理的成本，使 M001 可以聚焦“更新后生效链路”。
- Source: execution
- Primary owning slice: baseline
- Supporting slices: none
- Validation: validated
- Notes: 证据来自 `backend/src/common/knowledge/*` 与 `web/src/app/admin/knowledge/*` 的现有代码。

### R015 — 现有仓库已经存在报告页、回放 API、实时评分 / 销售阶段 / 模糊词消息协议与前端接收逻辑。
- Class: continuity
- Status: validated
- Description: 现有仓库已经存在报告页、回放 API、实时评分 / 销售阶段 / 模糊词消息协议与前端接收逻辑。
- Why it matters: 项目已有“反馈与复盘”的轮廓，后续工作重点应放在可信度、一致性和可用性，而不是重新发明整套接口。
- Source: execution
- Primary owning slice: baseline
- Supporting slices: none
- Validation: validated
- Notes: 证据来自 `web/src/hooks/websocket/message-handlers.ts`、`backend/src/common/conversation/replay.py`、`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 等现有实现。

## Deferred

### R016 — 在 PPT 对练过程中实时识别讲偏、讲错、讲太多并当场打断纠偏。
- Class: differentiator
- Status: deferred
- Description: 在 PPT 对练过程中实时识别讲偏、讲错、讲太多并当场打断纠偏。
- Why it matters: 这是高价值教练能力，但不应挤占 M001 对桌面端主链路稳定和会后复盘可信度的优先级。
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: 用户明确接受“第一版先会后统一总结”，前提是实时纠偏在技术和体验上都成立时再引入。

### R017 — 主管在系统里给人指定训练重点、派发任务、追踪完成情况并执行管理动作。
- Class: admin/support
- Status: deferred
- Description: 主管在系统里给人指定训练重点、派发任务、追踪完成情况并执行管理动作。
- Why it matters: 这有助于组织化运营，但第一版用户明确接受“先看报告，线下辅导”。
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: 第一版先提供趋势与报告判断依据，不做系统内管理闭环动作。

### R018 — 首发即覆盖移动端与企业微信工作台内使用体验。
- Class: launchability
- Status: deferred
- Description: 首发即覆盖移动端与企业微信工作台内使用体验。
- Why it matters: 长期会重要，但用户明确要求先把桌面端稳定性做满，不把移动端首发绑进 M001。
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: 桌面端验证通过后再评估移动端和企业微信环境的专项工作。

### R019 — 与外部登录、CRM、外部文档系统或企业内部账号体系打通。
- Class: integration
- Status: deferred
- Description: 与外部登录、CRM、外部文档系统或企业内部账号体系打通。
- Why it matters: 可能是后续规模化需求，但第一版用户明确要求先独立可用，不新增外部集成依赖。
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: 当前优先先完成独立训练系统的闭环证明。

## Out of Scope

### R020 — 不以“好玩”“看起来有 AI 感”为目标继续扩展娱乐化交互，而忽略主链路稳定、知识真实性、报告可信度和管理可用性。
- Class: anti-feature
- Status: out-of-scope
- Description: 不以“好玩”“看起来有 AI 感”为目标继续扩展娱乐化交互，而忽略主链路稳定、知识真实性、报告可信度和管理可用性。
- Why it matters: 这条约束防止路线图回到错误方向，保证所有取舍都围绕真实训练价值展开。
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: 用户已明确指出当前系统偏娱乐，升级目标是“真正切实可用、可闭环、较少 bug”。

### R021 — 不用新增更多页面、控制台和表层功能去掩盖主训练闭环未成型的问题。
- Class: anti-feature
- Status: out-of-scope
- Description: 不用新增更多页面、控制台和表层功能去掩盖主训练闭环未成型的问题。
- Why it matters: 既有业务分析文档已明确指出，不应把“更多页面”当作增长或效果改进。
- Source: research
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: 这条约束用于限制 roadmap 膨胀，优先建设高杠杆闭环能力。

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | primary-user-loop | validated | M001/S01 | M001/S08 | validated |
| R002 | failure-visibility | validated | M001/S01 | M001/S08 | validated |
| R003 | core-capability | validated | M001/S05 | M001/S04, M001/S07 | Validated by S05 slice verification: backend sales baseline/persona/compiler/contract/integration suites passed, web ScorePanel + websocket handler + report focused tests passed, live StepFun sales runtime showed value/price/competitor/evidence prompts driving sales-specific score_update dimensions and knowledge-check queries, and the canonical /practice/{sessionId}/report surfaced sales-specific main_issue, next_goal, pass_flags labels, and value/evidence/objection rollups from the unified evidence contract. |
| R004 | admin/support | validated | M001/S04 | M001/S07 | Validated by S04 slice verification: backend knowledge/presentation integration suites passed, web admin knowledge/admin presentation/agent entry focused tests passed, live runtime/browser checks showed admin knowledge search diagnostics + knowledge-check snapshot fields, and standard PPT replacement exposed stable presentation_id + version/status with explicit 409 active-session blocking while user entry displayed the current deck version/status. |
| R005 | launchability | validated | M001/S03 | M001/S02, M001/S08 | Validated by S03 slice verification: backend contract/admin integration tests passed, web focused report/admin tests passed, and live runtime report UAT (after alembic head) proved the first screen leads with result, main issue, next goal, and unified evidence without placeholder/export affordances. |
| R006 | admin/support | validated | M001/S03 | M001/S05, M001/S07 | Validated by S03 slice verification: admin sessions integration contract passed, admin detail + manager-lite focused tests passed, and live runtime admin APIs exposed projection-backed supervisor preview fields and canonical /practice/{sessionId}/report drill-in targets for the same completed sessions. |
| R007 | operability | validated | M001/S06 | M001/S03 | Validated by S06 slice verification: backend HistoryService/admin-user projection suites passed, focused /progress and /stats integration assertions stayed aligned with projection-backed /sessions previews, web admin user-detail tests passed, Alembic was upgraded to head, and live browser review on /admin/users/{id} proved the supervisor-readable continuous-change panel answers whether the learner is improving, what keeps repeating, whether focus should change, and how inline empty/error states behave when progress data is unavailable. |
| R008 | primary-user-loop | validated | M001/S07 | M001/S04 | Validated by S07 slice verification: backend presentation unit/degraded-path/contract/integration suites passed, live report API checks proved both complete and degraded presentation sessions keep `scenario_type="presentation"` plus canonical `presentation_review` without falling back to sales `main_issue`/`next_goal`, a fresh local audio-driven page-turn session (`8531c7f6-50da-4934-9fd4-63784c791edf`) completed through the real StepFun presentation websocket and produced page-aware summaries/coverage on `/api/v1/practice/sessions/{id}/report`, and the shared `/practice/{sessionId}/report` page rendered the PPT branch with sales-only sections absent while retry continuity preserved `presentation_id`. |
| R009 | differentiator | active | M007/S01 | M007/S02, M007/S03, M007/S04 | mapped |
| R010 | integration | validated | M003/S01 | M003/S02, M003/S03, M003/S04, M003/S05, M003/S06 | Validated by M003/S06 completion. Combined evidence: S05 already proved the live admin Persona/knowledge -> practice -> knowledge-check -> canonical report same-session chain on current routes, and S06 added fresh focused regressions plus a fresh localhost same-session proof that preserved the immediate sales `status="scoring"` lifecycle-end contract, promoted the persisted session to `completed` during background finalization even when optional enhanced-report generation failed, and then loaded `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, `GET /api/v1/sessions/{id}/highlights`, `/practice/{sessionId}/report`, and `/practice/{sessionId}/replay` truthfully on that same session while truly unfinished sessions still returned `[SESSION_NOT_COMPLETED]`. |
| R011 | continuity | validated | M004/S01 | M001/S02, M001/S06, M001/S07, M001/S08, M004/S02 | Validated by M004. Evidence chain: S01 delivered explanation-rich `learning_evidence` + shared issue/goal vocabulary across replay/highlight/report/history; S02 delivered canonical `replay_anchor` deep links with resolved/degraded/missing diagnostics; S03 delivered canonical `retry_entry.focus_intent` carried into new session `voice_policy_snapshot` and surfaced via `runtime_descriptor.focus_intent`; S04 delivered PPT page-level `presentation_review.page_summaries[*].issue_clusters` and replay/report evidence on existing routes; S05 completed live sales and PPT learner-loop proof with degraded states still understandable, backed by `.artifacts/m004-s05-t02/` and `.artifacts/m004-s05-t03/` and milestone validation in `.gsd/milestones/M004/M004-VALIDATION.md`. |
| R012 | operability | validated | M005 (provisional) | none | Validated by M005 close-out: S01 aligned current admin analytics/user drill-in to the projection-backed evidence line; S02 added persistent supervisor focus/reminder/result workflow; S03 added runtime-backed asset governance and linked-asset anomaly context on current pages; S04 added the fixed 7-day operating pack with context-preserving drill-ins; S05 proved the integrated shipped admin workflow. Milestone validation verdict: pass. Fresh close-out verification reran backend admin governance suites (49/49) and web admin governance suites (19/19). |
| R013 | primary-user-loop | validated | baseline | none | validated |
| R014 | admin/support | validated | baseline | none | validated |
| R015 | continuity | validated | baseline | none | validated |
| R016 | differentiator | deferred | none | none | unmapped |
| R017 | admin/support | deferred | none | none | unmapped |
| R018 | launchability | deferred | none | none | unmapped |
| R019 | integration | deferred | none | none | unmapped |
| R020 | anti-feature | out-of-scope | none | none | n/a |
| R021 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 1
- Mapped to slices: 1
- Validated: 14 (R001, R002, R003, R004, R005, R006, R007, R008, R010, R011, R012, R013, R014, R015)
- Unmapped active requirements: 0
