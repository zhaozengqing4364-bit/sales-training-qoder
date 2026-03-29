# S03: 音频审计降级与诊断

**Goal:** When audio upload fails, signing expires, or segments are partially missing, the learner sees clear degraded wording in report/replay explaining what happened. Admin/support runtime surfaces audio anomalies alongside existing diagnostic categories.
**Demo:** After this: After this, when audio upload fails, signing expires, or segments are partially missing, the learner sees clear degraded wording in report/replay explaining what happened. Admin/support runtime surfaces audio anomalies alongside existing diagnostic categories.

## Tasks
- [x] **T01: Add failure registration endpoint and enrich audio audit read model with degraded_reasons, failed_segments, and per-segment error_message** — Extend the audio-segment write contract so browser failures can be durably registered (upload_status=failed with compact error token). Extend build_session_audio_audit() to expose degraded reasons, failed counts, and per-segment error messages in the shared payload. Extend voice_policy_snapshot.runtime_metrics.audio_audit with bounded failure summary fields.
  - Estimate: 45m
  - Files: backend/src/common/api/practice.py, backend/src/common/db/schemas.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_audio_segment_api.py tests/contract/test_practice_evidence_contract.py tests/contract/test_audio_audit_contract.py -v
- [ ] **T02: Frontend: consume degraded truth in AudioAuditCard and normalize playback errors** — Update AudioAuditCard to consume canonical degraded fields (degraded_reasons, failed_segments, per-segment error_message) from the enriched backend payload. Render differentiated learner-facing wording for partial/failed states. Fix getSegmentAudioBlobUrl to preserve structured error codes instead of collapsing to generic HTTP status.
  - Estimate: 30m
  - Files: web/src/components/audio/AudioAuditCard.tsx, web/src/lib/api/client.ts, web/src/lib/api/types.ts
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
- [ ] **T03: Support runtime: classify audio anomalies in RuntimeStatusService** — Add audio anomaly kinds (audio_upload_degraded, audio_missing) to _build_fault_items(). Derive audio anomaly state from voice_policy_snapshot.runtime_metrics.audio_audit bounded summary on RuntimeSessionRecord. Reuse existing typed anomaly pattern so /support/runtime renders them generically.
  - Estimate: 30m
  - Files: backend/src/support/services/runtime_status_service.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py -v -k audio
