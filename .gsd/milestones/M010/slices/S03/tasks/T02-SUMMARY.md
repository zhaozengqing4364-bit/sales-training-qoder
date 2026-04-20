---
id: T02
parent: S03
milestone: M010
provides: []
requires: []
affects: []
key_files: ["web/src/app/(user)/practice/[sessionId]/replay/page.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", ".gsd/milestones/M010/slices/S03/tasks/T02-SUMMARY.md"]
key_decisions: ["Replay uses replayData.conclusion_evidence and replayData.evidence_degradation as the canonical provenance/degradation source, while the report snapshot remains retry-metadata-only.", "Cross-page learner evidence vocabulary stays helper-owned in session-evidence.ts and is defended by paired report/replay focused tests."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the planned slice verification command `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`. The focused gate passed with 33/33 Vitest tests green, covering shared provenance/degradation vocabulary, malformed replay inputs, stale report-snapshot non-authority, replay completion-gate behavior, retry CTA behavior, highlight/deep-link anchors, and presentation suppression."
completed_at: 2026-03-30T08:04:19.091Z
blocker_discovered: false
---

# T02: Replay now renders canonical helper-owned provenance/degradation copy and ignores stale report snapshots for those surfaces.

> Replay now renders canonical helper-owned provenance/degradation copy and ignores stale report snapshots for those surfaces.

## What Happened
---
id: T02
parent: S03
milestone: M010
key_files:
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/milestones/M010/slices/S03/tasks/T02-SUMMARY.md
key_decisions:
  - Replay uses replayData.conclusion_evidence and replayData.evidence_degradation as the canonical provenance/degradation source, while the report snapshot remains retry-metadata-only.
  - Cross-page learner evidence vocabulary stays helper-owned in session-evidence.ts and is defended by paired report/replay focused tests.
duration: ""
verification_result: passed
completed_at: 2026-03-30T08:04:19.091Z
blocker_discovered: false
---

# T02: Replay now renders canonical helper-owned provenance/degradation copy and ignores stale report snapshots for those surfaces.

**Replay now renders canonical helper-owned provenance/degradation copy and ignores stale report snapshots for those surfaces.**

## What Happened

Updated the learner replay page to render conclusion provenance and four-layer degradation from canonical replay payload fields through the shared session-evidence helper seam established in T01. Preserved replay-specific behavior for retry metadata, anchor banners, highlights, audio audit, and presentation flows, while ensuring presentation sessions still suppress the sales-only sections when replay returns null. Expanded replay tests with happy-path parity, malformed replay payload omission, stale report snapshot non-authority, degraded-layer rendering, and presentation-null assertions, then reran the paired report/replay suite as the slice gate.

## Verification

Ran the planned slice verification command `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`. The focused gate passed with 33/33 Vitest tests green, covering shared provenance/degradation vocabulary, malformed replay inputs, stale report-snapshot non-authority, replay completion-gate behavior, retry CTA behavior, highlight/deep-link anchors, and presentation suppression.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` | 0 | ✅ pass | 9200ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `.gsd/milestones/M010/slices/S03/tasks/T02-SUMMARY.md`


## Deviations
None.

## Known Issues
None.
