---
estimated_steps: 5
estimated_files: 7
skills_used: []
---

# T01: Create backend OSS signing service, segment model, and API endpoints

**Slice:** S01 — OSS 直传音频留痕基础链路
**Milestone:** M009

## Description

Build the server-side foundation for audio audit trail. This task creates:
1. An OSS signing service (`OssSigningService`) using the already-installed `oss2` Python SDK
2. A `session_audio_segments` SQLAlchemy model + Alembic migration
3. Three new FastAPI endpoints on the existing practice router
4. Unit tests covering signing, metadata registration, and segment query

The OSS signing service reads `ALI_OSS_*` env vars and generates presigned PUT/GET URLs. It does NOT handle audio bytes — only URL generation and object key construction.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| oss2 Auth/STS | Raise with clear "OSS credentials not configured" | N/A (no network call) | N/A |
| DB write (segment registration) | Rollback + 500 | N/A | 422 with field details |
| Missing session | 404 | N/A | N/A |

## Load Profile

- **Shared resources**: DB connection pool (one INSERT per segment)
- **Per-operation cost**: 1 DB write per segment, 1 oss2 call per signed URL request
- **10x breakpoint**: OSS signing is pure HMAC computation (no network), effectively unlimited

## Negative Tests

- **Malformed inputs**: session_id not UUID, missing required fields, negative sequence_number
- **Error paths**: ALI_OSS credentials missing → clear error message; non-existent session → 404
- **Boundary conditions**: segment sequence_number = 0, max file size edge

## Steps

1. Create `backend/src/common/oss/__init__.py` and `backend/src/common/oss/signing.py`:
   - `OssSigningService` class that reads `ALI_OSS_ACCESS_KEY_ID`, `ALI_OSS_ACCESS_KEY_SECRET`, `ALI_OSS_BUCKET`, `ALI_OSS_ENDPOINT` from env
   - `generate_put_url(object_key, content_type, expires=900) -> dict` with keys: `url`, `object_key`, `expires_at`
   - `generate_get_url(object_key, expires=3600) -> str`
   - `build_object_key(session_id, segment_sequence) -> str` producing `audio/{session_id}/seg_{sequence:04d}.webm`
   - Raise `OssConfigError` with actionable message if any required env var is missing
   - Use `oss2.Auth` + `oss2.Bucket` pattern; signing is pure HMAC, no network I/O

2. Add `SessionAudioSegment` model to `backend/src/common/db/models.py`:
   - Fields: `id` (UUID PK), `session_id` (FK → practice_sessions), `segment_sequence` (int, per-session sequential), `object_key` (str, OSS path), `content_type` (str), `size_bytes` (int, nullable), `duration_ms` (int, nullable), `upload_status` (str: pending/uploaded/failed), `error_message` (str, nullable), `created_at` (datetime)
   - Unique constraint on (session_id, segment_sequence)
   - Index on session_id

3. Create Alembic migration `backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py`:
   - Revises `20260326_1000_021`
   - Creates `session_audio_segments` table

4. Add three endpoints to `backend/src/common/api/practice.py`:
   - `POST /practice/sessions/{session_id}/audio-upload-urls` — body: `{segment_sequence, content_type}` → returns `{url, object_key, expires_at}`. Validates session exists and user owns it.
   - `POST /practice/sessions/{session_id}/audio-segments` — body: `{segment_sequence, object_key, size_bytes?, duration_ms?}` → creates/updates `SessionAudioSegment` row with `upload_status="uploaded"`. Updates `PracticeSession.audio_url` to point to first segment's directory.
   - `GET /practice/sessions/{session_id}/audio-segments` → returns list of segments with status info

5. Create `backend/tests/unit/test_oss_signing_service.py` and `backend/tests/unit/test_audio_segment_api.py`:
   - OSS signing tests: mock oss2.Auth/Bucket, verify URL generation, object key format, missing config error
   - API tests: use `TestClient` with test DB, prove segment registration, query, error cases

## Must-Haves

- [ ] `OssSigningService` generates valid presigned PUT/GET URLs using `oss2` with env-configured credentials
- [ ] `session_audio_segments` table created with correct columns, constraints, and FK
- [ ] Alembic migration revises `20260326_1000_021`
- [ ] Three endpoints work: generate upload URL, register segment, list segments
- [ ] Missing OSS credentials produce clear `OssConfigError`, not a cryptic import error
- [ ] Unit tests pass with mocked oss2 (no real OSS network calls)

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_oss_signing_service.py tests/unit/test_audio_segment_api.py -v`

## Observability Impact

- Signals added: structured log on each signed URL request (`audio_upload_url_generated`) and segment registration (`audio_segment_registered`)
- How a future agent inspects: `GET /api/v1/practice/sessions/{id}/audio-segments` shows per-segment status
- Failure state exposed: `upload_status` field, `error_message` column; `OssConfigError` on startup if credentials missing

## Inputs

- `backend/src/common/db/models.py` — existing PracticeSession model to add relationship
- `backend/src/common/db/session.py` — existing DB session factory
- `backend/src/common/api/practice.py` — existing router to add endpoints

## Expected Output

- `backend/src/common/oss/__init__.py` — module init
- `backend/src/common/oss/signing.py` — OssSigningService implementation
- `backend/src/common/db/models.py` — SessionAudioSegment model added
- `backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py` — migration
- `backend/src/common/api/practice.py` — three new endpoints
- `backend/tests/unit/test_oss_signing_service.py` — signing service tests
- `backend/tests/unit/test_audio_segment_api.py` — API endpoint tests
