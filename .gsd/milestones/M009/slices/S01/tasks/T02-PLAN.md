---
estimated_steps: 5
estimated_files: 2
skills_used: []
---

# T02: Build frontend useContinuousAudioUploader hook with segment splitting

**Slice:** S01 — OSS 直传音频留痕基础链路
**Milestone:** M009

## Description

Create a React hook (`useContinuousAudioUploader`) that captures browser microphone audio using `MediaRecorder` in webm/opus format, automatically splits it into ~15-second segments, requests signed PUT URLs from the backend for each segment, uploads directly to Alibaba Cloud OSS, and notifies the backend to register metadata.

This hook runs alongside the existing `useAudioRecorder` hook (which handles real-time PCM streaming to the WebSocket for ASR). While `useAudioRecorder` feeds chunks to the conversation engine, `useContinuousAudioUploader` creates durable audio audit trail segments on OSS.

## Steps

1. Create `web/src/hooks/use-continuous-audio-uploader.ts`:
   - Accepts `sessionId: string`, `enabled: boolean` props
   - Uses `MediaRecorder` API with `audio/webm;codecs=opus` mime type
   - Captures audio from `navigator.mediaDevices.getUserMedia({audio: true})`
   - Sets `MediaRecorder` `timeslice=15000` to produce ~15s blobs
   - On each `ondataavailable` event with `timeslice`:
     a. Call `POST /api/v1/practice/sessions/{sessionId}/audio-upload-urls` with `{segment_sequence, content_type}`
     b. Receive `{url, object_key, expires_at}`
     c. PUT the blob directly to the signed URL (using fetch with Content-Type header)
     d. On success, call `POST /api/v1/practice/sessions/{sessionId}/audio-segments` with `{segment_sequence, object_key, size_bytes}`
     e. On failure, increment error count and continue (don't block recording)
   - Exposes: `{isUploading, segmentCount, lastError, startUpload, stopUpload, uploadStatus}`
   - `startUpload()`: request mic permission, create MediaRecorder, begin capture
   - `stopUpload()`: call `recorder.stop()`, wait for final `ondataavailable`, then cleanup
   - Auto-increments segment_sequence starting from 0

2. Create `web/src/hooks/use-continuous-audio-uploader.test.ts`:
   - Mock `navigator.mediaDevices.getUserMedia` and `MediaRecorder`
   - Mock `fetch` for backend API calls and OSS PUT
   - Test: hook starts uploading when `enabled=true` and `startUpload()` called
   - Test: segments increment correctly through timeslice events
   - Test: upload failure doesn't crash hook, error state is set
   - Test: `stopUpload()` finalizes and cleans up
   - Test: backend 401/403 propagates to lastError

## Must-Haves

- [ ] `useContinuousAudioUploader` hook captures webm/opus audio via MediaRecorder
- [ ] 15-second segment splitting via MediaRecorder timeslice
- [ ] Each segment: request signed URL → PUT to OSS → register metadata with backend
- [ ] Upload failures don't crash the recording loop; error exposed via `lastError`
- [ ] `startUpload` / `stopUpload` lifecycle cleanly manages MediaRecorder
- [ ] Unit tests cover: segment flow, error handling, cleanup

## Verification

- `cd web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts`

## Observability Impact

- Signals added: hook exposes `segmentCount`, `uploadStatus` ("idle"|"uploading"|"error"|"stopped"), `lastError` for UI display
- How a future agent inspects: browser console logs segment sequence and upload result per segment
- Failure state exposed: `lastError` string with segment sequence number on failure

## Inputs

- `web/src/lib/api/client.ts` — existing API client for backend calls
- `web/src/lib/api/types.ts` — existing API types (session type with audio_url)

## Expected Output

- `web/src/hooks/use-continuous-audio-uploader.ts` — the hook implementation
- `web/src/hooks/use-continuous-audio-uploader.test.ts` — unit tests
