---
id: M004
title: "复盘与学习闭环增强"
status: complete
completed_at: 2026-03-26T05:27:53.290Z
key_decisions:
  - 坚持把 learner loop 限定在现有 report / replay / history / practice route family 与 `SessionEvidenceService` / replay payload / `presentation_review` authority line 上，不新增学习页面或第二个 evaluator。
  - 把 richer 学习语义继续挂在既有 payload 上：sales 走 `learning_evidence`、`replay_anchor`、`retry_entry.focus_intent`，PPT 走 `presentation_review.page_summaries[*].issue_clusters`，而不是引入第二套 read model。
  - 把 anchor drift、missing highlight、missing page metadata 视为一等降级路径，必须在 report / replay 上显式展示 diagnostics，而不是静默 fallback。
  - 定向再练 focus 走 completed-session evidence → create-session → frozen snapshot → runtime descriptor 的结构化链路，不依赖前端局部状态或额外 onboarding flow。
  - PPT learner loop 继续按 shared history / report / replay route family 交付：当前 shipped contract 是 history 行暴露 replay、report 暴露 retry，这个 nuance 被显式接受并纳入终验。
key_files:
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/api/practice.py
  - backend/src/training_runtime/service.py
  - backend/src/presentation_coach/services/presentation_report_service.py
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - web/src/components/highlights/HighlightList.tsx
  - web/src/lib/session-evidence.ts
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
lessons_learned:
  - 现有 authority line 足够承载更丰富的 learner-loop 语义，只要 backend payload、response model 和 frontend shared helper 一起演进，不需要再造第二条学习事实线。
  - 显式 degraded banner 比隐式 fallback 更重要；当 replay anchor 或 PPT page metadata 漂移时，用户至少要知道现在看到的是哪种近似定位或缺失状态。
  - 结构化 retry focus 只有在 create-session 时被冻结，并通过 typed runtime descriptor 投影到 practice 页面，才能在刷新和 reconnect 下稳定保留学习意图。
  - sales 与 PPT 可以共享同一 learner route family，但 entrypoint 细节必须写成可见 contract；否则很容易把当前 shipped behavior 与未来可能的 UX 扩展混为一谈。
---

# M004: 复盘与学习闭环增强

**现有 report / replay / history / practice 路由现在形成了一条 explanation-rich 的 sales + PPT 学习闭环，用户能定位问题片段、理解原因并带着同一焦点再练。**

## What Happened

M004 没有新增学习页面，也没有再造第二条 evaluator / learner model，而是把学习闭环压回现有 route family 与 authority line。S01 先把 replay / highlights / report / history 收口到 explanation-rich `learning_evidence` 与统一 issue/goal vocabulary；S02 在同一条 replay authority line 上补了 `replay_anchor`，让 report 可以直达 replay 的关键 turn，并在 resolved / degraded / missing 三种落点下都保留可见诊断；S03 把 completed-session 的 issue/goal 继续收口成 canonical `retry_entry.focus_intent`，冻结进新 session 的 `voice_policy_snapshot.focus_intent`，再投影到 `runtime_descriptor.focus_intent`，让 learner 在新 `/practice/{sessionId}` 首屏看到 carry-forward focus；S04 把同样的 learner-loop 原则扩到 PPT 的 shared report / replay 路由，用 `presentation_review.page_summaries[*].issue_clusters`、page anchor 与 completeness diagnostics 解释“哪一页出了什么问题、为什么要重讲”；S05 则用 live sales `history -> report -> replay -> retry` 与 live PPT `history -> report/replay -> retry` 证明两条闭环都跑通，同时把 `no_matching_highlight`、`missing_page_metadata` 等降级状态保留成可解释的 shipped behavior。里程碑级验证也确认 branch 相对 `001-ai-practice-system` 含有真实非 `.gsd` 代码改动，所有 slice summary/UAT 文件存在，`M004-VALIDATION.md` 判定为 pass，且 `.artifacts/m004-s05-t02/` 与 `.artifacts/m004-s05-t03/` 的 browser evidence packs 仍在磁盘上。

## Success Criteria Results

- ✅ **Shared learner-loop vision on current routes** — 学习证据继续留在现有 report / replay / history / practice route family 和既有 authority line（`SessionEvidenceService`、replay payload、`presentation_review`）上。证据：S01 建立 explanation-rich contract，S02/S03 扩展同一条 report→replay→retry 链，S04 把同样原则带到 PPT，S05 在现有入口上完成 sales + PPT 终验。
- ✅ **S01：当前 replay/highlight surface 能解释哪一轮重要、为什么重要、处于哪个阶段以及更好的回应** — 证据：S01 summary 记录 nested `learning_evidence`、共享 issue/goal vocabulary，以及通过 `tests/unit/test_replay_service.py`、`tests/integration/test_replay_api.py` 与 replay/highlight/report/history focused web suites 的验证。
- ✅ **S02：report 能把 learner 打到与当前 issue / goal 对应的 replay turn / marker** — 证据：S02 summary 记录 `replay_anchor` metadata、稳定 query handoff、replay resolved/degraded/missing banner，以及 replay anchor backend/web suites 通过。
- ✅ **S03：report 或 replay 能发起定向再练，并在新 session 首屏看到 carry-forward focus** — 证据：S03 summary 记录 canonical `retry_entry.focus_intent`、`voice_policy_snapshot.focus_intent`、`runtime_descriptor.focus_intent`、practice-page callout，以及 contract / integration / runtime / web focused tests 通过。
- ✅ **S04：当前 PPT report/replay route 能展示哪一页有哪类问题簇以及为什么要重讲** — 证据：S04 summary/UAT 与 `M004-VALIDATION.md` 记录 `presentation_review.page_summaries[*].issue_clusters`、aggregate diagnostics/completeness、shared PPT report overview、PPT replay page banner + SlideViewer + transcript jumps，以及 degraded / missing-page handling；focused backend/web verifiers 通过。
- ✅ **S05：至少一条 sales 和一条 PPT 路由在当前 entrypoints 上完成 live learning loop，且 degraded state 可理解** — 证据：S05 summary/UAT 与 `M004-VALIDATION.md` 记录 live sales `history -> report -> replay -> retry` proof、live PPT `history -> report/replay -> retry` proof、显式 degraded PPT `missing_page_metadata` 行为、重跑的 backend/web verification，以及磁盘上的 `.artifacts/m004-s05-t02/`、`.artifacts/m004-s05-t03/` evidence packs。

## Definition of Done Results

- ✅ **所有 roadmap slices 均已完成** — 预加载的 `M004-ROADMAP.md` slice overview 显示 S01–S05 全部为 done。
- ✅ **所有 slice summaries / UAT artifacts 均存在** — `find .gsd/milestones/M004 -maxdepth 4 -type f | sort` 确认 `S01`–`S05` 的 `S##-SUMMARY.md`、`S##-UAT.md` 与 task summaries 全部在磁盘上。
- ✅ **跨 slice 集成通过** — `M004-VALIDATION.md` verdict 为 `pass`，`Cross-Slice Integration` 明确记录无 material mismatch；S01→S02、S01/S02→S03、S01→S04、S03/S04→S05 的 contract 都已闭合。
- ✅ **里程碑包含真实实现代码而非仅规划工件** — `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` 返回 137 个非 `.gsd` 文件变更（7883 insertions / 27705 deletions），覆盖 backend、web、tests 与 shared contracts。
- ✅ **最终 route-level 证据存在且可追溯** — `.artifacts/m004-s05-t02/` 与 `.artifacts/m004-s05-t03/` 目录存在，包含 browser screenshots、summary/verification JSON 与 Playwright verifier。

## Requirement Outcomes

- **R011: Active → Validated**
  - 证明链 1（解释型学习证据）：S01 把现有 replay / highlight / report / history surface 对齐到 explanation-rich `learning_evidence` 与统一 issue/goal vocabulary；S04 把同样的解释结构扩到 PPT `presentation_review.page_summaries[*].issue_clusters`。
  - 证明链 2（可跳转的回放证据链）：S02 交付 canonical `replay_anchor` contract，让 report 能直达 replay 的相关 turn / marker，并在 anchor drift 时保留 resolved / degraded / missing 诊断。
  - 证明链 3（issue-family-driven 再练闭环）：S03 交付 canonical `retry_entry.focus_intent`，把 main issue / next goal 带入新 session；S05 live proof 则确认 sales 与 PPT 在当前 route family 上都能完成学习证据 → 回放 / 再练的闭环。
  - 里程碑级证据：`M004-VALIDATION.md` 判定 milestone requirement coverage 完整，`.artifacts/m004-s05-t02/` 与 `.artifacts/m004-s05-t03/` 提供 live browser proof packs。

## Deviations

产品交付与 milestone scope 基本一致。唯一接受的 contract nuance 是：PPT replay 仍通过现有 `/history` sibling entrypoint 暴露，而不是 sales-style 的 report 内 CTA；`M004-VALIDATION.md` 已将其判定为符合“强化现有 report / replay / history 入口家族”的边界，而非未交付。

## Follow-ups

M005 及后续学习面扩展应继续优先复用现有 report / replay / history / practice contracts，而不是新建 learner-only workflow。若产品后续希望 PPT report 像 sales report 一样直接跳 replay，应把它作为新的显式 scope，而不是把当前 history-row replay contract 误当成回归。
