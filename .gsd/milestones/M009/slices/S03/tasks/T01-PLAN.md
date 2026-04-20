---
estimated_steps: 6
estimated_files: 4
skills_used:
  - fastapi-python
---

# T01: Backend: persist audio failure facts and enrich degraded read model

**Slice:** S03 — 音频审计降级与诊断
**Milestone:** M009

## Description

Extend the audio-segment write contract so browser failures can be durably registered (upload_status=failed with compact error token). Extend build_session_audio_audit() to expose degraded reasons, failed counts, and per-segment error messages in the shared payload. Extend voice_policy_snapshot.runtime_metrics.audio_audit with bounded failure summary fields.

## Steps

1. Add a new `POST /practice/sessions/{id}/audio-segments/failure` endpoint that accepts `segment_sequence` (int) + `error_token` (str enum: signing_failed, oss_put_failed, register_failed, network_error, unknown). Creates/upserts a `SessionAudioSegment` row with `upload_status='failed'` and compact `error_message` from the error_token. Validates session ownership using the same pattern as `register_audio_segment`. Also updates `voice_policy_snapshot.runtime_metrics.audio_audit` with bounded failure summary (failed_segment_count, last_failure_reason).

2. Extend `AudioAuditSegmentSchema` with optional `error_message: str | None = None`. Extend `AudioAuditSummarySchema` with `failed_segments: int = 0` and `degraded_reasons: list[str] = []`.

3. Extend `build_session_audio_audit()` to derive `degraded_reasons` list from segment states: if any failed segments exist, include `'upload_failed'`; if any pending segments exist, include `'segments_pending'`. Compute `failed_segments` count from segment rows. Expose per-segment `error_message` in `AudioAuditSegmentSchema` when available.

4. Extend `register_audio_segment()` to also update `voice_policy_snapshot.runtime_metrics.audio_audit` with `failed_segment_count` (queried from segments where upload_status='failed') and `last_failure_reason` (from most recent failed segment's error_message).

5. Add unit tests in `test_audio_segment_api.py` proving: failure registration creates row with upload_status=failed; failure + success segments yield partial with degraded_reasons containing 'upload_failed'; all-failed yields missing with degraded_reasons=['upload_failed'].

6. Add contract tests in `test_practice_evidence_contract.py` proving report/replay audio_audit includes degraded_reasons and failed_counts for mixed failed/pending/uploaded segment scenarios.

## Must-Haves

- [ ] Failure registration endpoint validates ownership and persists failed row with compact error token
- [ ] build_session_audio_audit exposes degraded_reasons, failed_segments count, and per-segment error_message
- [ ] AudioAuditSummarySchema and AudioAuditSegmentSchema extended with degraded fields
- [ ] voice_policy_snapshot.runtime_metrics.audio_audit tracks bounded failure summary
- [ ] Existing tests pass without regression

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_audio_segment_api.py tests/contract/test_practice_evidence_contract.py tests/contract/test_audio_audit_contract.py -v`
- All tests pass, including new failure-registration and degraded-reason assertions

## Observability Impact

- Signals added: voice_policy_snapshot.runtime_metrics.audio_audit now tracks failed_segment_count and last_failure_reason
- How a future agent inspects: query SessionAudioSegment where upload_status='failed' or read runtime_metrics.audio_audit from session snapshot
- Failure state exposed: failed segment rows with error_message tokens, bounded summary in voice_policy_snapshot

## Inputs

- `backend/src/common/api/practice.py` — existing audio segment registration and build_session_audio_audit
- `backend/src/common/db/schemas.py` — AudioAuditSegmentSchema and AudioAuditSummarySchema to extend
- `backend/src/common/db/models.py` — SessionAudioSegment model (already has upload_status and error_message columns)
- `backend/tests/unit/test_audio_segment_api.py` — existing unit tests to extend
- `backend/tests/contract/test_practice_evidence_contract.py` — existing contract tests to extend
- `backend/tests/contract/test_audio_audit_contract.py` — existing contract tests to extend

## Expected Output

- `backend/src/common/api/practice.py` — failure registration endpoint + enriched build_session_audio_audit
- `backend/src/common/db/schemas.py` — extended AudioAuditSegmentSchema/SummarySchema with degraded fields
- `backend/tests/unit/test_audio_segment_api.py` — new failure registration unit tests
- `backend/tests/contract/test_practice_evidence_contract.py` — new degraded-reason contract tests
