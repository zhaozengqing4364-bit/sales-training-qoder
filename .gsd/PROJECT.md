# Project

## What This Is

这是一个企业内部 AI 销售训练平台，围绕真实销售与 PPT 演练闭环建设：管理员配置 Agent / Persona / 知识库 / PPT，学员发起训练，会话经过实时语音与评分链路，训练结束后在统一 report / replay / history 路由上复盘，并让主管据此进行线下辅导。

它不是一个“看起来有 AI 感”的演示站。当前工作的主方向是把已有能力收口成稳定、可信、可审计、可持续运营的产品能力。

## Core Value

把“训练 → 反馈 → 复盘 → 再训练”做成真实可用闭环：
- 训练过程稳定，不因生命周期、重连、路由或前端异常轻易断链。
- 训练事实可审计，报告结论能回到 transcript / retrieval / audio evidence。
- 管理员能维护长期运营资产，主管能用统一报告和趋势视角带人。
- learner/admin 前端表层行为统一、可信，不再依赖 demo 风格的弹窗、硬跳转或硬编码文案。

## Current Product State

### Shipped baseline
- 已有 sales / presentation 双训练模式。
- 已有 learner/admin 前端骨架与统一 practice / report / replay / history 路由族。
- 已有 FastAPI API、WebSocket runtime、PracticeSession 生命周期、报告与回放读侧。
- 已有 Agent、Persona、知识库、PPT、voice runtime policy 与对应 admin 页面。

### Validated milestone baseline
- **M001-M010**：首发训练闭环、知识与角色真实性、report/replay/history learner loop、主管趋势、retrieval truth、audio audit、conclusion evidence / degradation taxonomy 已验证。
- **M011-M018**：KnowledgeAnswerEngine control plane、learner launchability、frontend hygiene、auth/API/admin security contract、realtime/concurrency proof、performance / dependency / recovery baselines 已完成。
- **M019-M021**：authority seams、security/multi-instance runtime/recovery hardening、AI control plane / prompt / evaluation kernel 统一已完成 assembled close-out。
- **M022/S01-S02**：方法论/rubric contract 与 persona/scenario/industry-pack composed-asset contract 均已完成 slice close-out。

### M022 current state
- **S01 complete**：methodology-aware sales rubric contract 已落到 realtime、report、replay、history、admin shared seam。
- **S02 complete**：industry-pack / customer-pressure composed-asset contract 已落到现有 admin entrypoints、frozen `voice_policy_snapshot_ref.runtime_binding`、session detail/report/replay 与文档 operating rules。
- **S03 pending**：下一步应收口 manager calibration 与 admin truth surfaces，并直接复用 S01/S02 已固定的 canonical evidence / runtime-binding seams。
- **S04 pending**：organization / team / tenant target-state plan 仍待基于 S01-S03 的稳定 authority seam 制定执行路线。

## Current Product Truths

- learner 权威 surfaces 仍是现有 `/practice/{sessionId}`、`/practice/{sessionId}/report`、`/practice/{sessionId}/replay`、`/history`。
- admin 权威 surfaces 仍是现有 `/admin/*` 页面族，不应平行再造第二工作台。
- 会话事实权威线已经建立：生命周期、retrieval truth、audio audit、conclusion evidence、degradation taxonomy、methodology rubric、industry-pack runtime binding 都应复用现有 shared seam，而不是页面本地再推导。
- audited API error-contract 权威线明确：route-local 4xx 用 `JSONResponse(error_response(...))`，dependency/auth/RBAC 失败继续走结构化 `detail={error,message}`，前端统一经 `ApiRequestError` 读取。
- lifecycle / websocket / auth / support-runtime / canonical evaluation / methodology / industry-pack seams 都已在 M019-M022/S02 收口，不应重开第二套入口或本地推导逻辑。
- **industry pack 当前不是独立平台**：它仍是 composed asset，运行时 authority 来自现有 agent/persona/knowledge/scenario surfaces 与冻结的 `voice_policy_snapshot_ref.runtime_binding`，不是新表/新控制面。

## Current Focus

当前项目处于 **M022 进行中**：
1. **推进 M022/S03-S04**：在已固定的 methodology contract 与 industry-pack contract 之上，完成 manager/admin truth surface 收口与 organization/team/tenant target-state plan。
2. **保持已完成 seams 稳定**：S03 必须直接复用 `canonical_evaluation_kernel.methodology`、`compatibility_readers.sales_methodology_rubric_v1`、`voice_policy_snapshot_ref.runtime_binding`、canonical report/replay/detail surfaces，而不是重新发明 manager-only taxonomy 或第二条 evidence line。
3. **继续沿现有 admin entrypoints 运营内容资产**：customer pressure、knowledge bundle、scenario narrative 仍通过 agent/persona/knowledge/scenario 现有 surface 管理，避免 scope 回到新平台建设。

## M022 precise resume notes

- **S02 delivered seams**
  - `backend/src/agent/services/industry_pack_contract.py`
  - `backend/src/common/db/voice_policy_snapshot.py`
  - `backend/src/common/conversation/schemas.py`
  - `web/src/app/admin/personas/[id]/page.tsx`
  - `web/src/app/admin/agents/[id]/page.tsx`
  - `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- **S02 close-out remediation that is now landed**
  - `backend/src/common/knowledge/service.py`: embedding-failure fallback now drops from non-positive BM25 scores to a direct lexical scan on tiny collections instead of returning false `[KNOWLEDGE_SEARCH_UNAVAILABLE]` misses.
  - `backend/src/common/services/practice_report_service.py`: audio-segment failure path refreshes the session after commit so the updated snapshot remains visible on the shared ORM identity line.
  - `backend/tests/unit/test_audio_segment_api.py`: local ASGI fixture now overrides all live imported `get_db` callables, matching the broader test-harness pattern after app/auth reload tests.
  - `.gsd/KNOWLEDGE.md`: captured the BM25 fallback gotcha and the live-imported `get_db` override gotcha for future auto-mode runs.
- **Fresh S02 close-out proof**
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q`
  - `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"`
  - `npm --prefix web test -- --run "src/app/admin/agents/[id]/page.test.tsx"`
  - `rg -n "persona_policy|customer_pressure|scenario|knowledge_base|agent|industry" backend/src/agent backend/src/sales_bot backend/src/common/knowledge`
  - `rg -n "industry pack|customer pressure|scenario package|knowledge bundle" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- **Next session should start from S03 planning/execution**, not from additional S02 cleanup. Reuse `voice_policy_snapshot_ref.runtime_binding` and the existing admin detail/read surfaces as the manager/admin truth seam.

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
- [x] M021 — AI control plane / prompt / evaluation kernel 统一
- [ ] M022 — Sales productization / manager truth / organization-ready roadmap（S01-S02 complete；S03-S04 pending）
