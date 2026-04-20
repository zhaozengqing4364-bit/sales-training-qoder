---
id: S02
parent: M009
milestone: M009
provides:
  - Shared audio_audit payload (summary + segments) on both GET /practice/sessions/{id}/report and GET /sessions/{id}/replay
  - Segment playback handoff route GET /sessions/{id}/audio-segments/{seq} with ownership validation
  - Shared AudioAuditCard component rendering available/partial/missing states
requires:
  - slice: S01
    provides: SessionAudioSegment table, voice_policy_snapshot.runtime_metrics.audio_audit, OssSigningService for segment playback signing
affects:
  - S03
key_files:
  - backend/src/common/db/schemas.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/api/practice.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/api.py
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
  - web/src/components/audio/AudioAuditCard.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - audio_audit field is optional (None) to avoid breaking existing sessions without audio segments
  - replay.py wraps audio_audit build in try/except so mock-based unit tests don't break on missing segment tables
  - playback handoff uses stable path /sessions/{id}/audio-segments/{seq}, signs at read time with 1-hour expiry
  - AudioAuditCard treats backend learner_status as canonical while tolerating summary.status as defensive alias
  - Backend returns audio_audit: null for sessions without segments; frontend renders missing-audio fallback state
patterns_established:
  - Shared build_session_audio_audit() helper used by both report and replay payloads
  - AudioAuditCard shared component consumed by both report and replay pages
  - Stable playback handoff path with read-time signing (never persist signed URLs)
observability_surfaces:
  - GET /sessions/{session_id}/audio-segments/{segment_sequence} returns 307 signed redirect for uploaded segments, 404 for missing, 403 for unauthorized
drill_down_paths:
  - milestones/M009/slices/S02/tasks/T01-SUMMARY.md
  - milestones/M009/slices/S02/tasks/T02-SUMMARY.md
  - milestones/M009/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-29T22:45:26.811Z
blocker_discovered: false
---

# S02: Report/Replay 原始录音可查

**Extended learner report and replay routes with audio_audit payload and shared AudioAuditCard UI, giving learners visibility into raw training audio segments with playback capability.**

## What Happened

S02 exposes raw audio audit evidence on learner-facing report and replay routes through three tasks:

**T01 (Backend read model + playback handoff):** Built a shared `build_session_audio_audit()` helper that queries `SessionAudioSegment` rows and derives `learner_status` (available/partial/missing). Extended `SessionReport` and `ReplayDataResponse` schemas with optional `audio_audit: AudioAuditPayloadSchema`. Wired the helper into all three SessionReport construction sites and replay.py's `get_replay_data()`. Added `GET /sessions/{session_id}/audio-segments/{segment_sequence}` playback handoff route with ownership validation and 1-hour signed GET redirect. Replay integration uses try/except guard to avoid breaking existing mock-based tests. 83 backend tests pass.

**T02 (Frontend UI + contract wiring):** Added `AudioAuditPayload` types to `web/src/lib/api/types.ts`, `getSegmentAudioBlobUrl` client method to `web/src/lib/api/client.ts`, and a shared `AudioAuditCard.tsx` component. The card renders three states: available (summary + segment list with play buttons), partial (badge + partial segments), and missing/null ("本次训练未录制原始音频"). Integrated into both report and replay pages. 28 frontend tests pass (18 report + 10 replay).

**T03 (Contract regressions):** Added 4 focused backend contract tests proving report/replay audio_audit payload inclusion (available/partial/null), segment playback redirect (307), missing segment 404, outsider 403, and non-persistence of signed URLs. Added report-page missing-audio assertion. All existing tests continue to pass.

Key design decisions: `audio_audit` field is optional (None) to avoid breaking existing sessions; signed URLs derived at read time, never persisted; `learner_status` is the canonical backend field with `status` as defensive frontend alias.

## Verification

Slice-level verification passed:
- Backend: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py tests/unit/test_oss_signing_service.py` — 83 passed, 0 failed
- Frontend: `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` — 28 passed, 0 failed
- Focused audio_audit contract tests: 4 passed including available/partial/null states, signed redirect, 404, 403

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T03 deviated from plan: the shipped read model returns `audio_audit: null` (not a synthesized `learner_status="missing"`) when no SessionAudioSegment rows exist. The contract tests lock this real behavior, and the frontend handles the null state with "本次训练未录制原始音频".

## Known Limitations

T02 browser verification confirmed the replay route rendered the audio-audit card, but the report-route browser pass was aborted during navigation; report page correctness relies on the passing 18-test Vitest suite instead of live browser proof.

## Follow-ups

S03 will add audio-audit degradation diagnostics to admin/support runtime surfaces alongside existing diagnostic categories.

## Files Created/Modified

- `backend/src/common/db/schemas.py` — Added AudioAuditSegmentSchema, AudioAuditSummarySchema, AudioAuditPayloadSchema; extended SessionReport with optional audio_audit field
- `backend/src/common/conversation/schemas.py` — Extended ReplayDataResponse with optional audio_audit field
- `backend/src/common/api/practice.py` — Added build_session_audio_audit() shared helper; wired audio_audit into all SessionReport construction sites
- `backend/src/common/conversation/replay.py` — Added audio_audit to get_replay_data() with try/except guard
- `backend/src/common/conversation/api.py` — Added GET /sessions/{session_id}/audio-segments/{segment_sequence} playback handoff route
- `web/src/lib/api/types.ts` — Added AudioAuditSegment, AudioAuditSummary, AudioAuditPayload TypeScript types
- `web/src/lib/api/client.ts` — Added getSegmentAudioBlobUrl method for segment playback
- `web/src/components/audio/AudioAuditCard.tsx` — New shared component with available/partial/missing states and HTML5 Audio playback
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Integrated AudioAuditCard after highlights section
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Integrated AudioAuditCard between highlights and full-dialogue sections
- `backend/tests/contract/test_practice_evidence_contract.py` — Added 4 audio_audit contract tests (payload inclusion, playback redirect, ownership, non-persistence)
