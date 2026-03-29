---
id: T01
parent: S03
milestone: M009
provides: []
requires: []
affects: []
key_files: ["backend/src/common/db/schemas.py", "backend/src/common/api/practice.py", "backend/tests/unit/test_audio_segment_api.py", "backend/tests/contract/test_practice_evidence_contract.py"]
key_decisions: ["Failure endpoint only overwrites non-uploaded segments (failed/pending), preserving successful uploads", "Error tokens are a closed enum (signing_failed, oss_put_failed, register_failed, network_error, unknown)", "Shared async helper _update_audio_audit_failure_metrics for failure metric persistence"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "53 tests pass across 3 test files: 21 unit tests (test_audio_segment_api.py), 26 contract tests (test_practice_evidence_contract.py), 6 contract tests (test_audio_audit_contract.py). No regressions. All new failure-registration, degraded-reason, and voice-policy-snapshot assertions verified."
completed_at: 2026-03-29T23:19:51.743Z
blocker_discovered: false
---

# T01: Add failure registration endpoint and enrich audio audit read model with degraded_reasons, failed_segments, and per-segment error_message

> Add failure registration endpoint and enrich audio audit read model with degraded_reasons, failed_segments, and per-segment error_message

## What Happened
---
id: T01
parent: S03
milestone: M009
key_files:
  - backend/src/common/db/schemas.py
  - backend/src/common/api/practice.py
  - backend/tests/unit/test_audio_segment_api.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - Failure endpoint only overwrites non-uploaded segments (failed/pending), preserving successful uploads
  - Error tokens are a closed enum (signing_failed, oss_put_failed, register_failed, network_error, unknown)
  - Shared async helper _update_audio_audit_failure_metrics for failure metric persistence
duration: ""
verification_result: passed
completed_at: 2026-03-29T23:19:51.745Z
blocker_discovered: false
---

# T01: Add failure registration endpoint and enrich audio audit read model with degraded_reasons, failed_segments, and per-segment error_message

**Add failure registration endpoint and enrich audio audit read model with degraded_reasons, failed_segments, and per-segment error_message**

## What Happened

Extended the audio segment contract in three layers: (1) Schema extensions — added error_message to AudioAuditSegmentSchema, failed_segments and degraded_reasons to AudioAuditSummarySchema. (2) New POST /audio-segments/failure endpoint that accepts segment_sequence + error_token (closed enum: signing_failed, oss_put_failed, register_failed, network_error, unknown), upserts SessionAudioSegment with upload_status='failed', preserves already-uploaded segments, and updates voice_policy_snapshot.runtime_metrics.audio_audit with bounded failure summary. (3) Enriched build_session_audio_audit() to compute degraded_reasons from segment states (upload_failed if any failed, segments_pending if any pending), failed_segments count, and per-segment error_message. Also extended register_audio_segment() to persist failed_segment_count alongside existing upload metrics. Fixed a bug where the failure metrics helper was called without await. Updated one existing contract test to include new schema fields in exact-match assertion.

## Verification

53 tests pass across 3 test files: 21 unit tests (test_audio_segment_api.py), 26 contract tests (test_practice_evidence_contract.py), 6 contract tests (test_audio_audit_contract.py). No regressions. All new failure-registration, degraded-reason, and voice-policy-snapshot assertions verified.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_audio_segment_api.py tests/contract/test_practice_evidence_contract.py tests/contract/test_audio_audit_contract.py -v` | 0 | ✅ pass | 9800ms |


## Deviations

None

## Known Issues

None

## Files Created/Modified

- `backend/src/common/db/schemas.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_audio_segment_api.py`
- `backend/tests/contract/test_practice_evidence_contract.py`


## Deviations
None

## Known Issues
None
