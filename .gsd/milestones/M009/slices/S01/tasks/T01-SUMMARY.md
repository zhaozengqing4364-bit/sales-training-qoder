---
id: T01
parent: S01
milestone: M009
provides: []
requires: []
affects: []
key_files: ["backend/src/common/oss/__init__.py", "backend/src/common/oss/signing.py", "backend/src/common/db/models.py", "backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py", "backend/src/common/api/practice.py", "backend/tests/unit/test_oss_signing_service.py", "backend/tests/unit/test_audio_segment_api.py"]
key_decisions: ["OSS signing uses module-level singleton (get_oss_signing_service()) to validate env vars once at first use", "Endpoints use dict body instead of Pydantic request models to match existing practice.py pattern", "Segment registration is idempotent via upsert on (session_id, segment_sequence)"]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran 22 unit tests covering OSS signing service (9 tests) and audio segment API endpoints (13 tests). All pass.

Tests cover: config error on missing env vars, presigned PUT/GET URL generation, object key format, singleton, session ownership checks, 404/403/422/503 error codes, idempotent segment registration, audio_url directory update on first segment, ordered segment listing."
completed_at: 2026-03-29T20:43:43.987Z
blocker_discovered: false
---

# T01: Add OSS signing service, SessionAudioSegment model, Alembic migration, and three audio-segment API endpoints

> Add OSS signing service, SessionAudioSegment model, Alembic migration, and three audio-segment API endpoints

## What Happened
---
id: T01
parent: S01
milestone: M009
key_files:
  - backend/src/common/oss/__init__.py
  - backend/src/common/oss/signing.py
  - backend/src/common/db/models.py
  - backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py
  - backend/src/common/api/practice.py
  - backend/tests/unit/test_oss_signing_service.py
  - backend/tests/unit/test_audio_segment_api.py
key_decisions:
  - OSS signing uses module-level singleton (get_oss_signing_service()) to validate env vars once at first use
  - Endpoints use dict body instead of Pydantic request models to match existing practice.py pattern
  - Segment registration is idempotent via upsert on (session_id, segment_sequence)
duration: ""
verification_result: passed
completed_at: 2026-03-29T20:43:43.988Z
blocker_discovered: false
---

# T01: Add OSS signing service, SessionAudioSegment model, Alembic migration, and three audio-segment API endpoints

**Add OSS signing service, SessionAudioSegment model, Alembic migration, and three audio-segment API endpoints**

## What Happened

Built the complete server-side foundation for audio audit trail via OSS direct upload.

Step 1: Created `OssSigningService` in `backend/src/common/oss/signing.py`. It reads `ALI_OSS_*` env vars at construction time, Uses `oss2.Auth` + `oss2.Bucket` for pure HMAC signing (no network I/O). Provides `generate_put_url()`, `generate_get_url()`, and `build_object_key()`. Missing env vars raise `OssConfigError` with an actionable message listing which vars are absent.

Step 2: Added `SessionAudioSegment` model to `models.py` with fields: id (UUID PK), session_id (FK), segment_sequence, object_key, content_type, size_bytes, duration_ms, upload_status, error_message, created_at. Includes unique constraint on (session_id, segment_sequence) and check constraint on upload_status. Added `audio_segments` relationship to `PracticeSession`.

Step 3: Created Alembic migration `20260328_1000_022` revising `20260326_1000_021`. Creates the `session_audio_segments` table with all columns, constraints, and indexes.

Step 4: Added three endpoints to the practice router:
- `POST /practice/sessions/{id}/audio-upload-urls` — generates presigned PUT URL
- `POST /practice/sessions/{id}/audio-segments` — registers uploaded segment (idempotent upsert)
- `GET /practice/sessions/{id}/audio-segments` — lists all segments ordered by sequence

All endpoints validate session ownership, return proper error codes (404/403/422/503), and emit structured logs.

Step 5: Created comprehensive test suites — 22 tests total, all passing. Signing tests cover config errors, URL generation, object key formatting, singleton behavior. API tests cover success flows, error paths (missing session, negative sequence, missing object_key, OSS not configured), idempotent upsert, audio_url update, and ordered listing.

Also fixed a broken `pycryptodome` native module in the backend venv that was preventing `oss2` from importing.

## Verification

Ran 22 unit tests covering OSS signing service (9 tests) and audio segment API endpoints (13 tests). All pass.

Tests cover: config error on missing env vars, presigned PUT/GET URL generation, object key format, singleton, session ownership checks, 404/403/422/503 error codes, idempotent segment registration, audio_url directory update on first segment, ordered segment listing.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_oss_signing_service.py tests/unit/test_audio_segment_api.py -v` | 0 | ✅ pass | 14500ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/oss/__init__.py`
- `backend/src/common/oss/signing.py`
- `backend/src/common/db/models.py`
- `backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_oss_signing_service.py`
- `backend/tests/unit/test_audio_segment_api.py`


## Deviations
None.

## Known Issues
None.
