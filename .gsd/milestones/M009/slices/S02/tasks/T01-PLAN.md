---
estimated_steps: 29
estimated_files: 6
skills_used: []
---

# T01: Backend shared audio-audit read model + payload extension + playback handoff

Build a shared backend session-audio-audit read model and extend both report and replay payloads to include it. Add a segment playback handoff route that validates ownership and returns a short-lived signed GET redirect.

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

## Inputs

- `backend/src/common/db/schemas.py`
- `backend/src/common/conversation/schemas.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/api.py`
- `backend/src/common/oss/signing.py`
- `backend/src/common/db/models.py`

## Expected Output

- `backend/src/common/db/schemas.py`
- `backend/src/common/conversation/schemas.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/api.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py tests/unit/test_oss_signing_service.py -v

## Observability Impact

Signals added: audio_audit payload in report/replay response including segment_count, derived status, and per-segment playback paths. Inspection: GET /practice/sessions/{id}/report and GET /sessions/{id}/replay expose audio_audit field. Failure state: audio_audit.status shows partial/missing; playback route returns 404 with diagnostic for non-uploaded segments.
