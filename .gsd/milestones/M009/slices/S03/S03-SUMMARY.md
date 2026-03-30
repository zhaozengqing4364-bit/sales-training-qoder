---
id: S03
parent: M009
milestone: M009
provides:
  - Failure registration endpoint (POST /audio-segments/failure) for browser upload errors
  - Enriched audio audit payload with degraded_reasons, failed_segments, per-segment error_message
  - Differentiated learner-facing degraded wording in report/replay AudioAuditCard
  - Structured segment playback error codes preserved through web API client
  - Audio anomaly kinds (audio_upload_degraded, audio_missing) in support/runtime diagnostics
requires:
  - slice: S01
    provides: OSS signed PUT URL flow, session_audio_segments table, audio audit runtime metrics persistence
  - slice: S02
    provides: build_session_audio_audit() read model, AudioAuditCard component, report/replay audio_audit payload surface
affects:
  []
key_files:
  - backend/src/common/api/practice.py
  - backend/src/common/db/schemas.py
  - backend/src/support/services/runtime_status_service.py
  - backend/tests/unit/test_audio_segment_api.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/contract/test_audio_audit_contract.py
  - backend/tests/unit/test_support_runtime_service.py
  - web/src/components/audio/AudioAuditCard.tsx
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/lib/api/client.auth.test.ts
key_decisions:
  - Failure registration uses a closed error-token enum (signing_failed, oss_put_failed, register_failed, network_error, unknown) instead of free-text to keep diagnostics compact and searchable.
  - Failure endpoint only overwrites non-uploaded segments (failed/pending), preserving already-successful uploads.
  - AudioAuditCard maps canonical degraded_reasons tokens locally to stable Chinese learner copy instead of deriving wording from upload counts.
  - Audio anomaly state in RuntimeStatusService derived from voice_policy_snapshot.runtime_metrics.audio_audit bounded summary rather than querying SessionAudioSegment rows directly, keeping the runtime read model lightweight.
  - Severity escalation from warning to blocking when failed_segment_count exceeds 50% of total segments.
patterns_established:
  - Closed-enum error tokens for browser-to-backend failure registration — repeatable for other upload/asset flows.
  - Bounded failure metrics merged into voice_policy_snapshot.runtime_metrics keeps per-asset diagnostics lightweight and avoids unbounded row scans on the runtime status read path.
  - AudioAuditCard maps backend tokens to stable learner copy, keeping wording centralized and testable.
observability_surfaces:
  - POST /audio-segments/failure — browser failure registration endpoint
  - build_session_audio_audit() degraded_reasons/failed_segments/error_message in report/replay payload
  - RuntimeStatusService audio_upload_degraded / audio_missing anomaly kinds in /support/runtime
drill_down_paths:
  - milestones/M009/slices/S03/tasks/T01-SUMMARY.md
  - milestones/M009/slices/S03/tasks/T02-SUMMARY.md
  - milestones/M009/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-29T23:48:32.060Z
blocker_discovered: false
---

# S03: 音频审计降级与诊断

**When audio upload fails or segments are partially missing, learners see differentiated degraded wording in report/replay, and admin/support runtime surfaces audio_upload_degraded and audio_missing anomaly kinds alongside existing diagnostic categories.**

## What Happened

S03 closes the audio-audit chain by adding failure registration, learner-facing degraded wording, and admin diagnostics.

**T01 (backend failure registration & enriched read model):** Extended the audio segment write contract with `POST /audio-segments/failure` — the browser calls this when a PUT to OSS fails, passing a closed-enum error token (signing_failed, oss_put_failed, register_failed, network_error, unknown). The endpoint upserts the segment with `upload_status='failed'`, preserving already-uploaded segments, and merges bounded failure metrics into `voice_policy_snapshot.runtime_metrics.audio_audit`. The shared `build_session_audio_audit()` now computes `degraded_reasons` (upload_failed, segments_pending), `failed_segments` count, and per-segment `error_message` in the canonical payload. 53 tests across 3 test files pass.

**T02 (frontend degraded wording & structured error codes):** Updated `AudioAuditCard` to consume the canonical `degraded_reasons` tokens and render differentiated Chinese learner copy for partial/failed audio sessions. Updated `getSegmentAudioBlobUrl` to preserve backend error/error_code values from non-OK JSON responses so the UI can distinguish upload/signing/not-found failures. Added focused report/replay page tests for degraded wording and a direct API-client regression test for structured error propagation. 30 tests pass.

**T03 (admin support runtime audio anomalies):** Added `audio_upload_degraded` and `audio_missing` anomaly kinds to `RuntimeStatusService._build_fault_items()`. Audio anomaly state is derived from `voice_policy_snapshot.runtime_metrics.audio_audit` bounded summary (no direct `SessionAudioSegment` row queries). Severity escalates from warning to blocking when `failed_segment_count > 50%` of total segments. `learner_status` is computed from counts (available/partial/missing) matching the canonical derivation in `build_session_audio_audit()`. 8/8 tests pass including 5 new audio-specific tests.

All verification green: 53 backend audio-contract tests, 8 runtime-status tests, 30 frontend tests.

## Verification

Slice-level verification ran all three task verification suites:

1. **T01 backend:** `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_audio_segment_api.py tests/contract/test_practice_evidence_contract.py tests/contract/test_audio_audit_contract.py -v` — 53 passed, 0 failed.
2. **T03 backend:** `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py -v -k audio` — 5 passed (3 existing + 2 new), 3 deselected.
3. **T02 frontend:** `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` — 30 passed (19 report + 11 replay), 0 failed.

All degradation paths covered: failure registration, degraded read model, learner wording, structured playback errors, admin anomaly classification.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 added a small direct API-client regression test in `web/src/lib/api/client.auth.test.ts` beyond the planned report/replay page tests. The client seam was the most stable place to prove the structured error code propagation fix.

## Known Limitations

None.

## Follow-ups

None within M009 — S03 was the final slice. The audio-audit chain (S01 upload → S02 query/playback → S03 degradation/diagnostics) is now complete.

## Files Created/Modified

- `backend/src/common/db/schemas.py` — Added error_message to AudioAuditSegmentSchema, failed_segments and degraded_reasons to AudioAuditSummarySchema
- `backend/src/common/api/practice.py` — Added POST /audio-segments/failure endpoint, enriched build_session_audio_audit() with degraded reasons/failed counts/per-segment errors, added _update_audio_audit_failure_metrics helper
- `backend/src/support/services/runtime_status_service.py` — Added audio_upload_degraded and audio_missing anomaly kinds with severity escalation, _extract_audio_diagnostics helper
- `web/src/components/audio/AudioAuditCard.tsx` — Consumes canonical degraded_reasons tokens and renders differentiated Chinese learner copy for partial/failed audio states
- `web/src/lib/api/client.ts` — getSegmentAudioBlobUrl preserves structured backend error/error_code values from non-OK JSON responses
- `web/src/lib/api/types.ts` — Extended audio-audit types with degraded_reasons, failed_segments, per-segment error_message
- `backend/tests/unit/test_audio_segment_api.py` — 21 unit tests covering failure registration, degraded reasons, voice-policy-snapshot metrics
- `backend/tests/contract/test_practice_evidence_contract.py` — 26 contract tests updated for enriched schema fields
- `backend/tests/contract/test_audio_audit_contract.py` — 6 contract tests for audio audit payload shape
- `backend/tests/unit/test_support_runtime_service.py` — 5 new audio anomaly classification tests (missing, degraded warning, degraded blocking, empty, malformed)
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Added degraded audio wording assertions
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Added degraded audio wording assertions
- `web/src/lib/api/client.auth.test.ts` — Added structured segment playback error propagation regression test
