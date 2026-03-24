# M001/S07 — Research

**Date:** 2026-03-23

## Summary

S07 owns **R008**: PPT 对练结束后，用户必须拿到一份围绕真实 PPT 价值点、可执行且可信的统一复盘。现有代码并不是“完全没有 PPT 复盘”，而是 **runtime 已有、增强报告已有、共享报告页没有真正接上**。`backend/src/presentation_coach/services/presentation_report_service.py` 已经能基于 `ConversationMessage + InterruptionEvent + Page + RequiredTalkingPoint` 生成 6 个 PPT 维度、逐页总结、优势/改进点和建议；`PresentationStepFunRealtimeHandler` 也会把 `transcript_metadata.page_number` 写进消息。但用户实际看到的 `/practice/{sessionId}/report` 仍然是销售语义：页面硬编码“价值表达 / 证据与收益 / 异议推进”，展示 sales `main_issue` / `next_goal` / `pass_flags`，还会无条件拉 sales-only 的 knowledge-check。

根因不是单个页面文案，而是 **S02 的 unified evidence line 目前仍只懂 sales evidence**。`backend/src/common/conversation/session_evidence.py` 只按 `sales_stage` 生成 `stage_summary`，`ensure_effectiveness_snapshot()` 只会产出 sales `pass_flags / overall_result / main_issue / next_goal`。presentation session 即使有 `presentation_id`，共享 `/practice/sessions/{id}/report` 也只会落到 generic/sales 快照；真正像 PPT 复盘的内容只存在于 `PresentationReportService` / `/evaluation/sessions/{id}/report`，而 report 页面又把它当 optional enhancement。S07 如果继续沿这条路走，只会让 PPT 复盘继续依赖第二条事实线，违背 S02 的“统一事实基线”。

## Recommendation

**把 S07 做成“scenario-aware unified report contract” slice，而不是做一个 presentation-only 新页面或只补 `/evaluation/.../report`。**

具体做法：
1. **复用现有 `PresentationReportService`** 的 deterministic PPT 评分/逐页总结能力，不要在前端或另一条 API 上重新发明 PPT scorer。
2. **先把 presentation evidence 收进 shared report baseline**：扩展 `SessionEvidenceService` / `GET /practice/sessions/{id}/report`，让它能返回 top-level `scenario_type`，并附带一个 presentation-specific review payload（例如 `presentation_review`），里面至少要有：6 维评分、逐页总结、要点覆盖/缺失、forbidden/missing/vague 统计、建议。这样 `/practice/{id}/report` 继续是唯一权威读入口。
3. **web report page 再按 `scenario_type` 分支渲染**：presentation 时展示 PPT 复盘，不再显示 sales-only cards/knowledge-check；sales 保持现状。
4. **修补 legacy presentation websocket 的 page metadata persistence**。`PresentationStepFunRealtimeHandler` 已经写 `transcript_metadata.page_number`，但 `presentation_handler.py` 当前 `_update_message_analysis()` 调用没传 `transcript_metadata`，会导致 legacy 模式下无法稳定还原逐页复盘。

这条路最符合已加载技能约束：
- `test-driven-development`: 先写失败的 backend contract/web focused tests，再改实现。
- `verification-before-completion`: 最终必须跑 fresh backend + web focused suites；不能只凭页面结构或已有 optional enhancement 判断完成。
- `baseline-ui` / `fixing-accessibility`: web 侧应保持最小 scenario branch，继续使用现有 `GlassCard` / `Button` / 语义化文本，不新造交互系统。

## Implementation Landscape

### Key Files

- `backend/src/presentation_coach/services/presentation_report_service.py` — **现有 PPT 统一复盘 authority**。已经基于 `PracticeSession`、用户消息、`InterruptionEvent`、`Page`、`RequiredTalkingPoint` 生成：
  - 六维评分（流畅连贯性、准确性、专业性、生动性、互动问答、其他表现）
  - 逐页 `stage_summaries`
  - `key_strengths` / `key_improvements` / `recommendations`
  - `detailed_feedback`
  这里最适合抽成 shared builder / payload builder，避免 S07 再写第二套 PPT 打分逻辑。

- `backend/src/evaluation/services/comprehensive_report.py` — 已经在 `generate_report(..., scenario_type="presentation")` 时直接走 `PresentationReportService.build_report(session_id)`。说明 **PPT enhanced report 现成存在**；S07 需要做的是把它和 shared `/practice/sessions/{id}/report` 对齐，而不是再开第三条线。

- `backend/src/common/conversation/session_evidence.py` — 当前 unified evidence projection 仍是 **sales-first**：
  - `build_stage_summary()` 只按 `sales_stage` 聚合
  - `_build_evidence_completeness()` 只认 `sales_stage`
  - `ensure_effectiveness_snapshot()` / `evaluate_effectiveness_snapshot()` 只会产出 sales `pass_flags`、`overall_result`、`main_issue`、`next_goal`
  这里必须引入 presentation-aware branch，至少让 report baseline 能带出 PPT review payload，而不是强行复用 sales snapshot。

- `backend/src/common/api/practice.py` — shared `GET /practice/sessions/{session_id}/report`。当前只是把 `SessionEvidenceService.get_projection()` 映射成 `SessionReport`，没有 top-level `scenario_type`，也没有 presentation-specific payload；web report page 的 baseline 完全从这里来。S07 的 shared contract 扩展必须落在这里。

- `backend/src/common/db/schemas.py` — `SessionReport` 目前只有 generic score fields + sales-oriented snapshot fields；可安全扩展 top-level `scenario_type` 和 presentation review payload。

- `backend/src/common/conversation/schemas.py` — replay/data schemas 目前也偏 sales（`StageSummarySchema` 是 sales stage summary 语义），如果 S07 只收口 single-session report，可先不改 replay，但新 payload 设计要避免未来再次 rename。

- `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py` — StepFun presentation runtime 已在 `_handle_upstream_transcription_completed()` 里通过 `extras={"page_number": self.current_page}` 持久化 `transcript_metadata.page_number`。这是 page-based review 的正确写法。

- `backend/src/presentation_coach/websocket/presentation_handler.py` — legacy presentation runtime 当前 `_save_conversation_message()` + `_update_message_analysis()` 只写 `fuzzy_words/sales_stage/score_snapshot/ai_feedback`，**没有把 `transcript_metadata.page_number` 传进去**。如果不补，这个 slice 只会对 StepFun mode 可用。

- `backend/src/common/conversation/storage.py` — `update_analysis()` 已支持 `transcript_metadata` 参数，说明 legacy runtime 不需要改存储层，只要把 `page_number` 传进去。

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 当前页面硬编码销售语义：
  - `buildDimensionScores()` 只返回 3 张 sales card
  - 展示 `销售推进结果` / `下一轮销售目标` / `销售推进基线`
  - 无条件请求 `api.sessions.getKnowledgeCheck(sessionId)`
  - 把 `/evaluation/sessions/{id}/report` 当 optional enhancement，只消费 strengths/improvements/detailed feedback
  presentation variant 需要在这里做 scenario-aware rendering，并停止 presentation 场景下的 sales-only fetches/sections。

- `web/src/lib/api/types.ts` — `PracticeSessionReport extends SessionEvidenceContract`，而 `SessionEvidenceContract` 仍是 sales-shaped：
  - `pass_flags` 类型名是 `pass_3min_flow/pass_5turn_defense/pass_4step_structure`
  - `main_issue` / `next_goal` 的 label helper 只映射 sales issue/goal types
  这里需要扩展 `scenario_type` 和 presentation review type，而不是把 PPT 语义硬塞进 sales key names。

- `web/src/lib/session-evidence.ts` — 当前 stage/issue/goal label formatter 全是 sales label；如果 S07 让 `stage_summary.stage` 在 presentation 场景下变成 `page_1/page_2/...` 或新增 presentation issue types，这里要跟着扩。

- `web/src/components/practice/ScorePanel.tsx` — 当前 live panel 已支持 arbitrary `dimension_scores` + unknown-dimension fallback 排序。S07 不必优先改它，但如果后续想让 live PPT score 和 report 使用同一 6 维标签，这个组件无需重写。

- `backend/tests/unit/evaluation/test_comprehensive_report_service.py` — 已锁住 `generate_report(..., scenario_type="presentation")` 会走 `PresentationReportService`；如果抽 shared builder，这里要一起更新。

- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py` — 已锁住 page context/feedback event contract，是 StepFun presentation runtime 的现成 guardrail。

- `backend/tests/unit/test_presentation_handler_persistence.py` — 最合适补 legacy runtime page metadata persistence 的单测位置。

- `backend/tests/contract/test_practice_evidence_contract.py` — 当前只锁 sales report/replay parity；S07 若做 shared report contract 扩展，应该新增 presentation contract coverage（可扩此文件，或新建 `test_presentation_report_contract.py`）。

- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 目前只锁 sales report 视图和 enhancement degradation。S07 至少要补一组 presentation-focused assertions，并显式断言 sales-only affordances/sections 不出现。

### Build Order

1. **先把 presentation evidence authority 收稳**
   - 把 `PresentationReportService` 里的 metrics/summary builder 抽成可复用 helper，或直接给它增加一个返回 normalized review payload 的入口。
   - 同时修 `presentation_handler.py` 的 legacy message analysis 持久化，把 `transcript_metadata.page_number` 写进去。
   - 原因：没有稳定的 page/page-point evidence，后面的 unified report contract 只能猜。

2. **再扩 shared report contract，而不是先改页面**
   - 在 `SessionEvidenceService` / `practice.py` 上加 `scenario_type` + presentation review payload。
   - 建议让 payload 覆盖：`dimension_scores`、`page_summaries`、`required_point_coverage`、`forbidden_count/missing_count/vague_count`、`strengths/improvements/recommendations`。
   - 尽量不要把 presentation semantics 映射到 sales `pass_flags.pass_3min_flow` 这类名字上；presentation 目前没有需要兼容的同名 consumer，强塞只会让后续 drift 更难排。

3. **最后改 web report page 的 scenario-aware rendering**
   - 先等 `getReport()` 返回 `scenario_type` 后再决定渲染分支。
   - presentation 场景下：
     - 保留 overall score / retry CTA
     - 展示 6 维 PPT 评分与逐页总结
     - 展示 page coverage / required points / forbidden issues / suggestions
     - 隐藏 sales-only `overall_result/main_issue/next_goal/pass_flags/knowledge-check`
   - sales 场景继续走现有视图，避免 unrelated churn。

4. **如果保留 enhanced report，最后做逻辑对齐**
   - `/evaluation/sessions/{id}/report` 仍可提供 richer narrative，但它不应再是 presentation core facts 的唯一来源。
   - 最好让 enhanced report 也复用同一 presentation builder，避免 unified report 与 enhanced report 再次各算各的。

### Verification Approach

**Backend focused verification**

- `cd backend && pytest tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_presentation_handler_persistence.py`
- `cd backend && pytest tests/contract/test_practice_evidence_contract.py tests/integration/test_history_evidence_flow.py`

If the planner decides to create dedicated PPT report tests instead of extending mixed files, split them into:
- `tests/contract/test_presentation_report_contract.py`
- `tests/integration/test_presentation_report_flow.py`

and run those directly.

**Web focused verification**

- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`

**Runtime/UAT proof**

- Complete one presentation session with real page switches and transcript persistence.
- Open `/practice/{sessionId}/report`.
- Verify:
  - 页面显示 PPT 复盘，而不是 sales baseline cards。
  - 逐页总结 / 关键点覆盖 / 违规词或偏题提示可读。
  - 再练按钮保留原 `presentation_id`。
  - presentation report 不再出现 knowledge-check 这类 sales-only diagnostics。

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| PPT 会后六维评分、逐页总结、建议 | `backend/src/presentation_coach/services/presentation_report_service.py` | 这已经是 deterministic、material-aware 的 PPT scorer，直接读 `Page` / `RequiredTalkingPoint` / `InterruptionEvent` / `ConversationMessage`，比在 report page 或另一条 API 上重写 heuristic 更稳。 |
| 当前页 required points / forbidden words / page content 权威读取 | `backend/src/presentation_coach/services/coach_service.py#get_current_page_requirements` | S04 已经把 standard PPT 的 stable `presentation_id` + rebuilt page metadata 收稳，这里就是 live material authority。 |
| Presentation runtime page-context envelope | `backend/src/presentation_coach/websocket/components/presentation_event_emitter.py` | slide/page/point contract 已有稳定 envelope，可继续沿用到 persistence / tests，而不是重造 websocket shape。 |

## Constraints

- **S02 的统一事实线不能被绕开。** PPT 复盘不能只依赖 `/evaluation/sessions/{id}/report` enhancement；核心 facts 必须进入 `/practice/sessions/{id}/report`。
- **presentation runtime 有 legacy + StepFun 两条模式。** `PresentationStepFunRealtimeHandler` 已写 `page_number`，legacy `PresentationWebSocketHandler` 还没写；S07 不能默默把 proof 范围缩到 StepFun-only。
- **`SessionReport` / `PracticeSessionReport` 目前只被 shared report page 消费。** 扩 contract 的 blast radius 相对可控，但 `SessionEvidenceContract` 名字和 helper 文案都明显 sales-oriented，需要 scenario-aware 扩展而不是 key 复用。
- **report page 是 client-side 多请求页面。** 目前并行拉 report、enhanced report、knowledge-check、highlights；presentation variant 应避免无意义的 sales fetch，符合 `react-best-practices` 的“不要做不需要的 client 请求/状态工作”。

## Common Pitfalls

- **把 PPT 语义塞进 sales `pass_flags`** — `pass_3min_flow/pass_5turn_defense/pass_4step_structure` 是 sales 继承包袱；presentation 没有必要复用这组名字，强行 remap 只会让 future agent 误判。
- **只改 `/evaluation/.../report` 而不改 shared report** — 页面一旦 enhanced route 404/失败，用户仍会看到 sales view，等于 slice 目标没有真正落到 canonical report path。
- **只修 StepFun handler** — 这样 legacy presentation session 仍然没有 page-number evidence，逐页复盘会静默退化。
- **继续信任 `SessionEvidenceService.build_stage_summary()` 原样可用** — 它只认 `sales_stage`，对 PPT 来说不会自动变成逐页总结。
- **presentation report 仍无条件请求 knowledge-check** — 这是 S04 的 sales material diagnostics，会在 PPT 报告里制造噪声和错误状态，不是复盘内容的一部分。

## Open Risks

- 旧的 completed presentation sessions 可能没有 `transcript_metadata.page_number`。S07 需要明确 backward-compat 策略：
  - overall score 可继续显示；
  - 逐页总结/coverage 缺失时要有清晰 degraded 文案；
  - 不要直接掉回 sales UI。
- 如果规划时把 replay/history/trends 也一起并入 S07，slice 范围会明显膨胀。最小可信切法是：**先把 single-session report canonicalize**，并让 payload 设计可被 replay/history 后续复用。

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js | `react-best-practices`, `vercel-react-best-practices` | installed |
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` |