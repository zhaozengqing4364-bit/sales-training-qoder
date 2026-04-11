---
id: T01
parent: S04
milestone: M014
key_files:
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
  - web/src/components/practice/RightPanelContent.tsx
  - web/src/app/(user)/practice/layout.tsx
  - web/src/app/test-mic/page.tsx
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D178 — extend S04 preflight/interruption UX on the existing practice page + right-panel + LearnerHelpEntry seams instead of inventing a new route or learner-visible mic-test entry.
duration: 
verification_result: passed
completed_at: 2026-04-11T16:07:40.989Z
blocker_discovered: false
---

# T01: Documented the real practice preflight and interruption seams, including silent pause/resume failures and the off-path /app/test-mic tool.

**Documented the real practice preflight and interruption seams, including silent pause/resume failures and the off-path /app/test-mic tool.**

## What Happened

I audited `web/src/app/(user)/practice/[sessionId]/page.tsx`, `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`, `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`, `web/src/hooks/use-practice-websocket.ts`, `web/src/components/practice/RightPanelContent.tsx`, `web/src/app/(user)/practice/layout.tsx`, `web/src/components/layout/learner-help-entry.tsx`, and the live mic-test page. The inventory showed that ordinary practice sessions currently expose only the scenario title, connection/lifecycle state, record guidance, and the shared help entry; sales retry sessions additionally surface `focusIntent.main_issue` + `focusIntent.next_goal` on the page, while same-session learning cues, claim-truth, and score context live in `RightPanelContent` via `liveSessionSummary` / `scores`. For interruption UX, the lifecycle hook auto-starts preparing sessions, pause/resume requests go through REST but failure is only logged today, end failures surface through `lifecycleError` in the red banner with a `重试结束` affordance, and websocket connection failure adds a `重新连接` CTA. The task plan’s `web/src/app/(user)/practice/test-mic/*` path was stale locally; the actual dev tool is `web/src/app/test-mic/page.tsx`, and there is no learner-facing link to it from current practice/help shells. I wrote this seam inventory into `.gsd/KNOWLEDGE.md`, recorded D178 to anchor downstream implementation choices, and updated the loop state/log so T02 can build on the real surfaces instead of adding duplicate entrypoints.

## Verification

Ran the planned rg scan against the live practice page and websocket hook to confirm the existing scenario/persona/focus/interruption surface, then ran the focused practice page/lifecycle/layout Vitest suite to prove the inventory writeback did not disturb the current learner seams. The rg command exited 0, and `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/app/(user)/practice/layout.test.tsx'` finished 3 files / 11 tests green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "pause|resume|end|test-mic|persona|scenario|goal" 'web/src/app/(user)/practice/[sessionId]/page.tsx' 'web/src/hooks/use-practice-websocket.ts'` | 0 | ✅ pass | 32ms |
| 2 | `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/app/(user)/practice/layout.test.tsx'` | 0 | ✅ pass | 1492ms |

## Deviations

Minor local path correction only: the plan referenced `web/src/app/(user)/practice/test-mic/*`, but the live repo route is `web/src/app/test-mic/page.tsx` and it is not exposed from learner practice routes.

## Known Issues

Pause/resume failure remains log-only with no learner-facing copy, and ordinary practice sessions still lack a dedicated preflight goal/evaluation/persona card; both are the intended follow-up surface for T02.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/app/(user)/practice/layout.tsx`
- `web/src/app/test-mic/page.tsx`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
