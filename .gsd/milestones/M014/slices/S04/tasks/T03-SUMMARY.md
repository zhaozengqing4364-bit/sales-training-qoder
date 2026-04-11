---
id: T03
parent: S04
milestone: M014
key_files:
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
key_decisions:
  - Keep the proof in the existing focused page/lifecycle suites and assert learner-visible behavior rather than implementation details or a new umbrella integration test.
duration: 
verification_result: passed
completed_at: 2026-04-11T16:39:25.253Z
blocker_discovered: false
---

# T03: Locked practice preflight, interruption recovery, and test-mic boundary contracts with focused learner-facing tests.

**Locked practice preflight, interruption recovery, and test-mic boundary contracts with focused learner-facing tests.**

## What Happened

I extended the existing focused practice suites instead of adding a new umbrella test. In `web/src/app/(user)/practice/[sessionId]/page.test.tsx`, I added learner-visible proof that the preflight card only appears before a conversation starts, that end-failure interruption copy exposes the retry/end + reconnect recovery actions, and that the learner practice shell stays free of the developer-only `test-mic` wording. In `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`, I added proof that end-session failures preserve actionable backend detail inside the learner-facing error message. No production code changes were required because the shipped page and lifecycle hook already satisfied these contracts; this task’s deliverable was the regression proof.

## Verification

Ran the slice’s focused verification gate: `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"`. The run finished with 2 test files passing and 17/17 tests green, confirming the preflight card visibility boundary, interruption recovery messaging/actions, and the non-main-path `test-mic` exposure rule remain covered by focused tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"` | 0 | ✅ pass | 847ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
