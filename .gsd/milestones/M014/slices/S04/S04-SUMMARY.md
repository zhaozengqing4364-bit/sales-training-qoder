---
id: S04
parent: M014
milestone: M014
provides:
  - A learner-readable preflight contract for sales and presentation practice before first speech.
  - A single interruption-recovery UI contract for pause/resume/end failures on the existing practice page.
  - A preserved developer-only boundary for `/app/test-mic`, so future learner-loop slices can assume it is not part of the normal user path.
requires:
  []
affects:
  []
key_files:
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
  - web/src/app/test-mic/page.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D178 — extend S04 on the existing practice page/right-panel/help seams and keep `test-mic` off the learner route path.
  - D179 — keep runtime-lock metadata authoritative for IDs/focus intent, but hydrate learner-readable preflight labels from agent/presentation detail APIs.
patterns_established:
  - Practice preflight should be a thin card on the existing `/practice/{sessionId}` page, not a second route or modal.
  - Learner interruption recovery should reuse the current red error banner with structured copy + retry CTA instead of console-only failures or new overlay surfaces.
  - Developer-only utilities like `/app/test-mic` should stay explicitly labeled as debug tools and remain absent from learner shells.
observability_surfaces:
  - `usePracticeSessionLifecycle` now emits structured `PracticeLifecycleError` state for pause/resume/end failures.
  - The practice page red error banner is the learner-visible failure surface for interruption recovery, with paired retry/reconnect affordances.
  - Focused learner-facing Vitest suites (`page.test.tsx`, `use-practice-session-lifecycle.test.ts`) are the current regression proof boundary for preflight and interruption UX.
drill_down_paths:
  - .gsd/milestones/M014/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T16:44:47.322Z
blocker_discovered: false
---

# S04: 训练前预期管理与中断恢复 UX 收口

**Practice 主页面现在会在首次开口前给出训练目标/评价标准/角色简介预告，并把暂停、继续、结束失败统一翻译成 learner-facing 恢复提示，同时把 `test-mic` 明确压回开发工具边界。**

## What Happened

本 slice 在现有 practice 主页面上补齐了真正影响首次开练的预期管理，而没有再造第二条 preflight route。普通 learner 在 `messages.length===0` 且会话尚未结束时，会看到一张最小 preflight 卡片，明确说明本次训练目标、评价标准和角色简介；sales 会话的 learner-readable 文案来自 `api.agents.getAgentWithPersonas(agentId)`，presentation 会话则复用 `api.presentations.get(presentationId)` 的标题/上下文，而 `usePracticeRuntimeLock` 继续作为 scenario/agent/persona/presentation id 与 retry focus intent 的 authority seam。这样开练前就不再只有“场景标题 + 连接状态”，而是能看懂这次要练什么、按什么标准判断、对面是谁。

本 slice 同时把 interruption UX 从“只在控制台里知道失败”收口成 learner 可恢复的页面状态。`usePracticeSessionLifecycle` 现在把 pause / resume / end 失败统一翻译成结构化 `PracticeLifecycleError`，practice 页继续复用既有红色错误 banner，而不是另起 modal：失败时会显示具体动作文案、下一步指导，以及匹配当前失败动作的 CTA（`重试暂停` / `重试继续` / `重试结束`）；如果 websocket 连接也失败，则同一块错误区继续给出 `重新连接`。这让中断失败第一次对 learner 变成“知道发生了什么、下一步怎么做”的产品态，而不是留给人猜测是网络、按钮还是后端问题。

另一个收口点是把 `web/src/app/test-mic/page.tsx` 明确压回开发/支持工具边界。该页面现在直接标明“开发工具 · 不属于学员训练主流程”，并说明正常学员应从 practice 主页面进入；practice learner shell 侧的 focused proof 也锁定了这里的 copy 不会重新泄漏进学员主路径。这样 M014 前三块 learner 入口、auth/profile、shared help 的补齐，终于能在真正的 `/practice/{sessionId}` 主链路上形成一致体验：用户知道这次为什么练、失败时知道如何恢复，也不会再被 mic debug 工具误导。

## Operational Readiness
- **Health signal:** practice 页面在首次开口前应出现“开练前预告”卡片；当 pause/resume/end 成功时不应留下错误 banner；focused tests 与 practice diagnostics 均保持 clean。
- **Failure signal:** pause/resume/end 失败时会出现红色错误 banner，包含 learner-facing 主文案、下一步提示以及匹配动作的重试按钮；连接失败时同一区域继续提供 `重新连接`。
- **Recovery procedure:** 先按 banner 中对应 CTA 重试当前动作；若连接失败则先点击 `重新连接`，再重试继续/结束；若继续仍失败，按指导刷新页面后重新回到当前会话。
- **Monitoring gaps:** 本 slice 没有新增后台级 interruption telemetry，close-out 也未获得新的 live browser localhost 证明；当前运行健康主要依赖 focused Vitest 合同与页面内错误 banner 可见性，后续若要做运营级监控仍需额外埋点/日志面。

## Verification

Fresh close-out verification reran the slice-plan focused gate `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"` and it passed with 2 test files / 17 tests green. I also ran LSP diagnostics on `web/src/app/**/practice/**/*.ts*`, and the touched practice page, lifecycle hook, tests, report/replay neighbors, and layout files all reported no issues. No live localhost browser success claim is included in this close-out because prior task-level smoke remained environment-blocked by a Next dev server hang on `Compiling instrumentation Node.js ...`; the trustworthy proof for this slice remains the focused learner-facing contract tests plus clean diagnostics.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/page.tsx` — Added the learner-facing preflight card, wired retry-focused copy, and reused the existing practice error banner for pause/resume/end recovery guidance.
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` — Translated pause/resume/end failures into structured learner-facing lifecycle errors with action-specific guidance.
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx` — Locked the visible preflight contract, interruption error actions, and absence of developer-only `test-mic` copy in the learner shell.
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts` — Proved pause/resume/end failure messages and guidance remain learner-readable and actionable.
- `web/src/app/test-mic/page.tsx` — Reframed the standalone microphone page as a developer/debug tool rather than a learner training path.
- `.gsd/DECISIONS.md` — Recorded the preflight data-authority decision for agent/presentation detail hydration.
- `.gsd/KNOWLEDGE.md` — Captured the practice preflight authority seam and the local Next dev instrumentation-compile verification gotcha.
