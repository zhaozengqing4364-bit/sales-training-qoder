---
id: T03
parent: S04
milestone: M002
key_files:
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/lib/session-evidence.ts
key_decisions:
  - Replay must render the backend-provided aligned `main_issue` / `next_goal` directly instead of introducing any client-side recompute heuristic.
  - `web/src/lib/session-evidence.ts` remains the single vocabulary map for sales issue/goal badges so replay and admin surfaces stay readable when S04 alignment introduces new focus types like `evidence_gap` and `evidence_backing`.
duration: ""
verification_result: mixed
completed_at: 2026-03-24T23:55:37.119Z
blocker_discovered: false
---

# T03: Replay now surfaces the same aligned sales conclusion as report, admin badges understand the new S04 sales vocabulary, and the focused report/replay/admin web gate is green.

**Replay now surfaces the same aligned sales conclusion as report, admin badges understand the new S04 sales vocabulary, and the focused report/replay/admin web gate is green.**

## What Happened

I completed the missing T03 closure on the web read surfaces. First, I turned the plan into a red web check: the focused replay/admin/report suite failed because replay still omitted the shared coach conclusion block, the new S04 alignment vocabulary (`evidence_gap`, `evidence_backing`, etc.) was not mapped for admin badges, and one report fallback assertion was checking async degraded copy synchronously. I then made the smallest product change: `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` now renders a read-only “本场教练结论” section directly from the API’s `main_issue` and `next_goal` before stage evidence, without recomputing any rules on the client. I extended `web/src/lib/session-evidence.ts` so the new aligned sales issue/goal types resolve to readable Chinese labels across replay/admin surfaces. On the test side, I updated replay/admin focused tests to assert the aligned conclusion family and badge readability, switched the sales report focused fixture to S04’s aligned vocabulary, and fixed the existing async report fallback assertion to wait for the enhanced-report/highlights degraded copy that appears only after post-load effects complete. After that, the exact slice web verification command passed cleanly.

## Verification

Ran a red/green web verification loop around the exact S04 focused web command. The initial targeted run failed on the missing replay conclusion block, missing sales-alignment label mappings, and a synchronous assertion against async degraded copy. After rendering `main_issue` / `next_goal` directly on replay, extending the shared label map, and waiting for the async fallback text in the report test, the exact `cd web && /usr/bin/time -p npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` command passed with all 9 focused tests green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 1 | ❌ fail | 946ms |
| 2 | `cd web && /usr/bin/time -p npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1210ms |


## Deviations

Adjusted one pre-existing report-page async fallback assertion to wait for post-load degraded copy after the exact slice web gate exposed it; the product behavior already degraded correctly, so the change was to the focused test timing rather than the report contract itself.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/lib/session-evidence.ts`
