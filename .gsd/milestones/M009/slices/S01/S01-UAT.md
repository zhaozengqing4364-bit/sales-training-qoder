# S01: OSS 直传音频留痕基础链路 — UAT

**Milestone:** M009
**Written:** 2026-03-29T21:22:36.004Z

# S01 UAT: OSS 直传音频留痕基础链路

## Preconditions
- Backend running on `localhost:3444` with `ALI_OSS_ENDPOINT`, `ALI_OSS_ACCESS_KEY_ID`, `ALI_OSS_ACCESS_KEY_SECRET`, `ALI_OSS_BUCKET` env vars set
- Frontend running on `localhost:3445`
- User logged in via dev-login
- Alembic migrated to head (includes `20260328_1000_022`)

## Test Cases

### TC-01: Signing service returns presigned PUT URL
1. `POST /api/v1/practice/sessions/{sessionId}/audio-upload-urls` with body `{content_type: "audio/webm", segment_sequence: 1}`
2. **Expected**: 200 with `{upload_url: "https://...aliyuncs.com/...", object_key: "audio/{sessionId}/seg_001.webm"}`
3. The returned URL should be a valid HTTPS PUT URL on the configured OSS bucket

### TC-02: Segment metadata registration is idempotent
1. `POST /api/v1/practice/sessions/{sessionId}/audio-segments` with body `{segment_sequence: 1, object_key: "audio/.../seg_001.webm", content_type: "audio/webm", size_bytes: 204800, duration_ms: 15000}`
2. **Expected**: 200 with registered segment metadata
3. Repeat the same call with same segment_sequence
4. **Expected**: 200 (idempotent upsert, no duplicate rows)

### TC-03: Segments list ordered by sequence
1. Register segments with sequence 1, 3, 2 (out of order)
2. `GET /api/v1/practice/sessions/{sessionId}/audio-segments`
3. **Expected**: 200 with segments ordered [1, 2, 3]

### TC-04: Outsider denied access
1. Create a session owned by user A
2. Authenticate as user B
3. Call `POST .../audio-upload-urls` on user A's session
4. **Expected**: 403 Forbidden
5. Call `GET .../audio-segments` on user A's session
6. **Expected**: 403 Forbidden

### TC-05: First segment initializes audio_url
1. Session with `audio_url = null`
2. Register first segment
3. **Expected**: Session's `audio_url` updated to storage prefix derived from object key

### TC-06: Audio-audit metrics persisted on session snapshot
1. Register multiple segments
2. Fetch session detail
3. **Expected**: `voice_policy_snapshot.runtime_metrics.audio_audit` contains `{segment_count, total_bytes, latest_sequence, latest_object_key, storage_prefix}`

### TC-07: OSS not configured returns 503
1. Remove ALI_OSS_BUCKET env var
2. Call `POST .../audio-upload-urls`
3. **Expected**: 503 with error message indicating OSS not configured

### TC-08: Frontend hook starts/stops with recording toggle
1. Navigate to `/practice/{sessionId}` (active session)
2. Click recording toggle to start
3. **Expected**: MediaRecorder begins capturing audio, upload pipeline starts
4. Wait ~16 seconds for first segment to fire
5. **Expected**: Backend receives signed URL request, segment registration
6. Click recording toggle to stop
7. **Expected**: Final segment uploaded, MediaRecorder cleaned up

### TC-09: Upload failure does not stop recording
1. Mock OSS PUT to return 500
2. Start recording
3. **Expected**: First segment upload fails, `lastError` updated, but recording continues
4. Wait for second segment
5. **Expected**: Second segment attempt made despite prior failure

### TC-10: Session terminal state stops uploader
1. Start recording on active session
2. End the session (via lifecycle API or completion)
3. **Expected**: Uploader receives terminal status, calls stopUpload, cleans up MediaRecorder stream

## Edge Cases
- Zero-size blob from MediaRecorder should be filtered (no upload or registration)
- Negative segment_sequence should return 422
- Missing object_key in registration body should return 422
- Non-existent session should return 404

