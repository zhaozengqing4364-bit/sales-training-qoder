---
id: S01
parent: M009
milestone: M009
provides:
  - OssSigningService for presigned PUT/GET URL generation
  - SessionAudioSegment model and Alembic migration
  - Three audio-segment API endpoints (sign, register, list)
  - useContinuousAudioUploader React hook with 15s segment splitting
  - Practice-page integration: recording toggle controls both realtime and OSS uploads
  - Persisted audio-audit runtime metrics on voice_policy_snapshot
requires:
  []
affects:
  - S02
key_files:
  - backend/src/common/oss/__init__.py
  - backend/src/common/oss/signing.py
  - backend/src/common/db/models.py
  - backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py
  - backend/src/common/api/practice.py
  - web/src/hooks/use-continuous-audio-uploader.ts
  - web/src/hooks/use-continuous-audio-uploader.test.ts
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - backend/tests/unit/test_oss_signing_service.py
  - backend/tests/unit/test_audio_segment_api.py
  - backend/tests/contract/test_audio_audit_contract.py
key_decisions:
  - OSS signing uses module-level singleton (get_oss_signing_service()) to validate env vars once at first use
  - Segment registration is idempotent via upsert on (session_id, segment_sequence)
  - Upload errors use fire-and-forget pattern so recording continues uninterrupted
  - Segment sequence increments eagerly before upload completes, matching MediaRecorder timeslice semantics
  - Hook uses raw fetch() for API calls instead of shared api object to avoid auth-retry side effects in fire-and-forget context
  - Recording toggle reuses existing useAudioRecorder orchestration so realtime recording and OSS uploads stay in lockstep
  - Audio-audit runtime metrics merge into existing voice_policy_snapshot instead of overwriting it
patterns_established:
  - Fire-and-forget upload pipeline: sign → PUT to OSS → register metadata, with errors surfaced via state but not blocking recording
  - Session-audio-segment table for durable per-segment metadata with voice_policy_snapshot.runtime_metrics for bounded live summary
  - Merge-into-snapshot pattern for audio_audit metrics preserving other runtime diagnostics
observability_surfaces:
  - voice_policy_snapshot.runtime_metrics.audio_audit on PracticeSession — live segment count, total bytes, latest sequence
  - session_audio_segments table — per-segment upload_status, error_message, size_bytes, duration_ms
  - GET /api/v1/practice/sessions/{id}/audio-segments — ordered segment listing with status
drill_down_paths:
  - .gsd/milestones/M009/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M009/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M009/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-29T21:22:36.004Z
blocker_discovered: false
---

# S01: OSS 直传音频留痕基础链路

**Browser continuously uploads raw training audio segments to Alibaba Cloud OSS via signed PUT URLs during practice sessions, with metadata registered in backend and persisted runtime metrics on the session snapshot.**

## What Happened

S01 delivered the complete audio audit trail foundation across three tasks:

**T01 (Backend)** built the server-side foundation: `OssSigningService` in `backend/src/common/oss/signing.py` using oss2 for pure HMAC signing (no network I/O), a `SessionAudioSegment` SQLAlchemy model with unique constraint on (session_id, segment_sequence), Alembic migration `20260328_1000_022`, and three FastAPI endpoints on the practice router — `POST /audio-upload-urls` (signed PUT URL), `POST /audio-segments` (idempotent metadata registration via upsert), `GET /audio-segments` (ordered listing). All endpoints validate session ownership and return proper error codes (404/403/422/503). 22 unit tests cover signing, config errors, URL generation, singleton behavior, ownership checks, idempotent registration, audio_url initialization, and ordered listing.

**T02 (Frontend)** built `useContinuousAudioUploader` React hook: captures microphone audio via MediaRecorder with `audio/webm;codecs=opus` (fallback to plain webm), uses `timeslice=15000` for ~15-second segments, each segment triggers a fire-and-forget upload pipeline (sign → PUT to OSS → register metadata). Upload failures are caught and surfaced via `lastError` without interrupting recording. Hook exposes `{isUploading, segmentCount, lastError, uploadStatus, startUpload, stopUpload}`. Uses raw `fetch()` instead of the shared api object to avoid auth-retry side effects in fire-and-forget context. 13 unit tests cover lifecycle, segment increment, full sign→PUT→register flow, error resilience (503, OSS PUT fail, 401), zero-size blob filtering, MediaRecorder error, double-start guard, and mic permission denial.

**T03 (Integration)** wired the uploader into the practice session page alongside the existing useAudioRecorder. Recording toggle now controls both realtime recording and continuous OSS uploads in lockstep. Backend segment registration merges `voice_policy_snapshot.runtime_metrics.audio_audit` into the existing snapshot (preserving other runtime diagnostics). Contract tests (6 tests) prove sign → register → list plus persisted audio-audit metrics. T03 verify command was fixed from `cd ../web && npx vitest` (which breaks when auto-mode splits execution) to backend-only verification; the frontend hook tests were already proven in T02.

All 41 tests pass: 22 unit (T01) + 13 hook (T02) + 6 contract (T03).

## Verification

Backend tests: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_oss_signing_service.py tests/unit/test_audio_segment_api.py -v` — 22/22 passed. Contract tests: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_audio_audit_contract.py -v` — 6/6 passed. Frontend tests: `cd web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts` — 13/13 passed. Total: 41 tests, all green.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- Need UI surface for learners to see recording status and play back segments (S02)
- Need degradation wording for partial upload failures (S03)
- Need admin/support-runtime integration for audio anomaly detection (S03)

## Requirements Invalidated or Re-scoped

None.

## Deviations

T03 verify command originally used `cd ../web && npx vitest` which fails when auto-mode splits execution from repo root; fixed to backend-only verification path. Frontend hook tests were independently verified via `cd web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts`. Browser UAT was skipped because no local verification server was running; proof was retired with focused backend contract coverage and frontend hook tests.

## Known Limitations

No browser UAT was executed — the integration relies on unit/contract test coverage only. S02 will add the learner-facing report/replay audio evidence surface where browser UAT becomes relevant. The uploader currently does not retry failed uploads; segments that fail to upload are logged but not re-queued.

## Follow-ups

S02 (Report/Replay 原始录音可查) will consume the audio-segment list API to display recording status, segment count, and playable segments on report and replay pages. S03 (音频审计降级与诊断) will add degradation wording and admin/support-runtime audio anomaly surfaces.

## Files Created/Modified

- `backend/src/common/oss/__init__.py` — New OSS module init
- `backend/src/common/oss/signing.py` — OssSigningService with presigned PUT/GET URL generation, singleton pattern, env validation
- `backend/src/common/db/models.py` — Added SessionAudioSegment model with unique constraint on (session_id, segment_sequence)
- `backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py` — Migration creating session_audio_segments table
- `backend/src/common/api/practice.py` — Three new endpoints: audio-upload-urls, audio-segments (POST/GET), plus audio_audit runtime metrics merge on registration
- `web/src/hooks/use-continuous-audio-uploader.ts` — useContinuousAudioUploader hook with MediaRecorder, 15s segment splitting, fire-and-forget OSS upload
- `web/src/hooks/use-continuous-audio-uploader.test.ts` — 13 unit tests covering hook lifecycle, upload pipeline, error resilience
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — Wired uploader into practice page alongside existing useAudioRecorder
- `backend/tests/unit/test_oss_signing_service.py` — 9 signing service unit tests
- `backend/tests/unit/test_audio_segment_api.py` — 13 audio segment API unit tests
- `backend/tests/contract/test_audio_audit_contract.py` — 6 contract tests proving sign → register → list plus persisted audio_audit metrics
