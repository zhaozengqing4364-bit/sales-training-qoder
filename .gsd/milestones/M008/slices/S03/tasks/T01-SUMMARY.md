---
id: T01
parent: S03
milestone: M008
provides: []
requires: []
affects: []
key_files: ["web/src/lib/api/types.ts", "web/src/lib/session-evidence.ts", "web/src/app/(user)/practice/[sessionId]/report/page.tsx", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", ".gsd/milestones/M008/slices/S03/tasks/T01-SUMMARY.md"]
key_decisions: ["Made `report.effectiveness_snapshot.retrieval_facts` the learner-facing authority for retrieval truth on the report page.", "Kept `/knowledge-check` as a supplemental fetch only, so its failure no longer hides canonical retrieval facts."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Passed the slice task verification command `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` after adding canonical retrieval fixtures. The suite finished with 15/15 tests passing, covering the new retrieval-truth rendering behavior and existing report-page regressions."
completed_at: 2026-03-29T19:04:35.930Z
blocker_discovered: false
---

# T01: Rendered canonical retrieval truth on the report page from `effectiveness_snapshot.retrieval_facts` with focused regression coverage.

> Rendered canonical retrieval truth on the report page from `effectiveness_snapshot.retrieval_facts` with focused regression coverage.

## What Happened
---
id: T01
parent: S03
milestone: M008
key_files:
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - .gsd/milestones/M008/slices/S03/tasks/T01-SUMMARY.md
key_decisions:
  - Made `report.effectiveness_snapshot.retrieval_facts` the learner-facing authority for retrieval truth on the report page.
  - Kept `/knowledge-check` as a supplemental fetch only, so its failure no longer hides canonical retrieval facts.
duration: ""
verification_result: passed
completed_at: 2026-03-29T19:04:35.931Z
blocker_discovered: false
---

# T01: Rendered canonical retrieval truth on the report page from `effectiveness_snapshot.retrieval_facts` with focused regression coverage.

**Rendered canonical retrieval truth on the report page from `effectiveness_snapshot.retrieval_facts` with focused regression coverage.**

## What Happened

Added typed retrieval-facts support on the frontend, normalized canonical retrieval payloads through shared session-evidence helpers, and rewired the report page so the sales knowledge section renders from `effectiveness_snapshot.retrieval_facts` instead of depending on `/knowledge-check`. The report now keeps claim-truth messaging separate, renders bounded latest-attempt/result-summary copy when present, omits the retrieval card when canonical facts are absent, and survives malformed latest-attempt data by only showing normalized fields. Focused Vitest coverage now proves canonical retrieval hit + weak-evidence coexistence, omission when retrieval facts are absent, and continued rendering when the supplemental knowledge-check request rejects.

## Verification

Passed the slice task verification command `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` after adding canonical retrieval fixtures. The suite finished with 15/15 tests passing, covering the new retrieval-truth rendering behavior and existing report-page regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 17300ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `.gsd/milestones/M008/slices/S03/tasks/T01-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
