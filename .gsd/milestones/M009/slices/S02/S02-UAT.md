# S02: Report/Replay 原始录音可查 — UAT

**Milestone:** M009
**Written:** 2026-03-29T22:45:26.811Z

# S02 UAT: Report/Replay 原始录音可查

## Preconditions
- Backend running on localhost:3444 with latest migrations applied (`session_audio_segments` table exists)
- Frontend dev server running on localhost:3445
- At least one completed session with uploaded audio segments (from S01 flow)
- At least one completed session with NO audio segments (legacy session)

---

## Test Case 1: Report page shows audio audit for session with uploaded segments

**Precondition:** Session `SID_WITH_AUDIO` has ≥2 uploaded `SessionAudioSegment` rows.

1. Navigate to `/practice/{SID_WITH_AUDIO}/report`
2. **Expected:** Page renders normally with existing report sections
3. **Expected:** A section titled "原始录音" appears below highlights/comprehensive-insights
4. **Expected:** Section shows segment count (e.g., "共 2 段录音")
5. **Expected:** Each segment has a play button
6. **Expected:** Status badge reads "完整" (all uploaded) or "部分" (partial uploads)
7. **Expected:** Total duration is displayed in mm:ss format (or "未知时长" if duration_ms missing)

## Test Case 2: Report page shows missing-audio state for session without segments

**Precondition:** Session `SID_NO_AUDIO` has zero `SessionAudioSegment` rows.

1. Navigate to `/practice/{SID_NO_AUDIO}/report`
2. **Expected:** Page renders normally with existing report sections
3. **Expected:** A section shows "本次训练未录制原始音频" with brief explanation
4. **Expected:** No play buttons or segment list rendered

## Test Case 3: Replay page shows audio audit for session with uploaded segments

**Precondition:** Session `SID_WITH_AUDIO` is completed and has uploaded segments.

1. Navigate to `/practice/{SID_WITH_AUDIO}/replay`
2. **Expected:** Page renders normally with existing replay sections (highlights, full dialogue)
3. **Expected:** Audio audit section appears between highlights and full-dialogue areas
4. **Expected:** Same audio audit content as report page (shared AudioAuditCard)

## Test Case 4: Replay page shows missing-audio state for session without segments

**Precondition:** Session `SID_NO_AUDIO` is completed and has zero audio segments.

1. Navigate to `/practice/{SID_NO_AUDIO}/replay`
2. **Expected:** Page renders normally
3. **Expected:** "本次训练未录制原始音频" text visible

## Test Case 5: Segment playback handoff returns signed redirect

**Precondition:** Session `SID_WITH_AUDIO` has an uploaded segment at sequence 1.

1. `GET /api/v1/sessions/{SID_WITH_AUDIO}/audio-segments/1` (authenticated as session owner)
2. **Expected:** 307 redirect to a short-lived signed OSS URL
3. **Expected:** Signed URL expires within ~1 hour
4. **Expected:** Following redirect returns the audio blob

## Test Case 6: Segment playback rejects unauthorized access

1. `GET /api/v1/sessions/{SID_WITH_AUDIO}/audio-segments/1` (authenticated as different user)
2. **Expected:** 403 Forbidden

## Test Case 7: Segment playback returns 404 for missing segment

1. `GET /api/v1/sessions/{SID_WITH_AUDIO}/audio-segments/999` (authenticated as session owner)
2. **Expected:** 404 with diagnostic message

## Test Case 8: Signed URLs never appear in persisted state

**Precondition:** Any session with audio segments.

1. `GET /api/v1/practice/sessions/{SID}/report` — verify `audio_audit.segments[*].playback_path` contains stable `/api/v1/sessions/...` paths, NOT `https://oss-...` signed URLs
2. `GET /api/v1/sessions/{SID}/replay` — same check on `audio_audit.segments[*].playback_path`
3. **Expected:** No signed URLs in any persisted or returned payload field; signing only happens at playback time

## Test Case 9: Existing report/replay functionality unaffected

1. Open report page for any session — verify existing sections (result, main_issue, next_goal, evidence, highlights) render correctly
2. Open replay page for any completed session — verify highlights, full dialogue, and deep-link anchors still work
3. **Expected:** No regressions in existing functionality

