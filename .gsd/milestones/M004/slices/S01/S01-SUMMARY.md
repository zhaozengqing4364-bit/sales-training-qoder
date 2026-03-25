---
id: S01
parent: M004
milestone: M004
provides:
  - 现有 `/api/v1/sessions/{id}/replay` 与 highlights payload 上可稳定引用的 `learning_evidence` contract（reason、stage、nearby context、suggested response、issue-family、linked issue/goal）。
  - report / replay / history / highlight 共享的学习词汇层，可把 `main_issue` / `next_goal` 翻译成一致的 learner-facing cue。
  - 当前入口页在 no highlights / enhanced-data degrade 时的明确、可读降级行为。
  - 一组 focused backend + web regression tests，用来防止 replay/highlight learning contract 发生静默漂移。
requires:
  []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/schemas.py
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/components/highlights/HighlightList.tsx
  - web/src/components/highlights/HighlightDetailModal.tsx
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
key_decisions:
  - 继续以 `SessionEvidenceService` projection 作为 replay/highlight explanation 字段的唯一事实源，不新增第二个 scorer 或学习生成器。
  - 把 explanation-rich highlight evidence 收口到 nested `learning_evidence`，同时保留 `stage_name` / `context` / `suggested_response` 等兼容字段。
  - 让 replay/highlight/report/history 通过共享 frontend helper 复用同一 issue/goal vocabulary，并把 highlights / enhanced report 固定为可缺失增强层。
patterns_established:
  - 在现有 authority line 上用 nested `learning_evidence` 承载 richer semantics，同时保留 flat compatibility 字段，避免读侧一次性大迁移。
  - 前端通过共享 `extractSessionLearningCue(...)` / issue-label / goal-label helper 派生学习文案，避免 report/history/replay 各自手写一套词汇。
  - 把 highlights 与 enhanced report 视为 optional overlays；当前入口页的主体可读性必须继续由 unified session evidence contract 保底。
  - 后端 payload 扩展时必须同步更新 FastAPI `response_model`，否则服务层已生成的新字段会被序列化层静默裁掉。
observability_surfaces:
  - `replay_data_generated` structured log with `highlight_learning_count` and `issue_family`
  - `session_highlights_generated` structured log with `total_highlights` / `total_good` / `total_bad` / `issue_family`
  - Replay/report inline degraded-state hints for unavailable highlights, unavailable enhanced insights, not-evaluable sessions, and evidence completeness notes
drill_down_paths:
  - .gsd/milestones/M004/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-25T16:15:19.809Z
blocker_discovered: false
---

# S01: 当前 report/replay/highlight 入口的学习证据 contract

**现有 replay/highlight/report/history 入口现在共享一条 explanation-rich learning evidence contract，让学员在当前页面上看到关键轮次为什么重要、处于哪个阶段、卡在哪类问题，以及更好的回应。**

## What Happened

这条 slice 没有新增学习页面，也没有引入第二条事实线。T01 把 replay/highlight 的解释字段压回现有 `SessionEvidenceService` 权威投影：`backend/src/common/conversation/replay.py` 在生成 replay/highlights 时给高光 turn 附加 nested `learning_evidence`（reason、issue_family、objection_family、stage、nearby_context、suggested_response、linked_issue、linked_goal），同时继续输出 `stage_name` / `context` / `suggested_response` 这些 flat compatibility 字段；`backend/src/common/conversation/schemas.py` 也同步扩展 response_model，避免 FastAPI 在序列化时把新字段裁掉。`backend/src/common/conversation/session_evidence.py` 继续作为会话级 `main_issue` / `next_goal` / claim-truth / evidence completeness 的权威来源，replay 只是读取并挂接说明性 evidence，而不是重新评估。

T02 让现有 replay/highlight UI 直接消费这条 contract。`web/src/app/(user)/practice/[sessionId]/replay/page.tsx` 现在先读 canonical `getReplay(sessionId)`，再把 highlights 作为可选增强层叠加；页面会展示本场教练结论、claim-truth、evaluable/evidence completeness、阶段事实，以及 per-turn learning evidence。`HighlightList` / `HighlightCard` / `HighlightDetailModal` 则把 learning-evidence 的 why/stage/issue-family/linked-goal/linked-issue/nearby-context/suggested-response 直接渲染到现有高光卡片和详情弹窗里；当 highlights 接口不可用或返回空数组时，页面保留明确但克制的当前入口态，而不是把整页打成失败。

T03 把同一套 learning vocabulary 带到了 report/history。`web/src/lib/session-evidence.ts` 新增共享的 `extractSessionLearningCue(...)` 和 issue/goal label helpers；`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 与 `web/src/app/(dashboard)/history/page.tsx` 都改为从 `main_issue` / `next_goal` 生成一致的学习 cue，确保 report 的主问题/下一轮目标、history 的卡点/重点摘要、以及 highlights/enhanced-report 不可用时的降级文案都继续围绕同一条 unified evidence contract。结果是：当前 report / replay / highlight / history 入口都开始说同一种“为什么重要、怎么改、下一轮练什么”的语言，但仍然只依赖现有会话证据链。

## Verification

按 slice plan 跑了全部 fresh gate，并读取了完整输出确认通过：

1. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py`
   - 43 passed
   - 重点覆盖：`learning_evidence` 序列化、stale snapshot alignment override、legacy turn normalization、replay/highlights completed-session contract。

2. `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'`
   - 3 test files / 5 tests passed
   - 重点覆盖：replay page 不再拼接冲突消息源、高光卡片/详情弹窗渲染 richer learning evidence、empty state 保持干净。

3. `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`
   - 3 test files / 10 tests passed
   - 重点覆盖：report/history 共享 learning vocabulary；highlights/enhanced analytics 不可用时继续展示 canonical evidence；not-evaluable sessions 不会退化成 generic pending。

另外核对了 observability / degraded-state surfaces：backend `replay_data_generated` 与 `session_highlights_generated` 结构化日志会带出 highlight_learning_count / total_highlights / issue_family；web replay/report 页面保留 `高光片段暂不可用`、`综合洞察暂不可用`、`当前会话暂不可评估` 与 evidence completeness 提示，符合 slice plan 对降级可见性的要求。

## Requirements Advanced

- R011 — 在不新增学习页面或第二个 evaluator 的前提下，把现有 replay/highlight/report/history 入口提升为 explanation-rich 学习证据面：completed-session projection 现在能稳定暴露 why/stage/context/better-response/issue-goal linkage，且各入口使用同一 issue/goal learning vocabulary。

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

这条 slice 只覆盖 completed-session 的现有 report/replay/highlight/history 读侧 contract，没有改变 replay/highlights 仍受 `require_completed` gate 约束的事实。report 还不能直达 replay 的具体 turn/anchor；retry 入口也还没有消费 `learning_evidence.issue_family` / `linked_goal`；presentation 的 page-level learning evidence 仍由后续 S04 负责。

## Follow-ups

S02 应直接复用这次落下来的 highlight/message anchors 与 `learning_evidence.linked_issue` / `linked_goal` 做 report → replay 深链；S03 应把 `issue_family` + `linked_goal` 映射成再练 bootstrap contract；S04 应在 presentation page evidence 上复用同一类“reason / context / better response”解释结构。

## Files Created/Modified

- `backend/src/common/conversation/replay.py` — 在现有 replay/highlight 服务上挂接 nested `learning_evidence`，并保留 `stage_name` / `context` / `suggested_response` 等 flat compatibility 字段。
- `backend/src/common/conversation/session_evidence.py` — 继续作为会话级 `main_issue` / `next_goal` / claim-truth / evidence completeness 的权威投影，供 replay/report/history 复用同一 learning vocabulary。
- `backend/src/common/conversation/schemas.py` — 补齐 replay/highlight `response_model`，让 `learning_evidence` 与兼容字段真正穿过 FastAPI 序列化层。
- `backend/tests/unit/test_replay_service.py` — 增加 replay service focused tests，锁定 learning-evidence attachment、stale snapshot alignment 和 legacy turn normalization。
- `backend/tests/integration/test_replay_api.py` — 增加 replay/highlights API contract tests，验证 richer payload 和 completed-session gate 行为。
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — 让 replay 页面直接消费 canonical replay contract，展示本场教练结论、claim-truth、per-turn learning evidence 和 highlights degraded hint。
- `web/src/components/highlights/HighlightList.tsx` — 在现有高光列表中展示 why/stage/issue-family/goal 说明，并保持 empty state 简洁。
- `web/src/components/highlights/HighlightCard.tsx` — 把 richer learning evidence 渲染到现有高光卡片，包含为什么重要、阶段、问题标签和下一轮重点。
- `web/src/components/highlights/HighlightDetailModal.tsx` — 在详情弹窗中展示关联问题、下一轮目标、上下文和更好的回应。
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — 锁定 replay 页以 unified replay contract 为权威数据源，并验证高光学习证据渲染与 degraded behavior。
- `web/src/components/highlights/HighlightList.test.tsx` — 验证 highlight list/card 在现有 surface 上呈现 explanation-rich evidence，并覆盖 empty state。
- `web/src/components/highlights/HighlightDetailModal.test.tsx` — 验证高光详情弹窗渲染 linked issue/goal、nearby context 和 better response。
- `web/src/lib/session-evidence.ts` — 新增共享 learning cue / issue-label / goal-label helper，让 report/history/replay 说同一种学习语言。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 让 report 页在 highlights 或 enhanced report 不可用时继续使用 canonical issue/goal learning cue，并保留明确降级提示。
- `web/src/app/(dashboard)/history/page.tsx` — 让 history 卡片从 `main_issue` / `next_goal` 抽取统一 learning cue，并在 analytics degrade 时继续展示可读的训练结论。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 锁定 report 对 not-evaluable、enhanced-report degrade 和 learning vocabulary carry-forward 的行为。
- `web/src/app/(dashboard)/history/page.test.tsx` — 锁定 history 在 analytics degrade 和 not-evaluable 场景下仍显示 projection-backed learning cue。
