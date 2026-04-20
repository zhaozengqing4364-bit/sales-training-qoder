---
id: S03
parent: M015
milestone: M015
provides:
  - Explicit route-level loading/error fallback coverage for learner dashboard/auth/practice entry routes.
  - One durable baseline matrix plus one focused learner-shell proof file for future route-fallback audits.
  - A documented boundary between fixed learner-shell issues and intentionally deferred responsive/timezone product work.
requires:
  - slice: S01
    provides: shared debug/durable route-error seam via `debug.durableError(...)` and learner route error surfaces
  - slice: S02
    provides: frontend hygiene boundaries that removed interruptive dialog/navigation noise from adjacent learner/auth flows
affects:
  []
key_files:
  - .gsd/milestones/M015/slices/S03/tasks/T01-RESEARCH.md
  - web/src/components/learner/learner-route-loading-state.tsx
  - web/src/app/(dashboard)/loading.tsx
  - web/src/app/(auth)/loading.tsx
  - web/src/app/(auth)/error.tsx
  - web/src/app/(user)/practice/[sessionId]/loading.tsx
  - web/src/app/learner-shell-baseline.test.ts
key_decisions:
  - D185 — close learner loading gaps with one shared LearnerRouteLoadingState plus group-level dashboard/auth loaders and a dedicated live-practice loader.
  - D186 — count only learner-core route families toward S03 shell closure; exclude `/support/runtime` and admin route shells even though they live in the same app tree.
  - D187 — keep remaining responsive density and timezone semantics as explicit deferred baseline facts locked by focused proof instead of widening S03 scope.
patterns_established:
  - Use route-group loaders (`(dashboard)/loading.tsx`, `(auth)/loading.tsx`) as the default learner loading baseline, and only add page-local loaders when a route genuinely needs a more specific shell.
  - Keep learner route failures on the shared `LearnerRouteErrorState` + `debug.durableError(...)` seam instead of introducing route-specific error-reporting patterns.
  - Lock non-obvious shell-scope rules and deferred UX facts in one focused filesystem-backed proof (`web/src/app/learner-shell-baseline.test.ts`) so future slices do not have to reverse-engineer scope from audits.
observability_surfaces:
  - `debug.durableError("route-error.dashboard" | learner route error scopes)` remains the tagged frontend failure seam for learner route errors.
  - `web/src/app/learner-shell-baseline.test.ts` is the focused proof surface for learner-shell inventory, a11y seam coverage, and deferred responsive/timezone facts.
  - `src/components/error-reporting.test.tsx` and `src/app/(user)/practice/[sessionId]/error.test.tsx` remain the focused regression gate for learner route-error reporting.
drill_down_paths:
  - .gsd/milestones/M015/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M015/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M015/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T18:54:01.530Z
blocker_discovered: false
---

# S03: Learner error/loading 覆盖与 responsive/a11y/timezone baseline

**Closed learner-shell fallback gaps across dashboard/auth/practice, locked the a11y baseline on shared loading/error seams, and recorded the remaining responsive/timezone work as explicit deferred facts instead of reopening shell scope.**

## What Happened

## Delivered
- T01 established the learner-shell baseline matrix in `.gsd/milestones/M015/slices/S03/tasks/T01-RESEARCH.md`, defining learner-core scope as sidebar learner routes plus auth/practice flows and explicitly excluding `/support/runtime` from learner-shell closure.
- T01 also shipped the low-risk accessibility subset on existing learner surfaces: history/report/replay loading states now expose `role="status"`, `aria-live="polite"`, and `aria-busy="true"`, while login/forgot/reset forms gained explicit labels and alert semantics.
- T02 closed the missing learner loading coverage with one shared `LearnerRouteLoadingState` plus group-level loaders at `web/src/app/(dashboard)/loading.tsx` and `web/src/app/(auth)/loading.tsx`, and a dedicated live-practice loader at `web/src/app/(user)/practice/[sessionId]/loading.tsx`.
- T02 also added `web/src/app/(auth)/error.tsx` on the existing `LearnerRouteErrorState` + `debug.durableError(...)` seam so auth failures now land on the same explicit learner fallback path as practice/report/replay instead of bubbling to blank screens.
- T03 added `web/src/app/learner-shell-baseline.test.ts`, which locks three non-obvious truths for future slices: the learner-core route-shell inventory is closed without pulling in admin-only shells, the shared learner loading/error seams keep their a11y/diagnostic contract, and the remaining responsive/timezone issues stay visible as deferred baseline facts.

## What this slice actually provides
- Learner-core dashboard/auth/practice routes now have explicit route-level loading/error protection instead of relying on white screens, page-local fetch states, or implicit parent behavior.
- Future agents can re-run one focused learner-shell proof plus the existing learner history/report/replay suites to determine whether a learner-shell regression is real, instead of reconstructing S03 scope from raw audits.
- The slice deliberately does **not** widen into mobile-first redesign or timezone-contract work; it leaves those as source-backed baseline facts so later product decisions can address them intentionally.

## Why it matters downstream
S03 finishes M015’s frontend-hygiene work on the learner shell itself. Downstream auth/runtime/report changes can now reuse one shared learner loading state, one shared learner route-error seam, and one focused proof file to tell the difference between a real fallback gap and a known deferred responsive/timezone risk.

## Verification

Fresh slice-close verification passed on the current branch. Ran `find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` and got the expected learner/admin route-shell inventory plus 41/41 green across history/report/replay regressions. Then ran `npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts" "src/components/error-reporting.test.tsx" "src/app/(user)/practice/[sessionId]/error.test.tsx"` and got 8/8 green, confirming the focused learner-shell proof and the durable route-error observability seam still hold. Fresh LSP diagnostics on `web/src/app/learner-shell-baseline.test.ts` reported no issues.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None beyond scoped implementation choices already recorded in task summaries: S03 deliberately closed learner loading at the route-group seam (`(dashboard)`, `(auth)`, live practice) and captured remaining responsive/timezone work as proof-backed deferred baseline rather than page-by-page redesign.

## Known Limitations

Dashboard home/profile still contain denser page-level responsive layouts outside route-shell scope, and history/report/replay still use browser-local `toLocaleString("zh-CN")` formatting without an explicit product timezone contract. Those facts are now locked in `web/src/app/learner-shell-baseline.test.ts` instead of being silently rediscovered.

## Follow-ups

If a future milestone takes on mobile polish or timezone semantics, update `web/src/app/learner-shell-baseline.test.ts` and the matching knowledge entries together so the learner-shell proof stays aligned with the real scope. If a later route needs a more specific loader than the shared group shell, add that page-local `loading.tsx` deliberately rather than treating the current shared loader as missing coverage.

## Files Created/Modified

- `.gsd/milestones/M015/slices/S03/tasks/T01-RESEARCH.md` — Recorded the learner-core fallback inventory, low-risk a11y fixes, and the deferred responsive/timezone baseline.
- `web/src/components/learner/learner-route-loading-state.tsx` — Added the shared accessible learner route loading wrapper used by dashboard/auth/practice loaders.
- `web/src/app/(dashboard)/loading.tsx` — Introduced the shared learner dashboard loading shell for home/training/leaderboard/profile/agent routes.
- `web/src/app/(auth)/loading.tsx` — Introduced the shared auth loading shell for login/forgot/reset routes.
- `web/src/app/(auth)/error.tsx` — Added an auth route error boundary on the shared learner error + durableError seam.
- `web/src/app/(user)/practice/[sessionId]/loading.tsx` — Added the dedicated live-practice loading shell.
- `web/src/components/dashboard-skeleton.tsx` — Adjusted the shared dashboard skeleton so the fallback layout is safer on narrow screens.
- `web/src/app/learner-shell-baseline.test.ts` — Locked learner-shell closure, a11y seam coverage, and deferred responsive/timezone facts in one focused proof.
