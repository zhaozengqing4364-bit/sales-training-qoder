---
id: T02
parent: S02
milestone: M009
provides: []
requires: []
affects: []
key_files: ["web/src/lib/api/types.ts", "web/src/lib/api/client.ts", "web/src/components/audio/AudioAuditCard.tsx", "web/src/app/(user)/practice/[sessionId]/report/page.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.tsx", "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", ".gsd/milestones/M009/slices/S02/tasks/T02-SUMMARY.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["AudioAuditCard treats backend `audio_audit.summary.learner_status` as canonical while tolerating optional `summary.status` as a defensive alias.", "Report and replay surfaces both mount the same shared AudioAuditCard and rely on the same `audio_audit` payload shape plus `getSegmentAudioBlobUrl(...)` playback helper."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Focused slice verification passed via `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (27 tests green). Additional browser verification on the local Next dev server confirmed the replay route rendered the new audio-audit card, title, summary, and unknown-duration fallback under mocked local API responses. The report-route browser pass was attempted with the same local mock strategy but aborted during navigation; no functional regression was reproduced in the passing page-level test suite."
completed_at: 2026-03-29T22:29:04.045Z
blocker_discovered: false
---

# T02: Added shared audio-audit UI and contract wiring to learner report and replay pages.

> Added shared audio-audit UI and contract wiring to learner report and replay pages.

## What Happened
---
id: T02
parent: S02
milestone: M009
key_files:
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
  - web/src/components/audio/AudioAuditCard.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/milestones/M009/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - AudioAuditCard treats backend `audio_audit.summary.learner_status` as canonical while tolerating optional `summary.status` as a defensive alias.
  - Report and replay surfaces both mount the same shared AudioAuditCard and rely on the same `audio_audit` payload shape plus `getSegmentAudioBlobUrl(...)` playback helper.
duration: ""
verification_result: mixed
completed_at: 2026-03-29T22:29:04.046Z
blocker_discovered: false
---

# T02: Added shared audio-audit UI and contract wiring to learner report and replay pages.

**Added shared audio-audit UI and contract wiring to learner report and replay pages.**

## What Happened

Extended the frontend evidence contract with audio-audit types, added a segment-audio blob helper to the shared API client, and built a reusable AudioAuditCard for learner-facing raw audio evidence. Wired the shared card into both report and replay routes, including available/partial/missing states, aggregate duration formatting, per-segment playback, and graceful unknown-duration rendering. Updated both page-level test suites with concrete `audio_audit` payloads and stubs for the new playback helper so the shared card is exercised on both surfaces. Recorded the backend/frontend field-name mismatch (`learner_status` vs task-plan `status`) in knowledge and handled it defensively in the component without changing the backend authority seam.

## Verification

Focused slice verification passed via `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (27 tests green). Additional browser verification on the local Next dev server confirmed the replay route rendered the new audio-audit card, title, summary, and unknown-duration fallback under mocked local API responses. The report-route browser pass was attempted with the same local mock strategy but aborted during navigation; no functional regression was reproduced in the passing page-level test suite.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 1420ms |
| 2 | `browser_verify http://localhost:3445/practice/session-1/replay` | 0 | ✅ pass | 15000ms |
| 3 | `browser_verify http://localhost:3445/practice/session-1/report` | 1 | ❌ fail | 15000ms |


## Deviations

Accepted `audio_audit.summary.status` as an optional frontend alias in addition to the shipped backend `learner_status` field so task-plan wording and live payloads do not drift. Browser verification of the report route hit a transient navigation abort; replay browser proof passed and focused Vitest remained the authoritative gate.

## Known Issues

Automated browser verification of `/practice/session-1/report` hit a transient `net::ERR_ABORTED` during navigation in this session. Replay browser proof passed, and the focused report/replay Vitest suites passed with the new audio-audit assertions.

## Files Created/Modified

- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `web/src/components/audio/AudioAuditCard.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `.gsd/milestones/M009/slices/S02/tasks/T02-SUMMARY.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Accepted `audio_audit.summary.status` as an optional frontend alias in addition to the shipped backend `learner_status` field so task-plan wording and live payloads do not drift. Browser verification of the report route hit a transient navigation abort; replay browser proof passed and focused Vitest remained the authoritative gate.

## Known Issues
Automated browser verification of `/practice/session-1/report` hit a transient `net::ERR_ABORTED` during navigation in this session. Replay browser proof passed, and the focused report/replay Vitest suites passed with the new audio-audit assertions.
