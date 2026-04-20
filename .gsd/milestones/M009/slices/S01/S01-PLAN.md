# S01: OSS 直传音频留痕基础链路

**Goal:** 浏览器在训练过程中持续录制用户原始语音并直传阿里云 OSS，服务端只负责签名和元数据登记；训练中断时已上传的分段保持持久可查。
**Demo:** After this: After this, a learner can start a training session and during the session the browser continuously uploads raw audio segments to Alibaba Cloud OSS via signed PUT URLs, with metadata registered in backend. Training interruption leaves prior segments durable and queryable.

## Tasks
- [x] **T01: Add OSS signing service, SessionAudioSegment model, Alembic migration, and three audio-segment API endpoints** — Build the server-side foundation: an OSS signing service using oss2, a session_audio_segments table with Alembic migration, and three new FastAPI endpoints (generate signed PUT URL, register segment metadata, list segments for a session). Tests cover signing, metadata registration, and query.
  - Estimate: 2h
  - Files: backend/src/common/oss/signing.py, backend/src/common/oss/__init__.py, backend/src/common/db/models.py, backend/alembic/versions/20260328_1000_022_add_session_audio_segments.py, backend/src/common/api/practice.py, backend/tests/unit/test_oss_signing_service.py, backend/tests/unit/test_audio_segment_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_oss_signing_service.py tests/unit/test_audio_segment_api.py -v
- [x] **T02: Add useContinuousAudioUploader hook with 15s segment splitting, OSS presigned-URL upload, and backend metadata registration** — Create a React hook that uses MediaRecorder to capture audio in webm/opus format, splits it into ~15-second segments, requests signed PUT URLs from backend, uploads each segment directly to OSS, and notifies backend to register metadata. Handles pause/resume, errors, and cleanup.
  - Estimate: 2h
  - Files: web/src/hooks/use-continuous-audio-uploader.ts, web/src/hooks/use-continuous-audio-uploader.test.ts
  - Verify: cd web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts
- [x] **T03: Practice sessions now mirror live recording into OSS audio-audit uploads and persist segment runtime metrics with backend contract coverage.** — Wire useContinuousAudioUploader into the practice session page alongside the existing useAudioRecorder. When recording starts, also start the continuous uploader. When recording stops, finalize the last segment. Add backend+frontend contract tests proving the full cycle: backend signs URL -> mock upload -> metadata registered -> segments queryable.
  - Estimate: 1.5h
  - Files: web/src/app/(user)/practice/[sessionId]/page.tsx, backend/tests/contract/test_audio_audit_contract.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_audio_audit_contract.py -v && cd ../web && npx vitest run src/hooks/use-continuous-audio-uploader.test.ts
