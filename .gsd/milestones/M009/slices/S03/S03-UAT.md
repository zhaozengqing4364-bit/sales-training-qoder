# S03: 音频审计降级与诊断 — UAT

**Milestone:** M009
**Written:** 2026-03-29T23:48:32.060Z

# S03 UAT: 音频审计降级与诊断

## Preconditions
- Backend running on `localhost:3444` with Alembic at head (includes `session_audio_segments` table).
- Frontend running on `localhost:3445`.
- ALI_OSS_BUCKET and related env vars set (or mocked for contract tests).
- A completed practice session exists with at least some audio segments in various states.

## Test Cases

### TC-01: Failure registration endpoint registers failed segments
**Setup:** Create a practice session with audio segments (some uploaded, some pending).
**Steps:**
1. `POST /api/v1/practice/sessions/{id}/audio-segments/failure` with `segment_sequence=2&error_token=oss_put_failed`
2. `GET /api/v1/practice/sessions/{id}/audio-audit`
**Expected:**
- Step 1 returns 200, segment 2 has `upload_status='failed'`, `error_message='oss_put_failed'`
- Step 2 response includes `degraded_reasons` containing `"upload_failed"`, `failed_segments` count ≥ 1
- Already-uploaded segments remain `upload_status='uploaded'`

### TC-02: Failure endpoint preserves uploaded segments
**Setup:** Session with segment 1 uploaded, segment 2 pending.
**Steps:**
1. `POST /audio-segments/failure` for segment 1 (already uploaded) with `error_token=network_error`
2. `GET /audio-audit`
**Expected:**
- Step 1 returns 200 but segment 1 retains `upload_status='uploaded'` (not overwritten)
- Only segment 2 can be marked as failed if it was pending

### TC-03: Closed error token validation
**Setup:** Active session with audio segments.
**Steps:**
1. `POST /audio-segments/failure` with `error_token=invalid_token`
**Expected:**
- Returns 422 or 400 with validation error
- No segments are modified

### TC-04: Report page shows degraded wording for partial audio
**Setup:** Session where some segments failed.
**Steps:**
1. Navigate to `/practice/{sessionId}/report`
2. Locate the AudioAuditCard section
**Expected:**
- Card shows differentiated Chinese wording for partial audio (e.g., "部分录音上传失败" or similar degraded copy)
- Per-segment failure messages are visible for failed segments
- Successful segments remain playable

### TC-05: Report page shows missing audio wording
**Setup:** Session with no audio segments at all (`audio_audit: null`).
**Steps:**
1. Navigate to `/practice/{sessionId}/report`
2. Locate the AudioAuditCard section
**Expected:**
- Card shows "本次训练未录制原始音频" or equivalent missing-audio fallback wording

### TC-06: Replay page mirrors degraded wording
**Setup:** Same session as TC-04.
**Steps:**
1. Navigate to `/practice/{sessionId}/replay`
2. Locate the audio audit section
**Expected:**
- Same degraded wording as report page
- Per-segment failure details visible

### TC-07: Segment playback preserves structured error codes
**Setup:** Session with a failed segment.
**Steps:**
1. Attempt playback of a failed segment via `GET /api/v1/practice/sessions/{id}/audio-segments/{seq}/blob-url`
**Expected:**
- Returns structured error with `error_code` (e.g., `signing_failed`, `oss_put_failed`) not generic HTTP status
- Frontend SegmentPlayer shows specific failure copy per error code

### TC-08: Support runtime surfaces audio_upload_degraded anomaly
**Setup:** Session where >0 but <50% segments failed.
**Steps:**
1. `GET /api/v1/support/runtime/overview` or faults endpoint
**Expected:**
- Response includes anomaly kind `audio_upload_degraded` with severity `warning`
- Anomaly description references partial upload failure

### TC-09: Support runtime escalates to blocking for severe degradation
**Setup:** Session where >50% segments failed.
**Steps:**
1. `GET /api/v1/support/runtime/overview` or faults endpoint
**Expected:**
- Response includes anomaly kind `audio_upload_degraded` with severity `blocking`
- Anomaly description references majority upload failure

### TC-10: Support runtime surfaces audio_missing anomaly
**Setup:** Session where all audio segments failed.
**Steps:**
1. `GET /api/v1/support/runtime/overview` or faults endpoint
**Expected:**
- Response includes anomaly kind `audio_missing` with severity `warning`
- Anomaly description references complete audio loss

### TC-11: Support runtime handles missing/empty audio_audit gracefully
**Setup:** Session with no `voice_policy_snapshot.runtime_metrics.audio_audit` data.
**Steps:**
1. `GET /api/v1/support/runtime/overview`
**Expected:**
- No audio anomaly kinds emitted
- No crashes or errors from `_extract_audio_diagnostics()`

### TC-12: Voice policy snapshot preserves failure metrics
**Setup:** Session with failed segments.
**Steps:**
1. `POST /audio-segments/failure` for multiple segments
2. `GET /api/v1/practice/sessions/{id}` to inspect `voice_policy_snapshot.runtime_metrics.audio_audit`
**Expected:**
- `audio_audit` contains `failed_segment_count` matching the number of failed registrations
- Other runtime metrics are preserved (not overwritten)

