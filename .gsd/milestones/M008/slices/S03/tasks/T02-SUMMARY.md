---
id: T02
parent: S03
milestone: M008
provides: []
requires: []
affects: []
key_files: ["web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", ".gsd/milestones/M008/slices/S03/tasks/T02-SUMMARY.md"]
key_decisions: ["Treated canonical `effectiveness_snapshot.retrieval_facts` as the authority for miss/search_failed learner copy in the report-page suite.", "Kept presentation coverage explicit about both hiding the retrieval section and skipping `/knowledge-check`."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` and confirmed the focused report-page suite passed 17/17 tests, including the new canonical retrieval miss/search_failed fallback cases and the tightened PPT retrieval-suppression assertion."
completed_at: 2026-03-29T19:13:43.825Z
blocker_discovered: false
---

# T02: Locked report-page regression coverage for canonical retrieval miss/search_failed fallback copy and PPT retrieval safety.

> Locked report-page regression coverage for canonical retrieval miss/search_failed fallback copy and PPT retrieval safety.

## What Happened
---
id: T02
parent: S03
milestone: M008
key_files:
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - .gsd/milestones/M008/slices/S03/tasks/T02-SUMMARY.md
key_decisions:
  - Treated canonical `effectiveness_snapshot.retrieval_facts` as the authority for miss/search_failed learner copy in the report-page suite.
  - Kept presentation coverage explicit about both hiding the retrieval section and skipping `/knowledge-check`.
duration: ""
verification_result: passed
completed_at: 2026-03-29T19:13:43.826Z
blocker_discovered: false
---

# T02: Locked report-page regression coverage for canonical retrieval miss/search_failed fallback copy and PPT retrieval safety.

**Locked report-page regression coverage for canonical retrieval miss/search_failed fallback copy and PPT retrieval safety.**

## What Happened

Expanded the focused report-page Vitest suite with canonical retrieval-facts fixtures for `status="miss"` and `status="search_failed"`, both under the default rejected supplemental knowledge-check path. The new assertions verify that the report page continues to render canonical retrieval truth, the correct miss/failure explanation, and the weak-evidence retrieval note directly from the unified report payload. I also tightened the presentation regression to assert that PPT reports keep the retrieval section absent while `getKnowledgeCheck` remains uncalled. The runtime code already matched the intended contract, so no production code changes were needed.

## Verification

Ran `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` and confirmed the focused report-page suite passed 17/17 tests, including the new canonical retrieval miss/search_failed fallback cases and the tightened PPT retrieval-suppression assertion.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 9500ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `.gsd/milestones/M008/slices/S03/tasks/T02-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
