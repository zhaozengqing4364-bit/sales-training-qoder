---
id: T02
parent: S03
milestone: M009
provides: []
requires: []
affects: []
key_files: ["web/src/components/audio/AudioAuditCard.tsx", "web/src/lib/api/client.ts", "web/src/lib/api/types.ts", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", "web/src/lib/api/client.auth.test.ts", ".gsd/milestones/M009/slices/S03/tasks/T02-SUMMARY.md"]
key_decisions: ["AudioAuditCard maps canonical degraded_reasons tokens locally to stable Chinese learner copy instead of deriving wording from upload counts.", "Segment playback preserves backend error codes across api.sessions.getSegmentAudioBlobUrl(...) and resolves learner-facing playback copy in SegmentPlayer."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the focused Vitest suite for the report page, replay page, and API-client regression coverage. All targeted tests passed, including the new degraded audio wording assertions and the structured segment playback error assertion."
completed_at: 2026-03-29T23:36:03.016Z
blocker_discovered: false
---

# T02: Shipped canonical degraded audio wording in the shared AudioAuditCard and preserved structured segment playback error codes through the web API client.

> Shipped canonical degraded audio wording in the shared AudioAuditCard and preserved structured segment playback error codes through the web API client.

## What Happened
---
id: T02
parent: S03
milestone: M009
key_files:
  - web/src/components/audio/AudioAuditCard.tsx
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/lib/api/client.auth.test.ts
  - .gsd/milestones/M009/slices/S03/tasks/T02-SUMMARY.md
key_decisions:
  - AudioAuditCard maps canonical degraded_reasons tokens locally to stable Chinese learner copy instead of deriving wording from upload counts.
  - Segment playback preserves backend error codes across api.sessions.getSegmentAudioBlobUrl(...) and resolves learner-facing playback copy in SegmentPlayer.
duration: ""
verification_result: passed
completed_at: 2026-03-29T23:36:03.016Z
blocker_discovered: false
---

# T02: Shipped canonical degraded audio wording in the shared AudioAuditCard and preserved structured segment playback error codes through the web API client.

**Shipped canonical degraded audio wording in the shared AudioAuditCard and preserved structured segment playback error codes through the web API client.**

## What Happened

Aligned the shared learner audio-audit UI with the enriched backend payload by extending the frontend audio-audit types, rendering explicit degraded wording for partial audio sessions, and showing per-segment failure text when an upload failed. Updated the segment playback client to extract backend error/error_code values from non-OK JSON responses so the UI can distinguish upload/signing/not-found failures instead of collapsing everything to HTTP status. Added focused report/replay tests for the shared degraded wording and a direct API-client regression test for structured error propagation. Focused web verification passed.

## Verification

Ran the focused Vitest suite for the report page, replay page, and API-client regression coverage. All targeted tests passed, including the new degraded audio wording assertions and the structured segment playback error assertion.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd /Users/zhaozengqing/github/销售训练qoder/web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/lib/api/client.auth.test.ts'` | 0 | ✅ pass | 17400ms |


## Deviations

Added a small direct API-client regression test in web/src/lib/api/client.auth.test.ts to lock structured segment playback error propagation. The task plan only called for report/replay page tests, but the client seam was the most stable place to prove the fetch-boundary fix.

## Known Issues

None.

## Files Created/Modified

- `web/src/components/audio/AudioAuditCard.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/lib/api/client.auth.test.ts`
- `.gsd/milestones/M009/slices/S03/tasks/T02-SUMMARY.md`


## Deviations
Added a small direct API-client regression test in web/src/lib/api/client.auth.test.ts to lock structured segment playback error propagation. The task plan only called for report/replay page tests, but the client seam was the most stable place to prove the fetch-boundary fix.

## Known Issues
None.
