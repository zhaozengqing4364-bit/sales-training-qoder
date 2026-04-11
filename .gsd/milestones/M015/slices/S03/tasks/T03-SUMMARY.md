---
id: T03
parent: S03
milestone: M015
key_files:
  - web/src/app/learner-shell-baseline.test.ts
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Scope learner-shell closure proof to learner-core route families only; admin route shells in the same app tree are explicit out-of-scope noise for this baseline.
  - Record remaining responsive/timezone work as source-backed deferred facts in one focused learner test instead of reopening shell implementation scope.
duration: 
verification_result: passed
completed_at: 2026-04-11T18:49:14.614Z
blocker_discovered: false
---

# T03: Added a focused learner-shell baseline test that locks learner fallback coverage and the remaining deferred responsive/timezone facts.

**Added a focused learner-shell baseline test that locks learner fallback coverage and the remaining deferred responsive/timezone facts.**

## What Happened

I kept T03 scoped to proof closure instead of reopening learner-shell implementation work. Following the T01/T02 baseline, I first added a naive learner-shell inventory test and ran it red; it failed for the right reason because the raw `web/src/app/**/(error|loading).tsx` scan also includes `admin/error.tsx` and `admin/loading.tsx`, which are real route shells but out of learner scope. I then refined that proof into `web/src/app/learner-shell-baseline.test.ts`, which now does three things in one focused place: (1) scopes route-shell closure to the learner-core route families recorded in S03, while explicitly proving admin shells stay outside that assertion boundary; (2) locks the learner route a11y baseline by checking the shared loading/error seams and the explicit status semantics on history/report/replay loading shells; and (3) records the remaining responsive/timezone work as deferred source-backed facts by proving the shared dashboard skeleton is narrow-screen safe while dashboard page density and browser-local `toLocaleString("zh-CN")` formatting still remain intentionally unresolved product-baseline items. I also appended the non-obvious learner-scope inventory rule to `.gsd/KNOWLEDGE.md` and updated `.codex/loop/state.json` plus `.codex/loop/log.md` so future auto runs can resume from the new proof instead of stale T02 state.

## Verification

Ran the new focused proof with `npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts"`, which finished 3/3 green after the red-to-green scope correction. Then ran the slice verification gate `find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts" "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`, which showed the expected route-shell inventory and finished 44/44 green across the baseline proof plus learner history/report/replay regressions. Fresh LSP diagnostics on `web/src/app/learner-shell-baseline.test.ts` were clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts"` | 0 | ✅ pass | 438ms |
| 2 | `find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts" "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` | 0 | ✅ pass | 1340ms |
| 3 | `lsp diagnostics web/src/app/learner-shell-baseline.test.ts` | 0 | ✅ pass | 0ms |

## Deviations

Minor local adaptation only: instead of spreading the remaining-risk proof across multiple existing page suites, I landed one new filesystem-backed app-level test (`web/src/app/learner-shell-baseline.test.ts`) plus a matching knowledge entry. This kept the proof readable and let the learner-scope rule live next to the route-shell inventory it constrains.

## Known Issues

The remaining baseline risks stay intentionally deferred and are now encoded in the new proof: dashboard home/profile still carry denser multi-column responsive layouts outside route-shell scope, and history/report/replay still format timestamps with browser-local `toLocaleString("zh-CN")` without an explicit product timezone contract. No new runtime regression was introduced.

## Files Created/Modified

- `web/src/app/learner-shell-baseline.test.ts`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
