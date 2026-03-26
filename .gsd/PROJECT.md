# Project

## What This Is

这是一个企业内部 AI 智能演练平台，当前已经具备销售对练、PPT 对练、Agent / Persona / 知识库管理、实时语音交互、报告与回放等基础骨架。现阶段的核心工作不是继续堆新功能，而是把“偏演示、偏娱乐化”的销售训练能力收敛成一个真正可持续使用的训练系统：训练材料来自真实知识库，训练过程尽量稳定，训练后报告可信，主管可以据此做线下辅导，用户能在“训练 → 反馈 → 复盘 → 再训练”中持续改进。

## Core Value

把真实销售训练做成稳定、可信、可持续复用的能力闭环：让销售围绕公司真实产品和标准 PPT 练出“会讲价值、会处理异议、会顺畅多轮沟通”的能力，而不是只完成一场好看的 AI 对话演示。

## Current State

- 已有双场景产品骨架：销售对练（sales）与 PPT 对练（presentation）。
- 已有前后端主链路：Next.js 用户侧与管理侧、FastAPI API、WebSocket 实时交互、PracticeSession 会话模型、报告与回放入口。
- 已有训练资产治理骨架：Agent、Persona、知识库、提示词、语音 runtime policy、管理端列表与编辑页面。
- 已有部分能力模块：模糊词检测、销售阶段识别、实时评分、回放 API、会话状态服务、知识库服务。
- M001/S01 已完成：销售训练终态现在统一走单一后端 lifecycle 写入口；StepFun runtime 已接回最小可恢复快照与 `reconnected` 协议；训练页只信服务端 lifecycle 事件，并在结束失败时留在训练页暴露 `重试结束` 与 trace 诊断。
- M001/S02 已完成：逐轮 evidence 与会话级 evaluability / result metadata 已稳定落库，report / replay / history / trends 改为共享 `SessionEvidenceService` 投影，Web 页面也停止本地拼接冲突分数来源。
- M001/S03 已完成：单次报告首屏现在由 unified evidence 直接给出结论 / 主问题 / 下一轮唯一目标 / 关键证据，主管侧 completed session 预览与 manager-lite drill-in 也统一指向同一 `/practice/{sessionId}/report` 权威页面。
- M001/S04 已完成：管理员现在可以在知识库详情页自助上传 `xlsx/xls`、重试 failed/pending 文档并运行搜索诊断；新 sales session 会冻结当时的 `knowledge_base_ids` 到 `voice_policy_snapshot`，`/practice/sessions/{id}/knowledge-check` 与 report 能暴露 hit / miss / kb_not_ready / search_failed 证据；标准 PPT 则在 live `/api/v1/presentations` 上支持 stable `presentation_id` 原位替换、`version_number` / `status` 可视化、active-session blocker，以及用户入口对当前版本/状态的展示。
- M001/S05 已完成：sales StepFun 写入层、persona policy 编译链与 web 消费面现在统一切到“价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步”语义；live `score_update`、`ScorePanel`、`/practice/{sessionId}/knowledge-check` 与 canonical `/practice/{sessionId}/report` 会围绕 ROI、价格、竞品、证据追问输出销售主问题、下一轮目标和三类 rollup，而不再沿用旧 generic 沟通标签伪装成销售判断。
- M001/S06 已完成：`HistoryService` 现在提供 projection-backed supervisor progress snapshot，admin `/progress` 与 `/stats` 的 score-bearing 字段已与 `/sessions` completed preview / canonical report 对齐；`/admin/users/[id]` 会直接给出“最近有没有进步 / 总卡在哪 / 是否该换重点”的连续变化摘要，并在 progress 无可评估数据或加载失败时保留本地 inline empty/error state。
- M001/S07 已完成：presentation session 的 shared `/practice/{sessionId}/report` 现在按 `scenario_type="presentation"` 输出 canonical `presentation_review`，legacy 与 StepFun runtime 都有页码落库基线，旧缺页码 session 会返回显式 degraded PPT contract 而不是退回 sales 语义；shared report page 也会切到 PPT 复盘分支、跳过 knowledge-check/sales-only cards，并保留带 `presentation_id` 的再练入口。
- M001/S08 已完成：`/support/runtime` 现在基于 persisted session evidence、shared runtime diagnostics 与 canonical report semantics 输出 typed blocking / warning 发布健康，不再把 `status="scoring"` 伪装成 completed；repo-root verification gate 也补齐了 `alembic.ini` / `pyproject.toml` / `tests -> backend/tests` shim 与 backend `.env` fallback，最终 slice-close proof 能同时覆盖 repo-root auto verification、canonical sales report、主管连续变化页、PPT happy/degraded report，以及 support runtime anomaly surfacing。
- 本地运行时若要验证 supervisor preview，数据库必须先迁移到 Alembic head（至少包含 `20260317_2310_020`）；否则 admin session preview 读取会因缺少 `conversation_messages.transcript_metadata` 而假性失败。
- M001 已在里程碑级 close-out 中完成并封板：`git diff --stat "$(git merge-base HEAD 001-ai-practice-system)" HEAD -- ':!.gsd/'` 证明本里程碑包含真实实现代码，`M001-VALIDATION.md` 与 8 个 slice summaries 共同证明 6 条成功标准和跨 slice 集成全部通过；下一阶段重心转向 M002 的训练中实时教练与过程内反馈，而不是继续补 M001 的首发闭环。
- M002/S01 已完成：sales 训练页现在在 StepFun 与 classic voice mode 上共用同一套五维销售 rubric；classic action-card pass flags 改走 shared sales effectiveness helper，前端 `score_update` 不再只按 `overall_score + turn_count` 去重，同轮 stage / suggestion / dimension refresh 会更新到 ScorePanel，两个语音模式入口也明确描述同一套销售评分语义，而报告侧继续保持既有三 rollup contract。
- M002/S02 已完成：classic 与 StepFun runtime 现在共用一个 realtime-feedback arbiter 来做单轮唯一动作卡、同轮重复 suppression 与 reconnect-safe pacing；practice 页在新 final transcript 到来时会清掉上一轮 `actionCard` / `fuzzyDetections`，右侧面板把 `action_card` 收口成唯一主文本建议，同时保留 stage/score 作为上下文，不再让多条提示并排打架。
- M002/S03 已完成：`common.effectiveness.resolve_sales_coaching_focus(...)` 现在把销售阶段、最弱/下滑维度和既有 pass flags 收口成一套共享的下一轮教练规则；classic `CapabilityProcessor` 与 StepFun `_run_realtime_feedback(...)` 都会把 rich stage/score context 送进同一个 arbiter，因此 discovery / objection / closing 场景下的 `action_card` 会按上下文同步变化，而公开 `score_update` / `_latest_score_snapshot` 形状保持不变。
- M002/S04 已完成：completed sales session 的 `SessionEvidenceService` 现在会倒序挑选“最后一条仍可对齐”的 persisted sales stage + dimension evidence，projection-side override stale `main_issue` / `next_goal`，并把同一份 sales-first 结论稳定透传到 `/practice/{sessionId}/report`、`/practice/{sessionId}/replay`、admin/history 读侧；replay 页新增“本场教练结论”区块，admin 词汇映射也覆盖 `evidence_gap` / `evidence_backing` 等新对齐 vocabulary，而 projection log 会显式暴露 `sales_alignment_used/stage_key/focus_type/fallback_reason` 供后续 S05/S06 排查。
- M002 里程碑 close-out 审计（2026-03-25）未通过：当前仓库只存在 S01-S04 slice summaries，计划中的 S07/S08（教练降级/恢复可观测性、最终 live UAT）仍缺 summary/UAT 证据，因此“coach degraded / resumed 可见”与“同一 session 从 realtime coaching 到最终 report/replay 的 live 闭环证明”尚未退休；R009 继续保持 active，M002 不能宣称完成。
- M003 规划已按 2026-03-25 hard steer 收口到当前真实业务链路：只接受 `web/src/app/admin/personas/[id]/page.tsx`、`web/src/app/admin/knowledge/[id]/page.tsx`、`backend/src/common/api/practice.py`、`backend/src/agent/services/persona_policy.py`、`backend/src/sales_bot/services/voice_runtime_policy.py`、`backend/src/sales_bot/services/voice_instruction_compiler.py`、当前 practice / knowledge-check / report / replay surfaces 作为里程碑入口和验收面；Silence / Conda / `.env` / lockfile 等环境工件不再单独升格为 M003 scope，除非未来明确改成环境迁移目标。
- M003/S01 已完成：当前 admin Persona / knowledge → `POST /api/v1/practice/sessions` → learner practice / knowledge-check / report / replay 真实入口链、七个 learner/admin 可见 knowledge statuses，以及 focused backend / focused web / later live UAT proof boundary 已锁定到现有代码与可运行校验；Next.js 字面路径需要继续用带引号或转义的 shell verifier，replay proof 也必须继续绑在 `backend/src/common/conversation/api.py` + `backend/src/common/conversation/replay.py`，而不是误回到 `practice.py`。
- M003/S02 已完成：Persona policy 现在把压测行为规范化为 canonical nested `customer_pressure` 模型，现有 admin Persona 列表/详情页可审计并编辑这套结构，`POST /api/v1/practice/sessions` 会把它冻结进 `PracticeSession.voice_policy_snapshot.customer_pressure` 与 `source.customer_pressure_source`，而既有 snapshot baseline 在后续 detail/report/replay 读取和 runtime_metrics 追加后仍保持稳定；下一步 S03 直接在这条 frozen contract 上做多轮异议 ledger，而不是再从指令文案反推 Persona。
- M003/S03 已完成：sales realtime 现在会把 unresolved objection ledger（`objection_family` / `promised_proof` / `next_expected_evidence` / `closure_state`）沿现有 runtime/evidence 链落到 `ConversationMessage.transcript_metadata["objection_ledger"]` 与 StepFun reconnect snapshot；classic + StepFun feedback 在 topic drift 后仍会围绕同一条 open ledger 继续施压，reconnect 不再回放 stale `action_card`，而 completed-session `SessionEvidenceService` projection 会优先把 latest open ledger 翻成 report/replay 的 `main_issue` / `next_goal`。训练页右侧也把 `action_card` 收口成唯一主文本教练面，并把 `scores.suggestions[0]` 显示成“当前仍卡住的证明”，让 lingering proof gap 在 reconnect 后仍可见。
- M003/S04 已完成：sales evaluator、`SessionEvidenceService`、StepFun runtime diagnostics 与 learner report/replay 现在共享 canonical `effectiveness_snapshot.claim_truth` 合同；同一场会话可以在 realtime `/knowledge-check` 与 completed-session `/report` / `/replay` 上一致地区分 `unsupported_claim`、`weak_evidence`、`evidence_pending`、`evidence_verified`，同时保持 kb-lock `blocked_*` / chain-failure 状态留在 diagnostics 层，不冒充 claim truth。
- M003/S05 已完成：现有 admin Persona / knowledge → `/practice/{sessionId}` → `/practice/{sessionId}/knowledge-check` → canonical `/practice/{sessionId}/report` 的 objection-heavy live same-session proof 已落地，真实运行里可以看到 frozen `customer_pressure_source: explicit`、实时异议处理动作卡/评分、`knowledge-check.status=hit` 与 report 上的 `weak_evidence` 证据线；同时也确认当前 acceptance blocker 仍在——同一 session 可能停在 `status="scoring"`，导致 `/sessions/{id}/replay` 与 `/sessions/{id}/highlights` 因 `[SESSION_NOT_COMPLETED]` 被 completed gate 挡住，所以 M003 还不能宣称 milestone close-out。
- M003 里程碑 close-out 审计（2026-03-25）未通过：当前 branch 确实包含真实非 `.gsd` 代码改动，且 M003 的 focused backend/web verification 对已交付的 S01-S05 surfaces 通过；但 `.gsd/milestones/M003/slices/S06/` 仍缺 `S06-PLAN.md`、`S06-SUMMARY.md`、`S06-UAT.md`，accepted same-session replay/highlights proof 继续被 `status="scoring"`、`report_generation_failed [NO_STAGE_RESULTS]`、`no_scoring_context_available` 与 `[SESSION_NOT_COMPLETED]` 卡住，另外 roadmap 写死的“仅限业务代码目录”边界也被 `backend/src/common/effectiveness/*` 与 `web/src/lib/api/*` 这类共享 contract seam 超出；R010 继续保持 active，M003 不能封板。
- M004/S01 已完成：现有 replay/highlight authority line 现在会沿 `SessionEvidenceService` → `backend/src/common/conversation/replay.py` → `/api/v1/sessions/{id}/replay|highlights` 暴露 explanation-rich `learning_evidence`（reason、stage、context、suggested_response、issue/goal linkage），同时保留 `stage_name` / `context` / `suggested_response` 等 flat compatibility 字段；web replay/highlight/report/history 入口已共享同一 learning vocabulary，并在无 highlights 或 enhanced data 降级时继续保留明确、可读的当前入口态，而不是回退成另一套 generic 学习文案。
- M004/S02 已完成：当前 `/practice/{sessionId}/report` 会把 `main_issue`、`next_goal` 与高光 evidence 直接深链到现有 `/practice/{sessionId}/replay` 路由；backend replay authority line 会给 issue/goal 挂接 stable `replay_anchor` 元数据，report 继续复用当前 CTA 区而不新增页面，replay 则按 query params 自动定位到目标 turn，并在高光缺失或 marker 漂移时保留明确的 degraded / missing anchor banner 供用户继续手动检索。
- M004/S03 已完成：sales report 与 replay 入口现在都会复用 canonical `retry_entry.focus_intent` 直接发起定向再练，新的 create-session 会把该 focus intent 冻结进 `voice_policy_snapshot.focus_intent`，并经由 `runtime_descriptor.focus_intent` 在 `/practice/{sessionId}` 首屏展示“本次练习聚焦上次复盘问题”的主问题/下一轮目标卡片，形成当前 report → replay → retry 的学习闭环骨架而不新增第二套 retry flow。
- M004/S04 已完成：shared presentation report/replay authority line 现在会把 PPT 页级问题簇挂在 `presentation_review.page_summaries[*].issue_clusters` 上，并通过 diagnostics/completeness 暴露聚合计数；当前 `/practice/{sessionId}/report` 会显示页级问题总览与逐页 evidence 卡片，`/practice/{sessionId}/replay` 也能沿现有 replay route 展示 SlideViewer、page/page_anchor 状态 banner、逐页问题簇和 transcript jumps，让 learner 在当前 PPT 入口里直接看到“哪一页出了什么问题、为什么要重讲”。
- M004/S05 已完成：现有 learner `history/report/replay/retry` 路由家族已经拿到 sales + PPT 双场景终验。sales 侧保住了 canonical report 结论、replay 深链降级说明与 focus-intent retry；PPT 侧保住了 shared report/replay 的页级问题证据、保持同一 `presentation_id` 的 retry，以及 `missing_page_metadata` 时可理解的 degraded report/replay 文案。当前 shipped PPT contract 仍是“history 行暴露 replay、report 暴露 retry”，而不是 sales-style report 内直接跳 replay。
- M004 已在里程碑级 close-out 中完成并封板：`git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` 证明本里程碑包含真实非 `.gsd` 实现代码；`M004-VALIDATION.md` 与 S01-S05 summaries / UAT 共同证明 explanation-rich learning evidence、report→replay 深链、focus-intent 定向再练、PPT 页级纠偏与 sales + PPT live learner-loop 全部闭合；R011 已提升为 validated。下一阶段重心转向 M005 的治理与规模化运营，而不是继续补 M004 的学习闭环。
- M005/S01 已完成：`backend/src/common/analytics/admin_analytics_service.py`、`backend/src/admin/api/users.py`、`/admin/analytics`、`ManagerLitePanel` 与 `/admin/users/[id]` 现在都基于 HistoryService / SessionEvidenceService projection summary 说同一套 admin 语义：综合分只统计可评估的已完成训练，证据不足会话单独记账，问题家族 / 下一轮重点 / 查看统一报告 CTA 不再沿用 legacy 0.4/0.3/0.3 wording。
- M005/S02 已完成：`manager_interventions` 表和 `/api/v1/admin/interventions` 当前链路已经把主管重点、提醒状态与 resolving-session linkage 持久化下来；manager-lite 会 deep-link 到 `/admin/users/[id]` 并预填 focus query params，用户详情页可以直接创建/提醒主管重点，并通过 `HistoryService` + unified session evidence 在同一张卡片上看到“已改善 / 仍卡住 / 待判断”的结果与对应统一报告 drill-in。
- M005/S03 已完成：当前 `/admin/knowledge`、`/admin/personas`、`/admin/presentations`、`/admin/voice-runtime` 现在都会在原地显示 runtime-backed `governance_summary`（影响范围、最近变更、blocking/warning 健康信号），而 `/admin/analytics` 与 `/admin/users/[id]` 也会把 support/runtime fault 的 `linked_asset_changes` 直接渲染成资产链接与最近变更上下文，运营无需离开现有 admin 链路就能从异常追到可能的资产变更面。
- 真实首发目标已明确：先把桌面端稳定性做满，不在第一阶段绑定移动端 / 企业微信 / 外部系统集成。

## Architecture / Key Patterns

- 前端：Next.js 16 + React 19 + TypeScript，用户侧训练页位于 `web/src/app/(user)/practice/[sessionId]/`，管理侧位于 `web/src/app/admin/*`。
- 后端：FastAPI + SQLAlchemy Async + WebSocket，核心域包含 `common`、`sales_bot`、`presentation_coach`、`agent`、`evaluation`。
- 实时交互：销售与 PPT 场景分离，各自使用独立 WebSocket handler；桌面端训练页通过统一消息协议接收 `asr_transcript`、`fuzzy_detection`、`stage_update`、`score_update`、`action_card` 等事件。
- 数据闭环：`PracticeSession` 作为事实锚点，`ConversationMessage` 承载逐轮消息、评分快照、销售阶段、高光与回放数据；报告、回放、趋势判断应尽量引用同一事实源。
- 训练资产：知识库、PPT、Agent / Persona 配置是长期运营资产；M001 不把材料写死在 prompt，而是要求管理员更新知识库 / PPT 后能影响下一次训练。

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: 桌面端销售训练闭环可用化 — 把桌面端客户演练、PPT 会后复盘、知识生效、单次报告与连续变化做成可真实使用的训练闭环。
- [ ] M002: 实时教练闭环 — S01-S04 已交付 realtime sales rubric / pacing / shared coaching focus / completed-session alignment，但 close-out 审计仍缺 S07/S08 的教练降级/恢复可观测性与最终 live UAT 证据，暂不能封板。
- [ ] M003: 知识与角色真实性 — 沿现有 admin Persona / knowledge → practice runtime → knowledge-check / report / replay 业务链路，证明知识与 Persona 真的改变 objection-heavy 销售训练，而不是只停在 prompt 文案层。
- [x] M004: 复盘与学习闭环增强 — 已把现有 report / replay / history / practice 路由收口成 explanation-rich 的 sales + PPT learner loop，并在 milestone close-out 中完成验证与封板。
- [ ] M005: 后台治理与规模化运营 — S01-S03 已完成；当前 admin analytics / user drill-in / manager-lite / 用户详情页已经能沿统一 evidence line 完成“发现问题 → 设主管重点 → 记录提醒 → 查看后续结果”，知识库 / Persona / PPT / voice runtime 资产页也已在原地显示影响范围、最近变更与 blocking/warning 治理信号；后续继续补 cohort 问题面与组织化 UAT。
