---
id: T03
parent: S03
milestone: M021
key_files:
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
key_decisions:
  - Reuse one shared frontend score resolver with the same precedence as the documented retirement plan: canonical_evaluation_kernel first, compatibility_readers second, legacy top-level rollups last.
duration: 
verification_result: passed
completed_at: 2026-04-14T03:47:24.637Z
blocker_discovered: false
---

# T03: Made report, replay, and history consume the shared canonical/compat score contract explicitly and fixed the broken report/replay page runtime.

**Made report, replay, and history consume the shared canonical/compat score contract explicitly and fixed the broken report/replay page runtime.**

## What Happened

I resumed T03 from the stable baseline described in `.codex/loop/state.json`: the focused web tests already expressed the intended canonical-vs-compat behavior, but the previous attempt had left the runtime cutover incomplete and both report/replay pages syntactically broken. I first removed the accidental duplicated JSX tails at the end of `web/src/app/(user)/practice/[sessionId]/report/page.tsx` and `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` so both pages could compile again. Then I finished the actual read-side contract work instead of just fixing syntax: `web/src/lib/api/types.ts` now declares `canonical_evaluation_kernel` and `compatibility_readers` on the shared session-evidence contract, and the existing shared helper in `web/src/lib/session-evidence.ts` is now the explicit score resolver for report, replay, and history surfaces. Report now resolves logic/accuracy/completeness/overall through canonical -> compatibility reader -> legacy and exposes the chosen source via `data-contract-source`; replay does the same for its headline score; history uses the same resolver for list cards and trend deltas so compat fallback is intentional instead of implicit. The retirement-order note for canonical -> compat -> legacy readers was already present in `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`; I verified that durable doc still matches the runtime helper behavior rather than creating another parallel note.

## Verification

Ran the exact task-plan verification bundle after the runtime fixes: `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` finished 44/44 green. I also verified the retirement-order documentation with `rg -n "prefer `canonical_evaluation_kernel`|compatibility_readers|retire 阶段" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md -S`, which confirmed the architecture scan still records the canonical -> compatibility reader -> legacy fallback sequence that the shared web helper now enforces at runtime.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` | 0 | ✅ pass | 6029ms |
| 2 | `rg -n "prefer `canonical_evaluation_kernel`|compatibility_readers|retire 阶段" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md -S` | 0 | ✅ pass | 28ms |

## Deviations

The task plan called out report/replay/history focused tests and shared types; locally I also had to remove duplicated trailing JSX from `report/page.tsx` and `replay/page.tsx` because the prior failed attempt left both pages unparsable. That was a necessary local recovery step, not a contract change.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
