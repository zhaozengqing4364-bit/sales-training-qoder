---
id: T02
parent: S04
milestone: M014
key_files:
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
  - web/src/app/test-mic/page.tsx
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Hydrate learner-readable sales preflight context from `api.agents.getAgentWithPersonas(agentId)` and presentation titles from `api.presentations.get(presentationId)`, while keeping runtime-lock session metadata authoritative for IDs and retry focus intent.
  - Keep interruption recovery on the existing practice-page error banner and action buttons instead of introducing a new modal or preflight route.
duration: 
verification_result: mixed
completed_at: 2026-04-11T16:35:04.004Z
blocker_discovered: false
---

# T02: Added learner-facing practice preflight guidance, retry-aware interruption copy, and a developer-only label for /app/test-mic.

**Added learner-facing practice preflight guidance, retry-aware interruption copy, and a developer-only label for /app/test-mic.**

## What Happened

I extended `web/src/app/(user)/practice/[sessionId]/page.tsx` on the existing practice shell seam instead of inventing a new route. Ordinary learners now see a small preflight card before first speech with a training goal, evaluation criteria, and role intro. For sales sessions, the page truthfully hydrates learner-readable context from `api.agents.getAgentWithPersonas(agentId)` so the preflight can show the real agent/persona name + persona description; for presentation sessions it falls back to `api.presentations.get(presentationId)` for the PPT title, while `usePracticeRuntimeLock` remains the authority for runtime IDs and retry focus intent. I upgraded `use-practice-session-lifecycle.ts` so pause/resume/end failures no longer stay console-only: the hook now returns structured learner-facing error state with action-specific copy and next-step guidance, and the page banner reuses the existing red error surface to show that copy plus the right retry CTA (`重试暂停` / `重试继续` / `重试结束`) and reconnect affordance. I also relabeled `web/src/app/test-mic/page.tsx` as a developer/debug tool so it no longer reads like a learner practice entry. Focused page/lifecycle tests were expanded first, then the implementation was brought to green. I appended a knowledge note that future preflight UX should keep using the agent/presentation detail APIs for learner-readable labels instead of assuming `practice.getSession()` is enough.

## Verification

Ran the slice’s focused practice Vitest gate after the implementation and test updates: `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"` finished 13/13 green with clean output. Because this task changes learner-visible UI, I also attempted a real browser smoke flow by starting `npm --prefix web run dev` under `bg_shell` and navigating to `http://localhost:3445/practice/session-current?scenario_type=sales&voice_mode=legacy`; that verification was environment-blocked because the local Next dev server never progressed past `Compiling instrumentation Node.js ...`, so no truthful browser success claim was made and the managed background process was killed immediately to avoid polluting later runs.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"` | 0 | ✅ pass | 985ms |
| 2 | `browser smoke attempt: http://localhost:3445/practice/session-current?scenario_type=sales&voice_mode=legacy` | 1 | ❌ blocked (local Next dev hung on instrumentation compile) | 30000ms |

## Deviations

Minor local path correction only: the plan referenced `web/src/app/(user)/practice/test-mic/*`, but the live developer utility is `web/src/app/test-mic/page.tsx`. Browser smoke verification was attempted because this task touches UI, but local Next dev was environment-blocked by a stuck instrumentation compile, so only the focused automated gate could be closed in this task.

## Known Issues

Local browser smoke remains blocked until the repo’s Next dev server can serve pages instead of hanging on `Compiling instrumentation Node.js ...`. The shipped code changes are covered by focused tests, but a live browser pass could not be completed in this environment.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
- `web/src/app/test-mic/page.tsx`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
