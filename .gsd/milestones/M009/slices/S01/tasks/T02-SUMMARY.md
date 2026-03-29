---
id: T02
parent: S01
milestone: M009
provides: []
requires: []
affects: []
key_files: ["web/src/hooks/use-continuous-audio-uploader.ts", "web/src/hooks/use-continuous-audio-uploader.test.ts"]
key_decisions: ["Upload errors use fire-and-forget pattern (void uploadSegment) so recording continues uninterrupted", "Segment sequence increments eagerly before upload completes, matching MediaRecorder timeslice semantics", "Hook uses raw fetch() for API calls instead of the shared api object to avoid auth-retry side effects in fire-and-forget context"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran `cd web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts` — 13/13 tests pass. Tests cover start/stop lifecycle, segment increment, full sign→PUT→register flow, upload failure resilience (503, OSS PUT fail, 401), zero-size blob filtering, MediaRecorder error, double-start guard, and mic permission denial."
completed_at: 2026-03-29T20:55:35.553Z
blocker_discovered: false
---

# T02: Add useContinuousAudioUploader hook with 15s segment splitting, OSS presigned-URL upload, and backend metadata registration

> Add useContinuousAudioUploader hook with 15s segment splitting, OSS presigned-URL upload, and backend metadata registration

## What Happened
---
id: T02
parent: S01
milestone: M009
key_files:
  - web/src/hooks/use-continuous-audio-uploader.ts
  - web/src/hooks/use-continuous-audio-uploader.test.ts
key_decisions:
  - Upload errors use fire-and-forget pattern (void uploadSegment) so recording continues uninterrupted
  - Segment sequence increments eagerly before upload completes, matching MediaRecorder timeslice semantics
  - Hook uses raw fetch() for API calls instead of the shared api object to avoid auth-retry side effects in fire-and-forget context
duration: ""
verification_result: passed
completed_at: 2026-03-29T20:55:35.554Z
blocker_discovered: false
---

# T02: Add useContinuousAudioUploader hook with 15s segment splitting, OSS presigned-URL upload, and backend metadata registration

**Add useContinuousAudioUploader hook with 15s segment splitting, OSS presigned-URL upload, and backend metadata registration**

## What Happened

Built the `useContinuousAudioUploader` React hook (`web/src/hooks/use-continuous-audio-uploader.ts`) and its test suite (`web/src/hooks/use-continuous-audio-uploader.test.ts`).

The hook captures browser microphone audio via `MediaRecorder` with `audio/webm;codecs=opus` (with fallback to plain `audio/webm`), using `timeslice=15000` to produce ~15-second segments. Each `ondataavailable` event triggers a fire-and-forget `uploadSegment()` that: (1) calls `POST /api/v1/practice/sessions/{id}/audio-upload-urls` to get a presigned PUT URL, (2) PUTs the blob directly to OSS, (3) calls `POST /api/v1/practice/sessions/{id}/audio-segments` to register metadata. Upload failures are caught and surfaced via `lastError` without interrupting the recording loop.

The hook exposes: `{isUploading, segmentCount, lastError, uploadStatus, startUpload, stopUpload}`. State machine: idle → uploading → stopped/error. `startUpload()` requests mic permission, creates MediaRecorder, and begins capture. `stopUpload()` calls `recorder.stop()`, waits for final `ondataavailable`, then cleans up the stream. Double-start is guarded via ref.

13 unit tests cover: start/stop lifecycle, segment sequence increment through timeslice events, presigned URL flow (sign → PUT → register metadata), 503 signing failure resilience, OSS PUT failure handling, 401 error propagation to lastError, zero-size blob filtering, MediaRecorder runtime error, double-start guard, and microphone permission denial. All pass.

## Verification

Ran `cd web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts` — 13/13 tests pass. Tests cover start/stop lifecycle, segment increment, full sign→PUT→register flow, upload failure resilience (503, OSS PUT fail, 401), zero-size blob filtering, MediaRecorder error, double-start guard, and mic permission denial.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts` | 0 | ✅ pass | 1800ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `web/src/hooks/use-continuous-audio-uploader.ts`
- `web/src/hooks/use-continuous-audio-uploader.test.ts`


## Deviations
None.

## Known Issues
None.
