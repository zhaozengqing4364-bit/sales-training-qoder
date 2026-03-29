# S02: Report/Replay 原始录音可查

**Goal:** Expose raw audio audit evidence on learner-facing report and replay routes. A shared backend read model builds a session-level audio-audit payload (summary + ordered segments with stable playback handoff paths) from SessionAudioSegment rows and voice_policy_snapshot.runtime_metrics.audio_audit. Both GET /practice/sessions/{id}/report and GET /sessions/{id}/replay include this payload. A segment playback route validates ownership and returns a short-lived signed GET redirect. Frontend renders a shared AudioAuditCard component on both report and replay pages.
**Demo:** After this: After this, a learner can open /practice/{sessionId}/report and see a raw audio audit section showing recording status, segment count, and playable segments. The same audio evidence is available in /sessions/{id}/replay.

## Tasks
- [x] **T01: Add shared audio-audit read model to report/replay payloads and segment playback handoff route** — Build a shared backend session-audio-audit read model and extend both report and replay payloads to include it. Add a segment playback handoff route that validates ownership and returns a short-lived signed GET redirect.

## Steps

1. Add typed Pydantic models for the audio-audit contract:
   - `AudioAuditSegmentSchema`: segment_sequence, created_at, duration_ms, size_bytes, upload_status, playback_path
   - `AudioAuditSummarySchema`: recording_status, total_segments, uploaded_segments, total_bytes, latest_segment_sequence, storage_prefix, last_uploaded_at, derived learner_status (available|partial|missing)
   - `AudioAuditPayloadSchema`: summary + list of segments

2. Create a shared helper function `build_session_audio_audit(db, session_id, session)` in `backend/src/common/api/practice.py` (or a new small module if practice.py is too large) that:
   - Queries SessionAudioSegment rows ordered by segment_sequence
   - Reads voice_policy_snapshot.runtime_metrics.audio_audit for the bounded summary
   - Computes derived learner_status: "available" if uploaded_count == total_count and total > 0, "partial" if some uploaded, "missing" if zero
   - Returns AudioAuditPayloadSchema
   - For each uploaded segment, sets playback_path to `/api/v1/sessions/{session_id}/audio-segments/{segment_sequence}` (stable handoff, not a signed URL)

3. Extend `SessionReport` schema in `backend/src/common/db/schemas.py` to add `audio_audit: AudioAuditPayloadSchema | None = None`

4. Extend `ReplayDataResponse` schema in `backend/src/common/conversation/schemas.py` to add `audio_audit: AudioAuditPayloadSchema | None = None`

5. In practice.py report builders (both the inline end-session builder and the GET report builder), call `build_session_audio_audit()` and set `audio_audit=` on the SessionReport.

6. In replay.py `get_replay_data()`, after building the replay_data dict, call `build_session_audio_audit()` and add `audio_audit` key.

7. Add a new playback handoff route on the /sessions router in `backend/src/common/conversation/api.py`:
   - `GET /sessions/{session_id}/audio-segments/{segment_sequence}`
   - Validates session ownership via _ensure_session_access
   - Queries SessionAudioSegment for the specific sequence
   - If not found or upload_status != "uploaded", returns 404 with diagnostic
   - Calls OssSigningService.generate_get_url(object_key) for a 1-hour signed GET
   - Returns RedirectResponse to the signed URL

## Must-Haves

- [ ] Shared build_session_audio_audit helper used by both report and replay
- [ ] AudioAuditPayloadSchema with summary (status, counts, bytes) and segments (sequence, duration, size, upload_status, playback_path)
- [ ] Derived learner_status computed from segment upload state
- [ ] Segment playback handoff route with ownership validation and signed GET redirect
- [ ] Signed URLs derived at read time, never persisted
  - Estimate: 2h
  - Files: backend/src/common/db/schemas.py, backend/src/common/conversation/schemas.py, backend/src/common/api/practice.py, backend/src/common/conversation/replay.py, backend/src/common/conversation/api.py, backend/src/common/oss/signing.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py tests/unit/test_oss_signing_service.py -v
- [ ] **T02: Frontend types + shared AudioAuditCard + report/replay integration** — Extend frontend TypeScript types for the new audio_audit payload, create a shared AudioAuditCard component, and integrate it into both report and replay pages.

## Steps

1. Extend `SessionEvidenceContract` in `web/src/lib/api/types.ts` to add `audio_audit?: AudioAuditPayload | null` where AudioAuditPayload mirrors the backend schema:
   - AudioAuditSegment: segment_sequence, created_at, duration_ms, size_bytes, upload_status, playback_path
   - AudioAuditSummary: recording_status, total_segments, uploaded_segments, total_bytes, latest_segment_sequence, storage_prefix, last_uploaded_at, status (available|partial|missing)
   - AudioAuditPayload: summary + AudioAuditSegment[]

2. Add `getSegmentAudioBlobUrl` method to `web/src/lib/api/client.ts` in the sessions namespace:
   - Takes sessionId + segmentSequence
   - Fetches `/sessions/{sessionId}/audio-segments/{segmentSequence}` with credentials
   - Returns blob URL (same pattern as existing getAudioBlobUrl for messages)

3. Create `web/src/components/audio/AudioAuditCard.tsx` — a shared component that:
   - Accepts `audioAudit: AudioAuditPayload | null | undefined`
   - When null/undefined or status=missing: renders "本次训练未录制原始音频" with a brief explanation
   - When status=available/partial: renders a card with:
     - Summary line: "原始录音" + segment count + total duration (formatted mm:ss from ms)
     - Status badge: "完整" for available, "部分" for partial
     - Ordered list of segments, each with play button using the playback handoff route
     - Audio playback uses HTML5 Audio element with blob URL from getSegmentAudioBlobUrl
   - Handles missing duration_ms gracefully (shows "未知时长")
   - Follows existing GlassCard/section styling from HighlightList

4. Integrate AudioAuditCard into `web/src/app/(user)/practice/[sessionId]/report/page.tsx`:
   - Add AudioAuditCard after the existing highlights/comprehensive-insights area
   - Pass report.audio_audit

5. Integrate AudioAuditCard into `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`:
   - Add AudioAuditCard between highlights and full-dialogue sections
   - Pass replayData.audio_audit

6. Update report page test to add audio_audit to baseReport mock and assert the audio audit section renders.

7. Update replay page test to add audio_audit to baseReplayData mock and assert the audio audit section renders.

## Must-Haves

- [ ] TypeScript types for AudioAuditPayload mirroring backend contract
- [ ] getSegmentAudioBlobUrl client method
- [ ] Shared AudioAuditCard component with available/partial/missing states
- [ ] Report page renders AudioAuditCard from report.audio_audit
- [ ] Replay page renders AudioAuditCard from replayData.audio_audit
- [ ] Empty/no-audio state is non-fatal and clear
- [ ] Existing report/replay functionality unaffected
  - Estimate: 2h
  - Files: web/src/lib/api/types.ts, web/src/lib/api/client.ts, web/src/components/audio/AudioAuditCard.tsx, web/src/app/(user)/practice/[sessionId]/report/page.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.tsx, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
- [ ] **T03: Focused contract regression for audio-audit evidence chain** — Add dedicated backend contract tests proving the audio-audit read model, playback handoff, and ownership semantics. Add frontend test assertions proving report and replay render audio audit sections correctly.

## Steps

1. Add backend contract tests in `backend/tests/contract/test_practice_evidence_contract.py` (extend existing file):
   - Test that report payload for a session with uploaded audio segments includes audio_audit with correct summary (status=available, segment count, total bytes)
   - Test that report payload for a session with no segments includes audio_audit with status=missing
   - Test that report payload for a session with partial uploads shows status=partial
   - Test that replay payload after completion includes the same audio_audit structure
   - Test that segment playback route returns signed redirect (307) for uploaded segment with correct ownership
   - Test that segment playback route returns 404 for non-existent segment sequence
   - Test that outsider user gets 403 on playback route
   - Test that signed GET URLs are never persisted in DB state

2. Add frontend test assertions in report page test:
   - Add audio_audit to baseReport mock with available status and 2 segments
   - Assert "原始录音" heading is visible
   - Assert segment count is displayed
   - Assert play buttons are rendered
   - Add test for missing audio state: no audio_audit → renders "本次训练未录制原始音频"
   - Assert existing report assertions still pass

3. Add frontend test assertions in replay page test:
   - Add audio_audit to baseReplayData mock
   - Assert audio audit section renders without breaking highlights/full-dialogue
   - Assert existing blocked replay behavior still renders the current explicit message

## Must-Haves

- [ ] Backend contract tests for report/replay audio_audit inclusion with available/partial/missing states
- [ ] Backend contract tests for playback handoff (signed redirect, 404, 403)
- [ ] Frontend report test asserts audio audit section renders
- [ ] Frontend replay test asserts audio audit section renders without regressions
- [ ] All existing tests continue to pass
  - Estimate: 1.5h
  - Files: backend/tests/contract/test_practice_evidence_contract.py, web/src/app/(user)/practice/[sessionId]/report/page.test.tsx, web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -v -k audio_audit
