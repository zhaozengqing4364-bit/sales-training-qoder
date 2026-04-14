# T03 CONTEXT DRAFT — canonical/compat frontend read-side cutover

## Status
- Task **not complete**.
- I did **not** call `gsd_complete_task` because the verification gate is red and the task state would be inaccurate.
- I updated `.codex/loop/state.json` and `.codex/loop/log.md` to keep the continuation layer truthful.

## What Landed Durably
1. **Fail-first tests were added** to prove the intended T03 behavior:
   - `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
   - `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
   - `web/src/app/(dashboard)/history/page.test.tsx`
2. **Architecture note updated** in `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` to lock the reader retirement order as:
   - prefer `canonical_evaluation_kernel`
   - explicit fallback to `compatibility_readers`
   - use legacy top-level rollups only as the final fallback

## What Failed
I attempted to introduce a shared frontend score-reader helper and wire report/replay/history pages to it in one pass. That destabilized the report/replay surfaces and the exact verification bundle stopped passing. I then backed out the risky runtime path rather than leave the repo in a broken state, but the test files still reflect the desired T03 assertions.

## Last Verification Run
`npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"`

Result: **failed**.

Observed failure themes during the run:
- report/replay runtime wiring was not stable when the shared helper was introduced
- history still reads `overall_score` directly and does not yet consume compat rollups
- new tests correctly assert canonical/compat contract usage but the implementation is not finished

## Exact Resume Plan
1. Start from the current repo state and first confirm report/replay/history pages render normally on legacy fields.
2. Reintroduce the cutover **one surface at a time** instead of all three at once:
   - first: `history/page.tsx` overall score display only
   - second: `report/page.tsx` overall score + sales rollup cards
   - third: `replay/page.tsx` overall score only
3. Keep the helper tiny:
   - input: `canonical_evaluation_kernel`, `compatibility_readers`, top-level legacy scores
   - output: `{ source, overall, logic, accuracy, completeness }`
4. After each surface change, rerun the exact file test before touching the next surface.
5. Only call `gsd_complete_task` once the exact T03 verification bundle is green.

## Files To Re-check Before Editing
- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- the three focused test files above

## Known Safe Assumption
The backend contract work from T02 is already present; T03 is purely a frontend read-side cutover plus documentation/retirement-order write-back. No blocker was discovered in the slice plan itself.